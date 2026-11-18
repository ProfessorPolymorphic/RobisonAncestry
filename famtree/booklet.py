"""A printable family-register booklet (HTML laid out for US Letter; print to PDF with Chrome).

Made for keeping in the family Bible: a title page, the direct line, every descendant of the
earliest ancestor as an indented register, the families who married in, the dates the records
disagree on, and ruled pages for handwritten additions. Ink-light: white ground, green accents.
"""
from __future__ import annotations

import datetime as _dt
from html import escape
from typing import List, Optional, Set

from .model import Event, Family, Person, Tree

ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII"]


def e(s) -> str:
    return escape(str(s), quote=True)


class Booklet:
    def __init__(self, tree: Tree, root: Person, focus: Optional[Person]):
        self.t = tree
        self.root = root
        self.focus = focus
        self.disputed = {(c["owner"], c["kind"]) for c in tree.conflicts()}
        self.line: List[Person] = self._line(focus) if focus else [root]
        self.line_ids = {p.id for p in self.line}

    # ----- helpers -------------------------------------------------------
    def _line(self, p: Person) -> List[Person]:
        chain, cur = [], p
        while cur:
            chain.append(cur)
            if cur.id == self.root.id:
                break
            pars = self.t.parents(cur)
            cur = next((x for x in pars if x.id == self.root.id or self.root.id in self.t.ancestors(x)), None)
        return list(reversed(chain))

    def place(self, pid) -> str:
        return self.t.place_name(pid)

    def ev(self, owner: str, label: str, ev: Optional[Event], full_place=True) -> str:
        if not ev or not (ev.date.known or ev.place):
            return ""
        s = f"<span class=lbl>{label}</span> "
        if ev.date.known:
            s += e(ev.date.display())
            if (owner, ev.type) in self.disputed:
                s += "<sup class=dag>†</sup>"
        if ev.place:
            s += (", " if ev.date.known else "") + e(self.place(ev.place) if full_place else self.place(ev.place).split(",")[0])
        return f"<span class=ev>{s}</span>"

    def vitals(self, p: Person, full_place=True) -> str:
        parts = [self.ev(p.id, "b.", p.birth, full_place), self.ev(p.id, "d.", p.death, full_place)]
        parts = [x for x in parts if x]
        if not p.death and p.is_living() and not parts:
            parts.append("<span class=ev>living</span>")
        return " ".join(parts)

    def name(self, p: Person, cls="nm") -> str:
        n = p.name
        given = e(n.given)
        if n.nickname:
            given += f" <span class=nick>“{e(n.nickname)}”</span>"
        sur = f" <span class=sur>{e(n.surname)}</span>" if n.surname else ""
        return f"<span class={cls}>{given}{sur}</span>"

    def parents_of(self, p: Person) -> str:
        pars = self.t.parents(p)
        if not pars:
            return ""
        word = {"M": "son", "F": "daughter"}.get(p.sex or "", "child")
        return f"<span class=par>{word} of " + " &amp; ".join(e(x.display_name()) for x in pars) + "</span>"

    def other(self, fam: Family, p: Person) -> Optional[Person]:
        return next((self.t.people[x] for x in fam.partners if x != p.id and x in self.t.people), None)

    # ----- sections ------------------------------------------------------
    def title_page(self) -> str:
        r, f = self.root, self.line[-1]
        start = r.birth.date.year if r.birth and r.birth.date.known else None
        origin = self.place(r.birth.place).split(",")[0] if r.birth and r.birth.place else ""
        n_people = len(self.t.descendants(r)) + 1
        today = _dt.date.today()
        return f"""
<section class="page title">
  <div class=sett></div>
  <p class=kicker>A family register</p>
  <h1>The Robison Family</h1>
  <p class=sub>Our Roots, Our Story</p>
  <div class=orn>❦</div>
  <p class=span>From <b>{e(r.display_name())}</b>{f' of {e(origin)}' if origin else ''}{f', born {start}' if start else ''},<br>
  through {len(self.line)} generations to <b>{e(f.display_name())}</b></p>
  <p class=count>{n_people} descendants recorded · {len(self.t.people)} people in all</p>
  <div class=foot>
    <p>Prepared for the Robison family Bible<br>Compiled {today.strftime('%B %Y').replace(' 0', ' ')} from the family’s papers,<br>headstones, church and civil records</p>
  </div>
</section>"""

    def direct_line(self) -> str:
        rows = []
        for i, p in enumerate(self.line):
            spouse_html = ""
            nxt = self.line[i + 1] if i + 1 < len(self.line) else None
            fam = next((f for f in p.families_as_partner if nxt and any(c.person == nxt.id for c in f.children)), None)
            if fam is None and p.families_as_partner:
                fam = p.families_as_partner[0]
            if fam:
                sp = self.other(fam, p)
                if sp:
                    m = self.ev(fam.id, "m.", fam.marriage, full_place=False)
                    spouse_html = (f"<div class=sp>married {self.name(sp, 'spn')}"
                                   f"{' · ' + m if m else ''}<br><span class=spv>{self.vitals(sp, False)}</span></div>")
            rows.append(f"""
  <li>
    <div class=gen>{ROMAN[i]}</div>
    <div class=card>
      <div class=who>{self.name(p)}</div>
      <div class=vit>{self.vitals(p)}</div>
      {spouse_html}
    </div>
  </li>""")
        return f"""
<section class="page line">
  <h2>The Direct Line</h2>
  <p class=intro>{len(self.line)} generations, father to son, from {e(self.line[0].display_name())} to {e(self.line[-1].display_name())}.</p>
  <ol class=spine>{''.join(rows)}
  </ol>
</section>"""

    def register(self) -> str:
        out: List[str] = []
        seen: Set[str] = set()

        def walk(p: Person, depth: int, num: str):
            if p.id in seen:
                return
            seen.add(p.id)
            on_line = p.id in self.line_ids
            out.append(f"""<div class="ent d{min(depth, 9)}{' online' if on_line else ''}">
  <span class=gn>{ROMAN[depth]}</span>
  <div class=body><div class=hd><span class=num>{num}</span>{self.name(p)} <span class=vv>{self.vitals(p, False)}</span></div>""")
            fams = p.families_as_partner
            for fam in fams:
                sp = self.other(fam, p)
                if not sp and not fam.children:
                    continue
                m = self.ev(fam.id, "m.", fam.marriage, False)
                if sp:
                    bits = [x for x in (m, self.vitals(sp, False), self.parents_of(sp)) if x]
                    out.append(f"<div class=spl>{'married ' if len(fams) == 1 else '<span class=lbl>m.</span> '}"
                               f"{self.name(sp, 'spn')}{' — ' + '; '.join(bits) if bits else ''}</div>")
            out.append("</div></div>")
            kids = [self.t.people[c.person] for fam in fams for c in fam.children if c.person in self.t.people]
            for i, k in enumerate(kids, 1):
                walk(k, depth + 1, f"{i}.")

        walk(self.root, 0, "")
        return f"""
<section class="register">
  <h2>Descendants of {e(self.root.display_name())}</h2>
  <p class=intro>Each generation is indented beneath its parents and marked with its numeral. The direct line is set in green.</p>
  {''.join(out)}
</section>"""

    def allied(self) -> str:
        """Families who married in: the spouse's own parents, siblings and earlier ancestors."""
        tree_ids = self.t.descendants(self.root) | {self.root.id}
        blocks = []
        done: Set[str] = set()
        for pid in sorted(tree_ids, key=lambda x: self._sort(self.t.people[x])):
            for sp in self.t.spouses(self.t.people[pid]):
                if sp.id in tree_ids or not sp.family_as_child or sp.id in done:
                    continue
                # climb to the earliest recorded ancestor of this spouse
                top = sp
                while self.t.parents(top):
                    top = self.t.parents(top)[0]
                partner = self.t.people[pid]
                lines: List[str] = []
                seen: Set[str] = set()

                def walk(p: Person, depth: int):
                    if p.id in seen or p.id in tree_ids:
                        return
                    seen.add(p.id)
                    done.add(p.id)
                    hit = p.id == sp.id
                    lines.append(f"<div class='al d{min(depth, 6)}{' hit' if hit else ''}'>{self.name(p)} <span class=vv>{self.vitals(p, False)}</span>")
                    if hit:
                        lines.append(f"<div class=into>married {e(partner.display_name())}</div></div>")
                        return
                    lines.append("</div>")
                    fams = p.families_as_partner
                    for fam in fams:
                        o = self.other(fam, p)
                        if o and o.id not in tree_ids:
                            m = self.ev(fam.id, "m.", fam.marriage, False)
                            v = self.vitals(o, False)
                            kids = " · children:" if fam.children and len(fams) > 1 else ""
                            lines.append(f"<div class='spl al d{min(depth, 6)}'><span class=lbl>m.</span> {self.name(o, 'spn')}"
                                         f"{' — ' + '; '.join(x for x in (m, v) if x) if (m or v) else ''}<span class=lbl>{kids}</span></div>")
                        for c in fam.children:
                            if c.person in self.t.people:
                                walk(self.t.people[c.person], depth + 1)

                walk(top, 0)
                head = top.name.surname or top.display_name()
                blocks.append(f"<div class=fam><h3>The {e(head)} family</h3>{''.join(lines)}</div>")
        if not blocks:
            return ""
        return f"""
<section class="allied">
  <h2>Families Who Married In</h2>
  <p class=intro>Where the records reach back beyond a husband or wife who joined the Robisons, their own family is shown here.</p>
  {''.join(blocks)}
</section>"""

    def _sort(self, p: Person):
        b = p.birth
        return (b.date.sort_key() if b and b.date.known else (9999,), p.id)

    def disputes(self) -> str:
        rows = []
        for c in self.t.conflicts():
            if c["kind"] not in ("birth", "death", "marriage", "name"):
                continue
            owner = self.t.people.get(c["owner"])
            if owner:
                who = owner.display_name()
            else:
                fam = self.t.families.get(c["owner"])
                who = " & ".join(self.t.people[x].display_name() for x in fam.partners) if fam else c["owner"]
            shown, alt = c["claims"][0][0], c["claims"][1][0]
            rows.append(f"<tr><td>{e(who)}</td><td>{e(c['kind'])}</td><td>{e(shown)}</td><td>{e(alt)}</td></tr>")
        if not rows:
            return ""
        return f"""
<section class="disputes">
  <h2>Where the Records Disagree</h2>
  <p class=intro>Dates marked <sup class=dag>†</sup> in this register are given as the best-supported record has them
  (usually a headstone, certificate or the family Bible itself). Another source gives a different date:</p>
  <table><thead><tr><th>Person</th><th>Fact</th><th>Given here</th><th>Also recorded</th></tr></thead>
  <tbody>{''.join(rows)}</tbody></table>
</section>"""

    def name_line(self, poster: bool = False, everyone: bool = False) -> str:
        """The male line: every son of the name, father to son, as a left-to-right chart.
        Daughters are named in their father's box (their children carry other surnames).
        With everyone=True: every descendant, sons and daughters alike, each in a box of their own,
        with daughters' children following them."""
        surname = self.root.name.surname
        depth_max = [0]

        def years(p: Person) -> str:
            b, d = p.birth, p.death
            by = b.date.display() if b and b.date.known else ""
            dy = d.date.display() if d and d.date.known else ""
            if b and b.date.kind == "exact" and b.date.y:
                by = str(b.date.y)
            if d and d.date.kind == "exact" and d.date.y:
                dy = str(d.date.y)
            if by and dy:
                return f"{by} – {dy}"
            if by:
                return f"b. {by}"
            if dy:
                return f"d. {dy}"
            return ""

        def given(p: Person) -> str:
            n = p.name
            g = e(n.given)
            if everyone and n.surname and n.surname != surname:
                g += f" <span class=sur>{e(n.surname)}</span>"
            if n.nickname:
                g += f" <i>“{e(n.nickname)}”</i>"
            return g

        def node(p: Person, depth: int) -> str:
            depth_max[0] = max(depth_max[0], depth)
            kids = [k for k in self.t.children(p)]
            sons = kids if everyone else [k for k in kids if k.sex != "F"]
            daughters = [] if everyone else [k for k in kids if k.sex == "F"]
            wives = [w for w in self.t.spouses(p)]
            on = " on" if p.id in self.line_ids else ""
            dau = " dau" if everyone and p.sex == "F" else ""
            y = years(p)
            box = [f"<div class='nb{on}{dau}'><div class=g>{given(p)}</div>"]
            if y:
                box.append(f"<div class=y>{e(y)}</div>")
            for w in wives:
                box.append(f"<div class=w>m. {e(w.display_name())}</div>")
            if daughters:
                word = "daughter" if len(daughters) == 1 else "daughters"
                box.append(f"<div class=dt>{word}: " + ", ".join(e(d.name.given.split()[0]) for d in daughters) + "</div>")
            box.append("</div>")
            inner = "".join(f"<div class=k>{node(k, depth + 1)}</div>" for k in sons)
            kids_html = f"<div class=kids>{inner}</div>" if sons else ""
            return f"<div class=row>{''.join(box)}{kids_html}</div>"

        chart = node(self.root, 0)
        heads = "".join(f"<div>{ROMAN[i]}</div>" for i in range(depth_max[0] + 1))
        gens = str(depth_max[0] + 1)
        if everyone:
            kicker = f"{e(self.root.display_name())} and all his descendants, {gens} generations"
            title = f"The {e(surname)} Family Tree"
            intro = (f"Every recorded descendant of {e(self.root.display_name())}, sons and daughters alike, "
                     f"with each daughter’s children following her. Daughters are marked with a rose edge; "
                     f"the direct line is shown in green.")
        else:
            kicker = f"{e(self.root.display_name())} and his sons, {gens} generations"
            title = f"The {e(surname)} Name"
            intro = (f"Every son who carried the {e(surname)} name, father to son, from {e(self.root.display_name())}. "
                     f"Daughters are named with their fathers; their children carry other names and appear in the register. "
                     f"The direct line is shown in green.")
        return f"""
<section class="nameline{' poster' if poster else ''}{' everyone' if everyone else ''}">
  {'<p class=kicker>' + kicker + '</p>' if poster else ''}
  <h2>{title}</h2>
  <p class=intro>{intro}</p>
  <div class=fit><div class=nlc><div class=heads>{heads}</div>{chart}</div></div>
  <script>
  (function(){{ var f=document.currentScript.previousElementSibling, c=f.firstElementChild;
    function fit(){{ c.style.transform='none';
      var s=Math.min(2, f.clientWidth/c.offsetWidth, f.clientHeight/c.offsetHeight);
      c.style.transform='scale('+s+')'; }}
    fit(); document.fonts.ready.then(fit); }})();
  </script>
</section>"""

    def additions(self) -> str:
        def table(title, cols, n):
            head = "".join(f"<th>{c}</th>" for c in cols)
            body = "".join("<tr>" + "<td></td>" * len(cols) + "</tr>" for _ in range(n))
            return f"<h3>{title}</h3><table class=blank><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"
        return f"""
<section class="page additions">
  <h2>Family Additions</h2>
  <p class=intro>For the births, marriages and deaths still to come.</p>
  {table('Births', ['Name', 'Date', 'Place', 'Parents'], 7)}
  {table('Marriages', ['Names', 'Date', 'Place'], 5)}
  {table('Deaths', ['Name', 'Date', 'Place', 'Resting place'], 6)}
</section>"""

    def html(self) -> str:
        return self._doc("".join([self.title_page(), self.direct_line(), self.name_line(),
                                  self.name_line(everyone=True), self.register(),
                                  self.allied(), self.disputes(), self.additions()]))

    def poster_html(self, everyone: bool = False) -> str:
        today = _dt.date.today()
        foot = (f"<p class=pfoot>Prepared for the Robison family Bible · compiled {today.strftime('%B %Y')} "
                "from the family’s papers, headstones, church and civil records</p>")
        return self._doc(self.name_line(poster=True, everyone=everyone).replace("</section>", foot + "</section>"))

    def _doc(self, body: str) -> str:
        return f"""<!doctype html>
<html lang=en><head><meta charset=utf-8>
<title>The Robison Family — family register</title>
<link rel=preconnect href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Libre+Caslon+Text:ital,wght@0,400;0,700;1,400&family=Libre+Franklin:wght@400;500;600&display=swap" rel=stylesheet>
<style>{CSS}</style></head>
<body>{body}</body></html>"""


