#!/usr/bin/env python3
"""Fetch English Wikipedia season articles for the tiers no other source covers.

RSSSF gives the top flight and, from 2008/09, the second tier.  Hebrew Wikipedia
gives the second tier back to 1955/56.  Neither has the third or fourth tier in
any systematic way: Hebrew Wikipedia has exactly one Liga Alef article from the
years it spent at tier three, and the RSSSF season pages carry Liga Artzit for
2008/09 and Liga Alef for 2009/10 and nothing else.

English Wikipedia does have them, and the Mandate-era top flight too:

  Palestine League   English Wikipedia's article title for the pre-1949 top
                     flight, which this project calls the Eretz Israel League
  Liga Artzit        1976/77-2008/09, its whole existence
  Liga Alef          1951/52 onward
  Liga Bet           1941 onward
  Liga Gimel         scattered

Titles are discovered through the search API rather than constructed, because
the season naming is not uniform (1966-68 is one season, and the early years
are single calendar years).

  data/raw/en/*.wiki
"""

import json
import re
import subprocess
import time
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "en"

# English Wikipedia ARTICLE TITLES to search for -> the league name used
# everywhere else in this project. Only the left-hand side is that site's
# wording; the pre-1949 top flight is the Eretz Israel League.
LEAGUES = {
    "Palestine League": "Eretz Israel League",
    "Liga Artzit": "Liga Artzit",
    "Liga Alef": "Liga Alef",
    "Liga Bet": "Liga Bet",
    "Liga Gimel": "Liga Gimel",
}
TITLE = re.compile(r"^(\d{4})[–-](\d{2,4})\s+(.+?)\s*$")
SINGLE_YEAR = re.compile(r"^(\d{4})\s+(.+?)\s*$")


# Wikimedia asks for a descriptive User-Agent with a way to make contact, and
# rate-limits anonymous bursts. Both matter: without the throttle and backoff
# below this script gets a plain-text "too many requests" where it expects JSON.
UA = ("israeli-league-charts/1.0 (https://github.com/kadishay/israeli-league-charts; "
      "yotam.kadishay@gmail.com)")
THROTTLE = 1.0


def api(host: str, **params) -> dict:
    url = f"https://{host}/w/api.php?" + urllib.parse.urlencode(
        {**params, "format": "json"})
    for attempt in range(6):
        time.sleep(THROTTLE)
        out = subprocess.run(["curl", "-sL", "-A", UA, url],
                             capture_output=True, text=True, check=True).stdout
        try:
            return json.loads(out)
        except json.JSONDecodeError:
            wait = 5 * 2 ** attempt
            print(f"  api not ready ({out.strip().splitlines()[0][:60]!r}); "
                  f"waiting {wait}s")
            time.sleep(wait)
    raise SystemExit("giving up on the Wikipedia API; try again later")


def discover() -> dict[str, dict]:
    """Article title -> {league, start} for every season article we can find."""
    found: dict[str, dict] = {}
    for league, canonical in LEAGUES.items():
        offset = None
        while True:
            params = dict(action="query", list="search",
                          srsearch=f'intitle:"{league}"', srlimit="50", srnamespace=0)
            if offset:
                params["sroffset"] = offset
            r = api("en.wikipedia.org", **params)
            for hit in r["query"]["search"]:
                title = hit["title"]
                if m := TITLE.match(title):
                    if m.group(3) != league:
                        continue
                    found[title] = {"league": canonical, "start": int(m.group(1))}
                elif m := SINGLE_YEAR.match(title):
                    if m.group(2) == league:
                        found[title] = {"league": canonical, "start": int(m.group(1))}
            offset = r.get("continue", {}).get("sroffset")
            if not offset:
                break
    return found


def fetch(titles: list[str]) -> dict[str, str | None]:
    got: dict[str, str | None] = {}
    for i in range(0, len(titles), 40):
        batch = titles[i:i + 40]
        r = api("en.wikipedia.org", action="query", titles="|".join(batch),
                prop="revisions", rvprop="content", rvslots="main")
        for p in r["query"]["pages"].values():
            got[p["title"]] = (None if "missing" in p
                               else p["revisions"][0]["slots"]["main"]["*"])
        for kind in ("normalized", "redirects"):
            for m in r["query"].get(kind, []):
                got[m["from"]] = got.get(m["to"])
        print(f"  {min(i + 40, len(titles))}/{len(titles)}")
    return got


def safe(title: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", title).strip("-")


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    # The search API returns a varying subset between runs, so a fresh discovery
    # can come back with fewer titles than last time. Merging into the existing
    # index instead of replacing it keeps the corpus stable and only growing -
    # otherwise articles silently drop out of the dataset while their cached
    # files sit there orphaned, which cost 165 rows once.
    path = ROOT / "data" / "en_index.json"
    index = json.loads(path.read_text()) if path.exists() else {}
    before = len(index)
    found = discover()
    index.update(found)
    path.write_text(
        json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(f"index: {before} known, {len(found)} returned by search, "
          f"{len(index)} after merge")

    counts: dict[str, int] = {}
    for meta in index.values():
        counts[meta["league"]] = counts.get(meta["league"], 0) + 1
    print("discovered:", ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))

    todo = [t for t in index if not (RAW / f"{safe(t)}.wiki").exists()]
    print(f"downloading {len(todo)}")
    for title, wiki in fetch(todo).items():
        if wiki and title in index:
            (RAW / f"{safe(title)}.wiki").write_text(wiki)
    print(f"{len(list(RAW.glob('*.wiki')))} article(s) cached in {RAW}")


if __name__ == "__main__":
    main()
