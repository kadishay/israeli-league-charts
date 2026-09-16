# Clubs: identity, lineage, and what is known per club

Club identity is the hardest part of this dataset. Three sources spell the same club three
ways, clubs merge and de-merge, and Hebrew Wikipedia points historical names at a club's
current article — which resolves lineage for free but also over-merges.

## Clubs and identity

### Which clubs are charted

The 32 with the most top-flight seasons, **plus every club in the current top two tiers** —
42 in all. Ten are there because of the second half of that rule, including Hapoel Kfar
Shalem and Hapoel Afula, which have 58 and 49 recorded seasons but little top-flight
history. Two cannot be caught by any rule over this dataset and are named in
`club_status.json` under `always_chart`: Maccabi Ahi Nazareth and Maccabi Kiryat Gat climbed
back up through tiers whose coverage stops in 2020/21.

### How identity is resolved

One canonical name per club lineage, with a per-source alias file:

| File | Maps | Count |
|---|---|---|
| `data/aliases.json` | RSSSF spelling → canonical | 97 |
| `data/aliases_he.json` | Hebrew article name → canonical | 165 |
| `data/aliases_en.json` | English article name → canonical | 55 |

English names that already match a canonical name are accepted automatically, so
`aliases_en.json` only holds genuine differences. Each parser reports what it could not map.

Two guards sit behind the alias files, because an alias error is much harder to see than a
missing row:

1. **Founding years** in `data/club_status.json`. `build.py` drops any row that predates a
   club and reports it — see decision 5.
2. **Shallowest tier, then national** when a club has several rows for one season — see
   decision 7.

## Lineage decisions worth knowing

| Lineage | Treated as | Basis |
|---|---|---|
| Hapoel + Maccabi Kiryat Shmona → *Hapoel Ironi* (2000–02) → *Ironi* Kiryat Shmona | Predecessors separate; 2000 onward is Ironi | The club was formed by the 2000 merger. RSSSF still heads the 2007/08 table with the pre-merger name |
| Beitar Tel Aviv / Beitar Shimshon / Beitar Tel Aviv Bat Yam / Ramla | One club: Beitar Tel Aviv | Continuous club through renames and the Shimshon merger |
| Shimshon Tel Aviv | Separate from Beitar | Left the merger in 2011 and re-formed; the merged club's seasons sit under Beitar, and the chart draws them as a second line — see *Played as* below |
| Hapoel Nazareth Illit / הפועל נצרת עילית | Hapoel Nof HaGalil | Renamed 2019 |
| Hapoel Tzafririm Holon | Hapoel Holon | Same lineage |
| Hapoel Ironi Rishon LeZion | Hapoel Rishon LeZion | Same lineage |
| Maccabi Kabilio Jaffa | Maccabi Jaffa | Renamed |
| M.S. Ashdod / Ashdod SC / Agudat Sport Ashdod / F.C. Ashdod | Ashdod S.C. | Same club; *Maccabi Ironi Ashdod* and *Hapoel Ashdod* are the 1999 merger partners and stay separate |
| Hakoah Ramat Gan / Hakoah Amidar Ramat Gan | One club, founded 1962 | Infobox founding year. **Kept separate from Hakoah Tel Aviv** — see the open question below |
| Maccabi Nes Tziona / Maccabi Nes Ziona | One club | Spelling split across sources |
| British Police (המשטרה הבריטית) | **British Police** | Hebrew Wikipedia and RSSSF agree; only English Wikipedia's article title differs |
| Sektzia Ness Ziona / Sektzia Nes Tziona | One club | Spelling split; distinct from *Maccabi* Nes Ziona |

Roughly 900 lower-tier club names keep their English spelling rather than being merged. Their
rows are kept: dropping a club understates its division's size and shifts every position
below it.

### Played as another club

`club_status.json` carries a `played_as` block for the one case where a club's senior side
took the field under another club's name and this project keeps the two apart:

| Club | Seasons | Played as | Rows recorded under |
|---|---|---|---|
| Shimshon Tel Aviv | 2000/01 – 2010/11 | Beitar Shimshon Tel Aviv | Beitar Tel Aviv |

The chart draws those seasons as a dashed second line in the other club's colour, and names
both lines in the legend — the same statement English Wikipedia's club charts make with
"as Newton Heath" before "as Manchester United". The spell ends in 2011, when the club
merged with Ironi Ramla and Shimshon withdrew; the dormant span runs on to 2013 because
Shimshon had no senior side of its own until 2014.

This is deliberately not used for a merger of two clubs into a new one. Ashdod S.C. and
Ironi Kiryat Shmona each have two predecessors with full records of their own, and drawing
one of them as the new club's earlier self would pick a parent arbitrarily.

## Per club

Generated from `data/seasons.csv`. "Unknown" counts only seasons inside the club's active
life, excluding dormant spells and seasons with no table at that tier — see decisions 4 and 5.
"Best tier" is the highest level the club reached.

