from __future__ import annotations

import json

from livekit import api
from livekit.agents import Agent, RunContext, function_tool, get_job_context

from knowledge_base import restaurant
from personas.prompts import GENERIC_SAFETY, LANGUAGE_PROTOCOL, TELEPHONY_STYLE, TOOL_DISCIPLINE

R = restaurant.RESTAURANT

CALL_FLOW = f"""
CALL FLOW

Stage 1 — Open. Greet in English, say you are Lena from {R['name']}, that you
are returning their enquiry about a table, and ask if now suits.
- Bad time: apologise, ask when, schedule_callback, end_call.
- Does not remember enquiring: say it came through the website, ask if they
  would still like a table. If not, mark_do_not_call politely.

Stage 2 — Take the booking. One question per turn:
  a) Which day.
  b) Roughly what time.
  c) How many people.
Use check_availability for that day and offer the nearest available times.
Never offer a time the tool did not return.

Stage 3 — Answer whatever they ask. Menu, drinks, allergens, seating, parking,
access, dogs, high chairs, outdoor seating — use the tools. Never guess.

If they ask for something you have no tool for, say honestly that you will
check and have a colleague confirm. Do NOT produce a plausible answer. Saying
"we serve fresh juices" without checking is the single worst thing you can do
on this call.

If they state a preference — a window table, a quiet corner, the courtyard, a
highchair, a birthday — you must acknowledge it IN THE SAME TURN, before you
ask your next question. Call get_seating_options, say briefly what is possible,
call note_special_request, and only then continue the booking. Moving on to
"which day?" without answering what they just asked makes you sound like a form,
not a person, and they will notice.

Stage 4 — Confirm. Take full name and a contact number, read the number back,
then use book_table. Read the reference slowly.

Stage 5 — Close. Say what happens next, thank them, use end_call.
"""

PLAYBOOK = f"""
SCENARIO PLAYBOOK

Closed on the day they want.
Say plainly which day they asked for and that the restaurant is closed then.
Offer the nearest open day. Never invent a special opening.

Fully booked.
Say so, offer other times on that day, or another day. Do not promise to
"squeeze them in" — you cannot.

Large group.
Over {restaurant.MAX_PARTY_WITHOUT_APPROVAL} people needs manager approval and
a set menu. Take the details, say the manager will confirm, use
escalate_to_human. Never confirm a large group outright.

Allergy or dietary question.
Use get_menu_highlights and get_allergens. Be exact. If they name an allergen
you have no data on, do not reassure them — say the kitchen will confirm and
use escalate_to_human. Getting this wrong can hurt someone.

Vegetarian or vegan.
The tools flag which dishes qualify. Name only those.

Practical questions — parking, transport, wheelchair access, dogs, high chairs,
outdoor seating, dress code.
Use get_practical_info. It has real answers for all of these.

Wants to change or cancel a booking.
Use lookup_reservation with the reference, or the phone number if they lost it.
Then reschedule_reservation or cancel_reservation.

Asks about prices.
Use get_menu_highlights. Quote only prices it returns.

Asks for the chef, the owner, or a complaint.
Do not handle it yourself. escalate_to_human, confirm a callback.

Not interested / already booked elsewhere.
Thank them, mark_do_not_call, end_call. Do not try to win them back.
"""


