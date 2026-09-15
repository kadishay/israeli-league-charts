# Sources: what each one has, and how it breaks

Four sources. Three have a fetch script and a parser; the fourth, the IFA's own site, is
behind a Cloudflare challenge and is captured by hand. None covers the whole pyramid; the
overlaps are what make the cross-checks possible.

---

## RSSSF — `scripts/fetch.py` → `scripts/parse.py`

[rsssf.org/tablesi/israhist.html](https://www.rsssf.org/tablesi/israhist.html) plus one page
per season from 2008/09.

| Covers | |
|---|---|
| Top flight | 1949/50 – 2024/25, complete |
| Second tier | 2008/09 – 2024/25 |
| Third tier | 2008/09 (Liga Artzit) and 2009/10 (Liga Alef) only |

**Why it leads the precedence order.** All 73 of its champions match Wikipedia's champion
list, and the era boundaries in `structure.json` were drawn from it.

### Quirks

- Plain-text tables inside HTML. The club name runs up to the games-played column and is
  **not always separated by whitespace** — `Hapoel Ironi Rishon-Lezion39  10  13`. Anchoring
  the row regex on the goals column (`41-65`) is what makes it unambiguous.
- Per-season filenames are inconsistent: `isra09` is 2008/09, then `isra2010` … `isra2025`.
- Two page formats. From 2009/10 sections are `<h4><a name="haal">`; 2008/09 has plain-text
  headings. The parser splits on text headings, which works for both, and requires a
  `Final Table:` before the next heading so the table of contents is not read as a section.
- **The same table is sometimes printed twice verbatim.** Both copies start at position 1,
  which looked like parallel regional divisions until the duplicates were dropped first.
- Play-off tables carry **absolute** positions (championship 1–6, relegation 7–14), so they
  can be merged without renumbering. The regular-season table is superseded where they exist.
- A promotion/relegation play-off table sits *inside* the season's block and is not league
  standings. The marker appears as `Promotion/Relegation Play-Off:`, `Promotion/relegation
  play-off` and `Promotion play-off`, so the pattern is line-anchored — otherwise it matches
  the `play-off` annotation at the end of a standings row.
- **A real typo:** 2021/22 Liga Leumit skips position 13 and prints 16 twice.
- RSSSF heads the 2007/08 table with **"Hapoel Kiriat-Shmona"**, the pre-merger name of what
  had been Ironi Kiryat Shmona for seven years. Handled by a season-scoped fixup.

---

## Hebrew Wikipedia — `scripts/fetch_he.py` → `scripts/parse_he.py`

| Covers | |
|---|---|
| Season index | Every slot, with played/not-played — see decision 3 |
| Top flight | Mandate era (district by district), and 2025/26 |
| Second tier | 1937 – 2007/08 |

**Best on the Mandate era**, where it is substantially better than English: the
[ליגת ארץ ישראל](https://he.wikipedia.org/wiki/ליגת_ארץ_ישראל_בכדורגל) article and its
per-season articles, and the navboxes that index them.

### Quirks

- Two navbox item formats: plain wikilinks, and `{{בספורט|<league>|<y1>|<y2>}}` which expands
  to `עונת y1/y2 ב<league>`. Navbox parameters run over several lines and wikilinks contain
  their own `|`, so parameters are split on a `|` at the *start of a line*.
- **Row separators carry their own attributes on the same line** — `|- bgcolor="ccffcc"`.
  Reading those as the row's first cell silently dropped exactly the coloured rows: the
  promoted and relegated ones. That cost about 266 rows before the contiguity check caught
  it. The parser is line-based for this reason.
- Cells appear inline (`|1|| [[club]]||30`) and one per line, starting with either `|` or
  `||`.
- Defunct clubs are sometimes **unlinked plain text**, so a cell without a wikilink is still
  accepted — dropping those rows leaves a hole in the standings. A few cells carry
  `target|display` with the brackets missing from the source.
- Statistics sections (top scorers, assists, player of the round, transfers, coach changes)
  are numbered tables full of wikilinks, so they read as standings — with players where
  clubs should be. Excluded by section name, plus a minimum row width.
- `הפלייאוף העליון` / `הפלייאוף התחתון` are the league's own championship and relegation
  rounds and **must be kept**; `פלייאוף העלייה` is a cross-tier promotion play-off and must
  not be.
- **A real typo:** the 1939 South B district skips position 3 and prints 4 twice.
- Club identity comes from the wikilink **target**, which is the club's current article — so
  `[[הפועל נוף הגליל|הפועל נצרת עילית]]` resolves a 1980 club to its modern identity for
  free. This is also why the alias map can over-merge: see decision 5.
- The API rate-limits anonymous bursts and returns plain text where JSON is expected. Needs a
  descriptive User-Agent with contact details, a throttle and backoff.

---

## English Wikipedia — `scripts/fetch_en.py` → `scripts/parse_en.py`

The only source for tiers 3 and below.

| League | Seasons found |
|---|---|
| Liga Artzit | 33 — its whole 1976–2009 run |
| Liga Alef | 67 |
| Liga Bet | 64 |
| Liga Gimel | 30 of roughly 70 |
| Eretz Israel League | 13 — filed there under a different article title |

### Quirks

- 204 of 207 articles use the **sports-table module**, where standings are parameters rather
  than a table: `|team1=BTA|name_BTA=[[Beitar Tel Aviv F.C.|Beitar Tel Aviv]]`. Position comes
  from the number on `teamN`, the club from the matching `name_CODE`.
- Titles are discovered through the search API, not constructed: the naming is not uniform
  (single-year early seasons, `1966–68` for the double season).
- **The search returns a varying subset between runs.** A fresh discovery once came back with
  five fewer titles than the previous one, which silently dropped 165 rows while their cached
  files sat there orphaned. `fetch_en.py` therefore merges new discoveries into
  `data/en_index.json` rather than replacing it, so the corpus only ever grows.
- English Wikipedia files the Eretz Israel League's seasons under its own article title, so
  the fetcher searches for that and `parse_en.py` maps it back. The titles are addresses on
  that site, not the league's name.
- Its `1938–39` article is the season the Hebrew navbox calls **1938** — the infobox
  runs 1937 → this → 1939 and names Hapoel Tel Aviv's third title, matching the Hebrew table
  exactly. Remapped, or it would be a column that does not exist.
- **No Haifa district.** The Mandate top-flight articles have Tel Aviv, Samaria and Southern
  only, which is why Maccabi Haifa has unknown seasons.
- Below tier two nearly everything is regional, with headings like `North Division`,
  `Samaria Division`, `Sub-division A`. Promotion and relegation play-offs are skipped.
- Roughly 900 lower-tier club names keep their English spelling. Their rows are **kept, not
  dropped**: dropping a club understates its division's size and shifts every position below
  it. `parse_en.py` reports what is unmapped.

---

## The IFA — no fetch script → `scripts/parse_ifa.py`

[football.org.il](https://www.football.org.il/) league pages, captured by hand into
`data/ifa/*.json`.

| Covers | |
|---|---|
| Liga Alef South | 2021/22 – 2024/25 |
| Liga Bet South A | 2016/17 – 2018/19 |

**Why it exists.** It is the only source for the seasons Wikipedia skips outright — 2016/17
and 2018/19 Liga Bet have no article in *either* language — and the only one for tiers three
and below after 2020/21, where English Wikipedia's coverage stops.

**Why it has no fetch script.** The site is behind a Cloudflare challenge. `curl` gets the
"Attention Required" interstitial where it expects the page, so the tables were read out of a
real browser session. That is also why `data/ifa/` sits *outside* the gitignored `data/raw/`:
nothing in it can be regenerated by running a script, so it is committed.

**Why it is trusted.** `data/ifa/liga-bet-south-a-2017-18.json` is a season English Wikipedia
also has, captured deliberately as the control: all sixteen positions match. That overlap is
where the sixteen Liga Bet entries in `data/aliases_ifa.json` come from — each IFA name sits
opposite a name this dataset already had, rather than being guessed at.

### Capturing more

Open `/leagues/league/?league_id=<league>&season_id=<season>`. `season_id` is the season's
start year minus 1998 (2024/25 = 26). League ids are not guessable; take them from the
**ליגות** menu. Two that are known: 62 is Liga Alef South, 73 is Liga Bet South A.

### Quirks

- **The page opens on a stage, and the stage is not always the league.** The `ddlBoxes`
  select carries `סבב 1`, `סבב 2` and then the knockout rounds — `פלייאוף - גמר מחוזי`,
  `מבחן עליה לליגה לאומית`. Those are cross-tier competitions, not standings. The final
  league table is the last `סבב`.
- **The round select can default mid-season.** Check games played before believing a table:
  a complete double round-robin is `2 × (clubs − 1)`. Getting this wrong is how a partial
  table becomes a final position.
- Clubs that withdrew stay in the table with 0 games played — 2024/25 Liga Alef South lists
  17 clubs, one of which never played. The positions are still contiguous.
- Standings are `div.table_row` with `div.table_col.place` and `div.team_name`; there is no
  `<table>` element, so an HTML table parser finds nothing.
- **A frozen season looks exactly like a finished one at a glance.** 2019/20 Liga Bet South A
  shows 25 of 30 games and no knockout stages — the COVID freeze `structure.json` already
  records. 2025/26 has the same signature across both Liga Alef South and Liga Bet South A:
  22–23 games of 30, no knockout stages, while Ligat ha'Al that season finished normally.
  Nothing below tier two was taken from 2025/26 for that reason. See the open questions in
  `DECISIONS.md`.

---

## Sources that turned out not to help

Checked so the next person does not repeat it:

- **Club pages for season-by-season tables.** They do not have them. Maccabi Haifa's Hebrew
  article has 12 tables — squad, titles, top scorers, coaches, youth teams — and no league
  history. Hapoel Haifa's has none. Maccabi Nes Ziona's and Hakoah Tel Aviv's have **zero
  tables**. Maccabi Rishon LeZion's and Maccabi Rehovot's are sports-association stubs with
  no football article at all.
  Club pages *are* worth reading for prose: founding and dissolution dates, mergers, dormant
  spells, and the occasional explicit finishing position.
- **RSSSF second level before 2008.** Only `isra2-99` and `isra2-01` exist.
- **A third-tier navbox on Hebrew Wikipedia.** There is none, and only one `ליגה א'` article
  exists from its years at tier three.
- **The Haifa district, anywhere.** The Hebrew 1939 article names it in prose — "13 clubs in
  Haifa Division A" — but carries no table. The same holds one level down: Hapoel Jerusalem
  is named in the prose of the 1937 and 1946/47 Liga Bet articles and appears in none of
  their tables, which document only the northern and southern districts.

---

## Extending

To add a source, write a `fetch_*.py` that caches into `data/raw/<source>/` and a
`parse_*.py` that emits `data/raw/parsed/seasons_<source>.csv` with the shared columns, then
add it to the precedence list in `build.py`. A source that cannot be fetched by script
commits its captures instead, outside `data/raw/` — see the IFA above. Only
`data/seasons.csv` is committed; it carries
a `source` column so a row can always be traced back. `build.py` checks every row against `structure.json` and
the season index, so a new source's mistakes surface as reported errors rather than as
plausible-looking chart output.

The invariant that has caught every format surprise so far is the same one each time: **each
league-season's positions must form a contiguous 1..N.**
