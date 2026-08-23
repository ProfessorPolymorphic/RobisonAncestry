"""Load the YAML data files into a queryable Tree and validate them."""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import yaml

from .dates import DateError, GDate

DATA_FILES = {"people": "people.yaml", "families": "families.yaml",
              "sources": "sources.yaml", "places": "places.yaml"}
EVENT_TYPES = {"birth", "death", "burial", "marriage", "divorce", "immigration", "emigration",
               "residence", "occupation", "education", "military", "census", "baptism", "other"}
NAME_KINDS = {"primary", "variant", "conflict", "nickname"}
CONFIDENCE = {"documented", "inferred", "stated", "unverified"}
LIVING_HORIZON_YEARS = 100

# Allowed keys per record type. Unknown keys are errors — a stray key is almost always a typo
# or a comma-in-flow-mapping accident that silently truncated a value.
KEYS = {
    "person": {"id", "names", "sex", "living", "events", "notes", "todo"},
    "name": {"given", "surname", "kind", "nickname", "sources", "note"},
    "event": {"type", "date", "place", "sources", "note", "preferred"},
    "family": {"id", "partners", "events", "children", "sources", "notes"},
    "child": {"person", "confidence", "basis", "sources"},
    "source": {"id", "title", "type", "tier", "date", "author", "files", "url", "repository", "citation", "note"},
    "place": {"id", "name", "lat", "lon", "note"},
}


@dataclass
class Event:
    type: str
    date: GDate
    raw_date: Optional[str]
    place: Optional[str]
    sources: List[str]
    note: Optional[str]
    preferred: bool = False


@dataclass
class Name:
    given: str
    surname: Optional[str]
    kind: str = "primary"
    nickname: Optional[str] = None
    sources: List[str] = field(default_factory=list)
    note: Optional[str] = None

    def full(self, with_nick=True) -> str:
        s = self.given
        if with_nick and self.nickname:
            s += f' "{self.nickname}"'
        if self.surname:
            s += " " + self.surname
        return s


@dataclass
class ChildLink:
    person: str
    confidence: str = "stated"
    basis: Optional[str] = None
    sources: List[str] = field(default_factory=list)


@dataclass
class Person:
    id: str
    names: List[Name]
    sex: Optional[str]
    living: Optional[bool]
    events: List[Event]
    notes: Optional[str]
    todo: List[str]
    # filled in by Tree
    families_as_partner: List["Family"] = field(default_factory=list)
    family_as_child: Optional["Family"] = None

    @property
    def name(self) -> Name:
        return self.names[0]

    def display_name(self) -> str:
        return self.name.full()

    def events_of(self, etype: str) -> List[Event]:
        return [e for e in self.events if e.type == etype]

    def preferred(self, etype: str) -> Optional[Event]:
        evs = self.events_of(etype)
        if not evs:
            return None
        for e in evs:
            if e.preferred:
                return e
        return evs[0]

    @property
    def birth(self) -> Optional[Event]:
        return self.preferred("birth")

    @property
    def death(self) -> Optional[Event]:
        return self.preferred("death")

    def is_living(self, today_year: Optional[int] = None) -> bool:
        if self.living is not None:
            return self.living
        if self.death is not None or self.events_of("burial"):
            return False
        today_year = today_year or _dt.date.today().year
        b = self.birth
        if b and b.date.known and b.date.year is not None:
            return (today_year - b.date.year) < LIVING_HORIZON_YEARS
        return False  # no dates at all: assume historical


@dataclass
class Family:
    id: str
    partners: List[str]
    events: List[Event]
    children: List[ChildLink]
    sources: List[str]
    notes: Optional[str]

    def preferred(self, etype: str) -> Optional[Event]:
        evs = [e for e in self.events if e.type == etype]
        if not evs:
            return None
        for e in evs:
            if e.preferred:
                return e
        return evs[0]

    @property
    def marriage(self) -> Optional[Event]:
        return self.preferred("marriage")


@dataclass
class Source:
    id: str
    title: str
    raw: dict


@dataclass
class Place:
    id: str
    name: str
    raw: dict


class ValidationError(Exception):
    pass


