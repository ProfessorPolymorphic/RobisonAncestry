"""Render a descendant chart as SVG, and wrap it in a self-contained HTML page."""
from __future__ import annotations

import html
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .model import Family, Person, Tree

ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]

BOX_MIN, BOX_MAX = 112, 330
CHAR_W = 7.4          # approx px per character at 12px monospace
LINE_H = 15
PAD = 9
HGAP = 14
VGAP = 60
FONT = "ui-monospace, Menlo, Consolas, monospace"
LABEL_W = 48


def esc(s: str) -> str:
    return html.escape(str(s), quote=True)


@dataclass
class Node:
    person: Person
    lines: List[tuple]           # (text, style)  style in {name, fact, spouse}
    children: List["Node"] = field(default_factory=list)
    child_conf: Dict[str, str] = field(default_factory=dict)
    depth: int = 0
    x: float = 0.0               # left of box
    rel: float = 0.0             # centre offset from parent centre (set by layout)

    @property
    def h(self) -> int:
        return PAD * 2 + LINE_H * len(self.lines)

    @property
    def w(self) -> float:
        longest = max(len(t) * (CHAR_W * 1.1 if style == "name" else CHAR_W) + (14 if "indent" in style else 0)
                      for t, style in self.lines)
        return max(BOX_MIN, min(BOX_MAX, longest + PAD * 2))

    @property
    def cx(self) -> float:
        return self.x + self.w / 2


