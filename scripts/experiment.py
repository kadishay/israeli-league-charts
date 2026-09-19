#!/usr/bin/env python3
"""Render variants of a club's chart, for choosing between them.

Written to answer the review on Hebrew Wikipedia's village pump, where three
editors agreed the charts were worth having and disagreed about how they look:

* "the grey columns take up most of the graph's area and it isn't clear what
  they mean" - answered by `band_style="quiet"`.
* "I cannot tell whether they finished 2nd, 3rd or 4th in 1989" - answered by
  `positions`, which only fits once the axis is short enough.
* "for a club that has never left the top flight the lower bands are pointless,
  and for a club founded in 2005 there is no sense starting in 1931" - answered
  by cropping, which is done here rather than in render.py because both crops
  are just a smaller `seasons` list and a shorter `bands` list per season.

Nothing here writes to out/. Variants go to out/experiments/ so the published
charts are never touched by an experiment.

    python3 scripts/experiment.py                      # the three review cases
    python3 scripts/experiment.py "Maccabi Haifa"      # any club
"""

import copy
import sys
from pathlib import Path

import render as R

OUT = R.OUT / "experiments"


def crop_x(seasons: list[dict], history: dict, keep_before: int = 2) -> list[dict]:
    """Drop the seasons before the club existed, keeping a little run-up.

    The cost is that two clubs' charts no longer share an x-axis, which is what
    made them comparable; the gain is that Maccabi Bnei Reineh's chart stops
    being four fifths empty. Worth it per season, not in general - so it is a
    per-club choice, not a new default.
    """
    played = [i for i, s in enumerate(seasons) if s["label"] in history]
    if not played:
        return seasons
    start = max(0, played[0] - keep_before)
    return seasons[start:]


def crop_y(seasons: list[dict], history: dict, keep_below: int = 1) -> list[dict]:
    """Drop the tiers the club never reached, keeping one below for context.

    Without the one spare band a club that has only ever been top-flight gets a
    chart with a single band and no sense of what it is sitting above.
    """
    tiers = [e["tier"] for e in history.values() if e.get("tier")]
    if not tiers:
        return seasons
    depth = min(R.TIERS_SHOWN, max(tiers) + keep_below)
    out = copy.deepcopy(seasons)
    for s in out:
        s["bands"] = s["bands"][:depth]
    return out


# Fixed axes throughout: the shared x- and y-axis is what lets two clubs' charts
# be compared side by side, and that comparability is the point of a set rather
# than a single picture. The cropped variants stay available in crop_x/crop_y for
# anyone who wants to weigh that trade again, but they are not offered here.
VARIANTS = {
    "1-current": dict(),
    "2-quiet":   dict(band_style="quiet"),
    "3-modern":  dict(band_style="modern"),
}


def main() -> None:
    seasons, by_club = R.load()
    colors = R.club_colors()
    dormant, cut = R.inactive_spans(), R.abandoned_below()
    playing, shared = R.played_without_table(), R.played_as()
    names = R.hebrew_names()

    wanted = sys.argv[1:] or [
        "Maccabi Tel Aviv",     # never relegated: one flat line near the top
        "Hapoel Afula",         # moved between many leagues - the best case for a chart
        "Maccabi Jaffa",        # the other case named in the review
        "Hapoel Tel Aviv",      # a long record with a single relegation
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    made = []
    for club in wanted:
        if club not in by_club:
            print(f"  no such club: {club}")
            continue
        history = by_club[club]
        accent, casing = colors.get(club, (None, None))
        spells = []
        for spell in shared.get(club, []):
            src = spell.get("rows_under", club)
            ac, cs = colors.get(spell["rows_under"], (None, None)) \
                if spell.get("rows_under") else (None, None)
            spells.append({**spell, "history": by_club[src],
                           "color": ac or R.THEME["light"]["ink3"],
                           "casing": cs or R.THEME["light"]["ink2"]})
        for tag, opt in VARIANTS.items():
            opt = dict(opt)
            s = seasons
            if opt.pop("crop", None):
                s = crop_y(crop_x(s, history), history)
            for lang, suffix in (("en", ""), ("he", ".he")):
                svg = R.render(club, s, history, lang,
                               names.get(club, club) if lang == "he" else None,
                               inactive=dormant.get(club), abandoned=cut,
                               accent=accent, casing=casing,
                               played=playing.get(club), spells=spells, **opt)
                path = OUT / f"{R.slug(club)}--{tag}{suffix}.svg"
                path.write_text(svg)
            made.append(f"{R.slug(club)}--{tag}")
    print(f"{len(made)} variants x 2 languages -> {OUT}")
    for m in made:
        print(f"  {m}")


if __name__ == "__main__":
    main()
