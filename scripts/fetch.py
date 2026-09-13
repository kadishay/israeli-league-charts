#!/usr/bin/env python3
"""Download the raw RSSSF source pages for Israeli league final tables.

Two shapes of source:
  israhist.html          top flight, 1949/50 - 2007/08, all in one page
  isra09 / isra2010..    one page per season, 2008/09 - 2024/25, tiers 1 and 2

Pages are cached in data/raw/ and only re-fetched when missing.
"""

import time
import urllib.request
from pathlib import Path

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"
BASE = "https://www.rsssf.org/tablesi/"
UA = "Mozilla/5.0 (compatible; israeli-league-charts/1.0)"

# RSSSF's per-season filenames are not consistent: 2008/09 is "isra09",
# then 2009/10 onwards is "isra" + the calendar year the season ends.
SEASON_PAGES = {2008: "isra09", **{y: f"isra{y + 1}" for y in range(2009, 2025)}}


def get(name: str, dest: Path) -> bool:
    if dest.exists() and dest.stat().st_size > 2000:
        return False
    req = urllib.request.Request(BASE + name + ".html", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        dest.write_bytes(r.read())
    time.sleep(1)  # be polite to a volunteer-run archive
    return True


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    fetched = 0
    fetched += get("israhist", RAW / "israhist.html")
    for start_year, name in SEASON_PAGES.items():
        fetched += get(name, RAW / f"season-{start_year}.html")
    print(f"raw pages in {RAW}: {len(list(RAW.glob('*.html')))} ({fetched} newly downloaded)")


if __name__ == "__main__":
    main()
