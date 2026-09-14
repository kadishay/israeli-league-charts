#!/usr/bin/env python3
"""Turn the cached RSSSF pages into data/seasons_rsssf.csv.

scripts/build.py merges this with the Hebrew Wikipedia rows into data/seasons.csv.

Output columns: season_start,league,position,club
  season_start  the calendar year the season began (1966/68 is recorded as 1966)
  league        RSSSF's league name, normalised (see LEAGUE_NAMES)
  position      final position in the league, absolute across playoff groups
  club          canonical club name (see data/aliases.json)

RSSSF gives absolute positions even when a season splits into an upper and a
lower playoff group, so a season's rows always form a contiguous 1..N.  That
invariant is asserted, which is what catches format surprises.
"""

import csv
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "seasons_rsssf.csv"

# A standings row.  The club name runs up to the games-played column, which is
# not always separated by whitespace ("Hapoel Ironi Rishon-Lezion39  10  13").
# Anchoring on the goals column (e.g. "41-65") is what makes the row unambiguous.
ROW = re.compile(r"^\s*(\d{1,2})\.\s*(.*?)\s*(\d{1,3})\s+\d+\s+\d+\s+\d+\s+\d+\s*-\s*\d+")

# Season headers in israhist.html, e.g. "Liga Leumit 1966/68".
HIST_HEADER = re.compile(
    r"^(Israeli League|League A|Liga Leumit|Premier League)\s+(\d{4})/(\d{2,4})\s*$"
)

# In israhist.html a cross-tier play-off table sits inside the season's block.
# Anchored to the line start so it cannot match the "play-off" annotation that
# appears at the end of a standings row.
PLAYOFF_HEADER = re.compile(
    r"^\s*Promotion(?:/relegation)?\s+play-?off:?\s*$", re.I | re.M
)

# (season label, RSSSF's club name) -> the club it actually was. RSSSF heads
# the 2007/08 table with "Hapoel Kiriat-Shmona", but Hapoel and Maccabi Kiryat
# Shmona had merged in 2000 into what was by then Ironi Kiryat Shmona, whose
# article records 2007/08 as its first top-flight season, finishing third.
CLUB_FIXUPS = {("2007/2008", "Hapoel Kiriat-Shmona"): "Ironi Kiriat-Shmona"}

DISCREPANCIES: list[str] = []
SKIPPED: set[str] = set()

LEAGUE_NAMES = {
    "israeli league": "Israeli League",
    "league a": "Liga Alef",
    "liga leumit": "Liga Leumit",
    "premier league": "Ligat ha'Al",
    "ligat ha'al": "Ligat ha'Al",
    "liga artzit": "Liga Artzit",
    "liga alef": "Liga Alef",
}

# Every heading that ends a league section on a per-season page, so that cup
# group tables are never read as league standings.
SECTION_HEAD = re.compile(
    r"^(?:" + "|".join(re.escape(k) for k in LEAGUE_NAMES) + r"|cups \d{4}/\d{2}"
    r"|gvia hamedina.*|state cup|toto cup|about this document)$", re.I
)


