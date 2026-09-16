#!/usr/bin/env python3
"""Parse the cached Hebrew Wikipedia season articles into data/seasons_he.csv.

Output columns: season,season_start,league,division,position,club

Two things make these articles awkward:

* Cells appear both inline ("|1|| [[club]]||30||...") and one per line, so the
  tables are split into cells properly rather than matched with one regex.
* A season may be one national table, or two sequential playoff groups (upper
  1-8, lower 9-14), or two parallel regional groups (North 1-16, South 1-16).
  Liga Alef ran as North/South from 1963/64 to 1975/76, which means there is no
  national ranking for the second tier in those years - only a position within
  a region, recorded in the 'division' column.

Club identity comes from the wikilink *target*, not the display text: Hebrew
Wikipedia points historical names at the club's current article, so
"[[הפועל נוף הגליל|הפועל נצרת עילית]]" resolves a 1980 club to its modern
identity for free.  Only clubs listed in data/aliases_he.json are emitted, so
that the dataset does not fill up with half-identified minor clubs; anything
unmapped is reported so the map can be extended.
"""

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "he"
OUT = ROOT / "data" / "raw" / "parsed" / "seasons_he.csv"

# Sections holding a separate competition: a cross-tier promotion play-off or a
# cup.  Note that this must NOT catch הפלייאוף העליון / הפלייאוף התחתון, which
# are the championship and relegation rounds of the league itself and carry its
# final positions.
EXCLUDE_SECTION = re.compile(
    r"פלייאוף (ה?עלייה)|משחקי המבחן|גביע|מבחן"
    # Statistics and squad sections. Their tables are numbered and contain
    # wikilinks, so a top-scorer list would otherwise read as standings - with
    # players where clubs should be.
    r"|מלך השערים|מלך הבישולים|סטטיסטיק|שחקן ה|שחקנ|העברות|שינויי מאמנים"
    r"|אצטדיון|^ה?קבוצות$|הערות שוליים|פרסים",
    re.U | re.M,
)

# The modern format plays a regular season and then splits into an upper and a
# lower play-off.  Where both are present the play-off tables are the final
# standings and the regular-season table is superseded.
PLAYOFF_STAGE = re.compile(r"פלייאוף (העליון|התחתון)", re.U)
REGULAR_STAGE = re.compile(r"העונה הסדירה", re.U)

# A standings row carries position, club and at least games/wins/draws/losses/
# goals; a top-scorer or transfer table is much narrower.  Requiring the width
# is what keeps those out without maintaining a blacklist of section names.
MIN_STANDINGS_CELLS = 7
MIN_STANDINGS_ROWS = 4

# Regional group headings -> the division name recorded in the CSV.  Liga Alef
# ran as בית הצפון/בית הדרום from 1963/64 to 1975/76; the Mandate and early-state
# district leagues use מחוז <region>.  Upper/lower playoff groups
# (הבית העליון/הבית התחתון) are deliberately absent: their numbering continues
# across the groups, so they merge into a single national table instead.
DIVISIONS = {
    "בית הצפון": "North",
    "בית צפון": "North",
    "בית הדרום": "South",
    "בית דרום": "South",
}
REGIONS = {
    "צפון": "North",
    "הצפון": "North",
    "דרום": "South",
    "הדרום": "South",
    "השומרון": "Samaria",
    "השרון": "Sharon",
    "שרון": "Sharon",
    "תל אביב": "Tel Aviv",
    "ירושלים והדרום": "Jerusalem & South",
    "שומרון": "Samaria",
    "חיפה": "Haifa",
    "חיפה (צפון)": "Haifa",
    "תל אביב": "Tel Aviv",
    "ירושלים": "Jerusalem",
    "השפלה": "Shfela",
}


# The Mandate-era districts are sometimes split by standard as well as by
# place - "מחוז תל אביב א'" and "מחוז תל אביב ב'" - so the letter is kept as
# part of the division name.
LETTERS = {"א'": "A", "ב'": "B", "א": "A", "ב": "B"}


def division_of(heading: str) -> str:
    heading = heading.strip()
    if heading in DIVISIONS:
        return DIVISIONS[heading]
    if m := re.fullmatch(r"(?:מחוז|בית)\s+(.+?)(?:\s+([אב]'?))?", heading):
        region, letter = m.group(1).strip(), m.group(2)
        if region not in REGIONS:
            raise SystemExit(f"unknown district heading: {heading!r}")
        name = REGIONS[region]
        return f"{name} {LETTERS[letter]}" if letter else name
    return ""