class RestaurantAgent(Agent):
    def __init__(self, caller_name: str) -> None:
        self.caller_name = caller_name
        super().__init__(
            instructions=f"""
You are Lena, taking reservations for {R['name']}, a {R['cuisine']} restaurant
at {R['address']}.

You are returning a call to {caller_name}, who enquired about a table. Your
goal is to book them in, and to answer anything they ask about the restaurant
accurately.
{CALL_FLOW}{PLAYBOOK}{LANGUAGE_PROTOCOL}{TELEPHONY_STYLE}{TOOL_DISCIPLINE}{GENERIC_SAFETY}
"""
        )

    @function_tool
    async def get_opening_hours(self, ctx: RunContext) -> str:
        """Opening hours for every day of the week."""
        return json.dumps(restaurant.OPENING_HOURS)

    @function_tool
    async def check_availability(self, ctx: RunContext, day: str, party_size: int) -> str:
        """Which times still have a table on a given day.

        Args:
            day: Day of the week, e.g. "Friday".
            party_size: Number of people.
        """
        key = day.strip().capitalize()
        hours = restaurant.OPENING_HOURS.get(key)
        if hours is None:
            return "Unknown day. Ask them which day of the week they mean."
        if hours == "closed":
            open_days = [d for d, h in restaurant.OPENING_HOURS.items() if h != "closed"]
            return json.dumps({"closed_on": key, "open_days": open_days})
        slots = restaurant.AVAILABILITY.get(key, [])
        return json.dumps({
            "day": key, "opening_hours": hours, "available_times": slots,
            "fully_booked": not slots,
            "needs_manager_approval": party_size > restaurant.MAX_PARTY_WITHOUT_APPROVAL,
        })

    @function_tool
    async def get_menu_highlights(self, ctx: RunContext) -> str:
        """Signature dishes with prices and vegetarian/vegan flags."""
        return json.dumps(restaurant.MENU_HIGHLIGHTS)

    @function_tool
    async def get_allergens(self, ctx: RunContext) -> str:
        """Allergens per dish. Use for any allergy question — never guess."""
        return json.dumps({
            "allergens_by_dish": restaurant.ALLERGENS,
            "note": "If they ask about an allergen not listed, do not reassure "
                    "them. Escalate so the kitchen can confirm.",
        })

    @function_tool
    async def get_drinks(self, ctx: RunContext) -> str:
        """Drinks list with prices and vegan flags. Use for ANY drinks question
        — juices, wine, beer, coffee, alcohol-free. Never answer from memory."""
        return json.dumps(restaurant.DRINKS)

    @function_tool
    async def get_seating_options(self, ctx: RunContext) -> str:
        """Seating: window tables, quiet booths, bar, courtyard. Use whenever
        they ask for a particular table or spot."""
        return json.dumps(restaurant.SEATING)

    @function_tool
    async def note_special_request(self, ctx: RunContext, request: str) -> str:
        """Record a preference on the booking — a window table, a highchair, a
        birthday, a quiet corner. Use instead of ignoring what they asked for.

        Args:
            request: What they asked for, in their words.
        """
        restaurant.SPECIAL_REQUESTS.append(
            {"name": self.caller_name, "request": request}
        )
        return json.dumps({"noted": True,
                           "tell_caller": "noted on the booking, honoured where possible"})

    @function_tool
    async def get_practical_info(self, ctx: RunContext) -> str:
        """Parking, transport, wheelchair access, dogs, high chairs, outdoor
        seating, dress code, large-group policy."""
        return json.dumps({**restaurant.PRACTICAL, "address": R["address"]})

    @function_tool
    async def book_table(
        self, ctx: RunContext, day: str, time: str, party_size: int,
        full_name: str, phone: str,
    ) -> str:
        """Book a table. Confirm every detail with the caller first.

        Args:
            day: Day of the week, e.g. "Friday".
            time: Exactly as returned by check_availability.
            party_size: Number of people.
            full_name: Caller's full name.
            phone: Contact number, read back to them first.
        """
        key = day.strip().capitalize()
        slots = restaurant.AVAILABILITY.get(key, [])
        if time not in slots:
            return json.dumps({"booked": False, "available_on_that_day": slots})
        slots.remove(time)
        ref = restaurant.next_reference()
        pending = party_size > restaurant.MAX_PARTY_WITHOUT_APPROVAL
        restaurant.RESERVATIONS[ref] = {
            "day": key, "time": time, "party_size": party_size,
            "full_name": full_name, "phone": phone, "pending_approval": pending,
        }
        return json.dumps({
            "booked": True, "reservation_reference": ref, "restaurant": R["name"],
            "day": key, "time": time, "party_size": party_size,
            "status": "pending manager approval" if pending else "confirmed",
        })

    @function_tool
    async def lookup_reservation(
        self, ctx: RunContext, reference: str | None = None, phone: str | None = None
    ) -> str:
        """Find an existing reservation by reference, or by phone number.

        Args:
            reference: e.g. "RS2001".
            phone: Number used when booking, if they lost the reference.
        """
        if reference:
            r = restaurant.RESERVATIONS.get(reference.strip().upper())
            if r:
                return json.dumps({"reference": reference.strip().upper(), **r})
        if phone:
            for ref, r in restaurant.RESERVATIONS.items():
                if r["phone"].replace(" ", "") == phone.replace(" ", ""):
                    return json.dumps({"reference": ref, **r})
        return "No reservation found. Ask them to confirm the reference or number."

    @function_tool
    async def reschedule_reservation(
        self, ctx: RunContext, reference: str, new_day: str, new_time: str
    ) -> str:
        """Move a reservation.

        Args:
            reference: e.g. "RS2001".
            new_day: Day of the week.
            new_time: Exactly as returned by check_availability.
        """
        ref = reference.strip().upper()
        r = restaurant.RESERVATIONS.get(ref)
        if not r:
            return "No reservation with that reference."
        key = new_day.strip().capitalize()
        slots = restaurant.AVAILABILITY.get(key, [])
        if new_time not in slots:
            return json.dumps({"moved": False, "available_on_that_day": slots})
        slots.remove(new_time)
        restaurant.AVAILABILITY.setdefault(r["day"], []).append(r["time"])
        r["day"], r["time"] = key, new_time
        return json.dumps({"moved": True, "reference": ref, "day": key, "time": new_time})

    @function_tool
    async def cancel_reservation(self, ctx: RunContext, reference: str) -> str:
        """Cancel a reservation and release the table.

        Args:
            reference: e.g. "RS2001".
        """
        ref = reference.strip().upper()
        r = restaurant.RESERVATIONS.pop(ref, None)
        if not r:
            return "No reservation with that reference."
        restaurant.AVAILABILITY.setdefault(r["day"], []).append(r["time"])
        restaurant.CANCELLED[ref] = r
        return json.dumps({"cancelled": True, "reference": ref})

    @function_tool
    async def schedule_callback(self, ctx: RunContext, when: str, phone: str = "") -> str:
        """Agree a better time to call back, then end the call.

        Args:
            when: When they said, in their words.
            phone: Alternative number if given.
        """
        restaurant.CALLBACKS.append({"when": when, "phone": phone, "name": self.caller_name})
        return json.dumps({"scheduled": True, "when": when})

    @function_tool
    async def mark_do_not_call(self, ctx: RunContext, reason: str) -> str:
        """Remove them from the calling list. Use on any opt-out or complaint.

        Args:
            reason: Short reason.
        """
        restaurant.DO_NOT_CALL.append({"name": self.caller_name, "reason": reason})
        return json.dumps({"removed": True, "confirm_to_caller": True})

    @function_tool
    async def escalate_to_human(self, ctx: RunContext, topic: str, contact: str = "") -> str:
        """Hand to a human — large groups, complaints, unlisted allergens.

        Args:
            topic: What they need.
            contact: Phone or email if given.
        """
        restaurant.ESCALATIONS.append(
            {"name": self.caller_name, "topic": topic, "contact": contact}
        )
        return json.dumps({"escalated": True, "callback_within": "one working day"})

    @function_tool
    async def end_call(self, ctx: RunContext) -> None:
        """Hang up. After goodbye, or immediately on an opt-out."""
        await ctx.wait_for_playout()
        job = get_job_context()
        await job.api.room.delete_room(api.DeleteRoomRequest(room=job.room.name))