| Club | First | Recorded | Tier 1 | Titles | Best tier | Unknown | pre-1949 | Top two tiers now |
|---|---|---|---|---|---|---|---|---|
| Maccabi Tel Aviv | 1931/1932 | 86 | 86 | 25 | 1 | — | — | yes |
| Hapoel Tel Aviv | 1931/1932 | 86 | 83 | 13 | 1 | — | — | yes |
| Maccabi Petah Tikva | 1931/1932 | 86 | 75 | — | 1 | — | — | yes |
| Maccabi Haifa | 1931/1932 | 78 | 70 | 15 | 1 | 8 | 8 | yes |
| Maccabi Netanya | 1939 | 80 | 69 | 5 | 1 | — | — | yes |
| Hapoel Haifa | 1931/1932 | 83 | 68 | 1 | 1 | 3 | 3 | yes |
| Hapoel Petah Tikva | 1934/1935 | 81 | 63 | 6 | 1 | 3 | 3 | yes |
| Beitar Jerusalem | 1949/1950 | 74 | 57 | 6 | 1 | — | — | yes |
| Bnei Yehuda Tel Aviv | 1941/1942 | 76 | 55 | 1 | 1 | 2 | 2 | yes |
| Hapoel Be'er Sheva | 1954/1955 | 71 | 52 | 6 | 1 | — | — | yes |
| Hapoel Jerusalem | 1931/1932 | 78 | 43 | — | 1 | 7 | 7 | yes |
| Beitar Tel Aviv | 1937 | 77 | 41 | — | 1 | 1 | — | — |
| Hapoel Kfar Saba | 1946/1947 | 75 | 40 | 1 | 1 | — | — | yes |
| Maccabi Jaffa | 1949/1950 | 73 | 32 | — | 1 | 2 | — | yes |
| Shimshon Tel Aviv | 1949/1950 | 56 | 28 | — | 1 | 5 | — | — |
| Ashdod S.C. | 1999/2000 | 27 | 26 | — | 1 | — | — | yes |
| Hapoel Ramat Gan | 1939 | 80 | 25 | 1 | 1 | — | — | yes |
| Bnei Sakhnin | 1994/1995 | 32 | 21 | — | 1 | — | — | yes |
| Hapoel Rishon LeZion | 1938 | 81 | 20 | — | 1 | — | — | yes |
| Hakoah Ramat Gan | 1962/1963 | 57 | 20 | 2 | 1 | 5 | — | — |
| Ironi Kiryat Shmona | 2000/2001 | 23 | 17 | 1 | 1 | 3 | — | yes |
| Hapoel Hadera | 1939 | 77 | 16 | — | 1 | 8 | 3 | yes |
| Hapoel Holon | 1949/1950 | 64 | 12 | — | 1 | 5 | — | — |
| Maccabi Rehovot | 1933/1934 | 58 | 12 | — | 1 | 31 | 2 | — |
| Maccabi Nes Ziona | 1931/1932 | 13 | 12 | — | 1 | 1 | 1 | — |
| Hapoel Acre | 1949/1950 | 72 | 10 | — | 1 | 2 | — | yes |
| Maccabi Herzliya | 1939 | 63 | 10 | — | 1 | 16 | 5 | yes |
| Hakoah Tel Aviv | 1934/1935 | 21 | 10 | — | 1 | — | — | — |
| Hapoel Ra'anana | 1939 | 67 | 9 | — | 1 | 13 | 2 | yes |
| Hapoel Yehud | 1954/1955 | 39 | 8 | — | 1 | 6 | — | — |
| Hapoel Ironi Herzliya | 1937 | 68 | 7 | — | 1 | 14 | — | — |
| Maccabi Rishon LeZion | 1939 | 9 | 7 | — | 1 | 23 | — | — |
| Maccabi Bnei Reineh | 2005/2006 | 11 | 4 | — | 1 | 13 | — | yes |
| Hapoel Nof HaGalil | 1962/1963 | 56 | 3 | — | 1 | 7 | — | yes |
| Maccabi Ahi Nazareth | 1974/1975 | 49 | 2 | — | 1 | 3 | — | yes |
| Ironi Tiberias | 2006/2007 | 18 | 2 | — | 1 | 2 | — | yes |
| Maccabi Kiryat Gat | 1962/1963 | 54 | 1 | — | 1 | 9 | — | yes |
| Hapoel Kfar Shalem | 1962/1963 | 61 | — | — | 2 | 1 | — | yes |
| Hapoel Afula | 1957/1958 | 49 | — | — | 2 | 22 | — | yes |
| Ironi Modi'in | 2009/2010 | 13 | — | — | 2 | 6 | — | yes |
| M.S. Kafr Qasim | 2019/2020 | 7 | — | — | 2 | — | — | yes |
| M.S. Kiryat Yam | 2025/2026 | 1 | — | — | 2 | — | — | yes |

