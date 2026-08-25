"""Command-line interface: python3 tree.py <command> [args]"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .model import Tree
from .render import ChartBuilder, html_page

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
BUILD = ROOT / "build"


def load(args) -> Tree:
    t = Tree(args.data)
    if t.errors:
        print("DATA ERRORS:", file=sys.stderr)
        for e in t.errors:
            print("  -", e, file=sys.stderr)
        if not getattr(args, "force", False):
            sys.exit(1)
    return t


def _resolve(tree: Tree, ref: str):
    if ref in tree.people:
        return tree.people[ref]
    hits = tree.find(ref)
    if len(hits) == 1:
        return hits[0]
    if not hits:
        sys.exit(f"no person matches {ref!r}")
    sys.exit(f"ambiguous {ref!r}: " + ", ".join(p.id for p in hits))


def cmd_validate(args):
    t = load(args)
    for w in t.warnings:
        print("warn:", w)
    print(f"ok — {len(t.people)} people, {len(t.families)} families, {len(t.sources)} sources, "
          f"{len(t.places)} places; {len(t.errors)} errors, {len(t.warnings)} warnings")


def cmd_show(args):
    t = load(args)
    p = _resolve(t, args.person)
    print(f"{p.display_name()}  [{p.id}]  {p.sex or ''}{'  (living)' if p.is_living() else ''}")
    for n in p.names[1:]:
        print(f"  {n.kind:9} {n.full():32} [{', '.join(n.sources)}]" + (f"  — {n.note}" if n.note else ""))
    for e in p.events:
        place = t.place_name(e.place)
        print(f"  {e.type:11} {e.date.display():16} {place:40} [{', '.join(e.sources)}]"
              + (f"\n{'':30}{e.note}" if e.note else ""))
    pars = t.parents(p)
    if pars:
        link = next(c for c in p.family_as_child.children if c.person == p.id)
        print(f"  parents     {' & '.join(x.display_name() for x in pars)}  ({link.confidence})")
        if link.basis:
            print(f"{'':14}{link.basis}")
    for f in p.families_as_partner:
        sp = [t.people[x].display_name() for x in f.partners if x != p.id and x in t.people]
        m = f.marriage
        print(f"  family      {f.id}: with {', '.join(sp) or '—'}" + (f", m. {m.date.display()}" if m else ""))
        for c in f.children:
            print(f"{'':14}child {t.people[c.person].display_name():34} ({c.confidence})")
    if p.notes:
        print("  notes       " + p.notes.strip().replace("\n", "\n              "))
    for td in p.todo:
        print("  TODO        " + td)


def cmd_search(args):
    t = load(args)
    for p in t.find(args.text):
        b = p.birth.date.display() if p.birth else "?"
        d = p.death.date.display() if p.death else ("living" if p.is_living() else "?")
        print(f"{p.id:34} {p.display_name():36} {b} – {d}")


def cmd_conflicts(args):
    t = load(args)
    cs = t.conflicts()
    for c in cs:
        print(f"{c['owner']}: {c['kind']}")
        for v, s in c["claims"]:
            print(f"    {v:28} [{', '.join(s)}]")
        if c.get("note"):
            print(f"    note: {c['note']}")
    print(f"{len(cs)} conflicts")


def cmd_todo(args):
    t = load(args)
    items = t.todo()
    order = {"todo": 0, "link": 1, "missing": 2, "unsourced": 3}
    titles = {"todo": "Research questions", "link": "Parent links not yet documented",
              "missing": "Missing vitals", "unsourced": "Unsourced facts"}
    last = None
    for pid, kind, text in sorted(items, key=lambda x: (order.get(x[1], 9), x[0])):
        if kind != last:
            n = sum(1 for i in items if i[1] == kind)
            print(f"\n== {titles.get(kind, kind)} ({n})")
            last = kind
        print(f"  {pid:34} {text}")
    print(f"\n{len(items)} open items")


def cmd_lineage(args):
    t = load(args)
    p = _resolve(t, args.person)
    chain = []
    cur = p
    while cur:
        chain.append(cur)
        pars = t.parents(cur)
        cur = next((x for x in pars if x.names[0].surname == p.names[0].surname), pars[0] if pars else None)
    for i, x in enumerate(reversed(chain)):
        b = x.birth.date.display() if x.birth else "?"
        d = x.death.date.display() if x.death else ("living" if x.is_living() else "?")
        link = ""
        if x.family_as_child:
            link = next(c.confidence for c in x.family_as_child.children if c.person == x.id)
        print(f"{i + 1:2}. {x.display_name():40} {b} – {d}   {link}")


def cmd_render(args):
    t = load(args)
    root = _resolve(t, args.root) if args.root else t.default_root()
    focus = _resolve(t, args.focus) if args.focus else None
    builder = ChartBuilder(t, private=args.private)
    svg = builder.svg(root, focus, title=args.title)
    BUILD.mkdir(exist_ok=True)
    svg_path = BUILD / f"{args.name}.svg"
    html_path = BUILD / f"{args.name}.html"
    svg_path.write_text(svg, encoding="utf-8")
    html_path.write_text(html_page(t, svg, args.title), encoding="utf-8")
    print(f"wrote {svg_path.relative_to(ROOT)} and {html_path.relative_to(ROOT)}  (root={root.id}"
          + (f", focus={focus.id}" if focus else "") + ")")


def cmd_site(args):
    from .site import build_site
    t = load(args)
    focus = _resolve(t, args.focus) if args.focus else None
    out = Path(args.out)
    build_site(t, out, focus=focus, title=args.title, private=args.private, repo_url=args.repo)
    print(f"wrote site to {out}/ (index.html, data.json, robison-tree.svg, robison.ged)")


def cmd_gedcom(args):
    from .gedcom import export
    t = load(args)
    BUILD.mkdir(exist_ok=True)
    path = BUILD / f"{args.name}.ged"
    path.write_text(export(t), encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)}")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="tree.py", description="Robison family tree toolkit")
    ap.add_argument("--data", default=str(DATA), help="data directory (default: data/)")
    ap.add_argument("--force", action="store_true", help="continue despite data errors")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("validate", help="check the YAML files for errors").set_defaults(fn=cmd_validate)
    s = sub.add_parser("show", help="print everything known about one person"); s.add_argument("person"); s.set_defaults(fn=cmd_show)
    s = sub.add_parser("search", help="find people by name or id"); s.add_argument("text"); s.set_defaults(fn=cmd_search)
    sub.add_parser("conflicts", help="facts where sources disagree").set_defaults(fn=cmd_conflicts)
    sub.add_parser("todo", help="open questions and weak links").set_defaults(fn=cmd_todo)
    s = sub.add_parser("lineage", help="direct line from the earliest ancestor to a person"); s.add_argument("person"); s.set_defaults(fn=cmd_lineage)
    s = sub.add_parser("render", help="draw the descendant chart (SVG + HTML) into build/")
    s.add_argument("--root", help="person to start from (default: earliest ancestor of the main surname)")
    s.add_argument("--focus", help="highlight the direct line to this person")
    s.add_argument("--private", action="store_true", help="hide dates of living people")
    s.add_argument("--title", default="The Robison Family")
    s.add_argument("--name", default="robison-tree", help="output file base name")
    s.set_defaults(fn=cmd_render)
    s = sub.add_parser("site", help="generate the interactive static site (GitHub Pages)")
    s.add_argument("--out", default=str(ROOT / "_site"))
    s.add_argument("--focus", default="rory-bjorn-robison-2015", help="person whose direct line is drawn heavy ('' for none); the overview page's generation track follows this line up from the earliest ancestor")
    s.add_argument("--private", action="store_true", help="hide facts about living people")
    s.add_argument("--title", default="The Robison Family")
    s.add_argument("--repo", default="https://github.com/ProfessorPolymorphic/RobisonAncestry")
    s.set_defaults(fn=cmd_site)
    s = sub.add_parser("gedcom", help="export GEDCOM 5.5.1 into build/"); s.add_argument("--name", default="robison"); s.set_defaults(fn=cmd_gedcom)

    args = ap.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
