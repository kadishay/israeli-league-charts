#!/usr/bin/env python3
"""Render a league-performance chart per club as a self-contained SVG.

One column per season, one row per league position, with the tier bands drawn
behind so a club's depth in the pyramid is read off the background.  The
equivalent charts on Wikipedia are authored by hand; this builds them from
data/seasons.csv and data/structure.json.

Bands are labelled by tier *number*, never by league name, because the names
move: Liga Alef has been the first, second, third and fourth tier at different
times, so "Liga Alef" on a 1960 column and on a 2015 column mean different
depths.

Four things the data forces, which are what most of this file is about:

* The x-axis is a list of season *names*, not a year range.  There is no
  1936/37 and no 1967/68, 1937-1940 are single-year seasons, and the 1940
  season was played while 1940/1941 was not - so the start year is not even a
  unique key.  Columns come from data/seasons_index.json in order.
* Tier bands move.  The top flight has held 10 to 18 clubs, so the boundary
  between tier one and tier two steps up and down across the chart.
* Eleven season slots were never played.  Those columns are hatched and the
  line breaks across them - never interpolated.
* Below tier two nearly everything is regional, so the position is a rank
  within a district and not a national one.  The division is kept in the data
  and noted in docs/DECISIONS.md, but it is not drawn differently: the chart is
  read for the tier, and a dashed line qualified a within-band rank that nobody
  reads at this scale.

The line is a smooth curve through one point per season rather than a step.
That is a deliberate softening of the truth - a club's position does not drift
between one May and the next August - so the interpolation is monotone cubic,
which never bows past a position the club did not finish in.

Colour: the tier bands are a sequential ramp (one hue, light to dark with
depth), deliberately desaturated so that the one saturated thing on the chart is
the club.  Each club's line is its own kit colour exactly as data/club_colors.json
gives it - Maccabi Tel Aviv play in #FFFF00 and the chart says #FFFF00 - and
legibility comes from a casing drawn underneath rather than from altering the
colour on top.  The casing is the club's second kit colour where it has one, and
otherwise its own colour taken down to 4.5:1 against the lightest band.  The
champion marker keeps its own fixed amber so that it never becomes a second club
colour.  These charts commit to one light palette rather than following the
viewer's theme, so they read the same wherever they are embedded.

The chart bands tiers one to four and stops.  A fifth- or sixth-tier season has
no row to sit on and is marked like any other season with no position on the
chart; the rank is in seasons.csv, where below tier four it is a place inside a
regional group and not comparable to anything above it.  Everything below the
last band is bare page, which also covers the seasons when the pyramid itself was
shallower - it was two tiers deep in 1935.

The output is deliberately plain SVG: literal colours, no CSS custom properties,
and a font stack that ends in faces Wikimedia installs.  Wikimedia Commons
rasterises with librsvg at an SVG 1.0 / CSS 2 level, where a var() reference
resolves to nothing and the whole chart comes out colourless.
"""

import argparse
import csv
import json
import re
import urllib.parse
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "out"

FIRST_SEASON = 1929          # the first season slot the sources record
LAST_SEASON = 2025           # most recent completed season
TIERS_SHOWN = 4              # tiers with a band of their own; deeper ones share the floor

COL = 13                     # width of one season column
ROW = 7                      # height of one league position
PAD_R, PAD_T, PAD_B = 20, 76, 78
BOTTOM_BAND = 2              # rows below the last band, for the "no position" mark
CORNER = 3.5                 # radius of the rounded step corners
NOMINAL = {1: 14, 2: 16, 3: 16, 4: 16}   # band size where a season has no data

THEME = {
    "light": {
        "surface": "#FCFCFB", "ink": "#1A1D1F", "ink2": "#565F63", "ink3": "#868F93",
        # One per drawn tier, light to dark with depth. Four, because the chart
        # bands four tiers and everything below them is bare page.
        "band": ["#E9F0F2", "#DBE5E8", "#CBD8DC", "#B9C9CF"],
        "rule": "#C9CFD1", "accent": "#007C99", "accent_casing": "#004A5C",
        "champion": "#A06A0A", "hatch": "#A9B2B6",
    },
}

