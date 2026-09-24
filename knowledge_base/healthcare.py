from __future__ import annotations

CLINIC = {
    "name": "Riverside Practice",
    "specialty": "general practice",
    "address": "Kastanienallee 44, Berlin Prenzlauer Berg",
    "phone": "+49 30 5555 0200",
}

DOCTORS = {
    "Dr. Weber": {"specialty": "general practice", "languages": ["German", "English"]},
    "Dr. Ilhan": {"specialty": "general practice", "languages": ["German", "English", "Turkish"]},
    "Dr. Fischer": {"specialty": "dermatology", "languages": ["German"]},
}

OPENING_HOURS = {
    "Monday": "08:00 - 17:00",
    "Tuesday": "08:00 - 17:00",
    "Wednesday": "08:00 - 13:00",
    "Thursday": "08:00 - 19:00",
    "Friday": "08:00 - 15:00",
    "Saturday": "closed",
    "Sunday": "closed",
}

AVAILABILITY: dict[str, dict[str, list[str]]] = {
    "Dr. Weber": {
        "Monday": ["09:00", "09:20", "11:40"],
        "Tuesday": ["10:00", "10:20", "15:40"],
        "Thursday": ["17:00", "17:20", "18:00"],
    },
    "Dr. Ilhan": {
        "Monday": ["08:20", "13:40"],
        "Wednesday": ["08:20", "09:00"],
        "Friday": ["08:40", "09:20", "10:00"],
    },
    "Dr. Fischer": {
        "Tuesday": ["09:00"],
        "Thursday": ["17:40"],
    },
}

APPOINTMENT_TYPES = {
    "general checkup": {"duration_minutes": 20, "doctor_pool": ["Dr. Weber", "Dr. Ilhan"]},
    "follow-up": {"duration_minutes": 10, "doctor_pool": ["Dr. Weber", "Dr. Ilhan"]},
    "skin consultation": {"duration_minutes": 20, "doctor_pool": ["Dr. Fischer"]},
    "vaccination": {"duration_minutes": 10, "doctor_pool": ["Dr. Weber", "Dr. Ilhan"]},
}

INSURANCE_COVERAGE = {
    "general checkup": {"statutory": True, "private": True, "co_pay_eur": 0},
    "follow-up": {"statutory": True, "private": True, "co_pay_eur": 0},
    "skin consultation": {"statutory": True, "private": True, "co_pay_eur": 0},
    "vaccination": {"statutory": True, "private": True, "co_pay_eur": 0},
    "travel vaccination": {"statutory": False, "private": True, "co_pay_eur": 45},
}

PRACTICAL = {
    "wheelchair_access": "step-free entrance, accessible toilet on the ground floor",
    "parking": "no on-site parking; public garage two streets away on Kastanienallee",
    "nearest_transport": "Eberswalder Strasse U-Bahn, about five minutes on foot",
    "walk_in_policy": "no walk-ins; appointment required except for medical emergencies",
    "emergency_note": "For a medical emergency, hang up and call 112 immediately.",
}

APPOINTMENTS: dict[str, dict] = {}
CANCELLED: dict[str, dict] = {}
DO_NOT_CALL: list[dict] = []
ESCALATIONS: list[dict] = []
CALLBACKS: list[dict] = []


def next_reference() -> str:
    return f"AP{3000 + len(APPOINTMENTS) + 1}"
