# Israeli league performance charts

Season-by-season league-position charts for Israeli football clubs, in the style of the
[English club charts on Wikipedia](https://en.wikipedia.org/wiki/File:Manchester_United_FC_League_Performance.svg).

Those charts are hand-authored SVG — the Manchester United file opens with
`<!-- years are 10px wide, positions are 4px high -->` followed by manually written path
data, updated by hand each May. This repo generates them instead.

## Status

Research and the data pipeline are done. The renderer is not written yet.

| | |
|---|---|
| `docs/league-history.html` | Written history of the pyramid: what tier existed when, clubs per level, the 10 seasons with no champion. Read this first. |
| `data/structure.json` | The same history, machine-readable. Era table, per-season top-flight sizes, gap seasons, district-league seasons. |
| `data/seasons.csv` | 1,314 rows — `season_start,league,position,club`. 73 seasons, 71 clubs. |
| `data/aliases.json` | Source spelling → canonical club name, merging renames and mergers into one lineage. |
| `scripts/fetch.py` | Caches the RSSSF source pages into `data/raw/` (gitignored). |
| `scripts/parse.py` | `data/raw/` → `data/seasons.csv`. |

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

| Tier | Covered |
|---|---|
| 1 | 1949/50 – 2024/25, complete |
| 2 | 2008/09 – 2024/25 |
| 3 | 2008/09 only |

All 73 parsed champions match Wikipedia's champion list.

**Known gap:** pre-2008 lower tiers are not in any bulk source found so far. RSSSF has only
1998/99 and 2000/01 at second level, and neither English nor Hebrew Wikipedia carries
per-club season tables. That leaves roughly 110 gap seasons across a dozen major clubs
(Hapoel Kfar Saba 19, Hapoel Haifa 14, Beitar Jerusalem 14 — Maccabi Tel Aviv 0, never
relegated). Filling them needs per-season Hebrew Wikipedia articles or hand entry.

Source conflicts are flagged rather than papered over. English and Hebrew Wikipedia disagree
on whether 1934/35, 1938, 1942/43 and 1944/45 produced champions — the IFA has repeatedly
re-recognised Mandate-era titles, most recently restoring Maccabi Tel Aviv's 1939 title on
26 May 2024. `structure.json` follows the Hebrew navbox and records both readings. Still
open: whether the 1954/55 top flight was called Liga Alef or Liga Leumit (tier 1 either way).

## Usage

```sh
python3 scripts/fetch.py    # cache source pages
python3 scripts/parse.py    # rebuild data/seasons.csv
```

`parse.py` asserts that each league-season's positions form a contiguous `1..N`. That
invariant is what catches format surprises — it found a genuine RSSSF typo in 2021/22 Liga
Leumit, which skips position 13 and prints 16 twice. Positions are therefore taken from row
order, with the printed numbers used only to order playoff groups; any disagreement between
the two is reported on stdout.

## Sources

- [RSSSF Israel archive](https://www.rsssf.org/tablesi/israhist.html) — final tables.
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