HEADING = re.compile(r"^(={2,})\s*(.+?)\s*\1\s*$", re.M)
WIKILINK = re.compile(r"\[\[([^\]|]+)")
PARENTHETICAL = re.compile(r"\s*\([^)]*\)\s*$")

UNMAPPED: dict[str, int] = {}
DISCREPANCIES: list[str] = []


def club_key(cell: str) -> str | None:
    """Canonical Hebrew article name for the club in a table cell.

    Usually a wikilink, whose target is preferred over the display text because
    Hebrew Wikipedia points a club's historical names at its current article.
    Defunct clubs are sometimes unlinked plain text, so that is accepted too -
    dropping those rows would leave a hole in the standings.
    """
    if m := WIKILINK.search(cell):
        return PARENTHETICAL.sub("", m.group(1).strip())
    text = re.sub(r"\{\{[^}]*\}\}", "", cell)        # flags, notes
    text = re.sub(r"^[^|]*=[^|]*\|", "", text)       # cell attributes
    if "|" in text:   # a wikilink whose brackets are missing in the source
        text = text.rsplit("|", 1)[1]
    text = PARENTHETICAL.sub("", text.replace("'''", "").strip())
    return text or None


def rows_of(table: str) -> list[list[str]]:
    """Cells of each row of a wikitable, as a line-based parse.

    Splitting on "|-" is not enough: a row separator carries its own attributes
    on the same line ('|- bgcolor="ccffcc"'), and reading those as the row's
    first cell silently drops exactly the rows that are coloured - the promoted
    and relegated ones.  Cells also appear both inline ("|1|| [[club]]") and one
    per line, with either "|" or "||" starting the line.
    """
    rows: list[list[str]] = []
    for line in table.split("\n"):
        s = line.strip()
        if not s or s.startswith("{|") or s.startswith("|}") or s.startswith("!"):
            continue
        if s.startswith("|-"):
            rows.append([])          # rest of the line is row attributes
            continue
        if s.startswith("|"):
            if not rows:
                rows.append([])      # a table whose first row has no "|-"
            rows[-1] += [c.strip() for c in re.sub(r"^\|+", "", s).split("||")]
    return rows


def table_rows(table: str) -> list[tuple[int, str]]:
    """(position, club) for each standings row, or [] if this is not a table of
    standings at all."""
    out = []
    for cs in rows_of(table):
        if len(cs) < MIN_STANDINGS_CELLS or not re.fullmatch(r"\d{1,2}", cs[0]):
            continue
        if club := club_key(cs[1]):
            out.append((int(cs[0]), club))
    return out if len(out) >= MIN_STANDINGS_ROWS else []


def sections(wiki: str) -> list[tuple[str, str]]:
    """(heading, body) for each section, plus the lead under an empty heading."""
    marks = list(HEADING.finditer(wiki))
    if not marks:
        return [("", wiki)]
    out = [("", wiki[: marks[0].start()])]
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(wiki)
        out.append((m.group(2), wiki[m.end(): end]))
    return out


def parse_article(wiki: str) -> list[tuple[str, list[tuple[int, str]]]]:
    """(division, rows) for every league table in the article.

    Where a season split into an upper and a lower play-off, those tables are
    the final standings and the regular-season table is dropped.
    """
    found = []
    for heading, body in sections(wiki):
        if EXCLUDE_SECTION.search(heading):
            continue
        for table in re.findall(r"\{\|.*?\n\|\}", body, re.S):
            if rows := table_rows(table):
                found.append((heading, division_of(heading), rows))
    if any(PLAYOFF_STAGE.search(h) for h, _, _ in found):
        found = [t for t in found if not REGULAR_STAGE.search(t[0])]
    return [(div, rows) for _, div, rows in found]


def resolve(tables: list[tuple[str, list[tuple[int, str]]]], label: str
            ) -> list[tuple[str, int, str]]:
    """Flatten an article's tables into (division, position, club).

    Groups that both start at 1 are parallel regions and keep their own
    numbering; groups that continue each other (1-8, then 9-14) are one table
    split by a playoff and are merged in order.
    """
    tables = [t for t in tables if t[1]]
    if not tables:
        return []
    starting_at_one = sum(1 for _, rows in tables if min(p for p, _ in rows) == 1)
    if len(tables) > 1 and starting_at_one > 1:
        if any(not div for div, _ in tables):
            raise SystemExit(f"{label}: parallel tables without a division heading")
        out = []
        for div, rows in tables:
            out += [(div, pos, club)
                    for pos, club in renumber(rows, f"{label} {div}")]
        return out

    # Sequential play-off groups: the printed numbers are absolute (1-6, then
    # 7-14), so they are kept as they are.  Renumbering would paper over a
    # missing group and produce plausible-looking but wrong positions.
    merged: dict[int, str] = {}
    for _, rows in tables:
        for pos, club in rows:
            merged.setdefault(pos, club)
    ordered = [(pos, merged[pos]) for pos in sorted(merged)]
    check_contiguous(ordered, label)
    return [("", pos, club) for pos, club in ordered]


