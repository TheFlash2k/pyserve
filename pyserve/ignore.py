import fnmatch
import os
from typing import Iterable, List, Optional, Sequence, Tuple

def rel_parts_of(rel_path: str) -> Tuple[str, ...]:
    """Splits a relative posix path into its non empty segments."""
    return tuple(part for part in (rel_path or "").split("/") if part)

class IgnorePattern:

    """A single gitignore style rule.

    Attributes:
        pattern: The glob left after the prefixes and suffixes are stripped
        negated: True when the rule started with '!' and re-includes instead of hides
        dir_only: True when the rule ended with '/' and only applies to directories
        anchored: True when the rule is matched against the whole relative path
    """

    def __init__(self, raw: str):
        line = raw.strip()
        self.raw = line
        self.negated = line.startswith("!")
        if self.negated:
            line = line[1:].strip()
        self.dir_only = line.endswith("/")
        if self.dir_only:
            line = line[:-1]
        self.anchored = line.startswith("/")
        if self.anchored:
            line = line.lstrip("/")
        elif "/" in line:
            self.anchored = True
        self.pattern = line

    def matches(self, rel_path: str, basename: str, is_dir: bool) -> bool:
        """True when this rule applies to the given entry."""
        if not self.pattern:
            return False
        if self.dir_only and not is_dir:
            return False
        target = rel_path if self.anchored else basename
        return fnmatch.fnmatch(target, self.pattern)

    def __repr__(self) -> str:
        return f"IgnorePattern({self.raw!r})"

class IgnoreList:

    """gitignore style matcher with negation support.

    Rules are evaluated in file order and the last rule that matches wins, so a
    '!name' line placed after a broader rule brings that entry back into view.
    An entry is also hidden when one of its parent directories is hidden, unless
    the entry itself is explicitly re-included.
    """

    def __init__(self, patterns: Optional[Iterable[IgnorePattern]] = None, source: str = ""):
        self.patterns: List[IgnorePattern] = list(patterns or [])
        self.source = source

    def __len__(self) -> int:
        return len(self.patterns)

    def __bool__(self) -> bool:
        return bool(self.patterns)

    def __repr__(self) -> str:
        return f"IgnoreList({len(self.patterns)} patterns, source={self.source!r})"

    @classmethod
    def from_lines(cls, lines: Iterable[str], source: str = "") -> "IgnoreList":
        """Builds a list from raw lines, skipping blanks and '#' comments."""
        patterns = []
        for raw in lines:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            patterns.append(IgnorePattern(line))
        return cls(patterns, source=source)

    @classmethod
    def from_file(cls, path: str) -> "IgnoreList":
        """Builds a list from an ignore file, returning an empty list when absent."""
        if not path or not os.path.isfile(path):
            return cls([], source=path or "")
        with open(path, "r", encoding="utf-8", errors="ignore") as handle:
            return cls.from_lines(handle, source=path)

    def _decide(self, rel_path: str, basename: str, is_dir: bool) -> Optional[bool]:
        decision = None
        for pattern in self.patterns:
            if pattern.matches(rel_path, basename, is_dir):
                decision = not pattern.negated
        return decision

    def is_ignored(self, rel_parts: Sequence[str], is_dir: bool) -> bool:
        """True when the entry at rel_parts should be hidden."""
        if not self.patterns or not rel_parts:
            return False
        if self._decide("/".join(rel_parts), rel_parts[-1], is_dir) is False:
            return False
        for depth in range(1, len(rel_parts) + 1):
            prefix = rel_parts[:depth]
            is_last = depth == len(rel_parts)
            if self._decide("/".join(prefix), prefix[-1], is_dir if is_last else True):
                return True
        return False

    def is_path_ignored(self, rel_path: str, is_dir: bool) -> bool:
        """Convenience wrapper around is_ignored that takes a posix path string."""
        return self.is_ignored(rel_parts_of(rel_path), is_dir)
