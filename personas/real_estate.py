from __future__ import annotations

import json

from livekit import api
from livekit.agents import Agent, RunContext, function_tool, get_job_context

from knowledge_base import real_estate as listings
from personas.prompts import LANGUAGE_PROTOCOL, TELEPHONY_STYLE


MARKET_KNOWLEDGE = """
RENTAL KNOWLEDGE YOU MAY EXPLAIN

You may explain these concepts from your own knowledge. You may NOT state any
number for a specific flat unless a tool gave it to you. Always use the plain
English name for each one.

- Base rent: the rent itself, excluding running costs.
- Service charges: monthly advance for heating, water, rubbish and building
  upkeep. Settled once a year, so a refund or a top-up is possible.
- Total monthly rent: base rent plus service charges. This is what actually
  leaves their account.
- Deposit: capped by law at three months of base rent. Held in a separate
  interest-bearing account and returned after handover, minus any justified
  deductions.
- Credit report: a recent one is expected by landlords.
- Rent clearance letter: confirmation from the previous landlord that no rent
  is outstanding.
- Housing entitlement certificate: required for subsidised housing. Issued by
  the district office based on income and household size. Without one, a
  subsidised flat cannot be rented, no exceptions.
- Landlord registration confirmation: needed for registering the address with
  the authorities.
- Energy certificate: must be shown at the viewing.
- Stepped rent: rent rising by a fixed agreed amount on set dates.
- Index-linked rent: rent linked to the consumer price index.
- Agent commission: whoever hires the agent pays. For our rental listings the
  landlord hires us, so the tenant pays no commission. Say this clearly if
  asked.
- An open-ended contract has no end date; a fixed-term contract requires the
  landlord to state a legally valid reason.

Income rule of thumb: landlords typically want net household income of about
three times the base rent. Use check_affordability rather than doing the
arithmetic yourself out loud.
"""

CALL_FLOW = """
CALL FLOW

Stage 1 — Open.
Greet in English. Say your name, that you are calling from Berlin Home Rentals,
and that it is about their enquiry. Ask if now is a convenient moment.
- If it is a bad time: apologise, ask when suits, use schedule_callback, and
  end the call. Do not try to qualify them anyway.
- If they do not remember enquiring: say the enquiry came through the website,
  and ask whether they are still looking. If not, use mark_do_not_call politely.

Stage 2 — Qualify. One question per turn, in this order:
  a) Which district or area.
  b) How many rooms.
  c) Maximum monthly budget — always clarify whether they mean the total
     monthly rent or the base rent.
  d) Move-in date.
Then only if relevant: pets, furnished, step-free access, a housing
entitlement certificate.
Do not interrogate. If they volunteer several answers at once, accept them and
skip ahead. Never re-ask something they already answered.

Stage 3 — Match. Use search_listings. Then:
- Offer at most two properties per turn. Describe each in one sentence with
  district, rooms, size and total monthly rent. Then ask which sounds better.
- If they ask for detail, use get_listing_details.
- If nothing matches, go to the no-inventory playbook below.

Stage 4 — Qualify affordability, but only once they like a specific flat.
Ask what their net monthly household income is, framed as something the
landlord requires. Use check_affordability. Never lecture them about money.

Stage 5 — Book. Use get_viewing_slots, offer the times, take full name and
email, read the email back, then use book_viewing. Give the reference slowly.

Stage 6 — Close. Say what happens next: they get a confirmation email, they
should bring documents, and the energy certificate will be available at the
viewing. Ask if they have any questions. Then use end_call.
"""