def text_of(fragment: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", fragment))


def rows_from(block: str) -> list[tuple[int, str]]:
    """(printed position, club) for every standings row, in printed order."""
    found = []
    for line in block.split("\n"):
        m = ROW.match(line)
        if m and m.group(2):
            found.append((int(m.group(1)), m.group(2).strip()))
    return found


def standings(blocks: list[list[tuple[int, str]]], year: int, league: str) -> list[str] | None:
    """Merge playoff-group tables into one ordered list of clubs.

    Positions are taken from row *order*, not from the printed numbers: RSSSF
    occasionally mis-numbers a row (2021/22 Liga Leumit skips 13 and prints 16
    twice) but always lists clubs in standings order.  The printed numbers are
    still used to order the groups relative to each other, and any disagreement
    is reported so a real parse error cannot hide behind this repair.
    """
    # Some pages print the same table twice; drop the verbatim repeats before
    # anything reasons about how many blocks there are.
    blocks = list({tuple(b): b for b in blocks if b}.values())
    if not blocks:
        raise SystemExit(f"{year} {league}: no standings rows found")
    # Playoff groups within one league continue each other's numbering (1-6,
    # then 7-14).  Two blocks both starting at 1 mean parallel regional
    # divisions instead, which this dataset does not model.
    if sum(1 for b in blocks if min(p for p, _ in b) == 1) > 1:
        SKIPPED.add(f"{year} {league} (regional divisions)")
        return None
    order, seen = [], set()
    for block in sorted(blocks, key=lambda b: min(p for p, _ in b)):
        for printed, club in block:
            if club not in seen:  # a table is sometimes printed twice verbatim
                seen.add(club)
                order.append((printed, club))
    for i, (printed, club) in enumerate(order, start=1):
        if printed != i:
            DISCREPANCIES.append(f"{year} {league}: {club} printed as {printed}, ranked {i}")
    return [club for _, club in order]


def label_of(year: int, second: str) -> str:
    """Season label, e.g. 1966/1968 for the two-year season, else 1966/1967.

    The start year alone is not a key: the 1940 season was played and 1940/1941
    was not, and both start in 1940.
    """
    if len(second) == 4:
        end = int(second)
    else:
        end = year - year % 100 + int(second)
        if end < year:          # "1999/00" ends in 2000, not 1900
            end += 100
    return f"{year}/{end}"


def parse_hist(path: Path) -> list[tuple[int, str, str, int, str]]:
    """Top flight 1949/50 - 2007/08 from the single combined page."""
    lines = text_of(path.read_text(encoding="latin-1")).split("\n")
    starts = [(i, m) for i, line in enumerate(lines) if (m := HIST_HEADER.match(line.strip()))]
    out = []
    for n, (i, m) in enumerate(starts):
        end = starts[n + 1][0] if n + 1 < len(starts) else len(lines)
        league = LEAGUE_NAMES[m.group(1).lower()]
        year = int(m.group(2))
        label = label_of(year, m.group(3))
        # A promotion/relegation play-off table sits inside the season's block
        # and is not part of the league standings.  Anchored to the line start
        # so it does not match the "play-off" annotation on a standings row.
        block = PLAYOFF_HEADER.split("\n".join(lines[i:end]))[0]
        if table := standings([rows_from(block)], year, league):
            out += [(year, label, league, pos, club)
                    for pos, club in enumerate(table, start=1)]
    return out


def parse_season(path: Path, year: int) -> list[tuple[int, str, str, int, str]]:
    """One season page (2008/09 onwards), covering every tier it documents.

    Sections are delimited by bare heading lines.  Some pages wrap those in
    <h4> anchors and some (2008/09) do not, so the split is done on the text
    after tag stripping, which works for both.  The table of contents at the
    top repeats the league names; those are filtered out by requiring a
    "Final Table:" to appear before the next heading.
    """
    lines = text_of(path.read_text(encoding="latin-1")).split("\n")
    heads = [i for i, line in enumerate(lines) if SECTION_HEAD.match(line.strip())]
    out = []
    for n, i in enumerate(heads):
        league = LEAGUE_NAMES.get(lines[i].strip().lower())
        if not league:
            continue
        end = heads[n + 1] if n + 1 < len(heads) else len(lines)
        sec = "\n".join(lines[i:end])
        if "Final Table:" not in sec:
            continue  # a table-of-contents entry, not the section itself
        # A promotion/relegation playoff is a separate cross-tier competition;
        # its rows are not league standings.  "Relegation Playoff" on its own
        # *is* part of the standings and must be kept.
        sec = re.split(r"(?im)^\s*Promotion/Relegation\s+Play-?off", sec)[0]
        # Prefer the post-playoff tables; they carry the final absolute positions.
        parts = re.split(r"(?im)^\s*Playoff Stage\s*$", sec)
        blocks = [rows_from(b) for b in parts[-1].split("Final Table:")[1:]]
        if not any(blocks):  # no playoff that season: single regular-stage table
            blocks = [rows_from(b) for b in sec.split("Final Table:")[1:]]
        if table := standings(blocks, year, league):
            out += [(year, f"{year}/{year + 1}", league, pos, club)
                    for pos, club in enumerate(table, start=1)]
    if not any(r[2] == "Ligat ha'Al" for r in out):
        raise SystemExit(f"{year}: no top-flight table found in {path.name}")
    return out


def main() -> None:
    rows = parse_hist(RAW / "israhist.html")
    for path in sorted(RAW.glob("season-*.html")):
        rows += parse_season(path, int(path.stem.split("-")[1]))

    aliases = json.loads((ROOT / "data" / "aliases.json").read_text())
    unknown: set[str] = set()

    def canon(name: str) -> str:
        key = re.sub(r"\s+", " ", name).strip()
        if key not in aliases:
            unknown.add(key)
        return aliases.get(key, key)

    rows = [(y, lab, lg, p, canon(CLUB_FIXUPS.get((lab, c), c)))
            for y, lab, lg, p, c in rows]
    rows.sort(key=lambda r: (r[0], r[2], r[3]))

    with OUT.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["season", "season_start", "league", "division", "position", "club"])
        # RSSSF only documents national tables, so the division column is always empty.
        w.writerows((lab, y, lg, "", p, c) for y, lab, lg, p, c in rows)

    seasons = sorted({r[0] for r in rows})
    print(f"{len(rows)} rows, {len(seasons)} seasons ({seasons[0]}-{seasons[-1]}), "
          f"{len({r[4] for r in rows})} clubs -> {OUT}")
    if SKIPPED:
        print(f"\nskipped {len(SKIPPED)} league-seasons: {', '.join(sorted(SKIPPED))}")
    if DISCREPANCIES:
        print(f"\n{len(DISCREPANCIES)} rows where the printed number disagrees with the ranking:")
        for line in DISCREPANCIES:
            print(f"  {line}")
    if unknown:
        print(f"\n{len(unknown)} names missing from data/aliases.json:")
        for name in sorted(unknown):
            print(f'  "{name}": "",')


if __name__ == "__main__":
    main()
