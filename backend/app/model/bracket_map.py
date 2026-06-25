"""Official 2026 FIFA World Cup knockout bracket structure.

Verified against ESPN's published slot map (the R32 fixtures carry placeholder
names like "Group A 2nd Place", "Group C Winner", "Third Place Group A/B/C/D/F",
and the later rounds reference "Round of 32 N Winner"). This is a fixed,
published structure for the tournament, so it's encoded as a static table rather
than re-derived by rating seeding.

R32 slots are listed in the official FIFA match-number order (slot i = match
72+i), verified against Wikipedia's knockout-stage schedule and ESPN's bracket
(match 74 = "Winner E v 3rd A/B/C/D/F", match 76 = "Winner C v Runner-up F",
etc.). Official numbering is NOT chronological, so it must come from this table
rather than kickoff order.

R32 slots (1-indexed, slot i = official match 72+i):
   1 (73) A2 v B2              9 (81) D1 v 3rd[B,E,F,I,J]
   2 (74) E1 v 3rd[A,B,C,D,F] 10 (82) G1 v 3rd[A,E,H,I,J]
   3 (75) F1 v C2             11 (83) K2 v L2
   4 (76) C1 v F2             12 (84) H1 v J2
   5 (77) I1 v 3rd[C,D,F,G,H] 13 (85) B1 v 3rd[E,F,G,I,J]
   6 (78) E2 v I2             14 (86) J1 v H2
   7 (79) A1 v 3rd[C,E,F,H,I] 15 (87) K1 v 3rd[D,E,I,J,L]
   8 (80) L1 v 3rd[E,H,I,J,K] 16 (88) D2 v G2
"""
from __future__ import annotations

from .third_place_table import THIRD_PLACE_TABLE


def W(group: str) -> tuple:
    return ("W", group)  # group winner


def R(group: str) -> tuple:
    return ("R", group)  # group runner-up


def T(groups: str) -> tuple:
    return ("T", frozenset(groups))  # one of these groups' third-placed teams


# 16 R32 ties as (home_slot, away_slot), in official match-number order
# (slot i = match 72+i).
R32_SLOTS = [
    (R("A"), R("B")),        # 1  (73)
    (W("E"), T("ABCDF")),    # 2  (74)
    (W("F"), R("C")),        # 3  (75)
    (W("C"), R("F")),        # 4  (76)
    (W("I"), T("CDFGH")),    # 5  (77)
    (R("E"), R("I")),        # 6  (78)
    (W("A"), T("CEFHI")),    # 7  (79)
    (W("L"), T("EHIJK")),    # 8  (80)
    (W("D"), T("BEFIJ")),    # 9  (81)
    (W("G"), T("AEHIJ")),    # 10 (82)
    (R("K"), R("L")),        # 11 (83)
    (W("H"), R("J")),        # 12 (84)
    (W("B"), T("EFGIJ")),    # 13 (85)
    (W("J"), R("H")),        # 14 (86)
    (W("K"), T("DEIJL")),    # 15 (87)
    (R("D"), R("G")),        # 16 (88)
]

# Tree linkage (1-indexed slot/tie numbers, = official match-number offset).
# R16 tie j = official match 88+j; QF k = 96+k; SF l = 100+l; final = 104.
R16_PAIRS = [(2, 5), (1, 3), (4, 6), (7, 8), (11, 12), (9, 10), (14, 16), (13, 15)]
QF_PAIRS = [(1, 2), (5, 6), (3, 4), (7, 8)]   # indices into R16 winners
SF_PAIRS = [(1, 2), (3, 4)]                    # indices into QF winners
FINAL_PAIR = (1, 2)                            # indices into SF winners

# R32 match indices whose away slot is a third-placed team, with eligible groups.
THIRD_SLOT_INDICES = [i for i, (_, away) in enumerate(R32_SLOTS, start=1) if away[0] == "T"]

# Display order: lay each column out as a *planar* bracket tree, so every match
# sits vertically between the two feeders that produce it (no crossing lines).
# QF_PAIRS feeds R16 ties (1,2),(5,6),(3,4),(7,8) in QF order, so the R16 column
# must read 1,2,5,6,3,4,7,8 for QF1..QF4 to align top-to-bottom. The R32 column
# then follows each R16 tie's two feeders in that same order. Official match
# numbers are stamped per tie independently (see Simulator._annotate), so this
# reordering is purely visual and matches ESPN's bracket layout.
QF_DISPLAY = [1, 2, 3, 4]
SF_DISPLAY = [1, 2]
R16_DISPLAY = [j for pair in QF_PAIRS for j in pair]
R32_DISPLAY = [m for j in R16_DISPLAY for m in R16_PAIRS[j - 1]]


# --- Official match-number lookups -------------------------------------------
# Keyed by the unordered slot/feeder pair so home/away order doesn't matter.
R32_NUMBER = {frozenset(slots): 72 + i for i, slots in enumerate(R32_SLOTS, 1)}
R16_NUMBER = {frozenset(pair): 88 + j for j, pair in enumerate(R16_PAIRS, 1)}
QF_NUMBER = {frozenset(pair): 96 + k for k, pair in enumerate(QF_PAIRS, 1)}
SF_NUMBER = {frozenset(pair): 100 + l for l, pair in enumerate(SF_PAIRS, 1)}


def slot_label(slot: tuple) -> str:
    """Human-readable slot code: 'A1' (group winner), 'A2' (runner-up), '3rd'."""
    kind = slot[0]
    if kind == "W":
        return f"{slot[1]}1"
    if kind == "R":
        return f"{slot[1]}2"
    return "3rd"


def assign_thirds(qualified_thirds: dict[str, str]) -> dict[int, str]:
    """Assign the (up to 8) qualifying third-placed teams to the 8 third slots.
    `qualified_thirds` maps group_letter -> team_id. Returns
    {r32_match_index: team_id}.

    When exactly 8 thirds qualify, uses FIFA's official Annex C allocation table
    (`third_place_table.THIRD_PLACE_TABLE`) — the published, exact mapping of
    which group's third plays in which R32 match. Falls back to an
    eligibility-respecting backtracking match if the combination isn't in the
    table (e.g. fewer than 8 thirds available mid-prediction)."""
    if len(qualified_thirds) == 8:
        key = "".join(sorted(qualified_thirds))
        official = THIRD_PLACE_TABLE.get(key)
        if official is not None:
            return {idx: qualified_thirds[g] for idx, g in official.items()}

    slots = [(idx, R32_SLOTS[idx - 1][1][1]) for idx in THIRD_SLOT_INDICES]  # (idx, eligible set)
    groups = list(qualified_thirds.keys())

    result: dict[int, str] = {}
    used_groups: set[str] = set()

    def backtrack(si: int) -> bool:
        if si == len(slots):
            return True
        idx, eligible = slots[si]
        for g in groups:
            if g in used_groups or g not in eligible:
                continue
            used_groups.add(g)
            result[idx] = qualified_thirds[g]
            if backtrack(si + 1):
                return True
            used_groups.discard(g)
            del result[idx]
        return False

    if backtrack(0):
        return result
    # Fallback: assign leftover thirds to leftover slots ignoring eligibility.
    leftover = [g for g in groups if g not in used_groups]
    for (idx, _), g in zip(slots, leftover):
        if idx not in result:
            result[idx] = qualified_thirds[g]
    return result
