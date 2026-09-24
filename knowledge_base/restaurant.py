from __future__ import annotations

RESTAURANT = {
    "name": "Zur Goldenen Gans",
    "cuisine": "modern European",
    "address": "Oranienburger Strasse 12, Berlin Mitte",
    "phone": "+49 30 5555 0100",
}

OPENING_HOURS = {
    "Monday": "closed",
    "Tuesday": "17:00 - 23:00",
    "Wednesday": "17:00 - 23:00",
    "Thursday": "17:00 - 23:00",
    "Friday": "17:00 - 01:00",
    "Saturday": "12:00 - 01:00",
    "Sunday": "12:00 - 22:00",
}

MENU_HIGHLIGHTS = [
    {"dish": "Braised beef in vinegar marinade with red cabbage and potato dumplings", "price_eur": 26},
    {"dish": "Pan-fried zander with brown butter and dill potatoes", "price_eur": 29},
    {"dish": "Wild mushroom filled pasta pockets in chive broth", "price_eur": 21, "vegetarian": True},
    {"dish": "Beetroot tartare with horseradish cream", "price_eur": 17, "vegan": True},
    {"dish": "Red berry compote with vanilla sauce", "price_eur": 11, "vegetarian": True},
]

AVAILABILITY: dict[str, list[str]] = {
    "Friday": ["18:00", "18:30", "21:15", "21:45"],
    "Saturday": ["12:30", "13:00", "17:45", "18:15", "22:00"],
    "Sunday": ["12:00", "12:30", "13:00", "19:00", "19:30"],
    "Tuesday": ["18:00", "19:00", "20:00", "21:00"],
    "Wednesday": ["18:00", "19:00", "20:00", "21:00"],
    "Thursday": ["18:30", "19:30", "20:30"],
}

MAX_PARTY_WITHOUT_APPROVAL = 8

RESERVATIONS: dict[str, dict] = {}


def next_reference() -> str:
    return f"RS{2000 + len(RESERVATIONS) + 1}"


ALLERGENS = {
    "Braised beef in vinegar marinade with red cabbage and potato dumplings": ["gluten", "celery"],
    "Pan-fried zander with brown butter and dill potatoes": ["fish", "dairy"],
    "Wild mushroom filled pasta pockets in chive broth": ["gluten", "egg", "celery"],
    "Beetroot tartare with horseradish cream": [],
    "Red berry compote with vanilla sauce": ["dairy"],
}

PRACTICAL = {
    "nearest_transport": "Oranienburger Strasse city rail station, about three minutes on foot",
    "parking": "no private car park; paid street parking after eight in the evening",
    "wheelchair_access": "step-free entrance, accessible toilet on the ground floor",
    "outdoor_seating": "twelve seats in the courtyard, weather permitting",
    "dogs": "well-behaved dogs are welcome in the bar area",
    "high_chairs": "yes, three available",
    "large_group_policy": "groups over eight need manager approval and a set menu",
    "dress_code": "smart casual, no strict rule",
}

CANCELLED: dict[str, dict] = {}
DO_NOT_CALL: list[dict] = []
ESCALATIONS: list[dict] = []
CALLBACKS: list[dict] = []

DRINKS = [
    {"drink": "Freshly pressed orange juice", "price_eur": 6, "vegan": True},
    {"drink": "Apple spritzer", "price_eur": 4, "vegan": True},
    {"drink": "Berlin pilsner, half litre", "price_eur": 5, "vegan": True},
    {"drink": "Riesling, Mosel valley, glass", "price_eur": 8, "vegan": False,
     "note": "fined with egg white"},
    {"drink": "Pinot Noir, glass", "price_eur": 9, "vegan": True},
    {"drink": "Alcohol-free wheat beer", "price_eur": 5, "vegan": True},
    {"drink": "Filter coffee", "price_eur": 3.5, "vegan": True},
]

SEATING = {
    "window_tables": "six tables by the front windows; requestable but not guaranteed",
    "quiet_corner": "two booths at the back, best for conversation",
    "bar_seating": "eight stools, walk-in only",
    "courtyard": "twelve seats outside, weather permitting",
    "note": "Seating preferences are noted on the booking and honoured where "
            "possible, but never promised in advance.",
}

SPECIAL_REQUESTS: list[dict] = []
