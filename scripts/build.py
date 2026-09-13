#!/usr/bin/env python3
"""Merge the parsed sources into data/seasons.csv, the dataset the renderer reads.

Inputs:
  data/seasons_rsssf.csv   top flight 1949/50-, second tier 2008/09-  (parse.py)
  data/seasons_he.csv      second tier 1955/56-2007/08, 2025/26       (parse_he.py)
  data/seasons_en.csv      tiers 3-6, and the Mandate top flight      (parse_en.py)

Where two sources cover the same league-season the earlier one in that list
wins: RSSSF's champions have been checked against Wikipedia's list, and it is
the source the era boundaries in structure.json were drawn from.  Overlaps are
compared rather than ignored, so a disagreement between two independent sources
shows up as output instead of being silently resolved.

Every row is checked against structure.json: its league must exist at that
season, and the season must not be one that was never played.  Seasons are
keyed by label rather than by start year, because the start year is not unique
- the 1940 season was played and 1940/1941 was not, and both start in 1940.
"""

import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = DATA / "seasons.csv"
FIELDS = ["season", "season_start", "league", "division", "position", "club"]


def read(name: str) -> list[dict]:
    path = DATA / name
    if not path.exists():
        raise SystemExit(f"missing {path}; run the parse scripts first")
    with path.open() as f:
        return [{**r, "division": r.get("division", "") or ""} for r in csv.DictReader(f)]


def main() -> None:
    structure = json.loads((DATA / "structure.json").read_text())
    never_played = {e["label"] for e in structure["no_champion"]}

    def tier_of(year: int, league: str) -> int | None:
        for era in structure["eras"]:
            if era["from"] <= year and (era["to"] is None or year <= era["to"]):
                tiers = era["tiers"]
                return tiers.index(league) + 1 if league in tiers else None
        return None

    # Precedence: RSSSF first (its champions are checked against Wikipedia's
    # list), then Hebrew Wikipedia, then English Wikipedia - which is the only
    # source for tiers three and below, and for the Mandate-era top flight.
    sources = [("RSSSF", read("seasons_rsssf.csv")),
               ("Hebrew Wikipedia", read("seasons_he.csv")),
               ("English Wikipedia", read("seasons_en.csv"))]
    # Keyed per club-season, not per league-season. The Mandate-era regional
    # seasons are documented district by district and the two Wikipedias cover
    # different districts - English has the 1941/42 championship play-off,
    # Hebrew has the Jerusalem and Tel Aviv tables - so taking a whole
    # league-season from the first source that has it would discard the other's.
    # Keyed on the season label rather than the start year, because the 1940
    # season was played and 1940/1941 was not and both start in 1940.
    # The division is part of the key too: in 1941/42 Hebrew Wikipedia has
    # Maccabi Tel Aviv's Tel Aviv district row and English Wikipedia has the
    # national championship play-off that actually decided the title. Those are
    # different facts about the same club-season, so both are kept and
    # render.py picks the national one.
    key = lambda r: (r["season"], r["league"], r["club"], r["division"])

    rows: list[dict] = []
    taken: set[tuple] = set()
    added: dict[str, int] = {}
    disagreements = []
    for name, source in sources:
        positions = {key(r): (r["division"], int(r["position"])) for r in rows}
        kept = 0
        for r in source:
            if key(r) in taken:
                # Already covered by a higher-precedence source; compare rather
                # than discard silently, so a real conflict is visible.
                prior = positions.get(key(r))
                if prior and prior[1] != int(r["position"]):
                    disagreements.append(
                        f"{r['season_start']} {r['league']} {r['club']}: "
                        f"kept {prior[1]}, {name} says {r['position']}")
                continue
            rows.append(r)
            kept += 1
        taken |= {key(r) for r in source}
        added[name] = kept

    # A season that was abandoned can still have a partial table on Wikipedia
    # (1947/48 does). A partial table is not a final position, so those rows are
    # dropped and the season is left as a gap - but the drop is reported, never
    # silent.
    dropped: dict[str, int] = defaultdict(int)
    kept = []
    for r in rows:
        if r["season"] in never_played:
            dropped[f"{r['season']} {r['league']}"] += 1
        else:
            kept.append(r)
    rows = kept

    problems = sorted({
        f"{r['season']} {r['league']}: league not in the pyramid that season"
        for r in rows if tier_of(int(r["season_start"]), r["league"]) is None})
    if problems:
        for line in problems:
            print("  ERROR", line)
        raise SystemExit(f"{len(problems)} league-seasons contradict structure.json")

    # Columns come from the tier-1 season slots, so a row whose label is not one
    # of them can never be drawn. English Wikipedia titles some Mandate seasons
    # differently from the Hebrew navbox ("1938-39" against "1938" and "1939").
    index = json.loads((DATA / "seasons_index.json").read_text())
    slots = {k.split("#")[0] for k, v in index.items() if v["tier"] == 1}
    orphans = defaultdict(int)
    for r in rows:
        if r["season"] not in slots:
            orphans[f"{r['season']} {r['league']}"] += 1

    rows.sort(key=lambda r: (int(r["season_start"]), r["season"], r["league"],
                             r["division"], int(r["position"])))
    with OUT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows({k: r[k] for k in FIELDS} for r in rows)

    by_tier = defaultdict(int)
    for r in rows:
        by_tier[tier_of(int(r["season_start"]), r["league"])] += 1
    print(f"{len(rows)} rows -> {OUT}")
    print("  " + ", ".join(f"{n} from {name}" for name, n in added.items()))
    print(f"  rows by tier: {dict(sorted(by_tier.items()))}")
    print(f"  seasons: {len({r['season'] for r in rows})}, "
          f"clubs: {len({r['club'] for r in rows})}")
    if orphans:
        print(f"  {sum(orphans.values())} rows have a season label that is not a "
              f"chart column and will not be drawn: {', '.join(sorted(orphans))}")
    if dropped:
        print(f"  dropped {sum(dropped.values())} rows from seasons recorded as never "
              f"played (partial tables): {', '.join(sorted(dropped))}")
    if disagreements:
        print(f"\n{len(disagreements)} position disagreements between the two sources "
              f"(RSSSF kept):")
        for d in disagreements[:20]:
            print(f"  {d}")


if __name__ == "__main__":
    main()
