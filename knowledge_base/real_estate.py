from __future__ import annotations

from dataclasses import dataclass, field

INCOME_MULTIPLE_REQUIRED = 3.0
TENANT_PAYS_COMMISSION = False


@dataclass
class Listing:
    id: str
    title: str
    district: str
    address_hint: str
    bedrooms: int
    size_sqm: int
    cold_rent_eur: int
    nebenkosten_eur: int
    deposit_months: int
    floor: str
    lift: bool
    balcony: bool
    furnished: bool
    pets_allowed: bool
    wbs_required: bool
    available_from: str
    min_term_months: int | None
    building_year: int
    heating: str
    energy_class: str
    kitchen_included: bool
    highlights: list[str]
    viewing_slots: list[str] = field(default_factory=list)

    @property
    def warm_rent_eur(self) -> int:
        return self.cold_rent_eur + self.nebenkosten_eur

    @property
    def deposit_eur(self) -> int:
        return self.cold_rent_eur * self.deposit_months

    @property
    def required_net_income_eur(self) -> int:
        return int(self.cold_rent_eur * INCOME_MULTIPLE_REQUIRED)

    @property
    def move_in_cost_eur(self) -> int:
        return self.deposit_eur + self.warm_rent_eur


LISTINGS: dict[str, Listing] = {
    "BLN-101": Listing(
        id="BLN-101",
        title="Bright two-room period flat near Boxhagener Platz",
        district="Friedrichshain",
        address_hint="Krossener Strasse",
        bedrooms=2, size_sqm=68,
        cold_rent_eur=1180, nebenkosten_eur=240, deposit_months=3,
        floor="3rd floor", lift=False, balcony=True, furnished=False,
        pets_allowed=True, wbs_required=False,
        available_from="1 October", min_term_months=None,
        building_year=1904, heating="central gas heating", energy_class="D",
        kitchen_included=False,
        highlights=["original stucco ceilings", "south-facing balcony", "oak parquet"],
        viewing_slots=[
            "Tuesday 16 September at 5 PM",
            "Thursday 18 September at 6:30 PM",
            "Saturday 20 September at 11 AM",
        ],
    ),
    "BLN-204": Listing(
        id="BLN-204",
        title="Modern three-room family flat with lift",
        district="Prenzlauer Berg",
        address_hint="Greifswalder Strasse",
        bedrooms=3, size_sqm=94,
        cold_rent_eur=1750, nebenkosten_eur=340, deposit_months=3,
        floor="5th floor", lift=True, balcony=True, furnished=False,
        pets_allowed=False, wbs_required=False,
        available_from="15 September", min_term_months=None,
        building_year=2019, heating="district heating", energy_class="A",
        kitchen_included=True,
        highlights=["underfloor heating", "fitted kitchen included", "two bathrooms"],
        viewing_slots=[
            "Wednesday 17 September at 4 PM",
            "Friday 19 September at 1 PM",
        ],
    ),
    "BLN-315": Listing(
        id="BLN-315",
        title="Compact furnished studio, ideal for a short stay",
        district="Neukölln",
        address_hint="Weserstrasse",
        bedrooms=1, size_sqm=34,
        cold_rent_eur=740, nebenkosten_eur=140, deposit_months=2,
        floor="Ground floor, courtyard side", lift=False, balcony=False,
        furnished=True, pets_allowed=False, wbs_required=False,
        available_from="immediately", min_term_months=6,
        building_year=1962, heating="gas boiler in the flat", energy_class="E",
        kitchen_included=True,
        highlights=["fully furnished", "quiet courtyard", "six month minimum term"],
        viewing_slots=[
            "Monday 15 September at 12 PM",
            "Thursday 18 September at 10 AM",
        ],
    ),
    "BLN-422": Listing(
        id="BLN-422",
        title="Penthouse maisonette with roof terrace",
        district="Mitte",
        address_hint="Linienstrasse",
        bedrooms=3, size_sqm=132,
        cold_rent_eur=2900, nebenkosten_eur=450, deposit_months=3,
        floor="Top two floors", lift=True, balcony=True, furnished=False,
        pets_allowed=True, wbs_required=False,
        available_from="1 November", min_term_months=None,
        building_year=2015, heating="district heating", energy_class="B",
        kitchen_included=True,
        highlights=["forty square metre roof terrace", "underground parking", "concierge"],
        viewing_slots=["Saturday 20 September at 2 PM"],
    ),
    "BLN-508": Listing(
        id="BLN-508",
        title="Quiet two-room flat, housing certificate required",
        district="Wedding",
        address_hint="Togostrasse",
        bedrooms=2, size_sqm=58,
        cold_rent_eur=540, nebenkosten_eur=170, deposit_months=3,
        floor="2nd floor", lift=False, balcony=True, furnished=False,
        pets_allowed=True, wbs_required=True,
        available_from="1 October", min_term_months=None,
        building_year=1978, heating="central heating", energy_class="D",
        kitchen_included=False,
        highlights=["social housing rent level", "balcony facing the courtyard"],
        viewing_slots=[
            "Tuesday 16 September at 2 PM",
            "Friday 19 September at 9:30 AM",
        ],
    ),
    "BLN-611": Listing(
        id="BLN-611",
        title="Barrier-free ground floor flat with garden access",
        district="Steglitz",
        address_hint="Schlossstrasse",
        bedrooms=2, size_sqm=76,
        cold_rent_eur=1290, nebenkosten_eur=260, deposit_months=3,
        floor="Ground floor", lift=True, balcony=True, furnished=False,
        pets_allowed=True, wbs_required=False,
        available_from="1 October", min_term_months=None,
        building_year=2008, heating="district heating", energy_class="B",
        kitchen_included=True,
        highlights=["step-free access", "wide doorways", "private garden terrace"],
        viewing_slots=[
            "Wednesday 17 September at 11 AM",
            "Saturday 20 September at 3:30 PM",
        ],
    ),
    "BLN-707": Listing(
        id="BLN-707",
        title="Large four-room flat for a shared household",
        district="Kreuzberg",
        address_hint="Gneisenaustrasse",
        bedrooms=4, size_sqm=118,
        cold_rent_eur=2100, nebenkosten_eur=380, deposit_months=3,
        floor="4th floor", lift=False, balcony=True, furnished=False,
        pets_allowed=True, wbs_required=False,
        available_from="1 November", min_term_months=None,
        building_year=1910, heating="central gas heating", energy_class="E",
        kitchen_included=False,
        highlights=["shared households welcome", "four equal-sized rooms", "two balconies"],
        viewing_slots=[
            "Thursday 18 September at 5 PM",
            "Saturday 20 September at 12:30 PM",
        ],
    ),
    "BLN-819": Listing(
        id="BLN-819",
        title="New-build one-bedroom with smart heating",
        district="Lichtenberg",
        address_hint="Frankfurter Allee",
        bedrooms=1, size_sqm=45,
        cold_rent_eur=890, nebenkosten_eur=180, deposit_months=3,
        floor="6th floor", lift=True, balcony=True, furnished=False,
        pets_allowed=False, wbs_required=False,
        available_from="immediately", min_term_months=None,
        building_year=2022, heating="heat pump", energy_class="A+",
        kitchen_included=True,
        highlights=["very low heating costs", "smart thermostats", "bike storage"],
        viewing_slots=[
            "Monday 15 September at 4 PM",
            "Wednesday 17 September at 6 PM",
            "Friday 19 September at 5:30 PM",
        ],
    ),
}

