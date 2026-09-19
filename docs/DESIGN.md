# Design: what the chart chooses, and what it costs

Written after a review on Hebrew Wikipedia's village pump, where three editors agreed the
charts belong in club articles and disagreed about how they look. Each section below states
an objection, what the evidence says, and what was decided. Variants are reproducible:
`python3 scripts/experiment.py`.

---

## 1. The bands are grey and heavy

> *"The overall look is very dated, with a background full of grey columns whose meaning
> isn't really clear, and they take up most of the graph's area."*

**True, and the area figure is measurable.** In the current style a chart of Hapoel Afula is
470 `<rect>` elements of tier band; the line itself is three paths. The bands genuinely are
most of the picture.

They are not decoration, though. The band is what turns a number into a position *in the
pyramid* — 8th in tier 2 sits below 14th in tier 1, and only the band says so. Removing them
without replacement would leave a line whose height means nothing.

**Three treatments, same data:**

| Style | Band treatment | Afula file | Rect count |
|---|---|---|---|
| `solid` | four-step grey ramp, light to dark with depth | 38 KB | 470 |
| `quiet` | two near-white tones, hairline at each boundary | 49 KB | 470 + 241 rules |
| `modern` | **no fills at all** — a hairline at each boundary and the label beside it | **28 KB** | 133 |

`modern` is the direct answer to the objection: the only filled thing left on the chart is
the club's line. The tiers survive as boundaries, which is the minimum needed to keep a
height meaningful.

What `modern` gives up: with no fill, a reader scanning quickly has less to anchor on, and
the "which band am I in" judgement gets harder on a small thumbnail — exactly where the
charts are usually seen. That is the trade, and it is a judgement rather than a fact.

---

## 2. You cannot tell what position a club finished in

> *"I can't tell whether in 1989 Maccabi Tel Aviv finished 2nd, 3rd or 4th."*

**Correct, and mostly not fixable in a static image.** `render.py` takes
`positions="all"|"auto"`, which prints the finishing place above each point, and the result
shows why it is not the answer:

- Maccabi Tel Aviv's chart is 86 columns wide. Each column is 13px at full size and about
  4px at the width an article renders. A two-digit number does not fit in 4px.
- With the axis cropped so the numbers do fit, the chart stops sharing an axis with every
  other club — see §3.
- Even where the numbers fit, finding *one specific year* means counting columns. The
  number tells you the position but not which season you are looking at.

**Decision: no position labels.** The chart is for the trend across decades — how long a
club spent at each level, when it rose, when it fell. A reader who wants Maccabi Tel Aviv's
1989 placing wants a table, and the article already has one. A chart that tried to be both
would be worse at the first job without being good at the second.

This matches the review's own split: of the three editors, two said the trend is what
matters. The mark that *is* worth a per-season read — winning the league — has its own
marker.

---

## 3. Crop the axes per club?

> *"For a club that has never left the top flight the lower bands are pointless, and for a
> club founded in 2005 there is no sense starting in 1931. It's not pleasant when most of
> the graph is empty."*

**Both crops work and both are implemented** — `crop_x` and `crop_y` in
`scripts/experiment.py`, done by shortening the seasons list and the per-season bands list,
with no renderer change at all:

| Club | Cropped | Effect |
|---|---|---|
| Maccabi Tel Aviv | y-axis to tiers 1–2 | height 630 → 413; two empty bands gone |
| Maccabi Bnei Reineh | x-axis to 2005 onward | width 1372 → 423; the empty four fifths gone |

**Decision: keep both axes fixed.**

The shared axis is the reason to have a *set* of charts rather than a pile of pictures. Two
charts side by side are directly comparable — the same column is the same season, the same
height is the same tier — and a reader can see at a glance that one club was in tier 3 while
another was winning the league. Cropping makes each chart prettier alone and destroys that.

The empty space is also not meaningless. Bnei Reineh's chart being empty before 2005 says
the club did not exist; Maccabi Tel Aviv's empty lower bands say they have never been
relegated, which is one of the more remarkable facts about them.

Where cropping genuinely helps is a club whose whole history sits in tiers the chart does
not band, and there the real fix is different — see the limitation below.

---

## 4. "Tier" rather than the league name

> *"דרג זה ליגה?"* — is a tier a league?

Yes, but the name is deliberately omitted, and this is the oldest decision in the project
(decision 1 in `DECISIONS.md`).

League names move. **Liga Alef has been the 1st, 2nd, 3rd and 4th tier** at different
points. **Liga Leumit was the top flight until 1999 and the second tier after it**, when
Ligat ha'Al was created above it. Writing "Liga Leumit" on a 1960 column and on a 2010
column would put the same name on two different things — which is precisely the confusion a
chart spanning 1931 to today has to avoid.

The tier number is the one thing stable across the whole period. The cost is that the reader
must learn what "tier 2" means, which the legend should say more clearly than it does.

---

## Known limitation, stated plainly

The chart bands four tiers. A club whose history is mostly tier 5 or 6 — Maccabi Bnei
Reineh, Maccabi Nes Ziona — therefore renders as mostly "no position recorded", and cropping
the axis cannot manufacture a line where no row is drawn. For those clubs the chart is
currently a poor picture of a real history.

Fixing it means banding tier 5, which was removed deliberately (decision 11): below tier
four a position is a rank inside a regional group, not comparable to anything above it. The
honest summary is that these charts serve clubs that have spent time in the top four tiers,
and serve lower-league clubs badly.
