"""Official 2026 FIFA World Cup knockout bracket structure.

Verified against ESPN's published slot map (the R32 fixtures carry placeholder
names like "Group A 2nd Place", "Group C Winner", "Third Place Group A/B/C/D/F",
and the later rounds reference "Round of 32 N Winner"). This is a fixed,
published structure for the tournament, so it's encoded as a static table rather
than re-derived by rating seeding.

R32 slots (1-indexed, matching ESPN's "Round of 32 N"):
  1  A2 v B2          9  G1 v 3rd[A,E,H,I,J]
  2  C1 v F2         10  D1 v 3rd[B,E,F,I,J]
  3  E1 v 3rd[A,B,C,D,F]  11  H1 v J2
  4  F1 v C2         12  K2 v L2
  5  E2 v I2         13  B1 v 3rd[E,F,G,I,J]
  6  I1 v 3rd[C,D,F,G,H]  14  D2 v G2
  7  A1 v 3rd[C,E,F,H,I]  15  J1 v H2
  8  L1 v 3rd[E,H,I,J,K]  16  K1 v 3rd[D,E,I,J,L]
"""
from __future__ import annotations


def W(group: str) -> tuple:
    return ("W", group)  # group winner


def R(group: str) -> tuple:
    return ("R", group)  # group runner-up


def T(groups: str) -> tuple:
    return ("T", frozenset(groups))  # one of these groups' third-placed teams


# 16 R32 ties as (home_slot, away_slot), in ESPN "Round of 32 N" order.
R32_SLOTS = [
    (R("A"), R("B")),        # 1
    (W("C"), R("F")),        # 2
    (W("E"), T("ABCDF")),    # 3
    (W("F"), R("C")),        # 4
    (R("E"), R("I")),        # 5
    (W("I"), T("CDFGH")),    # 6
    (W("A"), T("CEFHI")),    # 7
    (W("L"), T("EHIJK")),    # 8
    (W("G"), T("AEHIJ")),    # 9
    (W("D"), T("BEFIJ")),    # 10
    (W("H"), R("J")),        # 11
    (R("K"), R("L")),        # 12
    (W("B"), T("EFGIJ")),    # 13
    (R("D"), R("G")),        # 14
    (W("J"), R("H")),        # 15
    (W("K"), T("DEIJL")),    # 16
]

# Tree linkage (1-indexed). Each pair feeds the next round in listed order.
R16_PAIRS = [(1, 3), (2, 5), (4, 6), (7, 8), (11, 12), (9, 10), (14, 16), (13, 15)]
QF_PAIRS = [(1, 2), (5, 6), (3, 4), (7, 8)]   # indices into R16 winners
SF_PAIRS = [(1, 2), (3, 4)]                    # indices into QF winners
FINAL_PAIR = (1, 2)                            # indices into SF winners

# R32 match indices whose away slot is a third-placed team, with eligible groups.
THIRD_SLOT_INDICES = [i for i, (_, away) in enumerate(R32_SLOTS, start=1) if away[0] == "T"]


def slot_label(slot: tuple) -> str:
    """Human-readable slot code: 'A1' (group winner), 'A2' (runner-up), '3rd'."""
    kind = slot[0]
    if kind == "W":
        return f"{slot[1]}1"
    if kind == "R":
        return f"{slot[1]}2"
    return "3rd"


def assign_thirds(qualified_thirds: dict[str, str]) -> dict[int, str]:
    """Assign the (up to 8) qualifying third-placed teams to the 8 third slots,
    respecting each slot's eligible-group list. `qualified_thirds` maps
    group_letter -> team_id. Returns {r32_match_index: team_id}.

    Uses backtracking to find a valid perfect matching (FIFA uses a fixed lookup
    table; any eligibility-respecting assignment yields a structurally valid
    bracket, which is what we need for prediction)."""
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
