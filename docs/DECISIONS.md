# Modelling decisions

Every entry is a choice that could reasonably have gone the other way, with the reason and
what would change it. They are here because several of them look like bugs until you know
why, and because the cheap-looking alternatives are all wrong in ways that are hard to see
in the output.

---

## 1. Tier is derived, never stored

`seasons.csv` records *(season, league, position)*. The tier comes from the era table in
`structure.json` at read time.

**Why.** League names move. Liga Alef has been the first, second, third and fourth tier at
different times; Liga Dalet appeared and vanished three times. "Liga Alef, 5th" means a
different depth in 1960 than in 2015.

**Consequence.** Chart bands are labelled `TIER 1 … TIER 4`, never by league name.

Below tier two the league is split into regional groups, so a position there is a rank
*within its group* and not a national one. Two clubs can both finish "1st" in the same tier
in the same season — in 1965/66 Maccabi Haifa won Liga Alef North and Sektzia Nes Tziona won
Liga Alef South.

Those seasons were once drawn with a dashed line to flag it. **That is gone.** The chart is
read for the *level*, and nobody reads an exact rank within a band at this scale, so the
dashed line was qualifying information the reader was not using — at the cost of a legend
row and two paragraphs of explanation. The `division` column stays in the data, and the
gallery says in one line that positions below tier two are regional ranks.

A useful general test: an encoding has to earn its legend row. If explaining a mark takes
more space than the mark conveys, drop the mark.

**What would change it.** Nothing. Any schema that stores a tier per league is wrong for
most of the 20th century.

---

## 2. A season's key is its label, not its start year

Rows carry a `season` label (`1966/1968`, `1937`, `2025/2026`) and the merge keys on it.

**Why.** The start year is not unique. **The 1940 season was played and 1940/1941 was not,
and both start in 1940.** Keying on the year made an abandoned season collide with a played
one, and the collision was silent.

Related traps in the same family:

- There is **no 1936/37**. The league ran calendar-year seasons from 1937 to 1940, so
  1935/36 is followed directly by 1937.
- There is **no 1967/68**. 1966/1968 was one championship played over two years.
- A naive century conversion turned RSSSF's `1999/00` into the label `1999/1900`.

**Consequence.** The x-axis is a list of season names from `seasons_index.json`, not a
range of years. Generating columns by looping over years invents two seasons and misaligns
everything after 1936.

---

## 3. Columns come from the Hebrew Wikipedia season navbox

`seasons_index.json` is built from `תבנית:עונות בליגה עליונה בכדורגל` and its second-tier
counterpart.

**Why.** It is the only source found that enumerates *every* season slot and marks the ones
never played, by striking them through. Everything else leaves it to be inferred from the
absence of an article, which cannot distinguish "not played" from "not written up".

This is what established the 10 unplayed top-flight slots, and it independently confirmed
both the missing 1936/37 and the single 1966/1968 entry.

---

## 4. Absent is not the same as unknown

A club is marked "no position recorded" **only for seasons inside its active life**. Before
its first recorded season and after its last, the chart draws plain background.

**Why.** Without this, Hakoah Tel Aviv — which merged into Hakoah Maccabi Ramat Gan — carried
sixty years of dotted marks asserting a missing record, when the truth is there was no club.
Hapoel Yehud and Maccabi Rehovot are both written up in the past tense.

Interior dormant spells need a source, so they live in `data/club_status.json` with a reason
and a citation. Two so far:

| Club | Span | Why |
|---|---|---|
| Shimshon Tel Aviv | 2000/01–2013/14 | Merged with Beitar Tel Aviv as Beitar Shimshon Tel Aviv; left the merger 2011; re-formed a senior team 2014 |
| Hapoel Yehud | 1998/99–2007/08 | Dissolved after relegation in 1998; a 2004 revival folded within months; re-founded 2008 |

A third case is a property of the season rather than the club: **2019/20 has no final table
below tier two**, because the IFA froze the non-professional leagues after 25 rounds for
COVID-19. It is recorded in `structure.json` as `abandoned_below` and accounted for seven
clubs' apparent gaps on its own.