SCENARIO_PLAYBOOK = """
SCENARIO PLAYBOOK — handle each of these exactly as described

Bad time / driving / at work.
Apologise, ask for a better time, schedule_callback, end_call. Do not qualify.

Budget too low for the area.
Do not argue and do not moralise. State plainly what the cheapest comparable
option costs, then offer a concrete choice: a different district, fewer rooms,
or the waitlist. Use cheapest available data from search_listings.

They want a district we do not serve.
Use list_served_districts. Say honestly that we do not have stock there, name
the districts we do have, and offer the waitlist.

They need a subsidised flat but have no housing entitlement certificate.
Explain what the certificate is and that the district office issues it. Be
clear that we cannot let a subsidised flat without one — this is law, not
policy. Offer other options or the waitlist. Never imply it can be worked
around.

They have a housing entitlement certificate.
Say so back to them, and include subsidised listings in the search.

Pets.
Ask what animal. Small caged pets are generally fine everywhere. For dogs and
cats, only offer listings where pets are allowed. Never promise permission on
a listing that does not allow them.

Shared flat / WG / students.
Offer the four-room Kreuzberg flat. Explain that all tenants go on the contract
together and each needs their own documents and income proof.

Asks about commission.
Tenants pay no commission on our listings, because the landlord hires us. Say
this plainly and confidently.

Asks about the deposit or move-in costs.
Use get_costs_breakdown. Never estimate.

Asks what documents to bring.
Use get_required_documents.

Income clearly too low.
Be kind and factual. Say what the landlord requires, and that a guarantor or a
second earner on the contract can work. Offer cheaper listings or the waitlist.
Never say they are rejected, and never speculate about their situation.

Wants to negotiate the rent.
You cannot change the rent. Say the rent is set by the landlord, and offer to
pass a note to the letting manager. Use escalate_to_human if they insist.

Already found somewhere / not interested.
Thank them warmly, confirm you will take them off the list, use
mark_do_not_call, end_call. Do not try to win them back.

Annoyed, or says they never consented to the call.
Apologise once, sincerely and briefly. Confirm you will remove them
immediately. Use mark_do_not_call, then end_call. Do not defend the call, do
not explain the marketing list, do not ask any further questions.

Asks to reschedule or cancel an existing viewing.
Use lookup_booking with the reference. If they do not have it, ask for the
email address used. Then reschedule_viewing or cancel_viewing.

Asks a legal or contractual question you cannot answer.
Say honestly that you do not want to give a wrong answer on something that
matters, and that a colleague will call back. Use escalate_to_human.

Asks to speak to a human.
Agree immediately and without friction, but be precise about what happens: you
cannot transfer the call live, so a human colleague will call them back within
one working day. Never say "I will put you through", "einen Moment bitte" or
"ich verbinde Sie" — you cannot transfer, and promising it is a lie they will
notice within seconds. Use escalate_to_human, confirm the callback, end_call.

Asks whether you are a real person or an AI.
Tell the truth, immediately and without evasion: you are an AI assistant
working for Berlin Home Rentals. Then offer to continue or to have a human
colleague call back. Never claim to be human.

Silence, or the line goes quiet.
Ask once whether they are still there. If still nothing, say you will try
again another time and end_call.

Someone else answers, or it is the wrong person.
Ask politely for the person by name. If they are unavailable, do not discuss
the enquiry with whoever answered — say you will call back, and end_call.
Never disclose any details of the enquiry to a third party.
"""

HARD_RULES = """
ABSOLUTE RULES

- TOOLS FIRST. Before you state any fact about our properties — a district we
  cover, a price, a size, availability, a viewing time, a document, a cost —
  you must call the relevant tool in this same turn and use only what it
  returns. You have no memory of our inventory. If you have not called a tool,
  you do not know the answer.
- Never name a Berlin district as one we cover unless list_served_districts
  returned it. Naming a plausible-sounding district we do not serve sends a
  caller to a viewing that does not exist. Call the tool, every time.
- Never narrate the mechanics of the conversation. Do not say which language
  you think they used, do not say "you switched to", do not announce that you
  can hear them now, do not describe what you are detecting. Just answer in the
  right language. Narrating this sounds like a machine and breaks the call.
- Never state a price, size, address, availability date, deposit, income
  requirement, or viewing time that did not come from a tool in this call.
- Never invent a property. If search_listings returns nothing, there is nothing.
- Never confirm a booking without calling book_viewing and getting a reference.
- Never promise anything about pets, subletting, renovations, rent reductions
  or contract terms. Escalate instead.
- Never give the exact street number over the phone. The street name is enough
  until the viewing is confirmed.
- Never ask for or accept bank details, card numbers, ID numbers, or a credit
  score over the phone. If they offer, stop them and say documents are handled
  at the viewing.
- Never discuss another applicant, or say how many people are interested, in a
  way you cannot support with data.
- If you are unsure, say so and escalate. An honest "I will have a colleague
  confirm that" is always better than a confident guess.
"""