STRINGS = {
    "en": {
        "dir": "ltr", "pad_l": 104,
        "tier": "TIER {n}", "tier_deep": "TIER {n}+",
        "kicker": "LEAGUE POSITION BY SEASON",
        "in_top": "{n} of {total} seasons in the top flight",
        "never_top": "{n} seasons recorded · highest level reached: tier {tier}",
        "never_top_one": "1 season recorded · highest level reached: tier {tier}",
        "titles": "{n} championship", "titles_plural": "{n} championships",
        "best": "best finish {pos}",
        "legend_line": "Final league position",
        "legend_as": "as {name}",
        "legend_champ": "Champions",
        "legend_stopped": "League abandoned mid-season",
        "legend_uncovered": "No position recorded",
        "legend_notplayed": "Season not played",
        "pub_en": "English:", "pub_he": "Hebrew:",
        "pub_in_article": "in the article",
        "pub_file": "file",
        "pub_uploaded": "on Commons",
        "pub_not_placed": "not yet in the article",
        "pub_lead": ("Where these charts are published. A chart can be on Commons "
                     "without being in any article — every Hebrew chart is in that "
                     "state, because Hebrew Wikipedia's edit filter 109 requires 100 "
                     "edits and the requests are sitting on the article talk pages."),
        "gallery_title": "Israeli league performance, {first}–{last}",
        "gallery_lead": ("{clubs} clubs across {seasons} season columns. Position is "
                         "counted down the whole pyramid, so each tier continues the "
                         "one above — the band boundaries step because the top flight "
                         "has held anywhere between 10 and 18 clubs."),
        "how": [
            ("One column per season, not per year",
             "There is no 1967/68 — 1966/68 was a single two-year championship. "
             "Hatched columns are seasons never played; the line breaks rather "
             "than guessing across them."),
            ("Dotted band at the bottom",
             "The club was playing but no final position is recorded, usually a "
             "Mandate-era district that no article tabulates. Blank means "
             "the club did not exist or fielded no senior side."),
            ("The chart stops at tier four",
             "Below it the line runs along a thin strip: the club was in tier "
             "five or deeper, which the chart records as a depth rather than a "
             "rank. Where the bands themselves stop short — the pyramid was two "
             "levels deep in 1935 — the rows below them are left blank, because "
             "there was no such tier to be in."),
            ("Below tier two, a position is a regional rank",
             "The lower divisions run in regional groups, so the height within "
             "those bands is a rank inside a group rather than a national one. "
             "The tier is what the chart is for; read the depth, not the exact "
             "position."),
        ],
    },
    "he": {
        "dir": "rtl", "pad_l": 96,
        "tier": "דרג {n}", "tier_deep": "דרג {n}+",
        "kicker": "מיקום בליגה לפי עונה",
        "in_top": "{n} עונות מתוך {total} בליגה הבכירה",
        "never_top": "{n} עונות רשומות · הדרג הגבוה ביותר: דרג {tier}",
        "never_top_one": "עונה אחת רשומה · הדרג הגבוה ביותר: דרג {tier}",
        "titles": "אליפות אחת", "titles_plural": "{n} אליפויות",
        "best": "המקום הטוב ביותר: {pos}",
        "legend_line": "מיקום סופי בליגה",
        "legend_as": "בתור {name}",
        "legend_champ": "אליפות",
        "legend_stopped": "הליגה הופסקה באמצע העונה",
        "legend_uncovered": "לא נרשם מיקום",
        "legend_notplayed": "העונה לא התקיימה",
        "pub_en": "אנגלית:", "pub_he": "עברית:",
        "pub_in_article": "בערך",
        "pub_file": "הקובץ",
        "pub_uploaded": "בוויקישיתוף",
        "pub_not_placed": "טרם נוסף לערך",
        "pub_lead": ("היכן הגרפים פורסמו. קובץ יכול להיות בוויקישיתוף בלי להופיע "
                     "בשום ערך — זה מצבם של כל הגרפים בעברית, מפני שמסנן 109 בוויקיפדיה "
                     "העברית דורש 100 עריכות, והבקשות מונחות בדפי השיחה של הערכים."),
        "gallery_title": "מיקומי קבוצות בליגות בישראל, {first}–{last}",
        "gallery_lead": ("{clubs} קבוצות על פני {seasons} עונות. המיקום נמדד לאורך כל "
                         "הפירמידה, כך שכל דרג ממשיך את זה שמעליו — גבולות הדרגים "
                         "משתנים מפני שבליגה הבכירה שיחקו בין 10 ל-18 קבוצות."),
        "how": [
            ("עמודה אחת לכל עונה, לא לכל שנה",
             "אין עונת 1967/1968 — עונת 1966/1968 הייתה אליפות אחת על פני שתי "
             "שנים. עמודות מקווקוות הן עונות שלא התקיימו, והקו נקטע ולא מנחש."),
            ("פס מנוקד בתחתית",
             "הקבוצה שיחקה אך לא נרשם מיקום סופי — בדרך כלל בית מחוזי בתקופת "
             "המנדט שלא תועד. רקע ריק פירושו שהקבוצה לא התקיימה או "
             "לא העמידה קבוצת בוגרים."),
            ("הגרף נעצר בדרג הרביעי",
             "מתחתיו הקו רץ על פס דק: הקבוצה שיחקה בדרג חמישי או נמוך יותר, "
             "והגרף מציין עומק ולא מיקום. היכן שהפסים עצמם נעצרים מוקדם — "
             "ב-1935 הפירמידה הייתה בת שני דרגים — השורות שמתחתיהם ריקות, "
             "מפני שלא היה דרג כזה."),
            ("מתחת לדרג השני — מיקום אזורי",
             "הליגות הנמוכות מחולקות לבתים אזוריים, ולכן הגובה בתוך אותם דרגים "
             "הוא דירוג בתוך בית ולא ארצי. הדרג הוא מה שהגרף מראה — קראו את "
             "העומק, לא את המיקום המדויק."),
        ],
    },
}


def short_label(label: str) -> str:
    """1929/1930 -> 29/30, and a single-year season stays as it is."""
    if "/" not in label:
        return label
    start, end = label.split("/")
    return f"{start[-2:]}/{end[-2:]}"