class Tree:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.people: Dict[str, Person] = {}
        self.families: Dict[str, Family] = {}
        self.sources: Dict[str, Source] = {}
        self.places: Dict[str, Place] = {}
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self._load()
        self._link()
        self._check()

    # ----- loading --------------------------------------------------------
    def _read(self, key) -> list:
        p = self.data_dir / DATA_FILES[key]
        with open(p, encoding="utf-8") as f:
            data = yaml.safe_load(f) or []
        if not isinstance(data, list):
            raise ValidationError(f"{p}: top level must be a list")
        return data

    def _keys(self, raw: dict, kind: str, owner: str):
        for k in raw:
            if k not in KEYS[kind]:
                self.errors.append(f"{owner}: unknown {kind} key {k!r} (unquoted comma in a note?)")

    def _event(self, raw: dict, owner: str) -> Event:
        self._keys(raw, "event", owner)
        etype = raw.get("type")
        if etype not in EVENT_TYPES:
            self.errors.append(f"{owner}: unknown event type {etype!r}")
        try:
            gd = GDate.parse(raw.get("date"))
        except DateError as e:
            self.errors.append(f"{owner}: {e}")
            gd = GDate("unknown")
        srcs = list(raw.get("sources") or [])
        return Event(etype or "other", gd, raw.get("date"), raw.get("place"), srcs,
                     raw.get("note"), bool(raw.get("preferred", False)))

    def _load(self):
        for raw in self._read("sources"):
            self._keys(raw, "source", raw.get("id", "?"))
            self.sources[raw["id"]] = Source(raw["id"], raw.get("title", raw["id"]), raw)
        for raw in self._read("places"):
            self._keys(raw, "place", raw.get("id", "?"))
            self.places[raw["id"]] = Place(raw["id"], raw.get("name", raw["id"]), raw)
        for raw in self._read("people"):
            pid = raw.get("id")
            if not pid:
                self.errors.append("person without id")
                continue
            if pid in self.people:
                self.errors.append(f"duplicate person id {pid}")
            self._keys(raw, "person", pid)
            names = []
            for i, n in enumerate(raw.get("names") or []):
                self._keys(n, "name", pid)
                kind = n.get("kind", "primary" if i == 0 else "variant")
                if kind not in NAME_KINDS:
                    self.errors.append(f"{pid}: unknown name kind {kind!r}")
                names.append(Name(str(n.get("given", "")), n.get("surname"), kind,
                                  n.get("nickname"), list(n.get("sources") or []), n.get("note")))
            if not names:
                self.errors.append(f"{pid}: no names")
                names = [Name(pid, None)]
            events = [self._event(e, pid) for e in (raw.get("events") or [])]
            for t in raw.get("todo") or []:
                if not isinstance(t, str):
                    self.errors.append(f"{pid}: todo item is not a string — quote it if it contains ': ' ({t!r})")
            self.people[pid] = Person(pid, names, raw.get("sex"), raw.get("living"), events,
                                      raw.get("notes"), list(raw.get("todo") or []))
        for raw in self._read("families"):
            fid = raw.get("id")
            if not fid:
                self.errors.append("family without id")
                continue
            if fid in self.families:
                self.errors.append(f"duplicate family id {fid}")
            self._keys(raw, "family", fid)
            children = []
            for c in raw.get("children") or []:
                if isinstance(c, str):
                    c = {"person": c}
                self._keys(c, "child", fid)
                conf = c.get("confidence", "stated")
                if conf not in CONFIDENCE:
                    self.errors.append(f"{fid}: unknown confidence {conf!r} for {c.get('person')}")
                children.append(ChildLink(c["person"], conf, c.get("basis"), list(c.get("sources") or [])))
            events = [self._event(e, fid) for e in (raw.get("events") or [])]
            self.families[fid] = Family(fid, list(raw.get("partners") or []), events, children,
                                        list(raw.get("sources") or []), raw.get("notes"))

    def _link(self):
        for fam in self.families.values():
            for pid in fam.partners:
                p = self.people.get(pid)
                if p is None:
                    self.errors.append(f"{fam.id}: unknown partner {pid}")
                else:
                    p.families_as_partner.append(fam)
            for c in fam.children:
                p = self.people.get(c.person)
                if p is None:
                    self.errors.append(f"{fam.id}: unknown child {c.person}")
                    continue
                if p.family_as_child is not None:
                    self.errors.append(f"{c.person}: child of two families ({p.family_as_child.id}, {fam.id})")
                p.family_as_child = fam

    # ----- validation -----------------------------------------------------
    def _check_refs(self, owner: str, events: Iterable[Event], sources: Iterable[str]):
        for s in sources:
            if s not in self.sources:
                self.errors.append(f"{owner}: unknown source {s!r}")
        for e in events:
            if e.place and e.place not in self.places:
                self.errors.append(f"{owner}: unknown place {e.place!r}")
            for s in e.sources:
                if s not in self.sources:
                    self.errors.append(f"{owner}: unknown source {s!r}")
            if not e.sources:
                self.warnings.append(f"{owner}: {e.type} has no source")

    def _check(self):
        for p in self.people.values():
            self._check_refs(p.id, p.events, [s for n in p.names for s in n.sources])
            for etype in ("birth", "death"):
                if sum(1 for e in p.events_of(etype) if e.preferred) > 1:
                    self.errors.append(f"{p.id}: more than one preferred {etype}")
            b, d = p.birth, p.death
            if b and d and b.date.known and d.date.known:
                if d.date.year_range()[1] < b.date.year_range()[0]:
                    self.errors.append(f"{p.id}: death before birth")
            if p.family_as_child:
                for par_id in p.family_as_child.partners:
                    par = self.people.get(par_id)
                    pb = par.birth if par else None
                    if pb and b and pb.date.known and b.date.known:
                        gap = b.date.year_range()[1] - pb.date.year_range()[0]
                        if gap < 12:
                            self.warnings.append(f"{p.id}: born only {gap} years after parent {par_id}")
        for f in self.families.values():
            self._check_refs(f.id, f.events, f.sources)
            for c in f.children:
                for s in c.sources:
                    if s not in self.sources:
                        self.errors.append(f"{f.id}: unknown source {s!r} on child {c.person}")
            if len(f.partners) > 2:
                self.errors.append(f"{f.id}: more than two partners")

    # ----- queries --------------------------------------------------------
    def person(self, pid: str) -> Person:
        if pid not in self.people:
            raise KeyError(f"no such person: {pid}")
        return self.people[pid]

    def find(self, text: str) -> List[Person]:
        t = text.lower()
        out = []
        for p in self.people.values():
            hay = " ".join([p.id] + [n.full() for n in p.names]).lower()
            if t in hay:
                out.append(p)
        return out

    def parents(self, p: Person) -> List[Person]:
        if not p.family_as_child:
            return []
        return [self.people[x] for x in p.family_as_child.partners if x in self.people]

    def children(self, p: Person) -> List[Person]:
        out = []
        for f in p.families_as_partner:
            out.extend(self.people[c.person] for c in f.children if c.person in self.people)
        return out

    def spouses(self, p: Person) -> List[Person]:
        return [self.people[x] for f in p.families_as_partner for x in f.partners
                if x != p.id and x in self.people]

    def ancestors(self, p: Person) -> set:
        seen, stack = set(), [p]
        while stack:
            cur = stack.pop()
            for par in self.parents(cur):
                if par.id not in seen:
                    seen.add(par.id)
                    stack.append(par)
        return seen

    def descendants(self, p: Person) -> set:
        seen, stack = set(), [p]
        while stack:
            cur = stack.pop()
            for ch in self.children(cur):
                if ch.id not in seen:
                    seen.add(ch.id)
                    stack.append(ch)
        return seen

    def place_name(self, pid: Optional[str]) -> str:
        if not pid:
            return ""
        pl = self.places.get(pid)
        return pl.name if pl else pid

    def roots(self) -> List[Person]:
        """People with no recorded parents who have descendants."""
        return [p for p in self.people.values() if p.family_as_child is None and self.children(p)]

    def default_root(self) -> Person:
        """Earliest ancestor of the family's main surname with the most descendants."""
        from collections import Counter
        surnames = Counter(p.name.surname for p in self.people.values() if p.name.surname)
        main = surnames.most_common(1)[0][0] if surnames else None
        cands = [p for p in self.roots() if p.name.surname == main] or self.roots() or list(self.people.values())
        return max(cands, key=lambda p: len(self.descendants(p)))

    # ----- analysis -------------------------------------------------------
    def conflicts(self) -> List[dict]:
        """Facts where sources disagree: incompatible dates for the same event, conflicting names."""
        out = []
        for p in self.people.values():
            for n in p.names[1:]:
                if n.kind == "conflict":
                    out.append({"owner": p.id, "kind": "name", "preferred": p.name.full(),
                                "claims": [(p.name.full(), p.name.sources), (n.full(), n.sources)],
                                "note": n.note})
            out.extend(self._event_conflicts(p.id, p.events))
        for f in self.families.values():
            out.extend(self._event_conflicts(f.id, f.events))
        return out

    def _event_conflicts(self, owner: str, events: List[Event]) -> List[dict]:
        out = []
        by_type: Dict[str, List[Event]] = {}
        for e in events:
            by_type.setdefault(e.type, []).append(e)
        for etype, evs in by_type.items():
            if etype in ("residence", "occupation", "education", "census", "other") or len(evs) < 2:
                continue
            head = evs[0]
            for other in evs[1:]:
                if not head.date.compatible(other.date):
                    out.append({"owner": owner, "kind": etype, "preferred": head.date.display(),
                                "claims": [(head.date.display(), head.sources),
                                           (other.date.display(), other.sources)],
                                "note": other.note})
        return out

    def todo(self) -> List[tuple]:
        """Open items: explicit todos, unverified/stated links, missing vitals, unsourced facts."""
        out = []
        for p in self.people.values():
            for t in p.todo:
                out.append((p.id, "todo", t))
            if not p.birth:
                out.append((p.id, "missing", "no birth date"))
            if not p.is_living() and not p.death:
                out.append((p.id, "missing", "no death date (not marked living)"))
            for n in p.names:
                if n.kind != "nickname" and not n.sources:
                    out.append((p.id, "unsourced", f"name {n.full()!r} has no source"))
        for f in self.families.values():
            for c in f.children:
                if c.confidence in ("unverified", "stated"):
                    out.append((c.person, "link", f"parent link to {f.id} is {c.confidence}"
                                + (f" — {c.basis}" if c.basis else "")))
        return out