---

## 5. A club cannot have a position before it was founded

`club_status.json` carries founding years and `build.py` drops rows that predate them,
reporting each one.

**Why.** Such a row is not a fact, it is an over-merged alias. Hakoah Ramat Gan was founded
in **1962**, yet the alias map was giving it Liga Bet rows from 1938 to 1946 — and 1946/47
had **two at once, a 2nd place and a 4th**, which is two clubs collapsed under one name.

This is a cheap integrity check that catches the most damaging class of alias error.

---

## 6. Sources merge per club-season-division, with precedence

Order: **RSSSF**, then **Hebrew Wikipedia**, then **English Wikipedia**. The key is
*(season, league, club, division)*.

**Why that key.** The Mandate-era regional seasons are documented district by district and
the two Wikipedias cover *different districts* — English has the 1941/42 championship
play-off, Hebrew the Jerusalem and Tel Aviv tables. Taking a whole league-season from the
first source that has it discarded the other's, which cost Maccabi Tel Aviv their 1941/42
title. Keeping the division in the key lets a district row and a national row for the same
club-season both survive.

**Why that order.** RSSSF's champions were checked against Wikipedia's list and all 73
match; it is also the source the era boundaries were drawn from.

Overlaps are compared rather than silently resolved — 16 position disagreements are
reported on every build, all adjacent-rank tie-break differences between the two Wikipedias.

---

## 7. Where a club has several rows for one season, prefer the shallowest tier, then national

**Why.** A regional season may list a club both in a district table and in the national
play-off that decided the title. Letting an arbitrary row win cost Maccabi Tel Aviv their
1941/42 championship; they read 86 of 86 seasons and 25 titles only once this rule was in.

---

## 8. A championship is a *national* first place

**Why.** A regional season has a winner per district. Counting every first place inflated
the totals until the corrected figures were checked against the known ones: Maccabi Tel Aviv
25, Maccabi Haifa 15, Beitar Jerusalem 6, Hapoel Be'er Sheva 6.

The chart therefore does not mark Maccabi Tel Aviv's 1939 title, which was won in the Tel
Aviv district. The IFA restored that title in May 2024, so the official count is 25 while
the marked count is 24.

---

## 9. Positions come from row order; the printed numbers only order the groups

**Why.** Sources mis-number rows. RSSSF's 2021/22 Liga Leumit skips 13 and prints 16 twice;
the Hebrew 1939 South B district skips 3 and prints 4 twice. Row order is standings order in
both. Every repair is reported so a real parse error cannot hide behind it.

**The exception.** Sequential play-off groups keep the strict contiguity check, because
there a gap can mean a whole group went missing — and renumbering the survivors from 1
produces plausible-looking but wrong positions rather than an error. That is not
hypothetical: it is how a missing upper-play-off group was caught.

---

## 10. Abandoned seasons are gaps, even when a partial table exists

English Wikipedia has a partial table for the abandoned 1947/48 season. Those 46 rows are
dropped and the season left as a gap, with the drop reported.

**Why.** A partial table is not a final position. The IFA lists leaders Nordia Tel Aviv as
champions, which is exactly the kind of claim a chart should not quietly make.

---

## 11. Tiers 1–4 get bands; 5 and below share the floor

Only tiers that **existed that season** are drawn, so the 1930s show two bands rather than
four — four would imply a depth the pyramid did not have.

The data for tiers 5–6 is in `seasons.csv` if you want to draw them.

---

## 12. The line is a smooth curve, interpolated monotonically

One point per season at the column centre, joined by a smooth curve rather than
a step.

**The honest caveat.** A season has one final position; nothing happens between
one May and the next August. A step line said exactly that, and a curve softens
it. This is a readability choice made deliberately: the curve makes a club's
trajectory far easier to follow across 96 columns.