**14 of the 42 have no unknown seasons at all.** The other 28 account for 221 between them,
36 before 1949 and 185 after.

That total went up, not down, when the chart stopped banding tier five. A season in Liga
Gimel used to sit on a strip at the floor and now has no row to sit on, so it is marked the
same way a season with no source is — the position is still in `seasons.csv`, but the chart
no longer places it. Maccabi Rehovot, who spent decades down there, carry 31 of the 221 for
that reason alone.

## Why the unknown seasons are unknown

Every club with unknown seasons was checked against its own article. The reasons fall into
four groups.

**Mandate-era districts that no article tabulates — 36 seasons.** Between 1934/35 and
1946/47 both the top flight and the second tier were played district by district, and the
sources cover some districts and not others. The Hebrew 1939 top-flight article names the
Haifa division in prose — "13 clubs in Haifa Division A" — but carries no table; the English
articles have Tel Aviv, Samaria and Southern only. One level down, Hapoel Jerusalem is named
in the prose of the 1937 and 1946/47 Liga Bet articles and appears in none of their tables.
Worst affected: Maccabi Haifa 8, Hapoel Jerusalem 7, Maccabi Herzliya 5.

**No football article at all — 38 seasons.** Maccabi Rishon LeZion (22) and Maccabi Rehovot
(16 post-1949) have Hebrew pages that are sports-association stubs. Nothing to extract.

**Tiers 4–6, where coverage is patchy, and tier 5–6 seasons the chart does not band.**
Maccabi Rehovot 31, Maccabi Rishon LeZion 23, Hapoel Afula 22, Maccabi Herzliya 16,
Hapoel Ironi Herzliya 14, Hapoel Ra'anana 13. English Wikipedia has roughly
30 Liga Gimel seasons out of about 70 and whole years are absent — 1990–91 Liga Gimel has no
article. These clubs' articles give founding years and narrate promotions and relegations but
not finishing positions. In several cases the article does state the *tier* — Bnei Sakhnin
played Liga Gimel from 1982 until promotion in 1989/90; Hapoel Acre were in Liga Gimel until
promoted at the end of 1953/54; Hapoel Ironi Herzliya were in the third tier until 1959/60 —
which is more than the chart shows, but a tier without a position is not something the
current model can draw.

**Liga Gimel in the early 1950s — 2 seasons.** Shimshon Tel Aviv's 1951/52 and 1953/54. They
are in neither Liga Bet article, Hebrew or English, for either season, so they were a tier
below; and no Liga Gimel article exists for 1951/52 or 1953/54 in either language. The league
did run — `structure.json` has Liga Gimel from 1951 — so this is a missing table rather than
a missing competition.

**Resolved by reading the article** — no longer unknown, listed so the checks are not
repeated: Shimshon Tel Aviv's 2000–2013 (merger, then dormant), Hapoel Yehud's 1998–2007
(dissolved), the 2019/20 COVID freeze below tier two (seven clubs), Ironi Kiryat Shmona's
2007/08 (RSSSF's pre-merger name), and Hakoah Ramat Gan's 1938–1946 rows (an over-merged
alias — the club was founded in 1962).

**Resolved by reading the IFA's own tables** — the league-seasons in `data/ifa/` closed 12
unknowns across six charted clubs, the ones Wikipedia has no article for at all: 2016/17 and
2018/19 Liga Bet, and Liga Alef from 2021/22 on.

**Still playing, but in a season with no table.** The IFA stopped Liga Alef, Bet and Gimel in
2025/26 because of the war (see `structure.json`), so five charted clubs — Shimshon Tel Aviv,
Maccabi Kiryat Gat, Maccabi Ahi Nazareth, Hapoel Ironi Herzliya and Hakoah Ramat Gan — played
a season that produced no final position. The abandoned captures in `data/ifa/` record that
they were there, which is what stops the chart ending their line in 2024/25 and drawing the
years since as though the club had folded. Their unknown counts rose as a result: this is a
club whose whereabouts are unrecorded, not a club that does not exist.

## Open question: the Hakoah lineage

Hebrew Wikipedia treats Hakoah Tel Aviv and Hakoah Ramat Gan as one continuous club — Hakoah
Berlin 1905 → Hakoah Vienna 1909 → Hakoah Tel Aviv 1934 → Ramat Gan — and narrates the whole
line in one article. English Wikipedia keeps them separate, and the Hebrew infobox itself
gives the founding year as **1962**.

They are currently separate, which is why Hakoah Tel Aviv's 21 recorded seasons end in the
1950s and Hakoah Ramat Gan's begin in 1962/63. Merging them would produce one continuous
chart and fill several early unknown seasons, but it contradicts the founding year that is
being used as an integrity check. Worth a decision; not one to make silently.
