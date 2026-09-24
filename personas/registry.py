from __future__ import annotations

from dataclasses import dataclass

from personas.real_estate import RealEstateAgent
from personas.restaurant import RestaurantAgent


@dataclass(frozen=True)
class Persona:
    key: str
    label: str
    blurb: str
    agent_display_name: str
    agent_cls: type
    greeting: str
    voicemail: str


PERSONAS: dict[str, Persona] = {
    "real_estate": Persona(
        key="real_estate",
        label="Real Estate",
        blurb="Anna from Berlin Home Rentals books apartment viewings.",
        agent_display_name="Anna",
        agent_cls=RealEstateAgent,
        greeting=(
            "Greet them in English, say you are Anna from Berlin Home Rentals calling "
            "about their apartment enquiry, and ask if now is a good moment."
        ),
        voicemail=(
            "Hello, this is Anna from Berlin Home Rentals. I am calling about your "
            "apartment enquiry. Please call us back so we can arrange a viewing "
            "appointment. Thank you and goodbye."
        ),
    ),
    "restaurant": Persona(
        key="restaurant",
        label="Restaurant",
        blurb="Lena takes table reservations for Zur Goldenen Gans.",
        agent_display_name="Lena",
        agent_cls=RestaurantAgent,
        greeting=(
            "Greet them warmly in English. Say you are Lena from the restaurant Zur "
            "Goldenen Gans, that this is a demonstration of an AI voice assistant, "
            "and that they are welcome to ask you anything about the restaurant or "
            "book a table. Then ask how you can help. Keep it to three short "
            "sentences and sound genuinely friendly, not scripted."
        ),
        voicemail=(
            "Hello, this is Lena from the restaurant Zur Goldenen Gans. I am returning "
            "your enquiry about a table. Please get in touch and we will reserve "
            "your table. Thank you and goodbye."
        ),
    ),
}

DEFAULT_PERSONA = "real_estate"


def get(key: str | None) -> Persona:
    return PERSONAS.get(key or DEFAULT_PERSONA, PERSONAS[DEFAULT_PERSONA])