class ChartBuilder:
    def __init__(self, tree: Tree, private: bool = False):
        self.tree = tree
        self.private = private

    # ----- text ---------------------------------------------------------
    def short_place(self, pid: Optional[str]) -> str:
        name = self.tree.place_name(pid)
        return name.split(",")[0] if name else ""

    def vitals(self, p: Person) -> List[str]:
        if self.private and p.is_living():
            return ["living"]
        out = []
        b, d = p.birth, p.death
        if b and (b.date.known or b.place):
            s = "b. " + b.date.display()
            if b.place:
                s += ", " + self.short_place(b.place)
            out.append(s)
        if d and (d.date.known or d.place):
            s = "d. " + d.date.display()
            if d.place:
                s += ", " + self.short_place(d.place)
            out.append(s)
        if not out and p.is_living():
            out.append("living")
        return out

    def spouse_vitals(self, p: Person) -> str:
        if self.private and p.is_living():
            return "   living"
        b, d = p.birth, p.death
        parts = []
        if b and b.date.known:
            parts.append("b. " + b.date.display())
        if d and d.date.known:
            parts.append("d. " + d.date.display())
        return "  " + " – ".join(parts) if parts else ""

    # ----- build --------------------------------------------------------
    def build(self, root: Person, depth: int = 0, seen=None) -> Node:
        seen = seen if seen is not None else set()
        seen.add(root.id)
        lines = [(root.display_name(), "name")]
        for v in self.vitals(root):
            lines.append((v, "fact"))
        for fam in root.families_as_partner:
            spouse = next((self.tree.people[x] for x in fam.partners if x != root.id and x in self.tree.people), None)
            m = fam.marriage
            mline = "m."
            if m and m.date.known and not (self.private and spouse and spouse.is_living()):
                mline += " " + m.date.display()
                if m.place:
                    mline += ", " + self.short_place(m.place)
            if spouse and mline == "m.":
                lines.append(("m. " + spouse.display_name(), "spouse"))
            else:
                lines.append((mline, "spouse"))
                if spouse:
                    lines.append((spouse.display_name(), "spouse indent"))
            if spouse:
                sv = self.spouse_vitals(spouse)
                if sv.strip():
                    lines.append((sv.strip(), "spouse indent"))
        node = Node(root, lines, depth=depth)
        for fam in root.families_as_partner:
            for link in fam.children:
                child = self.tree.people.get(link.person)
                if child is None or child.id in seen:
                    continue
                node.children.append(self.build(child, depth + 1, seen))
                node.child_conf[child.id] = link.confidence
        return node

    # ----- layout (contour-based: rows pack tightly, like the typed chart) ----
    def layout(self, n: Node) -> Dict[int, tuple]:
        """Position children relative to n (n.rel on each child = cx offset from parent cx).
        Returns the subtree contour {depth: (left, right)} relative to n's centre."""
        own = {n.depth: (-n.w / 2, n.w / 2)}
        if not n.children:
            return own
        acc: Dict[int, tuple] = {}
        positions: List[float] = []
        for c in n.children:
            cc = self.layout(c)
            if not acc:
                pos = 0.0
            else:
                pos = max((acc[d][1] - cc[d][0] + HGAP) for d in cc if d in acc)
            positions.append(pos)
            for d, (l, r) in cc.items():
                if d in acc:
                    acc[d] = (min(acc[d][0], l + pos), max(acc[d][1], r + pos))
                else:
                    acc[d] = (l + pos, r + pos)
        mid = (positions[0] + positions[-1]) / 2
        for c, pos in zip(n.children, positions):
            c.rel = pos - mid
        contour = {d: (l - mid, r - mid) for d, (l, r) in acc.items()}
        contour.update(own)
        return contour

    def place(self, n: Node, cx: float):
        n.x = cx - n.w / 2
        for c in n.children:
            self.place(c, cx + c.rel)

    def rows(self, n: Node) -> Dict[int, int]:
        heights: Dict[int, int] = {}
        stack = [n]
        while stack:
            cur = stack.pop()
            heights[cur.depth] = max(heights.get(cur.depth, 0), cur.h)
            stack.extend(cur.children)
        return heights

    # ----- svg ----------------------------------------------------------
    def svg(self, root: Person, focus: Optional[Person] = None, title: str = "") -> str:
        tree = self.tree
        node = self.build(root)
        contour = self.layout(node)
        left = min(l for l, _ in contour.values())
        right = max(r for _, r in contour.values())
        self.place(node, LABEL_W + 14 - left)
        heights = self.rows(node)
        y_of: Dict[int, float] = {}
        y = 60 if title else 20
        for d in sorted(heights):
            y_of[d] = y
            y += heights[d] + VGAP
        total_h = y - VGAP + 70
        total_w = (right - left) + LABEL_W + 30

        heavy = set()
        if focus:
            heavy = tree.ancestors(focus) | {focus.id}

        out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_w:.0f}" height="{total_h:.0f}" '
               f'viewBox="0 0 {total_w:.0f} {total_h:.0f}" font-family="{FONT}" font-size="12">',
               '<style>'
               '.box{fill:#fff;stroke:#777;stroke-width:1}'
               '.box.heavy{stroke:#111;stroke-width:2.2}'
               '.box.unverified{stroke-dasharray:5 4}'
               '.name{font-weight:700;font-size:13px;fill:#111}'
               '.fact{fill:#222}.spouse{fill:#555}'
               '.edge{fill:none;stroke:#111;stroke-width:1.2}'
               '.edge.stated{stroke:#999}'
               '.edge.unverified{stroke:#999;stroke-dasharray:5 4}'
               '.gen{fill:#888;font-size:13px}'
               '.title{font-weight:700;font-size:20px;fill:#111;font-family:Georgia,serif}'
               '.legend{fill:#777;font-size:11px}'
               '</style>',
               '<rect width="100%" height="100%" fill="#fff"/>']
        if title:
            out.append(f'<text class="title" x="{LABEL_W + 10}" y="34">{esc(title)}</text>')
        for d in sorted(heights):
            out.append(f'<text class="gen" x="14" y="{y_of[d] + 16:.0f}">{ROMAN[d] if d < len(ROMAN) else d + 1}</text>')

        stack = [node]
        while stack:
            n = stack.pop()
            top = y_of[n.depth]
            cls = "box" + (" heavy" if n.person.id in heavy else "")
            link_conf = n.person.family_as_child and next(
                (c.confidence for c in n.person.family_as_child.children if c.person == n.person.id), None)
            if link_conf == "unverified":
                cls += " unverified"
            out.append(f'<g id="{esc(n.person.id)}"><title>{esc(n.person.id)}</title>')
            out.append(f'<rect class="{cls}" x="{n.x:.1f}" y="{top:.1f}" width="{n.w:.1f}" height="{n.h}" rx="2"/>')
            ty = top + PAD + 11
            for text, style in n.lines:
                indent = 14 if "indent" in style else 0
                out.append(f'<text class="{style}" x="{n.x + PAD + indent:.1f}" y="{ty:.1f}">{esc(text)}</text>')
                ty += LINE_H
            out.append('</g>')
            if n.children:
                bus_y = y_of[n.depth + 1] - VGAP / 2
                out.append(f'<path class="edge" d="M{n.cx:.1f},{top + n.h:.1f} V{bus_y:.1f}"/>')
                xs = [c.cx for c in n.children]
                if len(xs) > 1:
                    out.append(f'<path class="edge" d="M{min(xs):.1f},{bus_y:.1f} H{max(xs):.1f}"/>')
                for c in n.children:
                    conf = n.child_conf.get(c.person.id, "stated")
                    ecls = "edge" + (" unverified" if conf == "unverified" else " stated" if conf == "stated" else "")
                    out.append(f'<path class="{ecls}" d="M{c.cx:.1f},{bus_y:.1f} V{y_of[c.depth]:.1f}"/>')
            stack.extend(n.children)

        ly = total_h - 30
        legend = ("Heavy box = direct line to " + focus.display_name() + ".  " if focus else "") + \
                 "Black connector = documented/inferred from records.  Grey = stated by family chart only.  Dashed = unverified placement."
        out.append(f'<text class="legend" x="{LABEL_W + 10}" y="{ly:.0f}">{esc(legend)}</text>')
        out.append("</svg>")
        return "\n".join(out)


# ----- HTML page ----------------------------------------------------------

