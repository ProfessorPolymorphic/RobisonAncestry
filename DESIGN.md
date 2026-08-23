# Robison Ancestry — design system

## Theme
Light. Scene: a cousin reading family records at a desk lamp in the evening, the mood of
opening a leather-bound ledger. Warm parchment paper, never white.

## Color (OKLCH, Clan Gunn tartan)
- `--pine`   oklch(0.33 0.06 165)  deep tartan green — masthead, links, primary
- `--pine-deep` oklch(0.26 0.05 170) — hero/masthead ground (Committed strategy: green carries the identity surfaces)
- `--navy`   oklch(0.33 0.06 250)  secondary structure
- `--red`    oklch(0.52 0.19 22)   the tartan overcheck — thin accents, active states, warnings
- `--paper`  oklch(0.965 0.012 95) parchment page ground
- `--card`   oklch(0.985 0.007 95) raised surfaces
- `--ink`    oklch(0.25 0.02 160)  text (green-tinted near-black; never #000)
- `--muted`  oklch(0.47 0.025 155)
- `--rule`   oklch(0.87 0.02 100)

Confidence semantics (must stay consistent site + SVG chart):
- documented → pine green · inferred → bronze oklch(0.55 0.1 80) · stated → muted grey · unverified → tartan red

Signature detail: the "sett rule" — a thin repeating stripe band (pine/black/navy with a
red hairline) used once under the masthead. Evokes the tartan without plaid cosplay.

## Typography
- Display & narrative: **Libre Caslon Text** — Caslon was the face of 18th-century
  British/colonial printing; Hugh Robison was born 1762. Period voice, earned.
- UI, tables, nav: **Libre Franklin** (ledger clarity at small sizes).
- IDs and dates-in-tables: system mono.
- Scale ≥1.25 ratio; hero clamp(34px, 5.5vw, 54px).

## Layout
- Reading column max 72ch for narrative; data tables full width to 1400px.
- Landing page: green hero band → story → the direct line (spine) → evidence model → status.
- No side-stripe borders, no gradient text, no icon-card grids.

## Chart (SVG)
Warm paper ground, alternating generation bands, serif roman generation numerals,
14px names / 12.5px facts, pine edges for documented/inferred, grey for stated,
dashed red for unverified, heavy pine outline for the direct line.
