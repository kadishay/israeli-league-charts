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
OUT = DATA / "raw" / "parsed" / "seasons_en.csv"

# fetch_en.py already records the canonical league name in en_index.json, so
# nothing needs translating here. Kept as a safety net for an older cache.
LEAGUE_NAMES: dict[str, str] = {}

# English Wikipedia titles one Mandate season as a split year where the Hebrew
# navbox - which supplies the chart's columns - uses a single one. Its infobox
# runs 1937 -> this -> 1939 and names Hapoel Tel Aviv's third title, matching
# the Hebrew table's "1938" row exactly.
LABEL_FIXUPS = {"1938/1939": "1938"}

# Sources disagree on what the 1954/55 top flight was called: RSSSF heads its
# table "Liga Leumit" and English Wikipedia "Liga Alef". They are the same
# competition, so it is renamed here to match the era table - which leaves
# build.py to drop it as already covered by RSSSF, rather than carrying the
# season twice under two names and double-counting the clubs in it.
LEAGUE_FIXUPS = {("1954/1955", "Liga Alef"): "Liga Leumit"}

INVOKE = re.compile(r"\{\{#invoke:\s*sports table", re.I)
HEADING = re.compile(r"^(={2,})\s*(.+?)\s*={2,}\s*$", re.M)
TEAM = re.compile(r"\|\s*team(\d{1,2})\s*=\s*([A-Za-z0-9_]+)")
NAME = re.compile(r"\|\s*name_([A-Za-z0-9_]+)\s*=\s*([^|}\n]+)")
LINK = re.compile(r"\[\[([^\]|]+)")

# Sections that are a separate competition rather than league standings.
SKIP_SECTION = re.compile(r"play-?off|promotion|relegation|qualif", re.I)
# Headings that mean "this is the whole league", not a region.
NATIONAL = {"final table", "league table", "table", "standings", "final standings"}

# (English name, first season start) -> the club it had become by then. Same
# shape as NAME_FROM in parse_he.py and CLUB_FIXUPS in parse.py.
#
# Beitar Tiberias merged with Hapoel Mo'atza Ezorit Galil Tahton in 2004; the
# joint club played as Hapoel Galil Tahton/Tiberias and was renamed Ironi
# Tiberias in 2006. English Wikipedia keeps filing the merged club under the
# Lower Galilee name for its last two seasons, so those rows belong to Ironi.
# Scoped from 2004 because the same name before that is the other parent, which
# has its own record and stays separate.
NAME_FROM = [("Hapoel Mo'atza Ezorit Galil Tahton", 2004, "Ironi Tiberias")]

UNMAPPED: dict[str, int] = {}


def label_of(title: str) -> str:
    """Season label from an article title.

    "1940 Palestine League" -> 1940, "1947-48 Palestine League" -> 1947/1948,
    "1966-68 Liga Alef" -> 1966/1968.  The first two are English Wikipedia's
    article titles for Eretz Israel League seasons, not the league's name.  The start year alone is not a key: the
    1940 season was played and 1940/1941 was not, and both start in 1940.
    """
    if m := re.match(r"^(\d{4})[\u2013-](\d{2,4})\s", title):
        start, end = m.group(1), m.group(2)
        return f"{start}/{end if len(end) == 4 else start[:2] + end}"
    return re.match(r"^(\d{4})\s", title).group(1)


def division_of(path: list[str]) -> str:
    """Division name from a heading and the headings it sits under.

    2020/21 is why this takes a path rather than one heading. That season the
    lower leagues ran in two phases, and the article nests the groups:

        ==North Division==
        ===Sub-division A===

    Reading only the innermost heading called that group "A", and South's
    Sub-division A was also "A", so two separate nine-team groups were filed as
    one eighteen-team division holding two clubs at every position from 1 to 9.
    Qualifying it with the parent gives "North A" and "South A".

    Only a sub-division is qualified, and only with an ancestor that is itself a
    division. Qualifying everything pulled in whatever structural heading
    happened to sit above the table - "League tables (as of 3 January 1948)",
    "Regular season results" - and renamed 250 rows that were already right.
    """
    own = path[-1].strip() if path else ""
    if own.lower() in NATIONAL:
        return ""
    if re.match(r"^sub-?division\b", own, flags=re.I):
        parent = next((h for h in reversed(path[:-1])
                       if re.search(r"\bdivision$", h.strip(), flags=re.I)
                       and not re.match(r"^sub-?division\b", h.strip(), flags=re.I)),
                      None)
        if parent:
            head = re.sub(r"\s+division$", "", parent.strip(), flags=re.I)
            tail = re.sub(r"^sub-?division\s+", "", own, flags=re.I)
            return f"{head} {tail}".strip()
    h = re.sub(r"\s+division$", "", own, flags=re.I)
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


def blocks(wiki: str) -> list[tuple[list[str], str]]:
    """(heading path, text) for each sports-table block.

    The path is the block's own heading plus the outer headings containing it,
    outermost first, so a nested group keeps the region it belongs to.
    """
    out = []
    for m in INVOKE.finditer(wiki):
        heads = [(len(lvl), txt) for lvl, txt in HEADING.findall(wiki[:m.start()])]
        heading: list[str] = []
        depth = 10 ** 6
        for lvl, txt in reversed(heads):
            if lvl < depth:
                heading.insert(0, txt)
                depth = lvl
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
    OUT.parent.mkdir(parents=True, exist_ok=True)
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
        league = LEAGUE_FIXUPS.get((label, league), league)
        year = meta["start"]
        if tier_of(year, league) is None:
            skipped_league.add(f"{year} {league}")
            continue
        for heading, block in blocks(path.read_text()):
            # The block's own heading decides whether it is standings, not its
            # ancestors: the 1941/42 championship decider sits as "Table" under
            # "Championship play-off", and testing the whole path threw away the
            # one national ranking that season has.
            if SKIP_SECTION.search(heading[-1] if heading else ""):
                continue
            div = division_of(heading)
            for pos, raw_club in rows_of(block):
                for name, since, becomes in NAME_FROM:
                    if raw_club == name and year >= since:
                        raw_club = becomes
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

    # Two clubs cannot share a position in one division. The existing dedupe is
    # per club, so it happily kept two clubs at position 1; this is the check
    # that catches a division label too coarse for the article's structure,
    # which is exactly how the 2020/21 sub-divisions hid for as long as they did.
    ranks: dict[tuple, dict[int, str]] = {}
    clashes = []
    for label, year, league, div, pos, club in deduped:
        at = ranks.setdefault((label, league, div), {})
        if pos in at:
            clashes.append(f"{label} {league} {div or '(national)'}: "
                           f"position {pos} held by {at[pos]} and {club}")
        else:
            at[pos] = club
    if clashes:
        print(f"{len(clashes)} duplicated position(s) - a division label is "
              f"probably merging two groups:")
        for c in clashes[:12]:
            print(f"  {c}")
        if len(clashes) > 12:
            print(f"  ... and {len(clashes) - 12} more")

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
