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
  within a district and not a national one.  Those seasons get a dashed line,
  because the depth is real even though the basis of the rank differs.

Colour: the tier bands are a sequential ramp (one hue, light to dark with
depth).  The club's line and the champion marker are the only two colours that
carry identity, and the pair (#007C99 and #A06A0A) passes the six-check
validator against the light surface.  These charts commit to one light palette
rather than following the viewer's theme, so they read the same wherever they
are embedded.
"""

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "out"

FIRST_SEASON = 1929          # the first season slot the sources record
LAST_SEASON = 2025           # most recent completed season
TIERS_SHOWN = 4              # tiers with a band of their own; deeper ones share the floor

COL = 13                     # width of one season column
ROW = 5                      # height of one league position
PAD_R, PAD_T, PAD_B = 20, 76, 78
BOTTOM_BAND = 5              # rows for "tier 5 and below"
NOMINAL = {1: 14, 2: 16, 3: 16, 4: 16}   # band size where a season has no data

THEME = {
    "light": {
        "surface": "#FCFCFB", "ink": "#1A1D1F", "ink2": "#565F63", "ink3": "#868F93",
        "band": ["#E9F0F2", "#DBE5E8", "#CBD8DC", "#B9C9CF", "#A7BAC1"],
        "rule": "#C9CFD1", "accent": "#007C99", "champion": "#A06A0A",
        "hatch": "#A9B2B6",
    },
}

STRINGS = {
    "en": {
        "dir": "ltr", "pad_l": 104,
        "tier": "TIER {n}", "tier_deep": "TIER {n}+",
        "kicker": "LEAGUE POSITION BY SEASON",
        "in_top": "{n} of {total} seasons in the top flight",
        "titles": "{n} championship", "titles_plural": "{n} championships",
        "best": "best finish {pos}",
        "legend_line": "Final league position",
        "legend_champ": "Champions",
        "legend_dashed": "Regional division — no national rank",
        "legend_uncovered": "No position recorded",
        "legend_notplayed": "Season not played",
        "gallery_title": "Israeli league performance, {first}–{last}",
        "gallery_lead": ("{clubs} clubs across {seasons} season columns. Position is "
                         "counted down the whole pyramid, so each tier continues the "
                         "one above — the band boundaries step because the top flight "
                         "has held anywhere between 10 and 18 clubs."),
    },
    "he": {
        "dir": "rtl", "pad_l": 96,
        "tier": "דרג {n}", "tier_deep": "דרג {n}+",
        "kicker": "מיקום בליגה לפי עונה",
        "in_top": "{n} עונות מתוך {total} בליגה הבכירה",
        "titles": "אליפות אחת", "titles_plural": "{n} אליפויות",
        "best": "המקום הטוב ביותר: {pos}",
        "legend_line": "מיקום סופי בליגה",
        "legend_champ": "אליפות",
        "legend_dashed": "מחוז אזורי — אין דירוג ארצי",
        "legend_uncovered": "לא נרשם מיקום",
        "legend_notplayed": "העונה לא התקיימה",
        "gallery_title": "מיקומי קבוצות בליגות בישראל, {first}–{last}",
        "gallery_lead": ("{clubs} קבוצות על פני {seasons} עונות. המיקום נמדד לאורך כל "
                         "הפירמידה, כך שכל דרג ממשיך את זה שמעליו — גבולות הדרגים "
                         "משתנים מפני שבליגה הבכירה שיחקו בין 10 ל-18 קבוצות."),
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
        depth = min(TIERS_SHOWN, len(era["tiers"]) if era else TIERS_SHOWN)
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


def rank_of(entry: dict, season: dict) -> int | None:
    """Position counted down the pyramid, so each tier continues the one above.

    None for a tier deeper than the chart draws bands for; those sit on the floor.
    """
    tier = entry["tier"]
    if tier > TIERS_SHOWN:
        return None
    return sum(season["bands"][: tier - 1]) + entry["position"]


def _vars(mode: str) -> dict:
    t = THEME[mode]
    out = {k: v for k, v in t.items() if k != "band"}
    out.update({f"band{i + 1}": c for i, c in enumerate(t["band"])})
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


def render(club: str, seasons: list[dict], history: dict[str, dict],
           lang: str = "en", name: str | None = None,
           inactive: list[dict] | None = None) -> str:
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

    def active(i: int, season: dict) -> bool:
        if not (first <= i <= last):
            return False
        return not any(sp["from"] <= season["start"] <= sp["to"] for sp in dormant)
    maxrank = max(sum(s["bands"]) for s in seasons) + BOTTOM_BAND
    plot_w, plot_h = len(seasons) * COL, maxrank * ROW
    width, height = pad_l + plot_w + PAD_R, PAD_T + plot_h + PAD_B
    x = lambda i: pad_l + i * COL
    y = lambda rank: PAD_T + (rank - 1) * ROW
    floor = PAD_T + plot_h

    css_light = ";".join(f"--{k}:{v}" for k, v in _vars("light").items())
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="ui-sans-serif, -apple-system, '
        f'\'Segoe UI\', Roboto, sans-serif" role="img" '
        f'aria-label="{esc(label)}, {seasons[0]["label"]} – {seasons[-1]["label"]}">',
        "<style>",
        "  .bg{fill:var(--surface)} .ink{fill:var(--ink)} .ink2{fill:var(--ink2)}",
        "  .ink3{fill:var(--ink3)} .rule{stroke:var(--rule)}",
        "  .area{fill:var(--accent);fill-opacity:.15}",
        "  .line{stroke:var(--accent);stroke-width:1.7;fill:none;stroke-linecap:square}",
        "  .champ{fill:var(--champion)}",
        f"  :root{{{css_light}}}",
        "</style>",
        "<defs>",
        '  <pattern id="notplayed" width="7" height="7" patternUnits="userSpaceOnUse" '
        'patternTransform="rotate(-45)">'
        '<line x1="0" y1="0" x2="0" y2="7" stroke="var(--hatch)" stroke-width="1.4"/>'
        "</pattern>",
        '  <pattern id="uncovered" width="5" height="5" patternUnits="userSpaceOnUse">'
        '<circle cx="1.4" cy="1.4" r="1" fill="var(--hatch)"/></pattern>',
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
        out.append(f'<rect x="{x(i)}" y="{top}" width="{COL}" '
                   f'height="{floor - top}" '
                   f'fill="var(--band{len(s["bands"]) + 1})"/>')

    # ── The club's own history.
    area, line, marks = [], [], []
    prev: tuple[int, int] | None = None
    for i, s in enumerate(seasons):
        if not s["played"]:
            area.append(f'<rect x="{x(i)}" y="{PAD_T}" width="{COL}" '
                        f'height="{plot_h}" fill="url(#notplayed)" fill-opacity=".8"/>')
            prev = None
            continue
        entry = history.get(s["label"])
        rank = rank_of(entry, s) if entry else None
        if rank is None:
            # No record, or a tier below the drawn bands. Mark it as an unknown
            # only while the club was actually competing.
            if active(i, s):
                top = y(sum(s["bands"]) + 1)
                area.append(f'<rect x="{x(i)}" y="{top}" width="{COL}" '
                            f'height="{floor - top}" fill="url(#uncovered)"/>')
            prev = None
            continue
        approx = bool(entry["division"])
        area.append(f'<rect class="area" x="{x(i)}" y="{y(rank)}" width="{COL}" '
                    f'height="{floor - y(rank)}"'
                    + (' fill-opacity=".07"/>' if approx else "/>"))
        dash = ' stroke-dasharray="3 2"' if approx else ""
        if prev and prev[0] == i - 1 and prev[1] != rank:
            line.append(f'<path class="line" d="M{x(i)} {y(prev[1])}V{y(rank)}"/>')
        line.append(f'<path class="line" d="M{x(i)} {y(rank)}h{COL}"{dash}/>')
        if entry["tier"] == 1 and entry["position"] == 1 and not entry["division"]:
            cx, cy = x(i) + COL / 2, y(rank) - 4
            marks.append(f'<path class="champ" d="M{cx} {cy - 3.6}l3.8 3.6-3.8 3.6'
                         f'-3.8-3.6z"/>')
        prev = (i, rank)
    out += area + line + marks

    # ── Tier labels, numbered, aligned to the most recent season's bands.
    last = seasons[-1]
    top = 1
    for t, size in enumerate(last["bands"], start=1):
        mid = (y(top) + y(top + size)) / 2
        out.append(text_el(pad_l - 11, mid + 3, S["tier"].format(n=t),
                           cls="ink2", size=10.5, lang=lang, align="right",
                           weight="600", extra=' letter-spacing=".05em"'))
        top += size
    mid = (y(top) + y(top + BOTTOM_BAND)) / 2
    out.append(text_el(pad_l - 11, mid + 3,
                       S["tier_deep"].format(n=len(last["bands"]) + 1),
                       cls="ink3", size=10.5, lang=lang, align="right",
                       extra=' letter-spacing=".05em"'))

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
    parts = [S["in_top"].format(n=top_flight, total=len(played))]
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
    items = [("line", S["legend_line"]), ("champ", S["legend_champ"]),
                       ("dashed", S["legend_dashed"]),
             ("uncovered", S["legend_uncovered"]),
             ("notplayed", S["legend_notplayed"])]
    slot = plot_w / len(items)
    lx, ly = pad_l, floor + 44
    for kind, text in items:
        if kind == "line":
            swatch = (f'<path class="line" d="M{lx} {ly - 3.5}h16"/>'
                      f'<rect class="area" x="{lx}" y="{ly - 3.5}" width="16" '
                      f'height="8"/>')
        elif kind == "champ":
            swatch = f'<path class="champ" d="M{lx + 8} {ly - 8}l4 4-4 4-4-4z"/>'
        elif kind == "dashed":
            swatch = (f'<path class="line" d="M{lx} {ly - 3.5}h16" '
                      f'stroke-dasharray="3 2"/>')
        else:
            swatch = (f'<rect x="{lx}" y="{ly - 9}" width="16" height="11" '
                      f'fill="url(#{kind})"'
                      + (' fill-opacity=".8"/>' if kind == "notplayed" else "/>"))
        out += [swatch,
                text_el(lx + 22, ly, text, cls="ink2", size=10.5, lang=lang)]
        lx += slot
    out.append("</svg>")
    return "\n".join(out) + "\n"


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


def gallery_html(clubs: list[str], seasons: list[dict], lang: str,
                 names: dict[str, str], suffix: str) -> str:
    S = STRINGS[lang]
    cards = [
        f'  <figure><div class="scroll"><img src="{slug(c)}{suffix}.svg" '
        f'alt="{esc(names.get(c, c))}" loading="eager"></div></figure>'
        for c in clubs
    ]
    title = S["gallery_title"].format(first=seasons[0]["label"],
                                      last=seasons[-1]["label"])
    lead = S["gallery_lead"].format(clubs=len(clubs), seasons=len(seasons))
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
  .charts {{ display:flex; flex-direction:column; gap:1.4rem; }}
  figure {{ margin:0; border:1px solid var(--rule); border-radius:3px;
            background:var(--surface); overflow:hidden; }}
  .scroll {{ overflow-x:auto; direction:ltr; }}
  img {{ display:block; max-width:100%; height:auto; }}
  footer {{ border-top:1px solid var(--rule-firm); padding-top:1.1rem;
            font-size:.82rem; color:var(--ink3); }}
</style>
<div class="wrap">
  <header>
    <h1>{esc(title)}</h1>
    <p>{esc(lead)}</p>
  </header>
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
        clubs = sorted(by_club, key=lambda c: (
            -sum(1 for e in by_club[c].values() if e["tier"] == 1),
            -len(by_club[c]), c))[:args.top]

    OUT.mkdir(exist_ok=True)
    names = hebrew_names()
    missing_he = [c for c in clubs if c not in names]
    dormant = inactive_spans()
    for club in clubs:
        spans = dormant.get(club)
        (OUT / f"{slug(club)}.svg").write_text(
            render(club, seasons, by_club[club], "en", inactive=spans))
        (OUT / f"{slug(club)}.he.svg").write_text(
            render(club, seasons, by_club[club], "he", names.get(club, club),
                   inactive=spans))
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