CSS = r"""
@page { size: letter; margin: 0.75in 0.8in 0.8in;
  @bottom-center { content: counter(page); font: 9pt 'Libre Caslon Text', Georgia, serif; color: #5c6b63; } }
@page :first { @bottom-center { content: none; } }
:root { --pine:#1f4a3d; --navy:#22344f; --red:#b8322f; --ink:#1d2a24; --muted:#5c6b63; --rule:#d6d2c4; }
* { box-sizing: border-box; }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { margin:0; color:var(--ink); background:#fff; font: 10.5pt/1.45 'Libre Caslon Text', Georgia, serif; }
h2 { font-weight:400; font-size:22pt; color:var(--pine); margin:0 0 4pt; letter-spacing:.01em; }
h2::after { content:""; display:block; width:48pt; height:2pt; margin-top:6pt;
  background: linear-gradient(90deg, var(--pine) 0 40%, var(--navy) 40% 70%, var(--red) 70% 76%, var(--pine) 76%); }
h3 { font: 600 9pt 'Libre Franklin', sans-serif; letter-spacing:.12em; text-transform:uppercase; color:var(--pine); margin:16pt 0 6pt; }
.intro { color:var(--muted); font-style:italic; margin:6pt 0 12pt; max-width:34em; }
.page { break-after: page; }
section + section { break-before: page; }
.lbl { font-style:italic; color:var(--muted); }
.dag { color:var(--red); font-size:.75em; margin-left:1px; }
.sur { font-variant: small-caps; letter-spacing:.03em; }
.nick { font-style:italic; font-weight:400; }

/* title page */
.title { height: 9.3in; display:flex; flex-direction:column; align-items:center; text-align:center; padding-top:1.3in; }
.title .sett { width:100%; height:9pt; margin-bottom:.9in;
  background: repeating-linear-gradient(90deg, var(--pine) 0 22pt, #18211d 22pt 30pt, var(--navy) 30pt 44pt, var(--red) 44pt 45.5pt, var(--navy) 45.5pt 52pt); }
.kicker { font: 600 9pt 'Libre Franklin', sans-serif; letter-spacing:.3em; text-transform:uppercase; color:var(--muted); margin:0; }
.title h1 { font-weight:400; font-size:44pt; line-height:1.1; color:var(--pine); margin:14pt 0 6pt; }
.title .sub { font-style:italic; font-size:16pt; margin:0; color:var(--navy); }
.orn { font-size:22pt; color:var(--red); margin:30pt 0; }
.title .span { font-size:13pt; line-height:1.7; margin:0; }
.title .count { font: 9.5pt 'Libre Franklin', sans-serif; color:var(--muted); margin-top:18pt; letter-spacing:.04em; }
.title .foot { margin-top:auto; font-size:10pt; color:var(--muted); font-style:italic; line-height:1.6; }

/* direct line */
.spine { list-style:none; margin:0; padding:0; position:relative; }
.spine::before { content:""; position:absolute; left:20pt; top:14pt; bottom:20pt; width:1.5pt; background:var(--pine); }
.spine li { display:flex; gap:14pt; align-items:flex-start; margin-bottom:5pt; break-inside:avoid; position:relative; }
.spine .gen { flex:0 0 40pt; height:24pt; display:flex; align-items:center; justify-content:center;
  background:#fff; border:1.5pt solid var(--pine); border-radius:13pt; color:var(--pine); font-size:11pt; position:relative; z-index:1; }
.spine .card { flex:1; border-bottom:.75pt solid var(--rule); padding-bottom:4pt; line-height:1.35; }
.spine .who { font-size:12.5pt; font-weight:700; }
.spine .vit { font-size:10pt; }
.spine .sp { font-size:9.5pt; color:var(--ink); margin-top:2pt; }
.spine .spn { font-weight:700; }
.spine .spv { color:var(--muted); }

/* register */
.ent { display:flex; gap:6pt; break-inside:avoid; margin:0 0 4pt; }
.ent .gn { flex:0 0 22pt; text-align:right; color:var(--muted); font-size:8pt; padding-top:2.5pt; font-family:'Libre Franklin',sans-serif; }
.ent .body { flex:1; }
.ent .hd .nm { font-weight:700; }
.ent .num { color:var(--muted); margin-right:4pt; font-size:9pt; }
.vv { font-size:9.5pt; }
.spl { font-size:9.3pt; color:#36443d; margin-left:12pt; }
.spl .spn { font-weight:700; color:var(--ink); }
.par { font-style:italic; color:var(--muted); }
.ent.online .hd .nm { color:var(--pine); }
.ent.online .gn { color:var(--pine); font-weight:600; }
""" + "".join(f".ent.d{i} .body {{ margin-left:{i * 13}pt; border-left:{'.6pt solid var(--rule)' if i else 'none'}; padding-left:{6 if i else 0}pt; }}\n" for i in range(10)) + r"""
/* allied */
.fam { break-inside:avoid; margin-bottom:6pt; }
.al { margin:0 0 3pt; }
.al .nm { font-weight:700; }
.al.hit .nm { color:var(--pine); }
.into { font-size:9pt; font-style:italic; color:var(--pine); margin-left:12pt; }
""" + "".join(f".al.d{i} {{ margin-left:{i * 14}pt; }}\n" for i in range(7)) + r"""
/* the name line (landscape) */
@page wide { size: letter landscape; margin: 0.5in 0.5in 0.6in; }
.nameline { page: wide; }
.nameline .intro { max-width:none; margin-bottom:8pt; }
.nameline .fit { width:10in; height:6.05in; overflow:hidden; }
@page poster { size: 17in 11in; margin: 0.6in 0.6in 0.5in; @bottom-center { content: none; } }
.nameline.poster { page: poster; height: 9.85in; display:flex; flex-direction:column; }
.poster .kicker { margin-bottom:4pt; }
.poster h2 { font-size:34pt; }
.poster .intro { font-size:12pt; max-width:60em; margin:8pt 0 14pt; }
.poster .fit { width:15.8in; height:auto; flex:1; }
.poster .nlc { --W:132pt; --G:18pt; }
.poster .pfoot { margin:6pt 0 0; font-size:9.5pt; font-style:italic; color:var(--muted); text-align:center; }
.nlc { transform-origin: 0 0; display:inline-block; --W:108pt; --G:16pt; }
.heads { display:flex; margin-bottom:4pt; }
.heads div { flex:0 0 var(--W); margin-right:var(--G); text-align:center; color:var(--red);
  font-size:10pt; border-bottom:.6pt solid var(--rule); padding-bottom:2pt; }
.row { display:flex; align-items:center; }
.nb { flex:0 0 var(--W); width:var(--W); border:.8pt solid #9aa59f; border-radius:3pt; background:#fff;
  padding:2.5pt 4pt 3pt; font-size:7pt; line-height:1.2; }
.nb .g { font-weight:700; font-size:8pt; }
.nb .y { color:var(--ink); }
.nb .w { color:var(--muted); font-style:italic; }
.nb .dt { color:var(--muted); font-size:6.5pt; margin-top:1pt; border-top:.4pt dotted var(--rule); padding-top:1pt; }
.nb.on { border:1.6pt solid var(--pine); background:#eef4f0; }
.nb.on .g { color:var(--pine); }
.nb.dau { border-left:2.4pt solid var(--red); }
.kids { position:relative; padding-left:calc(var(--G) / 2); display:flex; flex-direction:column; }
.kids::before { content:""; position:absolute; left:0; top:50%; width:calc(var(--G) / 2); border-top:.8pt solid var(--pine); }
.k { position:relative; padding:1.2pt 0 1.2pt calc(var(--G) / 2); }
.k::before { content:""; position:absolute; left:0; top:50%; width:calc(var(--G) / 2); border-top:.8pt solid var(--pine); }
.k::after { content:""; position:absolute; left:0; top:0; bottom:0; border-left:.8pt solid var(--pine); }
.k:first-child::after { top:50%; }
.k:last-child::after { bottom:50%; }
.k:only-child::after { display:none; }
/* tables */
table { width:100%; border-collapse:collapse; font-size:9.5pt; }
th { font: 600 7.5pt 'Libre Franklin', sans-serif; letter-spacing:.1em; text-transform:uppercase; color:var(--muted);
  text-align:left; border-bottom:1pt solid var(--pine); padding:4pt 6pt; }
td { border-bottom:.6pt solid var(--rule); padding:5pt 6pt; vertical-align:top; }
tr { break-inside:avoid; }
table.blank td { height:24pt; }
table.blank th:first-child { width:32%; }
"""


def build(tree: Tree, root: Person, focus: Optional[Person]) -> str:
    return Booklet(tree, root, focus).html()


def build_poster(tree: Tree, root: Person, focus: Optional[Person], everyone: bool = False) -> str:
    return Booklet(tree, root, focus).poster_html(everyone)
