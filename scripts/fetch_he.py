#!/usr/bin/env python3
"""Fetch Hebrew Wikipedia season articles for the tiers RSSSF does not cover.

RSSSF gives us the top flight from 1949/50 and the second tier only from
2008/09.  Hebrew Wikipedia has an article for every second-tier season back to
1955/56, which is what fills the gaps for clubs that dropped out of the top
flight.

The season navbox templates are the index: they list the exact article title for
every season slot and wrap the ones that were never played in <s>...</s>.  That
is both the article list and the authority on which seasons exist, so it is
parsed rather than guessed at.  Output:

  data/seasons_index.json   season label -> {tier, league, title, played}
  data/raw/he/*.wiki        cached article wikitext
"""

import json
import re
import subprocess
import time
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "he"
INDEX = ROOT / "data" / "seasons_index.json"

# Navbox template -> the tier its seasons sit at.
NAVBOXES = {
    "תבנית:עונות בליגה עליונה בכדורגל": 1,
    "תבנית:עונות בליגת משנה בכדורגל": 2,
}

# The navbox groups 1949/50's second tier with the district leagues, but that
# season's competition had its own name and its own entry in the era table.
SEASON_LEAGUE = {"1949/1950#2": "Liga Meuhedet"}

# Navbox group heading -> the league name used in data/structure.json.
LEAGUE_OF_GROUP = {
    "ליגת ארץ ישראל": "Eretz Israel League",
    "ליגה א' והליגה הלאומית": None,   # top flight; the era table resolves the name
    "ליגת העל": "Ligat ha'Al",
    "ליגות מחוזיות": "Liga Bet",
    "ליגה א'": "Liga Alef",
    "הליגה הארצית": "Liga Artzit",
    "הליגה הלאומית": "Liga Leumit",
}

# The most recent completed season.  2026/27 is under way and is left out: a
# chart must not show a club's current, partial position as a final one.
LATEST_COMPLETE = 2025

# RSSSF covers the top flight through 2024/25 and the second tier from 2008/09,
# so only the seasons outside those ranges are worth downloading here.
RSSSF_TOP_FLIGHT_UNTIL = 2024
RSSSF_SECOND_TIER_FROM = 2008

# The second tier is taken all the way back.  Before 1955 it was a set of
# district leagues - five regional groups of 45 clubs in 1949/50 - so those
# positions are ranks within a district rather than national ones, which the
# division column and the chart's dashed line already express.  The tier itself
# comes from the era table via the league name, not from the navbox's grouping,
# so the navbox filing 1953/54 and 1954/55 under the district leagues does not
# matter.  Excluding these was what left Hapoel Jerusalem's 1930s and 1940s
# blank: they had been relegated to Liga Bet and spent the 1940s moving between
# the two levels.
SECOND_TIER_FROM = 1930

# The Mandate-era top flight, which only Hebrew Wikipedia covers district by
# district.
MANDATE_UNTIL = 1948


def wanted(meta: dict) -> bool:
    if not meta["played"] or not meta["title"] or meta["start"] > LATEST_COMPLETE:
        return False
    if meta["tier"] == 1:
        # The Mandate era too: English Wikipedia documents the Tel Aviv,
        # Samaria and Southern districts of those regional seasons but not the
        # Haifa one, which is where Maccabi Haifa and Hapoel Haifa played.
        return meta["start"] <= MANDATE_UNTIL or meta["start"] > RSSSF_TOP_FLIGHT_UNTIL
    if meta["tier"] == 2:
        return meta["start"] >= SECOND_TIER_FROM and (
            meta["start"] < RSSSF_SECOND_TIER_FROM
            or meta["start"] > RSSSF_TOP_FLIGHT_UNTIL)
    return False


def api(**params) -> dict:
    url = "https://he.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
        {**params, "format": "json"}
    )
    out = subprocess.run(
        ["curl", "-sL", "-A", "israeli-league-charts/1.0 (research)", url],
        capture_output=True, text=True, check=True,
    ).stdout
    return json.loads(out)


