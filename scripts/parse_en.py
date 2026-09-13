#!/usr/bin/env python3
"""Parse the cached English Wikipedia season articles into data/seasons_en.csv.

Output columns: season,season_start,league,division,position,club

These articles are uniform: 204 of the 207 cached use Wikipedia's sports-table
module, where the standings are parameters rather than a table:

    |team1=BTA|name_BTA=[[Beitar Tel Aviv F.C.|Beitar Tel Aviv]]
    |team2=BEI|name_BEI=[[Beitar Jerusalem F.C.|Beitar Jerusalem]]

so position comes from the number on "teamN" and the club from the matching
"name_CODE".  Club identity is taken from the wikilink *target*, which is the
club's current article and therefore already lineage-resolved.

Below tier two almost everything is regional - "North Division", "Samaria
Division", "Sub-division A" - so the division is recorded and those positions
are ranks within a region, not national ones.  Promotion and relegation
play-offs are separate competitions between tiers and are skipped.
"""

import csv
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = DATA / "raw" / "en"
OUT = DATA / "seasons_en.csv"

# English Wikipedia's name for a league -> the name used in structure.json.
LEAGUE_NAMES = {"Palestine League": "Eretz Israel League"}

# English Wikipedia titles one Mandate season as a split year where the Hebrew
# navbox - which supplies the chart's columns - uses a single one. Its infobox
# runs 1937 -> this -> 1939 and names Hapoel Tel Aviv's third title, matching
# the Hebrew table's "1938" row exactly.
LABEL_FIXUPS = {"1938/1939": "1938"}

INVOKE = re.compile(r"\{\{#invoke:\s*sports table", re.I)
HEADING = re.compile(r"^={2,}\s*(.+?)\s*={2,}\s*$", re.M)
TEAM = re.compile(r"\|\s*team(\d{1,2})\s*=\s*([A-Za-z0-9_]+)")
NAME = re.compile(r"\|\s*name_([A-Za-z0-9_]+)\s*=\s*([^|}\n]+)")
LINK = re.compile(r"\[\[([^\]|]+)")

# Sections that are a separate competition rather than league standings.
SKIP_SECTION = re.compile(r"play-?off|promotion|relegation|qualif", re.I)
# Headings that mean "this is the whole league", not a region.
NATIONAL = {"final table", "league table", "table", "standings", "final standings"}

UNMAPPED: dict[str, int] = {}


def label_of(title: str) -> str:
    """Season label from an article title.

    "1940 Palestine League" -> 1940, "1947-48 Palestine League" -> 1947/1948,
    "1966-68 Liga Alef" -> 1966/1968.  The start year alone is not a key: the
    1940 season was played and 1940/1941 was not, and both start in 1940.
    """
    if m := re.match(r"^(\d{4})[\u2013-](\d{2,4})\s", title):
        start, end = m.group(1), m.group(2)
        return f"{start}/{end if len(end) == 4 else start[:2] + end}"
    return re.match(r"^(\d{4})\s", title).group(1)


def division_of(heading: str) -> str:
    h = heading.strip()
    if h.lower() in NATIONAL:
        return ""
    h = re.sub(r"\s+division$", "", h, flags=re.I)
    h = re.sub(r"^sub-?division\s+", "", h, flags=re.I)
    return "" if h.lower() in NATIONAL else h


def club_of(value: str) -> str | None:
    """Canonical club name from a name_CODE parameter value."""
    text = value.strip()
    if m := LINK.search(text):
        text = m.group(1)
    text = re.sub(r"\s*\([^)]*\)\s*$", "", text)
    text = re.sub(r"\s+(A\.?F\.?C\.?|F\.?C\.?|A\.?C\.?|S\.?C\.?)\s*$", "",
                  text).strip()
    return text or None


