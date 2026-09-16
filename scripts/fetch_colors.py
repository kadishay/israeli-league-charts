#!/usr/bin/env python3
"""Read each charted club's kit colour off Hebrew Wikipedia into data/club_colors.json.

The chart draws one line per club and that line now carries the club's own
colour, so the colours had to come from somewhere citable rather than from
memory.  Hebrew Wikipedia's football-club infobox already holds them as kit
parameters - `leftarm1`, `body1`, `socks1` - which is a stated fact on a sourced
page rather than a recollection of what a shirt looks like.

Picking one colour out of a kit needs a rule, because a kit is two or three
colours and the chart has room for one:

* Prefer the first parameter that is neither near-white nor near-black. A club
  playing in white with green trim is identified by the green, and a line drawn
  in white would be invisible on a light chart.
* Fall back to black only when every kit parameter is white or black, which is
  how the genuinely monochrome clubs come out.

The colour written here is the club's own, unmodified.  render.py is what
darkens it if it cannot hold its own against the band behind it - see
`legible()` there - so this file stays a record of what the source said.
"""

import json
import re
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = DATA / "club_colors.json"

UA = ("israeli-league-charts/1.0 (https://github.com/kadishay/israeli-league-charts; "
      "yotam.kadishay@gmail.com)")
THROTTLE = 1.0

# In preference order. leftarm/body/rightarm are the shirt; socks often carry the
# identifying colour when the shirt is white. The away kit comes last because a
# handful of clubs - Ironi Tiberias, Maccabi Jaffa - record an all-white home
# kit whose colour lives in a pattern file rather than a hex, leaving the away
# strip as the only stated colour on the page.
HOME_PARAMS = ["leftarm1", "body1", "rightarm1", "socks1", "shorts1"]
AWAY_PARAMS = ["leftarm2", "body2", "rightarm2", "socks2", "shorts2"]
KIT_PARAMS = HOME_PARAMS + AWAY_PARAMS
HEX = re.compile(r"^#?([0-9A-Fa-f]{6})$")


def api(**params) -> dict:
    url = "https://he.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
        {**params, "format": "json"})
    for attempt in range(6):
        time.sleep(THROTTLE)
        out = subprocess.run(["curl", "-sL", "-A", UA, url],
                             capture_output=True, text=True, check=True).stdout
        try:
            return json.loads(out)
        except json.JSONDecodeError:
            time.sleep(5 * 2 ** attempt)
    raise SystemExit("giving up on the Wikipedia API; try again later")


def wikitext(title: str) -> str | None:
    r = api(action="query", prop="revisions", rvprop="content", rvslots="main",
            titles=title, redirects=1)
    page = list(r["query"]["pages"].values())[0]
    if "missing" in page:
        return None
    return page["revisions"][0]["slots"]["main"]["*"]


# The lightest tier band, and so the worst surface a line has to sit on.
# Kept in step with THEME["light"]["band"][0] in render.py.
BAND1 = "E9F0F2"