SERVED_DISTRICTS = sorted({listing.district for listing in LISTINGS.values()})

BOOKINGS: dict[str, dict] = {}
WAITLIST: list[dict] = []
CALLBACKS: list[dict] = []
DO_NOT_CALL: list[dict] = []
ESCALATIONS: list[dict] = []


def search(
    max_warm_rent_eur: int | None = None,
    min_bedrooms: int | None = None,
    district: str | None = None,
    pets_needed: bool | None = None,
    furnished_needed: bool | None = None,
    has_wbs: bool | None = None,
    step_free_needed: bool | None = None,
) -> list[Listing]:
    results = list(LISTINGS.values())

    if max_warm_rent_eur is not None:
        results = [r for r in results if r.warm_rent_eur <= max_warm_rent_eur]
    if min_bedrooms is not None:
        results = [r for r in results if r.bedrooms >= min_bedrooms]
    if district:
        needle = district.strip().lower()
        results = [r for r in results if needle in r.district.lower()]
    if pets_needed:
        results = [r for r in results if r.pets_allowed]
    if furnished_needed is not None:
        results = [r for r in results if r.furnished == furnished_needed]
    if step_free_needed:
        results = [r for r in results if "Ground floor" in r.floor or r.lift]
    if not has_wbs:
        results = [r for r in results if not r.wbs_required]

    return sorted(results, key=lambda r: r.warm_rent_eur)


def cheapest_in(district: str | None = None, min_bedrooms: int | None = None) -> Listing | None:
    pool = search(district=district, min_bedrooms=min_bedrooms)
    return pool[0] if pool else None


def next_reference() -> str:
    return f"VW{1000 + len(BOOKINGS) + 1}"