def esc(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def text_el(x, y, content: str, *, cls: str, size: float, lang: str,
            align: str = "left", weight: str = "", extra: str = "") -> str:
    """A <text> element whose visual alignment survives translation.

    Hebrew needs direction="rtl" so that a mixed string like "40 עונות מתוך 86"
    orders correctly, but that also swaps what text-anchor start/end mean - the
    logical start of an RTL run is its right-hand edge.  So the anchor is
    flipped for Hebrew to keep the requested visual alignment.
    """
    anchor = {"left": "start", "right": "end", "middle": "middle"}[align]
    direction = ""
    if lang == "he":
        anchor = {"start": "end", "end": "start", "middle": "middle"}[anchor]
        direction = ' direction="rtl"'
    bits = [f'class="{cls}"', f'x="{x}"', f'y="{y}"',
            f'text-anchor="{anchor}"', f'font-size="{size}"']
    if weight:
        bits.append(f'font-weight="{weight}"')
    return f'<text {" ".join(bits)}{direction}{extra}>{esc(content)}</text>'


def load():
    structure = json.loads((DATA / "structure.json").read_text())
    index = json.loads((DATA / "seasons_index.json").read_text())

    def era_of(year: int) -> dict | None:
        for era in structure["eras"]:
            if era["from"] <= year and (era["to"] is None or year <= era["to"]):
                return era
        return None

    def tier_of(year: int, league: str) -> int | None:
        era = era_of(year)
        if not era or league not in era["tiers"]:
            return None
        return era["tiers"].index(league) + 1

    # Season columns, in order, from the Hebrew Wikipedia navbox index. Every
    # slot is a column, including the ones never played - they are the gaps.
    seasons = sorted(
        ({"label": k.split("#")[0], "start": v["start"], "played": v["played"]}
         for k, v in index.items()
         if v["tier"] == 1 and FIRST_SEASON <= v["start"] <= LAST_SEASON),
        key=lambda s: (s["start"], s["label"]),
    )

    rows = list(csv.DictReader((DATA / "seasons.csv").open()))
    for r in rows:
        r["start"], r["position"] = int(r["season_start"]), int(r["position"])
        r["tier"] = tier_of(r["start"], r["league"])

    # Band size per season per tier. For a regional tier that is one division's
    # worth, because a position there is a rank within a district.
    size: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    for r in rows:
        if r["tier"]:
            by = size[r["season"]]
            by[r["tier"]] = max(by[r["tier"]], r["position"])
    # Only draw bands for tiers that existed that season: in 1935 the pyramid
    # had two levels, and four bands would imply a depth that did not exist.
    for s in seasons:
        got = size.get(s["label"], {})
        era = era_of(s["start"])
        s["era_depth"] = len(era["tiers"]) if era else TIERS_SHOWN
        depth = min(TIERS_SHOWN, s["era_depth"])
        s["bands"] = [got.get(t) or NOMINAL[t] for t in range(1, depth + 1)]

    # A club can have more than one row for a season: a regional season may
    # list it both in a district table and in the national play-off that
    # decided the title, and two sources may name the same competition
    # differently. Pick the shallowest tier, and prefer a national ranking over
    # a district one - otherwise an arbitrary row wins and titles go missing.
    def better(a: dict, b: dict) -> dict:
        if a["tier"] != b["tier"]:
            return a if a["tier"] < b["tier"] else b
        if bool(a["division"]) != bool(b["division"]):
            return a if not a["division"] else b
        return a if a["position"] <= b["position"] else b

    by_club: dict[str, dict[str, dict]] = defaultdict(dict)
    for r in rows:
        if r["tier"]:
            seen = by_club[r["club"]].get(r["season"])
            by_club[r["club"]][r["season"]] = better(seen, r) if seen else r
    return seasons, by_club


def smooth_path(run: list[tuple[int, int]], x, y) -> str:
    """A smooth curve through one point per season, at the column centre.

    Monotone cubic interpolation (Fritsch-Carlson), not a cardinal spline: a
    cardinal spline overshoots past a local extreme, which here would draw a
    club finishing above 1st or below last in a season where it did neither.
    Monotone tangents stay within the two points they join, so the curve is
    smooth but never shows a position that did not happen.
    """
    pts = [(x(i) + COL / 2, y(rank)) for i, rank in run]
    if len(pts) == 1:
        cx, cy = pts[0]
        return f"M{cx - COL / 2:.1f} {cy:.1f}H{cx + COL / 2:.1f}"
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    h = [xs[i + 1] - xs[i] for i in range(len(xs) - 1)]
    d = [(ys[i + 1] - ys[i]) / h[i] for i in range(len(h))]

    m = [d[0]]
    for i in range(1, len(d)):
        if d[i - 1] * d[i] <= 0:
            m.append(0.0)             # a turning point: flatten, never overshoot
        else:
            limit = 3 * min(abs(d[i - 1]), abs(d[i]))
            m.append(max(-limit, min(limit, (d[i - 1] + d[i]) / 2)))
    m.append(d[-1])

    parts = [f"M{xs[0]:.1f} {ys[0]:.1f}"]
    for i in range(len(h)):
        parts.append(
            f"C{xs[i] + h[i] / 3:.1f} {ys[i] + m[i] * h[i] / 3:.1f} "
            f"{xs[i + 1] - h[i] / 3:.1f} {ys[i + 1] - m[i + 1] * h[i] / 3:.1f} "
            f"{xs[i + 1]:.1f} {ys[i + 1]:.1f}")
    return " ".join(parts)


def rank_of(entry: dict, season: dict) -> int | None:
    """Position counted down the pyramid, so each tier continues the one above.

    None for a tier deeper than the chart bands.  The chart draws four tiers and
    stops; a fifth- or sixth-tier season has no row to sit on and is marked like
    any other season with no position on this chart.  The position itself is not
    lost - it is in seasons.csv, where the rank is a place inside a regional
    group and not comparable to a national one anyway.
    """
    tier = entry["tier"]
    if tier > TIERS_SHOWN:
        return None
    return sum(season["bands"][: tier - 1]) + entry["position"]


def _vars(mode: str, accent: str | None = None,
          casing: str | None = None) -> dict:
    t = THEME[mode]
    out = {k: v for k, v in t.items() if k != "band"}
    out.update({f"band{i + 1}": c for i, c in enumerate(t["band"])})
    if accent:
        out["accent"] = accent
    out["casing"] = casing or t["accent_casing"]
    return out


def _rgb(hexval: str) -> tuple[int, int, int]:
    h = hexval.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _luminance(hexval: str) -> float:
    def channel(v: int) -> float:
        c = v / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = _rgb(hexval)
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast(a: str, b: str) -> float:
    la, lb = _luminance(a), _luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def shade(hexval: str, scale: float) -> str:
    """The same hue, that fraction of the way toward black."""
    r, g, b = _rgb(hexval)
    return "#%02X%02X%02X" % (round(r * scale), round(g * scale), round(b * scale))


def legible(hexval: str, against: str, minimum: float = 3.0) -> str:
    """The club's colour, darkened just enough to be seen against the bands.

    Kit colours are chosen to look good on a shirt, not to sit on a pale grey
    chart.  Maccabi Tel Aviv's #FFFF00 scores 1.07:1 against the lightest band -
    a line nobody can see.  Scaling the channels down preserves the hue and the
    ratio between them, so the line still reads as yellow, just a deep one; the
    alternative, swapping in a substitute colour, would lose the identity the
    colour was added for.

    3:1 is the WCAG floor for a graphical object, which a 2.6px line is.
    """
    r, g, b = _rgb(hexval)
    if max(r, g, b) == 0:
        return "#000000"
    for step in range(101):
        scale = 1 - step / 100
        cand = "#%02X%02X%02X" % (round(r * scale), round(g * scale),
                                  round(b * scale))
        if contrast(cand, against) >= minimum:
            return cand
    return "#000000"


def club_colors() -> dict[str, tuple[str, str]]:
    """Canonical club name -> (line colour, casing colour).

    The line is the club's kit colour exactly as the source gives it. Maccabi Tel
    Aviv play in #FFFF00 and the chart says #FFFF00.

    Yellow on a pale band is 1.07:1, which is not a line anyone can follow, so
    legibility comes from a casing drawn underneath rather than from altering the
    colour on top. Where the club's home kit has a second colour, that is the
    casing: Beitar Jerusalem and Maccabi Netanya both play in a yellow shirt with
    black shorts, so their charts are a yellow line with a black edge, which is
    the club's own pairing rather than one this project invented. Maccabi Tel
    Aviv, yellow throughout, falls back to its own colour taken down to 4.5:1.

    Every line gets a casing, so the treatment reads as deliberate rather than as
    something that happens to the pale clubs.
    """
    path = DATA / "club_colors.json"
    if not path.exists():
        return {}
    band1 = THEME["light"]["band"][0]
    out = {}
    for club, v in json.loads(path.read_text())["colors"].items():
        # Without the shade step a colour that already clears 4.5:1 comes back
        # unchanged - Maccabi Haifa's green was its own casing, an edge you
        # could not see. Darken first, then let legible() take it further if the
        # band still swallows it.
        casing = v.get("secondary") or legible(shade(v["color"], 0.6), band1, 4.5)
        out[club] = (v["color"], casing)
    return out


def _ordinal(n: int, lang: str) -> str:
    if lang == "he":
        return str(n)
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def inactive_spans() -> dict[str, list[dict]]:
    path = DATA / "club_status.json"
    return json.loads(path.read_text()).get("inactive", {}) if path.exists() else {}


def always_chart() -> list[str]:
    """Clubs to chart regardless of the ranking, beyond what the data can see."""
    path = DATA / "club_status.json"
    return json.loads(path.read_text()).get("always_chart", []) if path.exists() else []


def played_as() -> dict[str, list[dict]]:
    """Club -> spells it played under another club's name.

    Shimshon Tel Aviv spent 2000/01 to 2010/11 inside Beitar Shimshon Tel Aviv,
    and those seasons are in the dataset under Beitar Tel Aviv. The chart draws
    them as a second line rather than leaving eleven blank columns: the seasons
    were played, just not under this club's own name.
    """
    d = json.loads((DATA / "club_status.json").read_text())
    return d.get("played_as", {})


def played_without_table() -> dict[str, set[str]]:
    """Club -> seasons it is known to have played with no final position.

    A season can be abandoned partway, leaving clubs that certainly played and
    certainly have no final position. data/ifa/ carries the tables those seasons
    stopped at, marked `"abandoned": true`; parse_ifa.py takes no positions from
    them, so nothing reaches seasons.csv and the chart would otherwise read a
    club's last final position as the end of its life. Shimshon Tel Aviv, playing
    in Liga Alef South today, would end in 2024/25.

    Read straight from the captures rather than through the CSV: the fact wanted
    here is "was playing", which the dataset deliberately has no column for.
    """
    aliases = json.loads((DATA / "aliases_ifa.json").read_text())["aliases"]
    out: dict[str, set[str]] = defaultdict(set)
    for path in sorted((DATA / "ifa").glob("*.json")):
        cap = json.loads(path.read_text())
        if not cap.get("abandoned"):
            continue
        for entry in cap["standings"]:
            if club := aliases.get(entry["club"]):
                out[club].add(cap["season"])
    return out


def abandoned_below() -> dict[str, int]:
    """Season label -> the tier from which that season has no final table."""
    d = json.loads((DATA / "structure.json").read_text())
    return {a["season"]: a["tier"] for a in d.get("abandoned_below", [])}


def render(club: str, seasons: list[dict], history: dict[str, dict],
           lang: str = "en", name: str | None = None,
           inactive: list[dict] | None = None,
           abandoned: dict[str, int] | None = None,
           accent: str | None = None,
           casing: str | None = None,
           played: set[str] | None = None,
           spells: list[dict] | None = None) -> str:
    S = STRINGS[lang]
    pad_l = S["pad_l"]
    label = name or club

    # A season only counts as an unknown if it falls inside the club's active
    # life. Before its first recorded season and after its last, the club was
    # not there to have a position - Hakoah Tel Aviv merged away in 1959, so
    # marking its next sixty seasons "no position recorded" would claim a
    # missing record rather than a club that had ceased to exist. Interior
    # dormant spells are listed in data/club_status.json.
    recorded = [i for i, s in enumerate(seasons) if s["label"] in history]
    first, last = (recorded[0], recorded[-1]) if recorded else (0, -1)
    dormant = inactive or []
    cut = abandoned or {}
    # Seasons the club played that produced no final table. They carry no
    # position, so they cannot extend `recorded`, but they do extend the club's
    # life: without this a club still playing today ends on its last final
    # position and the chart draws the years since as though it had folded.
    playing = played or set()
    if playing:
        ends = [i for i, s in enumerate(seasons) if s["label"] in playing]
        if ends:
            first, last = min(first, min(ends)), max(last, max(ends))

    def nearest_tier(i: int) -> int:
        """The tier the club was at either side of a season it has no row for."""
        near = [abs(j - i) for j in recorded]
        j = recorded[near.index(min(near))]
        return history[seasons[j]["label"]]["tier"]

    def active(i: int, season: dict) -> bool:
        if not (first <= i <= last):
            return False
        if any(sp["from"] <= season["start"] <= sp["to"] for sp in dormant):
            return False
        # A season abandoned below some tier has no table to be missing from,
        # for a club that was playing at or below that tier.
        # A season abandoned below some tier has no table to be missing from,
        # so it is not counted against a club that was playing at that depth -
        # unless the club is positively known to have played, in which case
        # "no position recorded" is the literal truth and worth drawing.
        if season["label"] in cut and nearest_tier(i) >= cut[season["label"]]:
            return False
        return True
    maxrank = max(sum(s["bands"]) for s in seasons) + BOTTOM_BAND
    plot_w, plot_h = len(seasons) * COL, maxrank * ROW
    width, height = pad_l + plot_w + PAD_R, PAD_T + plot_h + PAD_B
    x = lambda i: pad_l + i * COL
    y = lambda rank: PAD_T + (rank - 1) * ROW
    floor = PAD_T + plot_h

    vars_light = _vars("light", accent, casing)
    if spells:
        vars_light["alt"] = spells[0]["color"]
        vars_light["alt-casing"] = spells[0]["casing"]
    # Custom properties are resolved here rather than declared, because the
    # charts have to survive Wikimedia Commons. Commons rasterises SVG with
    # librsvg at an SVG 1.0 / CSS 2 level and does not implement CSS custom
    # properties, so a var() reference resolves to nothing and the chart renders
    # with no colour at all. The indirection bought nothing anyway - every value
    # is fixed per file - so the literals go straight into the rules.
    def lit(css: str) -> str:
        for _ in range(4):                       # vars may refer to vars
            new = re.sub(r"var\(--([a-z0-9-]+)\)",
                         lambda m: str(vars_light.get(m.group(1), "")), css)
            if new == css:
                break
            css = new
        return css
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        # DejaVu and Liberation sit after the system faces and before the generic:
        # browsers never reach them, and Wikimedia Commons - which has none of the
        # system faces - lands on a font it actually installs instead of guessing.
        f'viewBox="0 0 {width} {height}" font-family="ui-sans-serif, -apple-system, '
        f'\'Segoe UI\', Roboto, \'DejaVu Sans\', \'Liberation Sans\', sans-serif" '
        f'role="img" '
        f'aria-label="{esc(label)}, {seasons[0]["label"]} – {seasons[-1]["label"]}">',
        "<style>",
        "  .bg{fill:var(--surface)} .ink{fill:var(--ink)} .ink2{fill:var(--ink2)}",
        "  .ink3{fill:var(--ink3)} .rule{stroke:var(--rule)}",
        "  .line,.casing{fill:none;stroke-linecap:round;stroke-linejoin:round}",
        "  .casing{stroke:var(--casing);stroke-width:4.4}",
        "  .line{stroke:var(--accent);stroke-width:2.4}",
        # Only when there is a second line to style. Emitting them regardless
        # left "stroke:" with nothing after it once the variables were resolved,
        # which is invalid CSS rather than a harmless unused rule.
        *([" .alt,.alt-casing{fill:none;stroke-linecap:butt;stroke-linejoin:round}",
           "  .alt-casing{stroke:var(--alt-casing);stroke-width:4.2}",
           "  .alt{stroke:var(--alt);stroke-width:2.2;stroke-dasharray:5 3}"]
          if spells else []),
        "  .champ{fill:var(--champion)}",

        "</style>",
        "<defs>",
        '  <pattern id="notplayed" width="7" height="7" patternUnits="userSpaceOnUse" '
        'patternTransform="rotate(-45)">'
        '<line x1="0" y1="0" x2="0" y2="7" stroke="var(--hatch)" stroke-width="1.4"/>'
        "</pattern>",
        '  <pattern id="uncovered" width="5" height="5" patternUnits="userSpaceOnUse">'
        '<circle cx="1.4" cy="1.4" r="1" fill="var(--hatch)"/></pattern>',
        # Horizontal bars, so a stopped season cannot be mistaken for the
        # diagonal hatch of a season never played or the dots of a missing one.
        '  <pattern id="stopped" width="4" height="4" patternUnits="userSpaceOnUse">'
        '<rect width="4" height="2" fill="var(--hatch)" fill-opacity=".55"/>'
        "</pattern>",
        # Not a texture but the page itself: "there was no tier this deep" should
        # read as absence, and every other state on this chart is a marking.
        '  <pattern id="notier" width="4" height="4" patternUnits="userSpaceOnUse">'
        '<rect width="4" height="4" fill="var(--surface)"/></pattern>',
        "</defs>",
        f'<rect class="bg" width="{width}" height="{height}"/>',
    ]

    # ── Tier bands, per column, so the moving boundaries show as steps.
    for i, s in enumerate(seasons):
        top = PAD_T
        for t, size in enumerate(s["bands"], start=1):
            bottom = y(sum(s["bands"][:t]) + 1)
            out.append(f'<rect x="{x(i)}" y="{top}" width="{COL}" '
                       f'height="{bottom - top}" fill="var(--band{t})"/>')
            top = bottom
        # Everything below the last band is bare page, whether the pyramid
        # was shallower than four tiers - it was two deep in 1935 - or deeper.
        # Shading it implied a band, and the chart no longer claims one.
        out.append(f'<rect x="{x(i)}" y="{top}" width="{COL}" '
                   f'height="{floor - top}" fill="url(#notier)"/>')

    # ── The club's own history.
    area, marks = [], []
    # Which states this club's chart actually contains. A legend is a key to the
    # marks on the page, so an entry for a mark that is not there is noise: 14 of
    # the 42 clubs have no unknown season at all, and a third of them never won
    # anything.
    drew = {"uncovered": False, "notplayed": False, "stopped": False}
    runs: list[list[tuple[int, int]]] = []      # unbroken stretches of (column, rank)
    prev: tuple[int, int] | None = None
    for i, s in enumerate(seasons):
        if not s["played"]:
            area.append(f'<rect x="{x(i)}" y="{PAD_T}" width="{COL}" '
                        f'height="{plot_h}" fill="url(#notplayed)" fill-opacity=".8"/>')
            drew["notplayed"] = True
            prev = None
            continue
        entry = history.get(s["label"])
        rank = rank_of(entry, s) if entry else None
        if rank is None:
            # No record, or a tier below the drawn bands. Mark it as an unknown
            # only while the club was actually competing.
            # A season the league abandoned is not a gap in the record: there
            # is no final table because none was ever produced. Drawn only for a
            # club that was playing at or below the tier that stopped - Maccabi
            # Tel Aviv finished 2019/20 as normal and should see nothing.
            stopped = cut.get(s["label"])
            if stopped and first <= i <= last and (
                    s["label"] in playing or nearest_tier(i) >= stopped):
                top = y(sum(s["bands"][: stopped - 1]) + 1)
                area.append(f'<rect x="{x(i)}" y="{top}" width="{COL}" '
                            f'height="{floor - top}" fill="url(#stopped)"/>')
                drew["stopped"] = True
            elif active(i, s):
                top = y(sum(s["bands"]) + 1)
                area.append(f'<rect x="{x(i)}" y="{top}" width="{COL}" '
                            f'height="{floor - top}" fill="url(#uncovered)"/>')
                drew["uncovered"] = True
            prev = None
            continue
        if prev and prev[0] == i - 1:
            runs[-1].append((i, rank))
        else:
            runs.append([(i, rank)])
        if entry["tier"] == 1 and entry["position"] == 1 and not entry["division"]:
            cx, cy = x(i) + COL / 2, y(rank) - 5
            marks.append(f'<path class="champ" d="M{cx} {cy - 3.6}l3.8 3.6-3.8 3.6'
                         f'-3.8-3.6z"/>')
        prev = (i, rank)
    curves = [smooth_path(r, x, y) for r in runs]
    out += area

    # Seasons played under another club's name, drawn before the club's own line
    # so that its own history stays the one on top. Dashed and in the other
    # club's colour: the same shape of statement as "as Newton Heath" on the
    # English club charts.
    alt = []
    for spell in (spells or []):
        srun: list[tuple[int, int]] = []
        runs_alt: list[list[tuple[int, int]]] = []
        for i, s in enumerate(seasons):
            entry = spell["history"].get(s["label"]) if s["played"] else None
            rank = rank_of(entry, s) if entry else None
            inside = spell["from"] <= s["start"] <= spell["to"]
            if rank is None or not inside:
                srun = []
                continue
            if srun and srun[-1][0] == i - 1:
                srun.append((i, rank))
            else:
                srun = [(i, rank)]
                runs_alt.append(srun)
        for r in runs_alt:
            alt.append(smooth_path(r, x, y))
    if alt:
        out += [f'<path class="alt-casing" d="{c}"/>' for c in alt]
        out += [f'<path class="alt" d="{c}"/>' for c in alt]

    out += [f'<path class="casing" d="{c}"/>' for c in curves]
    out += [f'<path class="line" d="{c}"/>' for c in curves] + marks

    # ── Tier labels, numbered, aligned to the most recent season's bands.
    last = seasons[-1]
    top = 1
    for t, size in enumerate(last["bands"], start=1):
        mid = (y(top) + y(top + size)) / 2
        out.append(text_el(pad_l - 11, mid + 3, S["tier"].format(n=t),
                           cls="ink2", size=10.5, lang=lang, align="right",
                           weight="600", extra=' letter-spacing=".05em"'))
        top += size
    # The floor strip is deliberately unlabelled. It is not a tier - it is every
    # tier below the fourth at once, and "TIER 5+" beside a two-row strip read as
    # a band of its own. The legend names it instead.

    # ── Season axis: a tick every decade, plus the two end seasons.
    last_i = len(seasons) - 1
    ticks = {0: short_label(seasons[0]["label"]),
             last_i: short_label(seasons[-1]["label"])}
    # One tick per decade: two slots can start in the same year, since the 1940
    # season was played and 1940/1941 was not.
    seen_decade: set[int] = set()
    for i, s in enumerate(seasons):
        if (s["start"] % 10 == 0 and 4 < i < last_i - 4
                and s["start"] not in seen_decade):
            seen_decade.add(s["start"])
            ticks[i] = str(s["start"])
    out.append(f'<path class="rule" d="M{pad_l} {floor + .5}h{plot_w}" fill="none"/>')
    for i, text in sorted(ticks.items()):
        anchor = "start" if i == 0 else ("end" if i == last_i else "middle")
        tx = x(i) if i == 0 else (x(i) + COL if i == last_i else x(i) + COL / 2)
        out += [
            f'<path class="rule" d="M{tx} {floor}v5" fill="none"/>',
            f'<text class="ink3" x="{tx}" y="{floor + 17}" text-anchor="{anchor}" '
            f'font-size="10.5">{esc(text)}</text>',
        ]

    # ── Title and a one-line summary.
    played = [s for s in seasons if s["played"]]
    entries = [history[s["label"]] for s in played if s["label"] in history]
    top_flight = sum(1 for e in entries if e["tier"] == 1)
    # Only a national first place is a championship: a regional season has a
    # winner per district, and counting those would inflate the total.
    titles = sum(1 for e in entries
                 if e["tier"] == 1 and e["position"] == 1 and not e["division"])
    best = min((e["position"] for e in entries if e["tier"] == 1), default=None)
    if top_flight:
        parts = [S["in_top"].format(n=top_flight, total=len(played))]
    else:
        key = "never_top_one" if len(entries) == 1 else "never_top"
        parts = [S[key].format(n=len(entries),
                               tier=min(e["tier"] for e in entries))]
    if titles:
        parts.append(S["titles"].format(n=titles) if titles == 1
                     else S["titles_plural"].format(n=titles))
    elif best:
        parts.append(S["best"].format(pos=_ordinal(best, lang)))
    out += [
        text_el(pad_l, 33, label, cls="ink", size=19, lang=lang, weight="600",
                extra=' letter-spacing="-.01em"'),
        text_el(pad_l, 54, " · ".join(parts), cls="ink2", size=11.5, lang=lang),
        text_el(width - PAD_R, 33, S["kicker"], cls="ink3", size=9.5, lang=lang,
                align="right", extra=' letter-spacing=".08em"'),
    ]

    # ── Legend: the states are distinguished by texture, not colour alone.
    # Equal-width slots rather than a width estimated from the string length,
    # which collided once the labels were translated.
    if spells:
        # The Hebrew chart needs the Hebrew name; falling through to the Latin
        # one leaves "בתור" in front of a left-to-right string.
        alt_name = spells[0].get(f"name_{lang}") or spells[0]["name"]
        items = [("line", S["legend_as"].format(name=label)),
                 ("alt", S["legend_as"].format(name=alt_name))]
    else:
        items = [("line", S["legend_line"])]
    if marks:
        items.append(("champ", S["legend_champ"]))
    if drew["stopped"]:
        items.append(("stopped", S["legend_stopped"]))
    if drew["uncovered"]:
        items.append(("uncovered", S["legend_uncovered"]))
    if drew["notplayed"]:
        items.append(("notplayed", S["legend_notplayed"]))
    slot = plot_w / len(items)
    lx, ly = pad_l, floor + 44
    for kind, text in items:
        if kind == "line":
            swatch = (f'<path class="casing" d="M{lx} {ly - 3.5}h16"/>'
                      f'<path class="line" d="M{lx} {ly - 3.5}h16"/>')
        elif kind == "alt":
            swatch = (f'<path class="alt-casing" d="M{lx} {ly - 3.5}h16"/>'
                      f'<path class="alt" d="M{lx} {ly - 3.5}h16"/>')
        elif kind == "champ":
            swatch = f'<path class="champ" d="M{lx + 8} {ly - 8}l4 4-4 4-4-4z"/>'
        else:
            swatch = (f'<rect x="{lx}" y="{ly - 9}" width="16" height="11" '
                      f'fill="url(#{kind})"'
                      + (' fill-opacity=".8"/>' if kind == "notplayed" else "/>"))
        out += [swatch,
                text_el(lx + 22, ly, text, cls="ink2", size=10.5, lang=lang)]
        lx += slot
    out.append("</svg>")
    return lit("\n".join(out)) + "\n"


