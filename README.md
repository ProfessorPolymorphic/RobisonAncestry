# Robison Ancestry

**Live site:** https://professorpolymorphic.github.io/RobisonAncestry/ — interactive chart, searchable
people index, every sourced claim, conflicts and open items. It is rebuilt automatically from the
YAML on every push to `main`.

A digital model of the Robison family tree, built so that paper records can be
assimilated one document at a time without losing track of *where each fact came from*
or *where the sources disagree*.

```
data/
  people.yaml      one entry per person — names, events (birth, death, …), notes, todos
  families.yaml    unions (partners + marriage events) and their children, with link confidence
  sources.yaml     every document/index/website that facts are cited from
  places.yaml      gazetteer: place ids → full names (+ lat/lon for a future map)
famtree/           the toolkit (Python 3, needs only PyYAML)
tree.py            command-line entry point
build/             generated output (chart SVG/HTML, GEDCOM) — never edit by hand
_site/             generated website (tree.py site) — deployed by GitHub Actions, not committed
scans/             put digitized paper here; reference files from sources.yaml
.github/workflows  the Pages build
```

Original inputs: `family tree 001.jpg` (the typed chart) and `The-Robison-Line_1.docx` (the 2026 research report).

## Commands

```bash
python3 tree.py validate                          # check the YAML (run after every edit)
python3 tree.py show herbert-barringer-robison-1904   # everything known about one person (id or name fragment)
python3 tree.py search falconer                   # find people
python3 tree.py lineage barrie-robison-1970       # direct line from the earliest ancestor
python3 tree.py conflicts                         # facts where sources disagree
python3 tree.py todo                              # open questions, weak links, missing vitals
python3 tree.py render --focus barrie-robison-1970    # build/robison-tree.svg + .html
python3 tree.py render --root samuel-robison-1802 --private --name samuel-branch
python3 tree.py gedcom                            # build/robison.ged — import into Gramps / Ancestry / FamilySearch
python3 tree.py site                              # _site/ — the website; serve with: python3 -m http.server -d _site
```

Setup: `pip install -r requirements.txt` (just PyYAML).

## Editing on GitHub

You don't need a local checkout to contribute. Open a file under `data/` on GitHub, press the
pencil icon, edit, and commit. The Actions workflow validates the YAML and redeploys the site in
about a minute; if validation fails the site is left as it was and the commit shows a red ✗ —
click it to read the error (usually an unquoted comma or an unknown id).

`render` options: `--root` (default: the ancestor with the most descendants), `--focus`
(draw the direct line heavy), `--private` (replace dates of living people with "living"),
`--title`, `--name`.

## The three ideas behind the model

**1. Facts cite sources.** Every name, event and parent-child link carries `sources: [...]`
referring to ids in `sources.yaml`. A fact without a source is flagged by `validate`.

**2. Conflicting claims coexist.** A person can have two `birth` events. The first listed
(or the one marked `preferred: true`) is what charts show; the rest are kept with their
sources. `tree.py conflicts` lists only the *incompatible* pairs — `abt 1838` vs
`1839-11-07` is a refinement and stays quiet; `1868-03-19` vs `1869-03-19` is a conflict.
Names work the same way (`kind: conflict` vs `kind: variant` for spelling/indexing differences).

**3. Links have confidence.** Each child entry in a family says how well the parent link
is established:

| confidence   | meaning |
|--------------|---------|
| `documented` | a record states the relationship (birth registration, obituary, marriage register) |
| `inferred`   | a chain of reasoning from records (census household adjacency, naming pattern) |
| `stated`     | asserted by a compiled source such as the typed chart — not yet checked (the default) |
| `unverified` | a placement guess; needs confirmation |

The chart draws these as black / black / grey / dashed connectors.

## Editing cheat-sheet

```yaml
- id: new-person-1900          # lowercase slug. Opaque: never rename it when a date changes.
  names:
    - {given: Jane, surname: Doe, nickname: Jenny, sources: [typed-chart]}
    - {given: Jane, surname: Dough, kind: variant, sources: [census-1911], note: "Indexed as Dough."}
  sex: F
  living: false                # optional; otherwise guessed (no death + born <100 years ago → living)
  events:
    - {type: birth, date: 1900-02-03, place: carman-mb, sources: [mb-vitals]}
    - {type: death, date: abt 1960, sources: [typed-chart], note: "Chart has year only, rest smudged."}
  notes: Free text, markdown ok.
  todo:
    - Find her marriage.
```

* **Dates:** `1869` · `1869-03` · `1869-03-19` · `abt 1802` · `bef 1851` · `aft 1871` · `bet 1802 and 1804`.
* **Event types:** birth, death, burial, marriage, divorce, immigration, emigration, residence,
  occupation, education, military, census, baptism, other.
* **Quote any value that contains a comma** when using the one-line `{...}` form, or YAML
  will silently cut it off. `validate` now catches this (it reports an "unknown key").
* **Places:** add to `places.yaml` first, then reference by id.
* **New source / scan:** add an entry to `sources.yaml`, drop the image in `scans/`, list it
  under `files:`. Then go through the document and add/adjust events citing that id.
  If it disagrees with what is already there, *add a second event* — don't overwrite.

