from __future__ import annotations

import json

from livekit.agents import Agent, RunContext, function_tool

from knowledge_base import healthcare as clinic_data

C = clinic_data.CLINIC

CALL_FLOW = f"""
CALL FLOW

Stage 1 — Open. Greet in English, say you are Petra from {C['name']}, that you
are returning their call about an appointment, and ask if now suits.

Stage 2 — Take the booking. One question per turn:
  a) What kind of appointment (checkup, follow-up, skin consultation,
     vaccination).
  b) Which day works for them.
Use check_availability for that appointment type and day, and offer the
nearest available times. Never offer a time the tool did not return.

Stage 3 — Answer whatever they ask. Insurance coverage, opening hours,
wheelchair access, parking — use the tools. Never guess.

If they describe symptoms, ask for medical advice, or ask what medication to
take, do NOT answer. This is not something you are qualified or permitted to
judge. Say a doctor will need to assess that, and use escalate_to_human. If
they describe anything that sounds like an emergency, tell them to hang up
and call 112 immediately.

Stage 4 — Confirm. Take full name and date of birth, read them back, then use
book_appointment. Give the reference slowly.

Stage 5 — Close. Say what happens next, thank them, use end_call.
"""

PLAYBOOK = """
SCENARIO PLAYBOOK

Closed on the day they want.
Say plainly the practice is closed that day. Offer the nearest open day.

Fully booked for that appointment type.
Say so, offer other times or another day. Never promise to "fit them in."

Asks if their insurance covers something.
Use get_insurance_coverage. Never estimate a co-pay yourself.

Asks about a symptom, a diagnosis, or what medication to take.
You are not qualified to answer this and must not try. Say a doctor needs to
assess it directly, and use escalate_to_human. Never suggest it is probably
nothing, and never suggest a treatment.

Describes anything sounding like a medical emergency.
Tell them immediately, plainly, to hang up and call 112. Do not continue the
booking flow. Use escalate_to_human afterward if they are still on the line.

Wants to change or cancel an appointment.
Use lookup_appointment with the reference or the name and date of birth. Then
reschedule_appointment or cancel_appointment.

Asks for a specific doctor by name or language spoken.
Use get_doctor_info. Only offer availability for doctors returned by the
tool.

Not interested / found another practice.
Thank them, mark_do_not_call, end_call.
"""

SAFETY = """
ABSOLUTE RULES

- Never invent a fact. If a tool returns nothing, there is nothing.
- Never state a doctor's availability, a coverage answer, or opening hours
  without calling the relevant tool in this same turn.
- Never give medical advice, never suggest a diagnosis, never recommend a
  medication or dosage, under any circumstance. Escalate every clinical
  question to a human.
- Never confirm a booking without calling book_appointment and getting a
  reference back.
- If asked whether you are a real person or an AI, say plainly that you are
  an AI assistant.
- If they sound annoyed or ask to be removed, apologise once, confirm you
  will remove them, use mark_do_not_call, then end_call.
"""


def _slots_for(appointment_type: str, day: str) -> tuple[list[str], list[str]]:
    info = clinic_data.APPOINTMENT_TYPES.get(appointment_type)
    if info is None:
        return [], []
    doctors = info["doctor_pool"]
    slots: list[str] = []
    for doc in doctors:
        day_slots = clinic_data.AVAILABILITY.get(doc, {}).get(day, [])
        slots.extend(f"{s} with {doc}" for s in day_slots)
    return doctors, slots