def blocks(wiki: str) -> list[tuple[str, str]]:
    """(heading, text) for each sports-table block, with its section heading."""
    out = []
    for m in INVOKE.finditer(wiki):
        heads = HEADING.findall(wiki[:m.start()])
        heading = heads[-1] if heads else ""
        # The block runs to the next invoke or the next heading, whichever first.
        rest = wiki[m.start():]
        nxt = INVOKE.search(rest, 1)
        end = nxt.start() if nxt else len(rest)
        if h := HEADING.search(rest[:end]):
            end = min(end, h.start())
        out.append((heading, rest[:end]))
    return out


def rows_of(block: str) -> list[tuple[int, str]]:
    names = {code: club_of(value) for code, value in NAME.findall(block)}
    rows = []
    for pos, code in TEAM.findall(block):
        if club := names.get(code):
            rows.append((int(pos), club))
    return rows


def main() -> None:
    index = json.loads((DATA / "en_index.json").read_text())
    structure = json.loads((DATA / "structure.json").read_text())
    aliases = json.loads((DATA / "aliases_en.json").read_text())

    # Any name already used as a canonical name by the other two sources is
    # accepted as-is; only genuinely new spellings need a mapping.
    known = set(json.loads((DATA / "aliases.json").read_text()).values())
    known |= set(json.loads((DATA / "aliases_he.json").read_text()).values())
    known.discard("")

    def tier_of(year: int, league: str) -> int | None:
        for era in structure["eras"]:
            if era["from"] <= year and (era["to"] is None or year <= era["to"]):
                return (era["tiers"].index(league) + 1
                        if league in era["tiers"] else None)
        return None

    def safe(title: str) -> str:
        return re.sub(r"[^A-Za-z0-9]+", "-", title).strip("-")

    rows: list[tuple[str, int, str, str, int, str]] = []
    skipped_league: set[str] = set()
    for title, meta in sorted(index.items()):
        path = RAW / f"{safe(title)}.wiki"
        if not path.exists():
            continue
        league = LEAGUE_NAMES.get(meta["league"], meta["league"])
        label = label_of(title)
        label = LABEL_FIXUPS.get(label, label)
        year = meta["start"]
        if tier_of(year, league) is None:
            skipped_league.add(f"{year} {league}")
            continue
        for heading, block in blocks(path.read_text()):
            if SKIP_SECTION.search(heading):
                continue
            div = division_of(heading)
            for pos, raw_club in rows_of(block):
                club = aliases.get(raw_club)
                if not club:
                    club = raw_club
                    if raw_club not in known:
                        UNMAPPED[raw_club] = UNMAPPED.get(raw_club, 0) + 1
                rows.append((label, year, league, div, pos, club))

    # Keep one row per club per league-season-division; a club listed twice is
    # an article quirk, not two finishes.
    seen: set[tuple] = set()
    deduped = []
    for r in rows:
        key = (r[0], r[2], r[3], r[5])
        if key not in seen:
            seen.add(key)
            deduped.append(r)
    deduped.sort(key=lambda r: (r[1], r[2], r[3], r[4]))

    with OUT.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["season", "season_start", "league", "division",
                    "position", "club"])
        w.writerows(deduped)

    by_tier: dict[int, int] = defaultdict(int)
    for r in deduped:
        by_tier[tier_of(r[1], r[2])] += 1
    seasons = sorted({r[1] for r in deduped})
    print(f"{len(deduped)} rows, {len(seasons)} seasons "
          f"({seasons[0]}-{seasons[-1]}), {len({r[5] for r in deduped})} clubs -> {OUT}")
    print(f"  rows by tier: {dict(sorted(by_tier.items()))}")
    if skipped_league:
        print(f"  skipped {len(skipped_league)} league-seasons not in the era table: "
              f"{', '.join(sorted(skipped_league)[:8])}")
    if UNMAPPED:
        print(f"\n{len(UNMAPPED)} club names needing data/aliases_en.json "
              f"(most frequent first):")
        for name, n in sorted(UNMAPPED.items(), key=lambda kv: -kv[1])[:30]:
            print(f'  {n:3}x  "{name}": "",')


if __name__ == "__main__":
    main()