def contrast(a: str, b: str) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def luminance(hex6: str) -> float:
    """Relative luminance, WCAG definition. Used only to reject white and black."""
    def channel(v: int) -> float:
        c = v / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (int(hex6[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def hsl(hex6: str) -> tuple[float, float, float]:
    r, g, b = (int(hex6[i:i + 2], 16) / 255 for i in (0, 2, 4))
    hi, lo = max(r, g, b), min(r, g, b)
    light = (hi + lo) / 2
    if hi == lo:
        return 0.0, 0.0, light
    d = hi - lo
    sat = d / (2 - hi - lo) if light > 0.5 else d / (hi + lo)
    if hi == r:
        hue = ((g - b) / d) % 6
    elif hi == g:
        hue = (b - r) / d + 2
    else:
        hue = (r - g) / d + 4
    return hue * 60, sat, light


def identifying(hex6: str) -> bool:
    """Does this kit colour identify the club, or is it just white or black?

    Saturation is the test, not lightness. Maccabi Tel Aviv's yellow is lighter
    than most greys and is unmistakably theirs; white is not, however dark the
    rest of the kit. Judging on lightness alone threw away every yellow club and
    kept the whites - the exact inversion of what the chart needs.
    """
    _, sat, light = hsl(hex6)
    if sat < 0.15:                 # achromatic: white, black, grey
        return False
    return 0.06 < light < 0.94     # a saturated colour, not at either extreme


def read_kit(text: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for param in KIT_PARAMS:
        m = re.search(rf"^\s*\|\s*{param}\s*=\s*(\S+)\s*$", text, re.M)
        if m and (h := HEX.match(m.group(1))):
            found[param] = h.group(1).upper()
    return found


def pick(found: dict[str, str]) -> tuple[str, str] | None:
    """(hex, which parameter it came from), or None if the infobox has no kit."""
    for param in KIT_PARAMS:
        h = found.get(param)
        if h and identifying(h):
            return h, param
    if found:
        # A genuinely monochrome kit. Take the darkest of them: on a light
        # chart black is a line and white is nothing at all.
        param = min(found, key=lambda p: luminance(found[p]))
        return found[param], f"{param} (monochrome kit)"
    return None


def pick_secondary(found: dict[str, str], primary: str) -> tuple[str, str] | None:
    """The club's other colour, when it has one that can outline the first.

    Beitar Jerusalem and Maccabi Netanya both play in a yellow shirt with black
    shorts, so their charts are a yellow line with a black edge - the club's own
    pairing rather than one this project invented.

    The home kit is asked first and the away kit second, because a club whose
    home strip is a single colour still has a second one: Maccabi Tel Aviv play
    in yellow throughout and change into blue, and yellow-and-blue is the club.
    Nothing is forced - a club that changes into plain white has no second colour
    by this test, since white cannot outline anything on a pale chart, and
    3:1 against the lightest band is the floor for the edge to do its job.
    """
    for param in HOME_PARAMS + AWAY_PARAMS:
        h = found.get(param)
        if h and h != primary and contrast(h, BAND1) >= 3.0:
            return h, param
    return None


def main() -> None:
    clubs = json.loads((DATA / "club_colors.json").read_text())["colors"] \
        if OUT.exists() and "--refresh" not in sys.argv else {}
    names: dict[str, str] = {}
    for he, canonical in json.loads((DATA / "aliases_he.json").read_text()).items():
        if not he.startswith("_") and canonical:
            names.setdefault(canonical, he)

    wanted = sys.argv[1:] or sorted(names)
    wanted = [c for c in wanted if not c.startswith("--")]

    colors: dict[str, dict] = {}
    missing = []
    for club in wanted:
        title = names.get(club)
        if not title:
            missing.append(f"{club} (no Hebrew article name in aliases_he.json)")
            continue
        # aliases_he.json holds whatever spelling the season tables link to, and
        # for the older clubs that is the sports association - מכבי תל אביב runs
        # a basketball club too, and its article has no kit. The football club
        # lives at the "(כדורגל)" title. Try that first and fall back, rather
        # than the other way round: the association page can carry a kit for a
        # different sport.
        got, used, kit = None, None, {}
        for candidate in (f"{title} (כדורגל)", title):
            text = wikitext(candidate)
            if text:
                kit = read_kit(text)
                if got := pick(kit):
                    used = candidate
                    break
        if got is None:
            missing.append(f"{club} (no kit parameters in '{title}')")
            continue
        title = used
        hexval, param = got
        entry = {"color": f"#{hexval}", "from": param, "article": title}
        if second := pick_secondary(kit, hexval):
            entry["secondary"] = f"#{second[0]}"
            entry["secondary_from"] = second[1]
        colors[club] = entry
        print(f"  {club:32} #{hexval}  ({param})"
              + (f"   + #{second[0]} ({second[1]})" if second else ""))

    merged = {**clubs, **colors}
    OUT.write_text(json.dumps({
        "_comment": [
            "Canonical club name -> the club's own colour, read off the kit",
            "parameters of its Hebrew Wikipedia infobox by scripts/fetch_colors.py.",
            "'from' records which kit parameter it came from, 'article' the page.",
            "",
            "'color' is drawn as-is: Maccabi Tel Aviv play in #FFFF00 and the chart",
            "says #FFFF00. Legibility comes from an edge drawn under the line, which",
            "is 'secondary' where the club's home kit has a second colour - Beitar",
            "Jerusalem's black shorts under its yellow shirt - and otherwise the same",
            "colour taken down to 4.5:1 against the lightest band by render.py.",
            "",
            "Clubs absent here fall back to the chart's default accent.",
        ],
        "colors": dict(sorted(merged.items())),
    }, ensure_ascii=False, indent=1) + "\n")
    print(f"\n{len(merged)} clubs -> {OUT}")
    if missing:
        print(f"{len(missing)} without a colour (they fall back to the default):")
        print("  " + "\n  ".join(missing))


if __name__ == "__main__":
    main()