## Where things stand (Aug 2026)

Three inputs were merged:

| source id | what it is |
|---|---|
| `typed-chart` | the cousin's typewritten chart (`family tree 001.jpg`) — nine generations, exact dates, no citations |
| `robison-line-report` | the 2026 research report (`The-Robison-Line_1.docx`) — censuses, vital indexes, cemetery, newspapers |
| `golden-field-lineage` | the working summary (`The Golden–Field–Nakusp Robison Lineage.md`) — found the 1904 county history, the Manitoba Historical Society biography and Bert's 2013 obituary |
| `journey-so-far-2006` + eight document sources | Colby's Aug 2026 photographs (`scans/PicturesfromColbyAug23_2026/`) of Paul A. Robison's bound family history **"A Journey So Far"** (2006) and loose family papers: headstone transcriptions, the 1965 BC death certificate, Jean's memorial card, Bill's funeral programs, the Spencer Lewis clipping and the 1911 Lewis family photo |

They agree on the spine (Hugh → Samuel → William Arthur → Herbert Edward → Herbert Barringer →
Bill → Barrie/Zane). `tree.py conflicts` tracks 13 disagreements, the notable ones being:

1. **Hugh and Rebecca's dates** — the headstones (Nov 1762 – 18 Jun 1844; Oct 1767 – 31 Aug 1850)
   contradict the retyped chart (1766–1842; 1766–1852). Headstones now preferred.
2. **Jane Arthur vs Jane Buchanan** — her headstone reads JANE ARTHUR (Jan 1814 – 28 Mar 1872),
   effectively refuting the report's Buchanan inference.
3. **Samuel's death** — headstone 24 Aug 1876 vs Ontario index 1875.
4. **Herbert Edward's birth** — 19 Mar 1869 (vitals index, MHS, census age) vs 19 Mar 1868 (his own
   headstone, both charts and Paul's book). Genuinely unresolved; he was born pre-registration.
5. **Anna Falconer's birth** — 30 Dec 1880 (stone) vs 31 Dec 1880 (index) vs 1882 (MHS).
6. **Herbert B. & Jean's marriage** — 12 Apr 1927 (chart) vs c.1930 (report's guess). With Jean now
   known to be an Eastport, Idaho girl, the marriage likely happened in the Idaho/BC border country.

What each source uniquely contributed:

* **Chart:** Hugh Robison (1766–1842) and Rebecca Dougall, eight siblings of Samuel, exact
  day-month-year dates throughout, and Bert's whole branch (Herbert Colby, Nancy Lee and their children).
* **Report:** the Nakusp cemetery stone and BC death index that tie "H. Barrie" to Herbert
  Barringer b. 1904; the Eastport border crossing; Jean as Nakusp librarian; Bill's and Zane's careers.
* **Working summary:** the 1904 history *Pioneer Life on the Bay of Quinte* (New Brunswick
  c.1792 → Hillier Township c.1806, Robison's Point, Dr. William Dougall) and the MHS biography,
  which names Herbert Edward's parents outright — so the III←II link is now `documented`, not
  inferred — plus Herbert Edward as lawyer, mayor of Carman 1911–13 and KC; and Bert's obituary
  (Field BC childhood, 43 years CP Rail, d. Golden 25 Aug 2013).

What the Aug 2026 photo trove settled: Jean's family (Spencer & Eva Lewis of Eastport, Idaho —
which also explains Herbert's Eastport border crossing), the 1965 death certificate (12 May 1965,
and "Beringer" is the registered spelling, not an index error), Bill's exact death date, the
Barringer ancestry (Dr. Walter Levi Barringer; Nancy Maria Weeks; Samual Weeks & Katherine Winne),
the chart's authorship (Bert), and Ivan's whole branch including Paul Athol Robison, author of
"A Journey So Far". Paul also reports that a professional genealogist **disproved** the family's
United Empire Loyalist claims in 2004, and that the family bible spells "Rebeca" and "Samuel".

### Open questions

* **Herbert Edward: 1868 or 1869?** Stone and family papers vs index and census. A delayed birth
  registration or baptism record would settle it.
* **Tyrone vs Clan Gunn.** A Presbyterian Tyrone origin suggests Ulster-Scots background but does
  not reach Caithness. Paul's book asserts the Gunn sept connection (his arms carry Gunn elements);
  the documentary trail still starts at Hugh. Land petition or Y-DNA.
* **Annie's parents** — a Falconer father and a Campbell mother, from Scotland 1850s/60s; names unknown.
* **Spencer and Eva Lewis** — full dates and Eva's maiden name; the Boundary County, Idaho censuses
  (1910/20/30) would give the household.
* `tree.py todo` lists the rest.

## Generation numbering

The chart numbers the root generation **I**, so with Hugh as root, Samuel is II and Barrie is
VIII. The 2026 report starts at Samuel = I; subtract one to compare. Render with
`--root samuel-robison-1802` to get the report's numbering.