def html_page(tree: Tree, svg: str, title: str) -> str:
    people = sorted(tree.people.values(), key=lambda p: (p.birth.date.sort_key() if p.birth else (9999, 1, 1)))
    rows = []
    for p in people:
        b = p.birth.date.display() if p.birth else ""
        d = p.death.date.display() if p.death else ("living" if p.is_living() else "")
        parents = ", ".join(x.display_name() for x in tree.parents(p))
        conf = ""
        if p.family_as_child:
            conf = next((c.confidence for c in p.family_as_child.children if c.person == p.id), "")
        nsrc = len({s for e in p.events for s in e.sources} | {s for n in p.names for s in n.sources})
        rows.append(f"<tr><td><code>{esc(p.id)}</code></td><td>{esc(p.display_name())}</td><td>{esc(b)}</td>"
                    f"<td>{esc(d)}</td><td>{esc(parents)}</td><td class='c-{conf}'>{esc(conf)}</td><td>{nsrc}</td></tr>")

    conf_rows = []
    for c in tree.conflicts():
        claims = "<br>".join(f"{esc(v)} <small>[{esc(', '.join(s))}]</small>" for v, s in c["claims"])
        conf_rows.append(f"<tr><td><code>{esc(c['owner'])}</code></td><td>{esc(c['kind'])}</td><td>{claims}</td>"
                         f"<td>{esc(c.get('note') or '')}</td></tr>")

    todo_rows = [f"<tr><td><code>{esc(pid)}</code></td><td>{esc(kind)}</td><td>{esc(text)}</td></tr>"
                 for pid, kind, text in tree.todo()]

    src_rows = []
    for s in tree.sources.values():
        files = ", ".join(s.raw.get("files") or [])
        src_rows.append(f"<tr><td><code>{esc(s.id)}</code></td><td>{esc(s.title)}</td><td>{esc(s.raw.get('tier',''))}</td>"
                        f"<td>{esc(files)}</td></tr>")

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{esc(title)}</title>
<style>
 body{{margin:0;padding:24px;font:15px/1.45 Georgia,serif;color:#222;background:#fafaf8}}
 h1{{font-size:26px;margin:0 0 4px}} h2{{font-size:19px;margin:36px 0 10px;border-bottom:1px solid #ccc;padding-bottom:4px}}
 .sub{{color:#666;margin:0 0 18px}}
 .chart{{overflow-x:auto;border:1px solid #ddd;background:#fff;padding:8px}}
 .chart.fit svg{{max-width:100%;height:auto}}
 .toggle{{font-size:13px;color:#555;margin:0 0 8px}}
 table{{border-collapse:collapse;width:100%;font-size:13.5px;background:#fff}}
 th,td{{text-align:left;vertical-align:top;padding:5px 8px;border-bottom:1px solid #e4e4e4}}
 th{{background:#f0efe9;font-weight:600}}
 code{{font:12px ui-monospace,Menlo,monospace;color:#444}}
 small{{color:#777}}
 .c-documented{{color:#1a6b2a}} .c-inferred{{color:#7a5d00}} .c-stated{{color:#888}} .c-unverified{{color:#b03030}}
 nav a{{margin-right:14px}}
 @media print{{.chart{{overflow:visible;border:0}} nav{{display:none}}}}
</style></head><body>
<h1>{esc(title)}</h1>
<p class="sub">{len(tree.people)} people · {len(tree.families)} families · {len(tree.sources)} sources · generated from <code>data/*.yaml</code> by <code>tree.py render</code></p>
<nav><a href="#chart">Chart</a><a href="#conflicts">Conflicts ({len(conf_rows)})</a><a href="#todo">Open items ({len(todo_rows)})</a><a href="#people">People</a><a href="#sources">Sources</a></nav>
<h2 id="chart">Descendant chart</h2>
<p class="toggle"><label><input type="checkbox" id="fit" checked onchange="document.getElementById('c').classList.toggle('fit',this.checked)"> fit to width (untick for full size, scroll sideways)</label> · <a href="robison-tree.svg">open SVG</a></p>
<div class="chart fit" id="c">{svg}</div>
<h2 id="conflicts">Where the sources disagree</h2>
<p class="sub">Each row is one fact with two incompatible claims. The first claim is what the chart shows; change the order (or set <code>preferred: true</code>) in the YAML to switch.</p>
<table><tr><th>Who</th><th>Fact</th><th>Claims [sources]</th><th>Note</th></tr>{''.join(conf_rows)}</table>
<h2 id="todo">Open items</h2>
<table><tr><th>Who</th><th>Kind</th><th>Item</th></tr>{''.join(todo_rows)}</table>
<h2 id="people">People</h2>
<table><tr><th>id</th><th>Name</th><th>Born</th><th>Died</th><th>Parents</th><th>Link</th><th>#src</th></tr>{''.join(rows)}</table>
<h2 id="sources">Sources</h2>
<table><tr><th>id</th><th>Title</th><th>Tier</th><th>Files</th></tr>{''.join(src_rows)}</table>
</body></html>"""
