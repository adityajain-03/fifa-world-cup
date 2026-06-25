"""Regenerate app/model/third_place_table.py from Wikipedia.

Parses "Template:2026 FIFA World Cup third-place table" (a transcription of
Annex C of the FIFA regulations) into a lookup keyed by the 8 qualifying group
letters. Run from backend/:  uv run python scripts/gen_third_place_table.py
"""
from __future__ import annotations

import re
from pathlib import Path

import httpx

# Assignment columns in table order, and the bracket_map.R32_SLOTS index each
# feeds (1A->match79=idx7, 1B->85=13, 1D->81=9, 1E->74=2, 1G->82=10, 1I->77=5,
# 1K->87=15, 1L->80=8).
COLS = ["A", "B", "D", "E", "G", "I", "K", "L"]
COL_TO_IDX = {"A": 7, "B": 13, "D": 9, "E": 2, "G": 10, "I": 5, "K": 15, "L": 8}
OUT = Path(__file__).resolve().parent.parent / "app" / "model" / "third_place_table.py"


def fetch_wikitext() -> str:
    r = httpx.get(
        "https://en.wikipedia.org/w/api.php",
        params={
            "action": "parse",
            "page": "Template:2026 FIFA World Cup third-place table",
            "prop": "wikitext", "format": "json",
        },
        timeout=30, headers={"User-Agent": "fifa-cup/1.0"},
    )
    return r.json()["parse"]["wikitext"]["*"]


def parse(wt: str) -> dict[str, dict[int, str]]:
    table: dict[str, dict[int, str]] = {}
    for row in wt.split("|-"):
        if not re.search(r'scope="row"\s*\|\s*(\d+)', row):
            continue
        # The only 3X tokens in a data row are the 8 assignment cells, in column
        # order; their letters are exactly the 8 qualifying groups.
        picks = re.findall(r"\b3([A-L])\b", row)
        if len(picks) != 8:
            continue
        table["".join(sorted(picks))] = {
            COL_TO_IDX[c]: g for c, g in zip(COLS, picks)
        }
    return table


def render(table: dict[str, dict[int, str]]) -> str:
    lines = []
    for k in sorted(table):
        v = table[k]
        inner = ", ".join(f"{i}: {v[i]!r}" for i in sorted(v))
        lines.append(f"    {k!r}: {{{inner}}},")
    body = "\n".join(lines)
    return (
        '"""Official FIFA 2026 third-placed-team allocation table (Annex C of the\n'
        "tournament regulations; 495 combinations).\n\n"
        'Auto-generated from Wikipedia\'s "Template:2026 FIFA World Cup third-place '
        'table",\nwhich transcribes Annex C. Regenerate with '
        "scripts/gen_third_place_table.py.\n\n"
        'Key: the 8 group letters (sorted, e.g. "ABCDEFGH") whose third-placed '
        "teams\nqualify. Value: {r32_match_index: group_letter} mapping each "
        "third-slot R32\nmatch (indices into bracket_map.R32_SLOTS) to the group "
        "whose third-placed team\nplays there. R32 indices 2,5,7,8,9,10,13,15 are "
        "official matches 74,77,79,80,\n81,82,85,87.\n"
        '"""\n'
        "from __future__ import annotations\n\n"
        "THIRD_PLACE_TABLE: dict[str, dict[int, str]] = {\n"
        f"{body}\n"
        "}\n"
    )


def main() -> None:
    table = parse(fetch_wikitext())
    assert len(table) == 495, f"expected 495 combinations, got {len(table)}"
    OUT.write_text(render(table))
    print(f"wrote {OUT} ({len(table)} combinations)")


if __name__ == "__main__":
    main()
