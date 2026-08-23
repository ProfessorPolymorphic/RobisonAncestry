"""Genealogical date grammar.

Accepted forms (case-insensitive, stored as strings in the YAML):

    1869              year
    1869-03           year-month
    1869-03-19        year-month-day
    abt 1802          about (treated as ±2 years for compatibility checks)
    bef 1851          before
    aft 1871          after
    bet 1802 and 1804 between (inclusive)
    ?  /  empty       unknown

Each parsed date knows how to display itself, sort, export to GEDCOM, and
test whether it is *compatible* with another date (so "abt 1838" and
"1839-11-07" are a refinement, not a conflict, while "1868-03-19" vs
"1869-03-19" is a conflict).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_YMD = re.compile(r"^(\d{4})(?:-(\d{1,2}))?(?:-(\d{1,2}))?$")
ABT_WINDOW = 2  # years either side for "abt"


class DateError(ValueError):
    pass


@dataclass(frozen=True)
class GDate:
    kind: str  # exact | abt | bef | aft | bet | unknown
    y: Optional[int] = None
    m: Optional[int] = None
    d: Optional[int] = None
    y2: Optional[int] = None  # for bet

    # ----- construction -------------------------------------------------
    @staticmethod
    def parse(raw) -> "GDate":
        if raw is None:
            return GDate("unknown")
        s = str(raw).strip()
        if s in ("", "?"):
            return GDate("unknown")
        low = s.lower()
        m = re.match(r"^bet\s+(\d{4})\s+and\s+(\d{4})$", low)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if b < a:
                raise DateError(f"'between' range out of order: {raw}")
            return GDate("bet", y=a, y2=b)
        kind = "exact"
        for prefix in ("abt", "bef", "aft"):
            if low.startswith(prefix + " "):
                kind = prefix
                low = low[len(prefix) + 1:].strip()
                break
        m = _YMD.match(low)
        if not m:
            raise DateError(f"unrecognised date: {raw!r}")
        y = int(m.group(1))
        mo = int(m.group(2)) if m.group(2) else None
        d = int(m.group(3)) if m.group(3) else None
        if mo is not None and not 1 <= mo <= 12:
            raise DateError(f"bad month in {raw!r}")
        if d is not None and not 1 <= d <= 31:
            raise DateError(f"bad day in {raw!r}")
        return GDate(kind, y, mo, d)

    # ----- presentation -------------------------------------------------
    def _core(self) -> str:
        if self.y is None:
            return ""
        parts = []
        if self.d is not None:
            parts.append(str(self.d))
        if self.m is not None:
            parts.append(MONTHS[self.m - 1])
        parts.append(str(self.y))
        return " ".join(parts)

    def display(self) -> str:
        if self.kind == "unknown":
            return "?"
        if self.kind == "exact":
            return self._core()
        if self.kind == "abt":
            return "c." + self._core()
        if self.kind == "bef":
            return "before " + self._core()
        if self.kind == "aft":
            return "after " + self._core()
        if self.kind == "bet":
            return f"{self.y}–{self.y2}"
        return "?"

    def gedcom(self) -> str:
        if self.kind == "unknown":
            return ""
        core = self._core().upper()
        return {
            "exact": core,
            "abt": f"ABT {core}",
            "bef": f"BEF {core}",
            "aft": f"AFT {core}",
            "bet": f"BET {self.y} AND {self.y2}",
        }[self.kind]

    # ----- comparison ---------------------------------------------------
    @property
    def known(self) -> bool:
        return self.kind != "unknown"

    def sort_key(self):
        if not self.known:
            return (9999, 12, 31)
        y = self.y if self.kind != "aft" else self.y + 1
        return (y, self.m or 1, self.d or 1)

    def year_range(self):
        """(lo, hi) inclusive year range this date could fall in."""
        if not self.known:
            return (-9999, 9999)
        if self.kind == "exact":
            return (self.y, self.y)
        if self.kind == "abt":
            return (self.y - ABT_WINDOW, self.y + ABT_WINDOW)
        if self.kind == "bef":
            return (-9999, self.y)
        if self.kind == "aft":
            return (self.y, 9999)
        return (self.y, self.y2)

    def compatible(self, other: "GDate") -> bool:
        """True if both dates could describe the same event."""
        if not (self.known and other.known):
            return True
        a, b = self.year_range(), other.year_range()
        if a[1] < b[0] or b[1] < a[0]:
            return False
        # If both are exact down to month/day, those must agree too.
        if self.kind == other.kind == "exact":
            if self.m and other.m and self.m != other.m:
                return False
            if self.d and other.d and self.d != other.d:
                return False
        return True

    def precision(self) -> int:
        """Higher = more specific. Used to pick the 'best' of compatible claims."""
        if not self.known:
            return 0
        base = {"bet": 1, "bef": 1, "aft": 1, "abt": 2, "exact": 3}[self.kind]
        return base * 10 + (1 if self.m else 0) + (1 if self.d else 0)

    @property
    def year(self) -> Optional[int]:
        return self.y