def check_contiguous(rows: list[tuple[int, str]], label: str) -> None:
    positions = sorted(p for p, _ in rows)
    if positions != list(range(1, len(positions) + 1)):
        raise SystemExit(
            f"{label}: positions are not a contiguous 1..N: {positions}")


def renumber(rows: list[tuple[int, str]], label: str) -> list[tuple[int, str]]:
    """Positions for one complete table, repaired from row order if need be.

    A single regional table is a full standings list, so its row order is
    reliable even where the printed numbers are not - the 1939 South B district
    skips 3 and prints 4 twice. The repair is reported so a real parse error
    cannot hide behind it. Sequential play-off groups deliberately do NOT get
    this treatment: there, a gap can mean a whole group went missing, and
    renumbering would produce plausible but wrong positions.
    """
    positions = [p for p, _ in rows]
    if positions == list(range(1, len(positions) + 1)):
        return rows
    DISCREPANCIES.append(f"{label}: printed {positions}, ranked by row order")
    return [(i, club) for i, (_, club) in enumerate(rows, start=1)]


# Club identity comes from the wikilink target, which is normally the club's
# current article and so resolves renames for free. It fails when the season
# article itself points at the wrong club: the Liga Leumit articles from 2003/04
# to 2005/06 link Kiryat Shmona to [[הפועל קריית שמונה]], but Hapoel and Maccabi
# Kiryat Shmona had merged in 2000 into Ironi Kiryat Shmona, whose own article
# calls 2003/04 "the club's first season in Liga Leumit". Hapoel had no senior
# side by then. Same shape as CLUB_FIXUPS in parse.py, which corrects RSSSF's
# 2007/08 table for the same club.
#
# Scoped from a season rather than applied outright: before 2000 the name is
# correct and the rows belong to the predecessor.
NAME_FROM = [("הפועל קריית שמונה", 2000, "Ironi Kiryat Shmona")]


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    index = json.loads((ROOT / "data" / "seasons_index.json").read_text())
    aliases = json.loads((ROOT / "data" / "aliases_he.json").read_text())
    rows: list[tuple[str, int, str, str, int, str]] = []

    for path in sorted(RAW.glob("*.wiki")):
        key = path.stem.replace("-", "/", 1)          # "1965-1966#2" -> "1965/1966#2"
        meta = index.get(key)
        if not meta:
            raise SystemExit(f"{path.name}: not in data/seasons_index.json")
        for div, pos, club_he in resolve(parse_article(path.read_text()), key):
            club = aliases.get(club_he)
            if not club:
                UNMAPPED[club_he] = UNMAPPED.get(club_he, 0) + 1
                continue
            for he, since, becomes in NAME_FROM:
                if club_he == he and meta["start"] >= since:
                    club = becomes
            rows.append((key.split("#")[0], meta["start"], meta["league"],
                         div, pos, club))

    rows.sort(key=lambda r: (r[1], r[2], r[3], r[4]))
    with OUT.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["season", "season_start", "league", "division",
                    "position", "club"])
        w.writerows(rows)

    seasons = sorted({r[1] for r in rows})
    span = f"{seasons[0]}-{seasons[-1]}" if seasons else "none"
    print(f"{len(rows)} rows, {len(seasons)} seasons ({span}), "
          f"{len({r[5] for r in rows})} clubs -> {OUT}")
    if DISCREPANCIES:
        print(f"\n{len(DISCREPANCIES)} table(s) whose printed numbering was repaired "
              f"from row order:")
        for line in DISCREPANCIES:
            print(f"  {line}")
    if UNMAPPED:
        print(f"\n{len(UNMAPPED)} club names not in data/aliases_he.json "
              f"(most frequent first); add the ones you need:")
        for name, n in sorted(UNMAPPED.items(), key=lambda kv: -kv[1])[:40]:
            print(f'  {n:3}x  "{name}": "",')


if __name__ == "__main__":
    main()
