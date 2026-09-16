# Israeli league performance charts

Season-by-season league-position charts for Israeli football clubs, in the style of the
[English club charts on Wikipedia](https://en.wikipedia.org/wiki/File:Manchester_United_FC_League_Performance.svg).

Those charts are hand-authored SVG — the Manchester United file opens with
`<!-- years are 10px wide, positions are 4px high -->` followed by manually written path
data, updated by hand each May. This repo generates them instead.

## Status

Working end to end. `out/` holds charts for the 32 clubs with the most top-flight seasons
**plus every club currently in the top two tiers** — 42 clubs, in English and Hebrew, with
`out/index.html` and `out/index.he.html` to view them together. All 14 clubs in Ligat ha'Al
and all 16 in Liga Leumit are covered.

Ten of those 42 are there because of the top-two-tiers rule rather than the ranking. Two
could not be caught by any rule over this dataset — Maccabi Ahi Nazareth and Maccabi Kiryat
Gat came up through tiers whose coverage stops in 2020/21 — so they are named in
`data/club_status.json` under `always_chart`, with the league article as the source. Update
that list when the leagues change.

```sh
python3 scripts/fetch.py      # cache the RSSSF pages
python3 scripts/fetch_he.py   # cache the Hebrew Wikipedia season articles
python3 scripts/fetch_en.py   # cache the English Wikipedia season articles
python3 scripts/parse.py      # RSSSF    -> data/raw/parsed/
python3 scripts/parse_he.py   # Hebrew   -> data/raw/parsed/
python3 scripts/parse_en.py   # English  -> data/raw/parsed/
python3 scripts/parse_ifa.py  # IFA      -> data/raw/parsed/  (no fetch; see SOURCES.md)
python3 scripts/build.py      # merge    -> data/seasons.csv   (the one dataset)
python3 scripts/fetch_colors.py  # kit colours -> data/club_colors.json (rarely needed)
python3 scripts/render.py     # charts   -> out/*.svg + the two gallery pages
```

`render.py` takes club names to render specific clubs, or `--top N` to change how many.

Bands are labelled **TIER 1 … TIER 4** and never by league name, because the names
move: "Liga Alef" on a 1960 column and on a 2015 column are different depths.

### Documentation

| | |
|---|---|
| [`docs/DECISIONS.md`](docs/DECISIONS.md) | The 21 modelling decisions, each with its reason and what would change it. Several look like bugs until you know why. Read this before changing the schema. |
| [`docs/SOURCES.md`](docs/SOURCES.md) | What each source covers, how each one breaks, and the sources that turned out not to help — so the dead ends are not re-walked. |
| [`docs/CLUBS.md`](docs/CLUBS.md) | Club identity and lineage, a per-club table of what is known, and why each unknown season is unknown. |
| [`docs/WIKIPEDIA.md`](docs/WIKIPEDIA.md) | What is published on Wikipedia and Commons, and how to add or update a chart. Updating is a Commons re-upload, not an article edit. |

### Files

| | |
|---|---|
| `docs/league-history.html` | Written history of the pyramid: what tier existed when, clubs per level, the 10 seasons with no champion. Read this first. |
| `data/structure.json` | The same history, machine-readable. Era table, per-season top-flight sizes, gap seasons, district-league seasons. |
| `data/seasons_index.json` | Every season slot, in order, with whether it was played — the x-axis, built from the Hebrew Wikipedia navboxes. |
| `data/seasons.csv` | **The dataset.** 10,426 rows — `season,season_start,league,division,position,club,source`. 86 seasons, 1,086 clubs, tiers 1–6. |
| `data/ifa/` | Seven league-season tables captured by hand from the IFA's site, which no script can fetch. Committed, unlike the other raw caches. |
| `data/club_status.json` | Founding years, and spans where a club existed but fielded no senior side. |
| `data/aliases*.json` | Source spelling → canonical club name, merging renames and mergers into one lineage. One file per source. |
| `data/club_colors.json` | Each club's kit colour, read off its Hebrew Wikipedia infobox by `scripts/fetch_colors.py`. The chart draws each line in its club's colour. |
| `scripts/fetch*.py` | Cache the sources into `data/raw/` (gitignored). |
| `scripts/parse*.py` | Raw pages → one CSV per source, under the gitignored `data/raw/parsed/`. |
| `scripts/build.py` | Merge the sources, checking every row against `structure.json`. |
| `scripts/render.py` | `data/seasons.csv` → one SVG per club, plus the gallery page. |

## Picking this up again

Where things stand, and what is worth knowing before changing anything:

- The pipeline runs end to end from the commands above. `data/seasons.csv` (10,426 rows) is
  the only committed dataset and carries a `source` column; the per-source CSVs are build
  artefacts under the gitignored `data/raw/parsed/`. The exception is `data/ifa/`: the IFA
  site sits behind a Cloudflare challenge, so those captures are committed because no script
  can refetch them.
- **Hebrew Wikipedia is the source of truth** where sources disagree — it wins the 964 rows
  it shares with English. It shares none with RSSSF. It cannot be the only source: 1,324
  rows, no top flight between 1949/50 and 2024/25, nothing below tier two.
- 42 clubs are charted in two languages, 84 SVGs in `out/`, committed. 16 have no unknown
  seasons; the other 26 account for 178, every one of them checked against the club's own
  article and explained in [`docs/CLUBS.md`](docs/CLUBS.md).
- Read [`docs/DECISIONS.md`](docs/DECISIONS.md) before touching the schema or the renderer.
  Several decisions look like bugs until you know why, and the cheap alternatives produce
  plausible-looking wrong output rather than errors.
- The one thing that needs a manual nudge each season is `always_chart` in
  `data/club_status.json`, for clubs promoted into the top two tiers through a tier whose
  coverage has stopped.
- Four questions are open rather than decided; they are listed at the end of
  `docs/DECISIONS.md`. The live one is the Hakoah lineage.

## The thing to get right

**A club's tier is not a property of its league name.** Liga Alef has been tier 1, 2, 3
and 4 at different times; Liga Dalet appeared and vanished three times; the top flight has
ranged from 10 clubs to 18. So `seasons.csv` stores *(season, league, position)* and the
tier is resolved at render time against the era table in `structure.json`. Any chart that
hardcodes a tier number per league will be quietly wrong for most of the 20th century.

Three more consequences, spelled out in `docs/league-history.html`:

- **The x-axis is a list of season names, not a range of years.** There is no 1936/37 (the
  league ran calendar-year seasons from 1937 to 1940, so 1935/36 is followed by 1937) and no
  1967/68 (1966/68 was one championship over two years). Looping over years to generate
  columns invents two seasons and misaligns everything after 1936.
- The y-axis rescales every few seasons, because cumulative rank across the pyramid depends
  on the size of every tier above.
- 10 seasons have no standings at all and need their own visual treatment — never
  interpolate across them.
- 4 further seasons (1939, 1940, 1941/42, 1944/45) were played as parallel district leagues:
  a champion exists but no national ranking does. Same for anything below tier two once the
  lower divisions went regional. These need a *different* mark from the 10 empty columns —
  "played, position unknowable" is not "not played".

## Data coverage

| Tier | Covered | Source |
|---|---|---|
| 1 | 1931/32 – 2025/26 | Hebrew Wikipedia to 1946/47 and for 2025/26, English for districts it lacks, RSSSF 1949/50–2024/25 |
| 2 | 1937 – 2025/26 | Hebrew Wikipedia to 2007/08, RSSSF from 2008/09 |
| 3 | 1954/55 – 2024/25 | English Wikipedia to 2020/21 (Liga Artzit 1976–2009, Liga Alef otherwise), IFA for Liga Alef South from 2021/22. 2025/26 was abandoned — no final table |
| 4 | 1954/55 – 2020/21 | English Wikipedia, plus the IFA for Liga Bet South A in 2016/17 and 2018/19, which Wikipedia has in neither language |
| 5–6 | 1976/77 – 2020/21, scattered | English Wikipedia |

All 73 champions in the RSSSF range match Wikipedia's champion list, and every row is
checked against `structure.json` — its league must exist at that tier in that season, and
the season must not be one that was never played.

Below tier two nearly everything is regional, so those positions are ranks within a
district, not national ones. The chart marks them with a dashed line: the depth is real,
the basis of the rank is not comparable.

### Absent is not the same as unknown

A club is only marked "no position recorded" for seasons **inside its active life**.
Before its first recorded season and after its last, the chart draws plain background: the
club was not there to have a position. Without that rule Hakoah Tel Aviv — which merged
into Hakoah Maccabi Ramat Gan in 1959 — carried sixty years of dotted marks claiming a
missing record, and the same held for Hapoel Yehud and Maccabi Rehovot, both written up in
the past tense.

Interior dormant spells need a source, so they live in `data/club_status.json`, each with a
reason and a citation:

- **Shimshon Tel Aviv, 2000/01–2013/14.** Merged with Beitar Tel Aviv as Beitar Shimshon Tel
  Aviv, left the merger in 2011, re-formed a senior team in 2014. Their gaps: 22 → 3. The
  eleven seasons inside the merger are drawn as a dashed second line in Beitar's blue,
  labelled *as Beitar Shimshon Tel Aviv* — the team played, under another name.
- **Hapoel Yehud, 1998/99–2007/08.** Relegated to Liga Bet in 1998 and dissolved; a 2004
  revival as Hapoel Monosson Yehud folded within months; re-founded 2008. Their gaps: 17 → 5.
- **2019/20 below tier two.** The IFA froze the non-professional leagues after 25 rounds
  because of COVID-19, so there is no final table to be missing from. The chart marks those
  columns *League abandoned mid-season*, and only on the 13 clubs that were actually playing
  at that depth — a club that finished its own season sees nothing. This alone accounts
  for seven clubs' apparent gaps, and lives in `structure.json` as `abandoned_below`.

The same file carries each club's **founding year**, and `build.py` drops any row dated
before it. A position predating a club is not a fact but an over-merged alias: Hakoah Ramat
Gan was founded in 1962, yet the alias map was giving it Liga Bet rows from 1938 to 1946 —
and 1946/47 had *two* of them, a 2nd place and a 4th, which is two different clubs collapsed
into one name.

Together these took the unknown seasons across the charted clubs from 408 to **142**. The
figure has since risen to 221, because the chart stopped banding tier five: a Liga Gimel
season is real data that the chart no longer has a row for. `docs/CLUBS.md` carries the
per-club breakdown.

### What is still missing, and why

Of the 42 clubs charted, **14 have no unknown seasons at all**. The remaining 221 are
concentrated in three places, all checked rather than assumed:

- **Mandate-era districts that no article tabulates.** Between 1934/35 and 1946/47 both the
  top flight and the second tier were played district by district, and the sources cover
  some districts and not others. The Hebrew 1939 top-flight article names the Haifa
  division in prose ("13 clubs in Haifa Division A") but carries no table; the English
  articles have Tel Aviv, Samaria and Southern only. The same holds one level down: Hapoel
  Jerusalem is named in the prose of the 1937 and 1946/47 Liga Bet articles but appears in
  none of their tables, which document only the northern and southern districts. That is
  why Maccabi Haifa has 8 unknown seasons, Hapoel Jerusalem 7 and Maccabi Herzliya 5, all
  before 1949.
- **~370 seasons in tiers 5–6** for clubs that spent decades down there. English Wikipedia
  has roughly 30 Liga Gimel seasons out of about 70, and whole years are simply absent
  (1990–91 Liga Gimel has no article). The clubs' own Hebrew articles carry **no season
  tables at all** — checked for Maccabi Haifa, Hapoel Haifa, Maccabi Nes Ziona and Hakoah
  Tel Aviv, all zero tables. This is why Maccabi Nes Ziona (12 top-flight seasons in the
  1930s–50s, then decades in the lower divisions) renders mostly as "no position recorded".

- **Tier 5 and 6 seasons the chart does not band.** These are not gaps in the data at all —
  the position is in `seasons.csv` — but the chart draws four tiers and a Liga Gimel season
  has no row to sit on. Maccabi Rehovot carry 31 marks for this reason, Maccabi Rishon LeZion
  23, Hapoel Afula 22.

Those gaps are drawn as the dotted "no position recorded" mark rather than interpolated or
guessed at. The mark appears in a chart's legend only when that club has one.

Three deliberate scope limits:

- **The chart stops at tier 4.** A fifth- or sixth-tier season has no row to sit on and is
  marked like any other season with no position on the chart. The positions are still in
  `seasons.csv`; below tier four a rank is a place inside a regional group, which is not
  comparable to a national one anyway.
- **Everything below the last band is bare page.** Where the pyramid was shallower than four
  tiers — it was two deep in 1935 — nothing is shaded beneath it, so the bands stop where the
  pyramid stopped.
- **2026/27 is excluded.** It is in progress, and a chart must not show a current partial
  position as a final one. The same rule takes 2025/26 out below tier two: the IFA stopped
  Liga Alef, Bet and Gimel that season because of the war, so no final table exists. The
  clubs that were playing are recorded anyway, in the abandoned captures under `data/ifa/`,
  so a club still in Liga Alef today does not render as one that folded in 2024/25.

**Minor clubs may appear under a source-specific spelling.** The alias files merge the
lineages that matter, and `parse_en.py` reports what is still unmapped, but roughly 900
lower-tier club names are left as English Wikipedia spells them. Their rows are kept rather
than dropped, because dropping them would understate a division's size and shift every
position below the missing club.

Source conflicts are flagged rather than papered over. English and Hebrew Wikipedia disagree
on whether 1934/35, 1938, 1942/43 and 1944/45 produced champions — the IFA has repeatedly
re-recognised Mandate-era titles, most recently restoring Maccabi Tel Aviv's 1939 title on
26 May 2024. `structure.json`'s no-champion list follows the Hebrew navbox, while the
Mandate-era *standings* come from English Wikipedia, so title counts before 1949 follow the
English convention: the charts give Hapoel Tel Aviv 13 championships where a Hebrew source
would say 14. Also still open: whether the 1954/55 top flight was called Liga Alef or Liga
Leumit (tier 1 either way).

An abandoned season can still have a partial table on Wikipedia — 1947/48 does. Those rows
are dropped and the season is left as a gap, because a partial table is not a final
position. `build.py` reports the drop.

## Notes on the parsers

The parsers assert that each league-season's positions form a contiguous `1..N`, and
`build.py` asserts every row against the era table and the season index. Those invariants
caught every format surprise in this repo, and four real bugs:

- A genuine RSSSF typo in 2021/22 Liga Leumit, which skips position 13 and prints 16 twice.
  Positions are therefore taken from row order, with the printed numbers used only to order
  playoff groups; any disagreement is reported on stdout.
- In the Hebrew tables, a row separator carries its own attributes on the same line
  (`|- bgcolor="ccffcc"`). Reading those as the row's first cell silently dropped exactly
  the coloured rows — the promoted and relegated ones — which cost about 266 rows. The
  contiguity check is what surfaced it; without it the survivors were being renumbered from
  1, which produces plausible-looking but wrong positions rather than an error.

- **A season's start year is not a unique key.** The 1940 season was played and 1940/1941
  was not, and both start in 1940 — so rows carry a season *label* and the merge keys on it.
  Keying on the year made an abandoned season collide with a played one.
- A century-arithmetic slip turned RSSSF's "1999/00" into the label `1999/1900`, which the
  season-index check caught as a column that does not exist.

A season may be one national table, two sequential playoff groups (upper 1–8, then lower
9–14), or two parallel regional groups (North 1–16, South 1–16). The two are told apart by
whether a second group starts at 1: if it does they are regions and each keeps its own
numbering in the `division` column; if it continues the first they are one table split by a
playoff and merge in order.

A championship is a *national* first place. A regional season has a winner per district, so
counting every first place inflated the title counts until the check against the known
champion list caught it.

## Sources

- [The IFA's own league pages](https://www.football.org.il/) — the only source for tiers
  three and below after 2020/21, and for two Liga Bet seasons Wikipedia skips entirely.
  Behind a Cloudflare challenge, so captured by hand into `data/ifa/`.
- [RSSSF Israel archive](https://www.rsssf.org/tablesi/israhist.html) — final tables.
- English Wikipedia season articles for tiers 3–6 and the Mandate-era top flight; they use
  the sports-table module, so standings are template parameters rather than a table.
- Hebrew Wikipedia for the Mandate era, where it is substantially better than English:
  [ליגת ארץ ישראל](https://he.wikipedia.org/wiki/ליגת_ארץ_ישראל_בכדורגל) and its per-season
  articles. The season navbox (עונות בליגה העליונה בישראל) is the authority for which
  seasons were played — it strikes through the ones that were not, and is the only source
  found that enumerates every season slot.
- Wikipedia: [league system](https://en.wikipedia.org/wiki/Israeli_football_league_system),
  [champions](https://en.wikipedia.org/wiki/List_of_Israeli_football_champions),
  [Liga Artzit](https://en.wikipedia.org/wiki/Liga_Artzit),
  [Liga Alef](https://en.wikipedia.org/wiki/Liga_Alef),
  [Liga Bet](https://en.wikipedia.org/wiki/Liga_Bet),
  [Liga Gimel](https://en.wikipedia.org/wiki/Liga_Gimel),
  [Liga Dalet](https://en.wikipedia.org/wiki/Liga_Dalet) — structural history.