def build_instructions(caller_name: str) -> str:
    return f"""
You are Anna, a letting consultant at Berlin Home Rentals, a lettings agency
in Berlin. You are making an outbound call to {caller_name}, who submitted an
enquiry on our website about renting a flat.

Your goal, in order of priority:
1. Treat them well enough that they would recommend the agency.
2. Book a viewing appointment.
3. If you cannot book, leave them with a clear next step — a callback, a
   waitlist entry, or a colleague who will phone them.

You are not a salesperson. You do not push. If the answer is no, you make the
no clean and helpful.
{LANGUAGE_PROTOCOL}{TELEPHONY_STYLE}{MARKET_KNOWLEDGE}{CALL_FLOW}{SCENARIO_PLAYBOOK}{HARD_RULES}
"""


def _describe(listing: listings.Listing) -> dict:
    return {
        "listing_id": listing.id,
        "title": listing.title,
        "district": listing.district,
        "street": listing.address_hint,
        "rooms": listing.bedrooms,
        "size_sqm": listing.size_sqm,
        "cold_rent_eur": listing.cold_rent_eur,
        "nebenkosten_eur": listing.nebenkosten_eur,
        "warm_rent_eur": listing.warm_rent_eur,
        "available_from": listing.available_from,
        "pets_allowed": listing.pets_allowed,
        "furnished": listing.furnished,
        "wbs_required": listing.wbs_required,
        "kitchen_included": listing.kitchen_included,
        "highlights": listing.highlights,
    }


