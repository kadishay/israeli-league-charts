# Publishing the charts to Wikipedia

What is already published, and how to add or update one without re-deriving any of it.

---

## What is live

**`data/wikipedia.json` is the ledger** — every club, both languages, the Commons file name,
the article, and whether the image is actually placed. Read it rather than this prose when
deciding what to update; the summary below will drift.

The scope is the **14 clubs of the 2026/27 Ligat ha'Al**. 28 files on Wikimedia Commons
(English and Hebrew labels for each), uploaded 16 September 2026 by [User:Kadishay], all
**CC BY-SA 4.0**, all `{{own}}` work. All 14 English charts are placed; **no Hebrew chart is
placed**, for the reason below.

The naming follows the precedent this project copied,
[`File:Manchester United FC League Performance.svg`](https://commons.wikimedia.org/wiki/File:Manchester_United_FC_League_Performance.svg).
Note the file names use `FC` with no full stops, while the English article titles use `F.C.`

Each chart sits in the **History** section of its article, directly after the heading.

**The Hebrew files are uploaded but placed nowhere.** See *The Hebrew Wikipedia block* below.

---

## Updating a chart each season

This is the common case, and it is much smaller than it looks: **an update is a Commons
re-upload under the same file name.** No article is touched, because the article points at a
name and Commons serves whatever version that name currently holds.

```sh
python3 scripts/fetch.py && python3 scripts/fetch_he.py && python3 scripts/fetch_en.py
python3 scripts/parse.py && python3 scripts/parse_he.py && python3 scripts/parse_en.py
python3 scripts/parse_ifa.py
python3 scripts/build.py
python3 scripts/render.py
git commit -am "…" && git push          # Pages redeploys, and raw.githubusercontent updates
```

Then re-upload each changed file with `ignorewarnings=1` (the warning is only "a file with
this name exists", which is the point) and a comment naming the season, the way the
Manchester United file logs each year's update.

Two things to get right before uploading:

- **Wait until the position is final.** The Manchester United file is updated "once final
  table position became a mathematical certainty", and `LAST_SEASON` in `render.py` has to be
  bumped for the new season to appear at all.
- **Check `always_chart` in `data/club_status.json`** if a charted club was promoted from a
  tier whose coverage has stopped.

---

## Adding a club

### 1. Check the chart is worth publishing

`docs/CLUBS.md` has the per-club unknown count. A club with many dotted columns is honest
but invites "this chart is mostly gaps". The clubs with none: Maccabi Tel Aviv, Hapoel Tel
Aviv, Maccabi Petah Tikva, Beitar Jerusalem, Hapoel Kfar Saba, Bnei Sakhnin, Ashdod S.C.,
Hapoel Be'er Sheva, Hapoel Ramat Gan, Hapoel Rishon LeZion, Maccabi Jaffa, Maccabi Netanya,
M.S. Kafr Qasim, M.S. Kiryat Yam.

### 2. Upload to Commons

Source the SVG from `raw.githubusercontent.com`, which sets `Access-Control-Allow-Origin: *`
so a browser on commons.wikimedia.org can fetch it directly:

```
https://raw.githubusercontent.com/kadishay/israeli-league-charts/main/out/<slug>.svg
https://raw.githubusercontent.com/kadishay/israeli-league-charts/main/out/<slug>.he.svg
```

File page wikitext — the `other fields` block is the part the Manchester United file lacks,
which is why it sits in Commons' maintenance category *Information graphics without data
source*:

```wikitext
=={{int:filedesc}}==
{{Information
|description={{en|1=Chart of the league performance of [[:en:<ARTICLE>|<CLUB>]] in the Israeli football league system, from <FIRST> to 2025–26. Position is counted down the whole pyramid, so each tier continues the one above; the band boundaries step because the top flight has held between 10 and 18 clubs. Hatched columns are seasons that were never played.}}
{{he|1=גרף מיקומי [[:he:<HE ARTICLE>|<HE CLUB>]] בליגות הכדורגל בישראל, מעונת <FIRST HE> ועד עונת 2025/2026.}}
|date=<DATE>
|source={{own}}
|author=[[User:Kadishay|Kadishay]]
|other fields={{Information field|name=Data sources|value=
* [https://www.rsssf.org/tablesi/israhist.html RSSSF Israel archive] – final league tables, 1949–50 to 2024–25
* [https://www.football.org.il/ Israel Football Association] – official league tables
* Per-season league articles on the English and Hebrew Wikipedias
}}
}}

=={{int:license-header}}==
{{self|cc-by-sa-4.0}}

[[Category:<COMMONS CLUB CATEGORY>]]
[[Category:Table rank diagrams]]
```

Verify the club category exists first — Commons uses `Beitar Jerusalem FC`, not
`Beitar Jerusalem F.C.`, and guessing produces a redlink.

### 3. Place it in the article

```wikitext
[[File:<FILE>|thumb|upright=1.8|A chart showing the progress of <CLUB> through the
[[Israeli football league system]], from <FIRST> to the present|alt=refer to caption]]
```

Immediately after the `==History==` heading, which is where the Manchester United article
puts its chart. `upright=1.8` gives about 450px; the default thumb width is far too small for
a chart 2.2 times wider than it is tall.

**Link the first season only if the article exists and is the right competition.** This is
the step that nearly put two wrong links into articles: Beitar Jerusalem's first recorded
season was in Liga Meuhedet and Hapoel Be'er Sheva's was in **Liga Gimel**, the fourth tier,
so neither belongs to the `Liga Alef` season article the year would suggest. Take the league
from `data/seasons.csv`, not from the year.

Hebrew equivalent, floated left because that is the trailing side in a right-to-left layout:

```wikitext
[[קובץ:<FILE>|ממוזער|שמאל|400px|גרף המציג את מיקומי <CLUB> בליגות הכדורגל בישראל, מעונת <FIRST> ועד היום]]
```

### 4. Check the rendered thumbnail, not the local file

Commons rasterises with librsvg, which is stricter than a browser — see decision 21 in
`DECISIONS.md` for what the renderer does not support. Thumbnail generation is also
asynchronous: a blank image right after an edit usually means the thumbnail has not been
built yet, so reload with a cache-buster before concluding anything is wrong.

---

## The Hebrew Wikipedia block

Every Hebrew article edit was refused by **abuse filter 109**,
*הגדרת משתמש ותיק לפי החלטת הקהילה*. That is a community-decided restriction and is not to
be worked around; the filter is the community's answer, not an obstacle to route past.

The requirement is **30 days since registration and 100 edits**. The account registered in
2019, so only the edit count is short — 3 at the time of writing. All fourteen Hebrew files
are uploaded, so placing them later is one line of wikitext each.

Three ways through, in rising order of how much they ask of other people:

1. **Make the edits.** 97 ordinary contributions and the filter stops firing.
2. **Request the edit** on each article's talk page — **done on 16 September 2026**, one
   section per article, each naming the file and giving the exact wikitext to paste. Note
   there is no `{{בקשת עריכה}}` template on he.wikipedia; it does not exist, so a plain,
   clearly written talk section is the form. Talk namespace is not filtered, only articles.
3. **Ask more widely** at [ויקיפדיה:הכיכר](https://he.wikipedia.org/wiki/ויקיפדיה:הכיכר) whether
   the community wants the charts at all, which is worth doing before adding fourteen.

---

## Things worth not relearning

- **Don't link the GitHub Pages site from an article body.** As a source on the Commons file
  page it is expected; in the article it reads as self-promotion under
  [WP:ELNO](https://en.wikipedia.org/wiki/Wikipedia:External_links#Links_normally_to_be_avoided).
- **A chart built by an editor is not original research.**
  [WP:OI](https://en.wikipedia.org/wiki/Wikipedia:No_original_research#Original_images) allows
  it as long as it introduces no unpublished argument, and the Manchester United chart is the
  standing precedent. What it must not do is cite Wikipedia as its source
  ([WP:CIRCULAR](https://en.wikipedia.org/wiki/Wikipedia:Reliable_sources#Wikipedia_and_sources_that_mirror_or_use_it)),
  which is why the file page lists RSSSF and the IFA.
- **Don't bulk-add.** Five charts appearing across major articles in one hour from an account
  with no edit history is a pattern that attracts reverts. If one comes back, the answer is
  the talk page, not re-adding it.