def slug(club: str) -> str:
    keep = "".join(c.lower() if c.isalnum() else "-" for c in club)
    return "-".join(p for p in keep.split("-") if p)


def hebrew_names() -> dict[str, str]:
    """Canonical club name -> Hebrew name, for the Hebrew charts.

    data/aliases_he.json maps Hebrew -> canonical and several Hebrew spellings
    can share a canonical name; the first one wins, which is the modern article
    name in that file's ordering.
    """
    out: dict[str, str] = {}
    for he, canonical in json.loads((DATA / "aliases_he.json").read_text()).items():
        if he.startswith("_") or not canonical:
            continue
        out.setdefault(canonical, he)
    return out


def wiki_url(host: str, title: str) -> str:
    # Colons and parentheses are legal in a wiki path and encoding them gives
    # File%3AFoo%28Hebrew%29, which works but is unreadable in a status line.
    return f"https://{host}/wiki/" + urllib.parse.quote(
        title.replace(" ", "_"), safe=":()/'")


def status_bar(entry: dict | None, S: dict) -> str:
    """The publication line under a chart: where it is, and how far it got.

    Three states, and the middle one is the point of having this at all - a file
    can be on Commons without being in any article, which is where every Hebrew
    chart currently sits.
    """
    if not entry:
        return ""
    bits = []
    for lang_key, label in (("en", S["pub_en"]), ("he", S["pub_he"])):
        side = entry.get(lang_key)
        if not side:
            continue
        host = "en.wikipedia.org" if lang_key == "en" else "he.wikipedia.org"
        file_url = wiki_url("commons.wikimedia.org", "File:" + side["commons"])
        if side.get("placed"):
            bits.append(
                f'<span class="pub is-live">{esc(label)} '
                f'<a href="{esc(wiki_url(host, side["article"]))}">'
                f'{esc(S["pub_in_article"])}</a> · '
                f'<a href="{esc(file_url)}">{esc(S["pub_file"])}</a></span>')
        else:
            bits.append(
                f'<span class="pub is-waiting">{esc(label)} '
                f'<a href="{esc(file_url)}">{esc(S["pub_uploaded"])}</a> — '
                f'{esc(S["pub_not_placed"])}</span>')
    if not bits:
        return ""
    return '    <p class="pubs">' + "".join(bits) + "</p>\n"


