"""Export the tree as GEDCOM 5.5.1 (importable into Gramps, Ancestry, FamilySearch, etc.)."""
from __future__ import annotations

from typing import Dict, List

from .model import Event, Tree

TAGS = {"birth": "BIRT", "death": "DEAT", "burial": "BURI", "marriage": "MARR", "divorce": "DIV",
        "immigration": "IMMI", "emigration": "EMIG", "residence": "RESI", "occupation": "OCCU",
        "education": "EDUC", "census": "CENS", "baptism": "BAPM", "military": "EVEN", "other": "EVEN"}


def _lines(level: int, tag: str, value: str = "") -> List[str]:
    """One GEDCOM line, wrapping long values with CONC."""
    value = (value or "").replace("\n", " ").strip()
    if len(value) <= 200:
        return [f"{level} {tag} {value}".rstrip()]
    out = [f"{level} {tag} {value[:200]}"]
    rest = value[200:]
    while rest:
        out.append(f"{level + 1} CONC {rest[:200]}")
        rest = rest[200:]
    return out


def _event(tree: Tree, e: Event, level: int, src_x: Dict[str, str]) -> List[str]:
    tag = TAGS.get(e.type, "EVEN")
    out = _lines(level, tag, "")
    if tag == "EVEN":
        out += _lines(level + 1, "TYPE", e.type)
    if e.date.known:
        out += _lines(level + 1, "DATE", e.date.gedcom())
    if e.place:
        out += _lines(level + 1, "PLAC", tree.place_name(e.place))
    if e.note:
        out += _lines(level + 1, "NOTE", e.note)
    for s in e.sources:
        if s in src_x:
            out += _lines(level + 1, "SOUR", src_x[s])
    return out


def export(tree: Tree) -> str:
    ind_x = {pid: f"@I{i + 1}@" for i, pid in enumerate(tree.people)}
    fam_x = {fid: f"@F{i + 1}@" for i, fid in enumerate(tree.families)}
    src_x = {sid: f"@S{i + 1}@" for i, sid in enumerate(tree.sources)}

    out = ["0 HEAD", "1 SOUR famtree", "2 NAME Robison ancestry toolkit", "1 GEDC", "2 VERS 5.5.1",
           "2 FORM LINEAGE-LINKED", "1 CHAR UTF-8"]

    for p in tree.people.values():
        out += [f"0 {ind_x[p.id]} INDI"]
        out += _lines(1, "REFN", p.id)
        for i, n in enumerate(p.names):
            out += _lines(1, "NAME", f"{n.given} /{n.surname or ''}/")
            if i > 0:
                out += _lines(2, "TYPE", "aka")
            out += _lines(2, "GIVN", n.given)
            if n.surname:
                out += _lines(2, "SURN", n.surname)
            if n.nickname:
                out += _lines(2, "NICK", n.nickname)
            if n.note:
                out += _lines(2, "NOTE", n.note)
            for s in n.sources:
                if s in src_x:
                    out += _lines(2, "SOUR", src_x[s])
        if p.sex in ("M", "F"):
            out += _lines(1, "SEX", p.sex)
        for e in p.events:
            out += _event(tree, e, 1, src_x)
        if p.family_as_child:
            out += _lines(1, "FAMC", fam_x[p.family_as_child.id])
        for f in p.families_as_partner:
            out += _lines(1, "FAMS", fam_x[f.id])
        if p.notes:
            out += _lines(1, "NOTE", p.notes)
        for t in p.todo:
            out += _lines(1, "NOTE", "TODO: " + t)

    for f in tree.families.values():
        out += [f"0 {fam_x[f.id]} FAM"]
        out += _lines(1, "REFN", f.id)
        partners = [tree.people[x] for x in f.partners if x in tree.people]
        husb = next((x for x in partners if x.sex == "M"), None)
        wife = next((x for x in partners if x.sex == "F"), None)
        leftover = [x for x in partners if x is not husb and x is not wife]
        if husb is None and leftover:
            husb = leftover.pop(0)
        if wife is None and leftover:
            wife = leftover.pop(0)
        if husb:
            out += _lines(1, "HUSB", ind_x[husb.id])
        if wife:
            out += _lines(1, "WIFE", ind_x[wife.id])
        for c in f.children:
            if c.person in ind_x:
                out += _lines(1, "CHIL", ind_x[c.person])
        for e in f.events:
            out += _event(tree, e, 1, src_x)
        for s in f.sources:
            if s in src_x:
                out += _lines(1, "SOUR", src_x[s])
        notes = [f.notes] if f.notes else []
        for c in f.children:
            if c.confidence != "documented" or c.basis:
                notes.append(f"Link to {c.person}: {c.confidence}" + (f" — {c.basis}" if c.basis else ""))
        for n in notes:
            out += _lines(1, "NOTE", n)

    for s in tree.sources.values():
        out += [f"0 {src_x[s.id]} SOUR"]
        out += _lines(1, "REFN", s.id)
        out += _lines(1, "TITL", s.title)
        if s.raw.get("author"):
            out += _lines(1, "AUTH", s.raw["author"])
        if s.raw.get("repository"):
            out += _lines(1, "PUBL", s.raw["repository"])
        for key in ("url", "citation", "note"):
            if s.raw.get(key):
                out += _lines(1, "NOTE", f"{key}: {s.raw[key]}")
        for fpath in s.raw.get("files") or []:
            out += _lines(1, "OBJE", "")
            out += _lines(2, "FILE", fpath)

    out.append("0 TRLR")
    return "\n".join(out) + "\n"