class HealthcareAgent(Agent):
    def __init__(self, caller_name: str) -> None:
        self.caller_name = caller_name
        super().__init__(
            instructions=f"""
You are Petra, scheduling appointments for {C['name']}, a {C['specialty']}
practice at {C['address']}.

You are returning a call to {caller_name}, who enquired about an appointment.
Your goal is to book them in and answer practical questions accurately. You
are never the right person to answer a clinical question.
{CALL_FLOW}{PLAYBOOK}{SAFETY}
"""
        )

    @function_tool
    async def get_opening_hours(self, ctx: RunContext) -> str:
        """Opening hours for every day of the week."""
        return json.dumps(clinic_data.OPENING_HOURS)

    @function_tool
    async def get_doctor_info(self, ctx: RunContext) -> str:
        """Doctors at the practice, their specialty and languages spoken."""
        return json.dumps(clinic_data.DOCTORS)

    @function_tool
    async def check_availability(self, ctx: RunContext, appointment_type: str, day: str) -> str:
        """Which times are available for a given appointment type on a day.

        Args:
            appointment_type: e.g. "general checkup", "follow-up",
                "skin consultation", "vaccination".
            day: Day of the week, e.g. "Monday".
        """
        key = day.strip().capitalize()
        appt = appointment_type.strip().lower()
        if appt not in clinic_data.APPOINTMENT_TYPES:
            return json.dumps({"error": "unknown_appointment_type",
                                "known_types": list(clinic_data.APPOINTMENT_TYPES)})
        hours = clinic_data.OPENING_HOURS.get(key)
        if hours == "closed":
            open_days = [d for d, h in clinic_data.OPENING_HOURS.items() if h != "closed"]
            return json.dumps({"closed_on": key, "open_days": open_days})
        doctors, slots = _slots_for(appt, key)
        return json.dumps({
            "day": key, "appointment_type": appt,
            "doctors_offering_this": doctors,
            "available_slots": slots, "fully_booked": not slots,
        })

    @function_tool
    async def get_insurance_coverage(self, ctx: RunContext, appointment_type: str) -> str:
        """Whether an appointment type is covered by statutory or private
        insurance, and any co-pay. Never estimate this yourself.

        Args:
            appointment_type: e.g. "general checkup", "travel vaccination".
        """
        appt = appointment_type.strip().lower()
        coverage = clinic_data.INSURANCE_COVERAGE.get(appt)
        if coverage is None:
            return json.dumps({"error": "no_coverage_data",
                                "advice": "Do not guess. Escalate to a human."})
        return json.dumps({"appointment_type": appt, **coverage})

    @function_tool
    async def get_practical_info(self, ctx: RunContext) -> str:
        """Wheelchair access, parking, transport, walk-in policy."""
        return json.dumps({**clinic_data.PRACTICAL, "address": C["address"]})

    @function_tool
    async def book_appointment(
        self, ctx: RunContext, appointment_type: str, day: str, slot: str,
        full_name: str, date_of_birth: str,
    ) -> str:
        """Book an appointment. Confirm name and date of birth first.

        Args:
            appointment_type: As checked with check_availability.
            day: Day of the week.
            slot: Exactly as returned by check_availability, e.g.
                "09:00 with Dr. Weber".
            full_name: Caller's full name.
            date_of_birth: Confirmed date of birth.
        """
        key = day.strip().capitalize()
        appt = appointment_type.strip().lower()
        _, slots = _slots_for(appt, key)
        if slot not in slots:
            return json.dumps({"booked": False, "available": slots})
        ref = clinic_data.next_reference()
        clinic_data.APPOINTMENTS[ref] = {
            "appointment_type": appt, "day": key, "slot": slot,
            "full_name": full_name, "date_of_birth": date_of_birth,
        }
        return json.dumps({
            "booked": True, "appointment_reference": ref,
            "practice": C["name"], "day": key, "slot": slot,
        })

    @function_tool
    async def lookup_appointment(
        self, ctx: RunContext, reference: str | None = None,
        full_name: str | None = None, date_of_birth: str | None = None,
    ) -> str:
        """Find an existing appointment by reference, or by name and date of birth.

        Args:
            reference: e.g. "AP3001".
            full_name: Caller's full name, if reference lost.
            date_of_birth: Used to confirm identity if reference lost.
        """
        if reference:
            found = clinic_data.APPOINTMENTS.get(reference.strip().upper())
            if found:
                return json.dumps({"reference": reference.strip().upper(), **found})
        if full_name and date_of_birth:
            for ref, a in clinic_data.APPOINTMENTS.items():
                if (a["full_name"].lower() == full_name.strip().lower()
                        and a["date_of_birth"] == date_of_birth.strip()):
                    return json.dumps({"reference": ref, **a})
        return "No appointment found. Ask them to confirm the reference or their details."

    @function_tool
    async def cancel_appointment(self, ctx: RunContext, reference: str) -> str:
        """Cancel an appointment.

        Args:
            reference: e.g. "AP3001".
        """
        ref = reference.strip().upper()
        appt = clinic_data.APPOINTMENTS.pop(ref, None)
        if not appt:
            return "No appointment with that reference."
        clinic_data.CANCELLED[ref] = appt
        return json.dumps({"cancelled": True, "reference": ref})

    @function_tool
    async def mark_do_not_call(self, ctx: RunContext, reason: str) -> str:
        """Remove them from the calling list.

        Args:
            reason: Short reason.
        """
        clinic_data.DO_NOT_CALL.append({"name": self.caller_name, "reason": reason})
        return json.dumps({"removed": True})

    @function_tool
    async def escalate_to_human(self, ctx: RunContext, topic: str, contact: str = "") -> str:
        """Hand to clinical staff — any symptom, diagnosis, medication, or
        emergency-adjacent question.

        Args:
            topic: What they need, e.g. "asked about medication dosage".
            contact: Phone or email if given.
        """
        clinic_data.ESCALATIONS.append(
            {"name": self.caller_name, "topic": topic, "contact": contact}
        )
        return json.dumps({"escalated": True, "callback_within": "one working day"})

    @function_tool
    async def end_call(self, ctx: RunContext) -> None:
        """Hang up. After goodbye, or immediately on an opt-out."""
        return None
