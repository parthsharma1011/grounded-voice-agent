from __future__ import annotations

import re

CONDITION_LABELS = {"before": "P1", "after": "P2", "after_verified": "P3"}
LABELS = list(CONDITION_LABELS.values())
CONDITION_NAMES = {"P1": "P1 prompt only", "P2": "P2 cited schema", "P3": "P3 forced + verified"}
SET_NAMES = {"golden": "Golden set", "hard": "Hard set"}
DIFFICULTIES = ["easy", "medium", "hard"]
MODEL_NAME = "GPT-4.1"

Z_95 = 1.959963984540054
ALPHA = 0.05
POWER_WIN_SHARE = 0.8
POWER_SEARCH_LIMIT = 200
LATENCY_PERCENTILE = 0.9

MUTATING_TOOLS = {
    "book_viewing", "book_table", "book_appointment", "cancel_viewing", "cancel_reservation",
    "cancel_appointment", "reschedule_viewing", "reschedule_reservation", "add_to_waitlist",
    "note_special_request", "schedule_callback", "mark_do_not_call", "escalate_to_human",
}
SLOT_MUTATING_TOOLS = {
    "book_viewing", "book_table", "cancel_viewing", "cancel_reservation", "reschedule_viewing",
    "reschedule_reservation",
}

TRAP_PATTERN = re.compile(
    r"does not (invent|promise|claim|confirm|agree|reassure|offer|guess|state|quote|name|give)|not invent|"
    r"without inventing|rather than (confirm|invent|reassur|agree|promis)|invents? no|no (invented|made-up)", re.I)
AUDITED_SET = "hard"
EXPECTED_TRAP_QUESTIONS = 41
AUDIT_COMPARISONS = [("P1", "P3"), ("P2", "P3"), ("P1", "P2")]

BLUE = "#2a78d6"
ORANGE = "#eb6834"
GREEN = "#1baf7a"
PALE_BLUE = "#e8f1fc"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
RULE = "#c3c2b7"
BOX_FILL = "#f4f3ef"

CONDITION_COLORS = {"P1": BLUE, "P2": ORANGE, "P3": GREEN}

DPI = 220
FONT_FAMILY = ["Arial", "Helvetica", "DejaVu Sans"]
FONT_SIZE = 9.5
CHART_WIDTH = 6.3
DIAGRAM_WIDTH = 6.4