def published() -> dict[str, dict]:
    """Club -> where its chart is published, from data/wikipedia.json.

    The gallery says so per club, because "is this one on Wikipedia, and is the
    Hebrew one placed or only uploaded?" is the question this page gets asked and
    the answer is otherwise only in a JSON file nobody opens.
    """
    path = DATA / "wikipedia.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text())["clubs"]


def gallery_html(clubs: list[str], seasons: list[dict], lang: str,
                 names: dict[str, str], suffix: str) -> str:
    S = STRINGS[lang]
    pub = published()
    # The club name is drawn inside each SVG, but an <img> is opaque to
    # find-in-page and to a search engine. Repeating it as a real heading, with
    # an id, makes every club on this page searchable and linkable - and in the
    # Hebrew gallery it carries both spellings, so either finds the chart.
    cards = []
    for c in clubs:
        shown = names.get(c, c)
        both = f"{shown} · {c}" if shown != c else shown
        cards.append(
            f'  <figure id="{slug(c)}">\n'
            f'    <h2><a href="#{slug(c)}">{esc(both)}</a></h2>\n'
            f'    <div class="scroll"><img src="{slug(c)}{suffix}.svg" '
            f'alt="{esc(shown)}" loading="lazy"></div>\n'
            f'{status_bar(pub.get(c), S)}'
            f'  </figure>')
    title = S["gallery_title"].format(first=seasons[0]["label"],
                                      last=seasons[-1]["label"])
    lead = S["gallery_lead"].format(clubs=len(clubs), seasons=len(seasons))
    pub_note = (f'<p class="pub-lead">{esc(S["pub_lead"])}</p>' if pub else "")
    how = [f'    <div><b>{esc(h)}</b><span>{esc(t)}</span></div>'
           for h, t in S["how"]]
    return f"""<title>{esc(title)}</title>
<style>
  :root {{
    --paper:#F6F4EF; --surface:#FFFDF9; --ink:#191C1E; --ink2:#4C5559;
    --ink3:#7E878B; --rule:#DDD8CD; --rule-firm:#C3BCAE;
  }}
  /* The charts commit to one light palette, so the page does too - a dark
     page behind light charts reads as a mistake. */
  :root {{ color-scheme: light; }}
  body {{
    background:var(--paper); color:var(--ink); margin:0; direction:{S['dir']};
    padding:clamp(1.5rem,5vw,3.5rem) clamp(1rem,4vw,2rem) 5rem;
    font:16px/1.6 ui-sans-serif,-apple-system,"Segoe UI",Roboto,sans-serif;
  }}
  .wrap {{ max-width:1320px; margin:0 auto; display:flex; flex-direction:column;
           gap:1.8rem; }}
  h1 {{ font-size:clamp(1.5rem,4vw,2.1rem); line-height:1.15; font-weight:600;
        letter-spacing:-.015em; margin:0 0 .7rem; text-wrap:balance; }}
  p {{ color:var(--ink2); max-width:68ch; margin:0; }}
  .how {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(16rem,1fr));
          gap:1px; background:var(--rule); border:1px solid var(--rule);
          border-radius:3px; }}
  .how div {{ background:var(--surface); padding:.85rem 1rem; }}
  .how b {{ display:block; font-size:.85rem; margin-bottom:.15rem; }}
  .how span {{ font-size:.82rem; color:var(--ink2); }}
  .pub-lead {{ font-size:.86rem; color:var(--ink2); max-width:60ch; }}
  .charts {{ display:flex; flex-direction:column; gap:1.4rem; }}
  figure {{ margin:0; border:1px solid var(--rule); border-radius:3px;
            background:var(--surface); overflow:hidden; scroll-margin-top:1rem; }}
  figure h2 {{ font-size:.82rem; font-weight:600; letter-spacing:.04em;
               text-transform:uppercase; color:var(--ink2); margin:0;
               padding:.6rem .9rem; border-bottom:1px solid var(--rule); }}
  figure h2 a {{ color:inherit; text-decoration:none; }}
  figure h2 a:hover {{ text-decoration:underline; }}
  figure h2 a:focus-visible {{ outline:2px solid var(--ink2);
                               outline-offset:2px; }}
  .pubs {{ margin:0; padding:.5rem .9rem .6rem; border-top:1px solid var(--rule);
           display:flex; flex-wrap:wrap; gap:.4rem 1.2rem; font-size:.78rem; }}
  .pub {{ color:var(--ink2); }}
  /* State is carried by a word as well as the dot, so it survives being read
     aloud or printed in greyscale. */
  .pub::before {{ content:""; display:inline-block; width:.5rem; height:.5rem;
                  border-radius:50%; margin-inline-end:.35rem;
                  vertical-align:.02rem; }}
  .is-live::before {{ background:#2E7D32; }}
  .is-waiting::before {{ background:#B26A00; }}
  .pubs a {{ color:var(--ink); }}
  .pubs a:focus-visible {{ outline:2px solid var(--ink2); outline-offset:2px; }}
  .scroll {{ overflow-x:auto; direction:ltr; }}
  img {{ display:block; max-width:100%; height:auto; }}
  footer {{ border-top:1px solid var(--rule-firm); padding-top:1.1rem;
            font-size:.82rem; color:var(--ink3); }}
</style>
<div class="wrap">
  <header>
    <h1>{esc(title)}</h1>
    <p>{esc(lead)}</p>
    {pub_note}
  </header>
  <div class="how">
{chr(10).join(how)}
  </div>
  <div class="charts">
{chr(10).join(cards)}
  </div>
  <footer>RSSSF · English Wikipedia · Hebrew Wikipedia — see README.md</footer>
</div>
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("clubs", nargs="*", help="clubs to render (default: the clubs with "
                                             "the most top-flight seasons)")
    ap.add_argument("--top", type=int, default=32, help="how many clubs when none named")
    args = ap.parse_args()

    seasons, by_club = load()
    if args.clubs:
        if missing := [c for c in args.clubs if c not in by_club]:
            raise SystemExit(f"no data for: {', '.join(missing)}")
        clubs = args.clubs
    else:
        ranked = sorted(by_club, key=lambda c: (
            -sum(1 for e in by_club[c].values() if e["tier"] == 1),
            -len(by_club[c]), c))
        # Always chart the current top two tiers, however short a club's history:
        # a chart set that leaves out a club playing this season is incomplete.
        latest = seasons[-1]["label"]
        current = {c for c in by_club
                   if (e := by_club[c].get(latest)) and e["tier"] in (1, 2)}
        current |= {c for c in always_chart() if c in by_club}
        clubs = ranked[:args.top]
        missing = [c for c in ranked if c in current and c not in clubs]
        clubs += missing
        if missing:
            print(f"  added {len(missing)} club(s) from the current top two tiers: "
                  f"{', '.join(missing)}")

    OUT.mkdir(exist_ok=True)
    names = hebrew_names()
    missing_he = [c for c in clubs if c not in names]
    dormant, cut = inactive_spans(), abandoned_below()
    colors = club_colors()
    still_playing = played_without_table()
    shared = played_as()
    no_color = [c for c in clubs if c not in colors]
    for club in clubs:
        spans = dormant.get(club)
        accent, casing = colors.get(club, (None, None))
        plays = still_playing.get(club)
        # The other club's rows, and its colour: the line says whose team this
        # was as much as it says where they finished.
        spells = []
        for spell in shared.get(club, []):
            alt_colour, alt_casing = colors.get(spell["rows_under"], (None, None))
            spells.append({
                **spell,
                "history": by_club[spell["rows_under"]],
                "color": alt_colour or THEME["light"]["accent"],
                "casing": alt_casing or THEME["light"]["accent_casing"],
            })
        (OUT / f"{slug(club)}.svg").write_text(
            render(club, seasons, by_club[club], "en", inactive=spans,
                   abandoned=cut, accent=accent, casing=casing, played=plays,
                   spells=spells))
        (OUT / f"{slug(club)}.he.svg").write_text(
            render(club, seasons, by_club[club], "he", names.get(club, club),
                   inactive=spans, abandoned=cut, accent=accent, casing=casing,
                   played=plays, spells=spells))
    if no_color:
        print(f"  {len(no_color)} club(s) without a colour in "
              f"data/club_colors.json, drawn in the default accent: "
              f"{', '.join(no_color)}")
    for lang, suffix, out_name in [("en", "", "index.html"), ("he", ".he", "index.he.html")]:
        body = gallery_html(clubs, seasons, lang,
                            names if lang == "he" else {}, suffix)
        (OUT / out_name).write_text(
            '<!doctype html>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            + body)
        (OUT / f"gallery-body{suffix or '.en'}.html").write_text(body)

    print(f"{len(clubs)} clubs x 2 languages, {len(seasons)} season columns "
          f"({seasons[0]['label']}–{seasons[-1]['label']}) -> {OUT}")
    if missing_he:
        print(f"  no Hebrew name for {len(missing_he)}: {', '.join(missing_he)}")


if __name__ == "__main__":
    main()
