"""Generate the interactive static site (GitHub Pages): data.json + index.html + chart + GEDCOM."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from .gedcom import export as gedcom_export
from .model import Tree
from .render import ChartBuilder


def _event(tree: Tree, e):
    return {"type": e.type, "date": e.date.display() if e.date.known else "", "raw": e.raw_date,
            "year": e.date.sort_key()[0] if e.date.known else None,
            "place": e.place, "placeName": tree.place_name(e.place), "sources": e.sources,
            "note": e.note, "preferred": e.preferred}


def data_json(tree: Tree, private: bool = False, focus: str | None = None) -> dict:
    people = {}
    for p in tree.people.values():
        living = p.is_living()
        link = None
        if p.family_as_child:
            c = next(x for x in p.family_as_child.children if x.person == p.id)
            link = {"family": p.family_as_child.id, "confidence": c.confidence, "basis": c.basis, "sources": c.sources}
        events = [] if (private and living) else [_event(tree, e) for e in p.events]
        b, d = p.birth, p.death
        people[p.id] = {
            "id": p.id, "name": p.display_name(), "surname": p.name.surname, "given": p.name.given,
            "names": [{"full": n.full(), "kind": n.kind, "sources": n.sources, "note": n.note} for n in p.names],
            "sex": p.sex, "living": living,
            "birth": "" if (private and living) else (b.date.display() if b and b.date.known else ""),
            "death": "" if (private and living) else (d.date.display() if d and d.date.known else ""),
            "birthYear": b.date.sort_key()[0] if b and b.date.known else None,
            "events": events,
            "parents": [x.id for x in tree.parents(p)],
            "spouses": [x.id for x in tree.spouses(p)],
            "children": [x.id for x in tree.children(p)],
            "familiesAsPartner": [f.id for f in p.families_as_partner],
            "link": link, "notes": p.notes, "todo": p.todo,
        }
    families = {f.id: {"id": f.id, "partners": f.partners, "events": [_event(tree, e) for e in f.events],
                       "children": [{"person": c.person, "confidence": c.confidence, "basis": c.basis, "sources": c.sources}
                                    for c in f.children],
                       "sources": f.sources, "notes": f.notes} for f in tree.families.values()}
    sources = {s.id: {"id": s.id, "title": s.title, **{k: v for k, v in s.raw.items() if k not in ("id", "title")}}
               for s in tree.sources.values()}
    places = {pl.id: {"id": pl.id, "name": pl.name, **{k: v for k, v in pl.raw.items() if k not in ("id", "name")}}
              for pl in tree.places.values()}
    # which people/facts cite each source
    cited = {sid: set() for sid in sources}
    for p in tree.people.values():
        for n in p.names:
            for s in n.sources:
                cited.setdefault(s, set()).add(p.id)
        for e in p.events:
            for s in e.sources:
                cited.setdefault(s, set()).add(p.id)
    for f in tree.families.values():
        for e in f.events:
            for s in e.sources:
                for pid in f.partners:
                    cited.setdefault(s, set()).add(pid)
        for c in f.children:
            for s in c.sources:
                cited.setdefault(s, set()).add(c.person)
    for sid, ppl in cited.items():
        if sid in sources:
            sources[sid]["cites"] = sorted(ppl)
    conflicts = [{"owner": c["owner"], "kind": c["kind"],
                  "claims": [{"value": v, "sources": s} for v, s in c["claims"]], "note": c.get("note")}
                 for c in tree.conflicts()]
    todo = [{"who": pid, "kind": kind, "text": text} for pid, kind, text in tree.todo()]
    return {"people": people, "families": families, "sources": sources, "places": places,
            "conflicts": conflicts, "todo": todo, "root": tree.default_root().id, "focus": focus,
            "stats": {"people": len(people), "families": len(families), "sources": len(sources)}}


def build_site(tree: Tree, out: Path, focus=None, title="The Robison Family", private=False, repo_url="") -> None:
    out.mkdir(parents=True, exist_ok=True)
    root = tree.default_root()
    builder = ChartBuilder(tree, private=private)
    svg = builder.svg(root, focus, title="")
    data = data_json(tree, private, focus=focus.id if focus else None)
    scan = Path(__file__).resolve().parent.parent / "scans" / "typed-chart-web.jpg"
    if scan.exists():
        shutil.copyfile(scan, out / "typed-chart.jpg")
    (out / "data.json").write_text(json.dumps(data, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    (out / "robison-tree.svg").write_text(builder.svg(root, focus, title=title), encoding="utf-8")
    (out / "robison.ged").write_text(gedcom_export(tree), encoding="utf-8")
    (out / ".nojekyll").write_text("")
    tpl = (Path(__file__).parent / "site_template.html").read_text(encoding="utf-8")
    page = (tpl.replace("__TITLE__", title)
               .replace("__REPO__", repo_url)
               .replace("__SVG__", svg)
               .replace("__DATA__", json.dumps(data, ensure_ascii=False, default=str).replace("</", "<\\/")))
    (out / "index.html").write_text(page, encoding="utf-8")