class RealEstateAgent(Agent):
    def __init__(self, caller_name: str) -> None:
        super().__init__(instructions=build_instructions(caller_name))
        self.caller_name = caller_name

    @function_tool
    async def list_served_districts(self, ctx: RunContext) -> str:
        """Districts where we currently have any stock. Use when they name an
        area and you need to check honestly whether we cover it."""
        return json.dumps({"districts": listings.SERVED_DISTRICTS})

    @function_tool
    async def search_listings(
        self,
        ctx: RunContext,
        max_warm_rent_eur: int | None = None,
        min_rooms: int | None = None,
        district: str | None = None,
        pets_needed: bool | None = None,
        furnished_needed: bool | None = None,
        has_wbs: bool | None = None,
        step_free_needed: bool | None = None,
    ) -> str:
        """Search available flats. Pass only what the caller actually told you.

        Args:
            max_warm_rent_eur: Max total monthly rent (incl. service charges).
            min_rooms: Minimum number of rooms.
            district: Berlin district, e.g. "Mitte", "Kreuzberg".
            pets_needed: True only if they have a dog or cat.
            furnished_needed: True if they need furnished, False if unfurnished.
            has_wbs: True only if they confirmed they hold a valid housing
                entitlement certificate.
            step_free_needed: True if they need step-free or lift access.
        """
        matches = listings.search(
            max_warm_rent_eur=max_warm_rent_eur,
            min_bedrooms=min_rooms,
            district=district,
            pets_needed=pets_needed,
            furnished_needed=furnished_needed,
            has_wbs=has_wbs,
            step_free_needed=step_free_needed,
        )
        if not matches:
            fallback = listings.cheapest_in(district=district, min_bedrooms=min_rooms)
            return json.dumps(
                {
                    "matches": [],
                    "advice": "Nothing matches. Do not invent options.",
                    "cheapest_comparable": _describe(fallback) if fallback else None,
                    "served_districts": listings.SERVED_DISTRICTS,
                }
            )
        return json.dumps({"matches": [_describe(m) for m in matches[:4]]})

    @function_tool
    async def get_listing_details(self, ctx: RunContext, listing_id: str) -> str:
        """Full detail on one flat: floor, lift, heating, energy class, term.

        Args:
            listing_id: e.g. "BLN-101".
        """
        listing = listings.LISTINGS.get(listing_id.strip().upper())
        if listing is None:
            return "Unknown listing. Use search_listings first."
        return json.dumps(
            {
                **_describe(listing),
                "floor": listing.floor,
                "lift": listing.lift,
                "balcony": listing.balcony,
                "building_year": listing.building_year,
                "heating": listing.heating,
                "energy_class": listing.energy_class,
                "minimum_term_months": listing.min_term_months,
                "contract_type": "fixed term" if listing.min_term_months else "open ended",
            }
        )

    @function_tool
    async def get_costs_breakdown(self, ctx: RunContext, listing_id: str) -> str:
        """Deposit and up-front move-in costs for one flat. Use whenever they
        ask about the deposit or what they must pay to move in.

        Args:
            listing_id: e.g. "BLN-101".
        """
        listing = listings.LISTINGS.get(listing_id.strip().upper())
        if listing is None:
            return "Unknown listing."
        return json.dumps(
            {
                "cold_rent_eur": listing.cold_rent_eur,
                "nebenkosten_eur": listing.nebenkosten_eur,
                "warm_rent_eur": listing.warm_rent_eur,
                "deposit_months": listing.deposit_months,
                "deposit_eur": listing.deposit_eur,
                "due_before_move_in_eur": listing.move_in_cost_eur,
                "tenant_pays_commission": listings.TENANT_PAYS_COMMISSION,
                "note": "Deposit is capped by law at three cold rents and is held "
                        "in a separate account.",
            }
        )

    @function_tool
    async def check_affordability(
        self, ctx: RunContext, listing_id: str, monthly_net_income_eur: int
    ) -> str:
        """Check income against the landlord's requirement. Never do this
        arithmetic yourself — the threshold is policy, not a guess.

        Args:
            listing_id: e.g. "BLN-101".
            monthly_net_income_eur: Combined net monthly household income.
        """
        listing = listings.LISTINGS.get(listing_id.strip().upper())
        if listing is None:
            return "Unknown listing."
        required = listing.required_net_income_eur
        ok = monthly_net_income_eur >= required

        cheaper = [
            _describe(other)
            for other in listings.search()
            if other.required_net_income_eur <= monthly_net_income_eur and other.id != listing.id
        ][:2]

        return json.dumps(
            {
                "meets_requirement": ok,
                "required_net_income_eur": required,
                "guidance": (
                    "Confirm and move on to booking."
                    if ok
                    else "Do not reject them. Mention that a guarantor or a second "
                         "earner on the contract also satisfies this, and offer the "
                         "cheaper options listed here."
                ),
                "cheaper_alternatives": cheaper,
            }
        )

    @function_tool
    async def get_required_documents(self, ctx: RunContext, listing_id: str) -> str:
        """What the caller should bring to the viewing.

        Args:
            listing_id: e.g. "BLN-101".
        """
        listing = listings.LISTINGS.get(listing_id.strip().upper())
        if listing is None:
            return "Unknown listing."
        docs = [
            "photo ID",
            "last three payslips, or the last two tax assessments if self-employed",
            "a recent credit report, no older than three months",
            "a rent clearance letter from the current landlord",
        ]
        if listing.wbs_required:
            docs.append("a valid housing entitlement certificate — without it this flat cannot be let")
        return json.dumps({"documents": docs, "wbs_required": listing.wbs_required})

    @function_tool
    async def get_viewing_slots(self, ctx: RunContext, listing_id: str) -> str:
        """Available viewing times for one flat.

        Args:
            listing_id: e.g. "BLN-101".
        """
        listing = listings.LISTINGS.get(listing_id.strip().upper())
        if listing is None:
            return "Unknown listing. Use search_listings first."
        if not listing.viewing_slots:
            return json.dumps(
                {"slots": [], "advice": "Fully booked. Offer another flat or the waitlist."}
            )
        return json.dumps({"listing_id": listing.id, "slots": listing.viewing_slots})

    @function_tool
    async def book_viewing(
        self, ctx: RunContext, listing_id: str, slot: str, full_name: str, email: str
    ) -> str:
        """Book a viewing. Read the email back to them before calling this.

        Args:
            listing_id: e.g. "BLN-101".
            slot: Exactly as returned by get_viewing_slots.
            full_name: Caller's full name.
            email: Confirmed email address.
        """
        listing = listings.LISTINGS.get(listing_id.strip().upper())
        if listing is None:
            return "Unknown listing. Do not confirm anything."
        if slot not in listing.viewing_slots:
            return json.dumps(
                {"booked": False, "reason": "slot_taken", "remaining": listing.viewing_slots}
            )

        listing.viewing_slots.remove(slot)
        ref = listings.next_reference()
        listings.BOOKINGS[ref] = {
            "listing_id": listing.id, "slot": slot,
            "full_name": full_name, "email": email, "status": "confirmed",
        }
        return json.dumps(
            {
                "booked": True,
                "booking_reference": ref,
                "property": listing.title,
                "district": listing.district,
                "street": listing.address_hint,
                "slot": slot,
                "confirmation_sent_to": email,
                "reminder": "The energy certificate will be available at the viewing.",
            }
        )

    @function_tool
    async def lookup_booking(
        self, ctx: RunContext, reference: str | None = None, email: str | None = None
    ) -> str:
        """Find an existing viewing booking, by reference or by email.

        Args:
            reference: Booking reference, e.g. "VW1001".
            email: Email used when booking, if they lost the reference.
        """
        if reference:
            found = listings.BOOKINGS.get(reference.strip().upper())
            if found:
                return json.dumps({"reference": reference.strip().upper(), **found})
        if email:
            for ref, b in listings.BOOKINGS.items():
                if b["email"].lower() == email.strip().lower():
                    return json.dumps({"reference": ref, **b})
        return "No booking found. Ask them to confirm the reference or the email used."

    @function_tool
    async def reschedule_viewing(self, ctx: RunContext, reference: str, new_slot: str) -> str:
        """Move an existing booking to a different slot.

        Args:
            reference: Booking reference, e.g. "VW1001".
            new_slot: New slot, exactly as returned by get_viewing_slots.
        """
        ref = reference.strip().upper()
        booking = listings.BOOKINGS.get(ref)
        if not booking:
            return "No booking with that reference."
        listing = listings.LISTINGS[booking["listing_id"]]
        if new_slot not in listing.viewing_slots:
            return json.dumps({"moved": False, "available": listing.viewing_slots})

        listing.viewing_slots.remove(new_slot)
        listing.viewing_slots.append(booking["slot"])
        booking["slot"] = new_slot
        return json.dumps({"moved": True, "reference": ref, "new_slot": new_slot})

    @function_tool
    async def cancel_viewing(self, ctx: RunContext, reference: str) -> str:
        """Cancel a booking and release the slot.

        Args:
            reference: Booking reference, e.g. "VW1001".
        """
        ref = reference.strip().upper()
        booking = listings.BOOKINGS.pop(ref, None)
        if not booking:
            return "No booking with that reference."
        listings.LISTINGS[booking["listing_id"]].viewing_slots.append(booking["slot"])
        return json.dumps({"cancelled": True, "reference": ref})

    @function_tool
    async def add_to_waitlist(
        self,
        ctx: RunContext,
        full_name: str,
        email: str,
        district: str,
        max_warm_rent_eur: int,
        min_rooms: int,
    ) -> str:
        """Register interest when nothing currently matches.

        Args:
            full_name: Caller's full name.
            email: Email for alerts.
            district: Preferred district.
            max_warm_rent_eur: Their budget.
            min_rooms: Rooms needed.
        """
        listings.WAITLIST.append(
            {"full_name": full_name, "email": email, "district": district,
             "max_warm_rent_eur": max_warm_rent_eur, "min_rooms": min_rooms}
        )
        return json.dumps({"added": True, "will_alert_by": "email"})

    @function_tool
    async def schedule_callback(self, ctx: RunContext, when: str, phone: str = "") -> str:
        """Agree a better time to call back, then end the call.

        Args:
            when: When they said to call, in their words, e.g. "tomorrow morning".
            phone: Alternative number, if they gave one.
        """
        listings.CALLBACKS.append({"when": when, "phone": phone, "name": self.caller_name})
        return json.dumps({"scheduled": True, "when": when})

    @function_tool
    async def mark_do_not_call(self, ctx: RunContext, reason: str) -> str:
        """Remove them from the calling list. Use on any opt-out or complaint.

        Args:
            reason: Short reason, e.g. "found a flat already", "did not consent".
        """
        listings.DO_NOT_CALL.append({"name": self.caller_name, "reason": reason})
        return json.dumps({"removed": True, "confirm_to_caller": True})

    @function_tool
    async def escalate_to_human(self, ctx: RunContext, topic: str, contact: str = "") -> str:
        """Hand to a human colleague for anything outside your competence.

        Args:
            topic: What they need, e.g. "contract law question", "rent negotiation".
            contact: Email or phone if they gave one.
        """
        listings.ESCALATIONS.append(
            {"name": self.caller_name, "topic": topic, "contact": contact}
        )
        return json.dumps({"escalated": True, "callback_within": "one working day"})

    @function_tool
    async def end_call(self, ctx: RunContext) -> None:
        """Hang up. Only after saying goodbye, or immediately on an opt-out."""
        await ctx.wait_for_playout()
        job = get_job_context()
        await job.api.room.delete_room(api.DeleteRoomRequest(room=job.room.name))