**Why monotone cubic (Fritsch-Carlson) and not a cardinal spline.** A cardinal
spline overshoots past a local extreme. Here that would draw a club finishing
*above 1st place* in a season where it came first, or below last place in a
season where it came last - inventing positions that cannot exist. Monotone
tangents stay within the two points they join, and turning points are flattened
rather than rounded through. Verified: across all 34 charts the highest point
any curve reaches is exactly the y of 1st place, never above it.

Row height went from 5px to 7px per position at the same time, so ranks inside
a band are separable enough for the curve to be worth reading.

---

## 13. Charts commit to one light palette

No `prefers-color-scheme`. The club line (`#007C99`) and champion marker (`#A06A0A`) pass
the six-check colour validator against the light surface; the tier bands are a sequential
ramp of one hue.

**Why.** They read the same wherever they are embedded. A dark gallery page behind light
charts reads as a mistake.

---

## 14. Hebrew charts set `direction="rtl"` on the text elements, not the root

**Why both halves matter.** `direction="rtl"` is required for a mixed string like
`40 עונות מתוך 86` to order correctly. But it also swaps what `text-anchor` means — the
logical start of an RTL run is its *right* edge — so the anchor is flipped for Hebrew to
preserve the intended visual alignment. Probing Chrome directly settled it:

| Intent | LTR | RTL |
|---|---|---|
| left-aligned at x | `start` | `end` + `direction="rtl"` |
| right-aligned at x | `end` | `start` + `direction="rtl"` |

Setting `direction` on the root `<svg>` instead re-lays-out the whole document and pushes a
standalone chart off to one side. Year ticks stay LTR — they are digits.

---

## 15. Club selection: the top 32 by top-flight seasons, plus the entire current top two tiers

**Why the second half.** A chart set that leaves out a club playing this season is
incomplete, however short its history. Ranking by top-flight seasons alone missed Ironi
Tiberias and Maccabi Bnei Reineh in the top flight, and seven of the sixteen Liga Leumit
clubs — including Hapoel Kfar Shalem and Hapoel Afula, which have 58 and 49 recorded
seasons each.

**The limit of a data-driven rule.** Two clubs cannot be caught by any rule over this
dataset: Maccabi Ahi Nazareth was last recorded in 2022/23 and Maccabi Kiryat Gat in
2020/21 at tier five, and both climbed back through tiers whose coverage stops there. They
are named explicitly in `club_status.json` under `always_chart`, sourced from the league
article. This is the one place the club set needs a manual nudge each season, and it is
better than either charting nobody new or inferring promotions the data cannot see.

---

## 16. 2026/27 is excluded

It is in progress. A chart must not show a current partial position as a final one.

---

## Open questions

Flagged rather than decided:

- **The Hakoah lineage.** Hebrew Wikipedia treats Hakoah Tel Aviv and Hakoah Ramat Gan as
  one continuous club (Hakoah Berlin 1905 → Vienna → Tel Aviv 1934 → Ramat Gan). English
  Wikipedia and the 1962 founding date treat them as separate. Merging them would fill
  several of Hakoah Ramat Gan's early unknown seasons but contradicts the founding year used
  as an integrity check in decision 5.
- **1954/55's top flight.** RSSSF heads the table "Liga Leumit", Wikipedia keeps Liga Alef on
  top until 1955/56. Tier 1 under either name, so the charts are unaffected; the era boundary
  follows RSSSF because that is where the standings come from. English Wikipedia's
  "1954–55 Liga Alef" is treated as the same competition to stop it being counted twice.
- **Mandate-era title counts.** The no-champion list follows the Hebrew navbox, while the
  Mandate standings come from English Wikipedia, so pre-1949 title counts follow the English
  convention. The charts give Hapoel Tel Aviv 13 championships where a Hebrew source would
  say 14. English and Hebrew disagree on whether 1934/35, 1938, 1942/43 and 1944/45 produced
  champions at all; both readings are recorded in `structure.json`.
- **Shimshon Tel Aviv's top-flight total.** The chart says 28 seasons, their article says 29.
  The likely cause is 1966/1968, counted here as one season because it was one championship.