def pages(titles: list[str]) -> dict[str, str | None]:
    """Wikitext for up to 50 titles at a time; None where the page is missing."""
    got: dict[str, str | None] = {}
    for i in range(0, len(titles), 50):
        batch = titles[i:i + 50]
        r = api(action="query", titles="|".join(batch), prop="revisions",
                rvprop="content", rvslots="main")
        for p in r["query"]["pages"].values():
            got[p["title"]] = (
                None if "missing" in p else p["revisions"][0]["slots"]["main"]["*"]
            )
        # Redirects and title normalisation mean a requested title may come back
        # under a different key; map those back so lookups by request work.
        for kind in ("normalized", "redirects"):
            for m in r["query"].get(kind, []):
                got[m["from"]] = got.get(m["to"])
        time.sleep(0.3)
    return got


def season_start(label: str) -> int:
    """1955/1956 -> 1955, 1966/1968 -> 1966, 1937 -> 1937."""
    return int(label.split("/")[0])


SEASON_LABEL = re.compile(r"\d{4}(?:/\d{4})?")


def template_params(wiki: str) -> dict[str, str]:
    """Navbox parameters. Values run over several lines, and wikilinks contain
    their own '|', so parameters are split on a '|' at the start of a line."""
    params: dict[str, str] = {}
    for chunk in re.split(r"\n(?=\|)", wiki):
        m = re.match(r"\|([^=|\[{]+?)\s*=\s*(.*)", chunk, re.S)
        if m:
            params[m.group(1).strip()] = m.group(2)
    return params


def parse_item(item: str) -> tuple[str, str | None] | None:
    """(season label, article title) for one navbox entry, or None.

    Two forms appear: a plain wikilink, and {{בספורט|<league>|<y1>|<y2>}}, which
    expands to "עונת y1/y2 ב<league>".  A season that was never played often has
    no article at all, just a struck-through bare label.
    """
    if m := re.search(r"\{\{בספורט\|([^|}]+)\|(\d{4})(?:\|(\d{4}))?", item):
        league, y1, y2 = m.group(1).strip(), m.group(2), m.group(3)
        label = f"{y1}/{y2}" if y2 else y1
        return label, f"עונת {label} ב{league}"
    if m := re.search(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", item):
        title, label = m.group(1), (m.group(2) or m.group(1))
        label = re.sub(r"</?s>|'''", "", label).strip()
        return (label, title) if SEASON_LABEL.fullmatch(label) else None
    bare = re.sub(r"</?s>|'''|\s", "", item)
    return (bare, None) if SEASON_LABEL.fullmatch(bare) else None


def parse_navbox(wiki: str, tier: int) -> dict[str, dict]:
    """Season label -> {tier, league, title, played} from one navbox template."""
    params = template_params(wiki)
    out: dict[str, dict] = {}
    for key, heading in params.items():
        if not (n := re.fullmatch(r"קבוצה(\d+)", key)):
            continue
        # Headings carry bold markup and sometimes a wikilink.
        heading = re.sub(r"'''", "", heading)
        if link := re.search(r"\[\[[^\]|]+\|([^\]]+)\]\]|\[\[([^\]]+)\]\]", heading):
            heading = link.group(1) or link.group(2)
        league = LEAGUE_OF_GROUP.get(heading.strip())
        for item in params.get(f"רשימה{n.group(1)}", "").split("•"):
            if parsed := parse_item(item):
                label, title = parsed
                out[label] = {"tier": tier, "league": league, "title": title,
                              "played": "<s>" not in item,
                              "start": season_start(label)}
    return out


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    navboxes = pages(list(NAVBOXES))
    index: dict[str, dict] = {}
    for name, tier in NAVBOXES.items():
        wiki = navboxes.get(name)
        if not wiki:
            raise SystemExit(f"navbox not found: {name}")
        for label, meta in parse_navbox(wiki, tier).items():
            key = f"{label}#{tier}"
            if key in SEASON_LEAGUE:
                meta = {**meta, "league": SEASON_LEAGUE[key]}
            index.setdefault(key, meta)

    INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n")
    played = sum(1 for m in index.values() if m["played"])
    print(f"{len(index)} season slots indexed ({played} played) -> {INDEX}")

    todo = {
        m["title"]: key for key, m in index.items()
        if wanted(m) and not (RAW / f"{key.replace('/', '-')}.wiki").exists()
    }
    print(f"downloading {len(todo)} articles")
    if todo:
        for title, wiki in pages(list(todo)).items():
            key = todo.get(title)
            if key and wiki:
                (RAW / f"{key.replace('/', '-')}.wiki").write_text(wiki)
    have = len(list(RAW.glob("*.wiki")))
    print(f"{have} article(s) cached in {RAW}")


if __name__ == "__main__":
    main()
