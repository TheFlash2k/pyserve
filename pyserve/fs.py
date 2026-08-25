import fnmatch
import os
import re
import shutil
from typing import Dict, List, Optional, Sequence, Tuple

from .assets import read_asset
from .cache import DirectoryCache
from .ignore import IgnoreList, rel_parts_of
from .utils.logger import logger

NUMBERED_COPY = " ({0}){1}"
DEFAULT_IGNORE_ASSET = "default.ignore"

def load_ignore(root: str, ignore_file: str = ".ignore", use_default: bool = True) -> IgnoreList:
    """Reads the ignore file at the served root, falling back to the bundled one."""
    path = os.path.join(root, ignore_file)
    if os.path.isfile(path):
        return IgnoreList.from_file(path)
    if not use_default:
        return IgnoreList([], source=path)
    rules = IgnoreList.from_lines(
        read_asset(DEFAULT_IGNORE_ASSET).splitlines(), source=DEFAULT_IGNORE_ASSET
    )
    logger.debug(f"No {ignore_file} at {root}, using the bundled default rules")
    return rules

def safe_join(root: str, rel_path: str) -> Optional[str]:
    """Resolves rel_path under root and returns None when it escapes the root."""
    rel_path = (rel_path or "").strip("/")
    target = os.path.normpath(os.path.join(root, rel_path)) if rel_path else root
    root_abs = os.path.abspath(root)
    target_abs = os.path.abspath(target)
    if target_abs != root_abs and not target_abs.startswith(root_abs + os.sep):
        return None
    return target_abs

def is_safe_name(name: str) -> bool:
    """True for a bare filename with no separators and no '.' or '..'."""
    if not name or name in (".", ".."):
        return False
    return "/" not in name and "\\" not in name

def split_ext(filename: str) -> Tuple[str, str]:
    """Splits a filename into its stem and extension, keeping dotfiles intact."""
    dot = filename.rfind(".")
    if dot <= 0:
        return filename, ""
    return filename[:dot], filename[dot:]

GLOB_CHARS = "*?["
QUERY_SEPARATORS = ";"
REGEX_DELIMITER = "/"
REGEX_FLAGS = {"i": re.IGNORECASE}
MAX_REGEX_LENGTH = 200

def looks_like_glob(query: str) -> bool:
    """True when a query is meant to be matched as a shell style pattern."""
    return any(char in query for char in GLOB_CHARS)

def split_regex(chunk: str):
    """Splits '/pattern/flags' into its source and flags, or (None, '') when it is not one."""
    if len(chunk) < 3 or not chunk.startswith(REGEX_DELIMITER):
        return None, ""
    close = chunk.rfind(REGEX_DELIMITER)
    if close <= 0:
        return None, ""
    flags = chunk[close + 1:]
    if any(flag not in REGEX_FLAGS for flag in flags):
        return None, ""
    return chunk[1:close], flags

def split_query(raw: str):
    """Splits a query on ';', leaving a whole '/pattern/' in one piece."""
    if split_regex(raw)[0] is not None:
        return [raw]
    return [chunk.strip() for chunk in raw.split(QUERY_SEPARATORS) if chunk.strip()]

def path_score(target: str, name: str) -> int:
    """Ranks a pattern hit so shallower paths and shorter names come first."""
    return max(1, 1000 - target.count("/") * 10 - len(name))

class QueryPart:

    """One piece of a search query.

    A part wrapped in slashes is a regular expression, one holding '*', '?' or
    '[' is a shell style glob, and anything else is a fuzzy subsequence match.
    A regex or glob containing a '/' is matched against the path relative to the
    folder being searched instead of against the entry name.

    Attributes:
        raw: The part exactly as it was typed
        kind: One of 'regex', 'glob' or 'fuzzy'
        anchored: True when the whole relative path is the match target
        error: Why the part could not be compiled, empty when it is fine
    """

    def __init__(self, chunk: str):
        self.raw = chunk
        self.kind = "fuzzy"
        self.error = ""
        self.regex = None
        self.pattern = chunk.lower()
        self.anchored = "/" in chunk

        source, flags = split_regex(chunk)
        if source is not None:
            self.kind = "regex"
            self.anchored = "/" in source
            if len(source) > MAX_REGEX_LENGTH:
                self.error = f"regular expression is longer than {MAX_REGEX_LENGTH} characters"
                return
            options = 0
            for flag in flags:
                options |= REGEX_FLAGS[flag]
            try:
                self.regex = re.compile(source, options)
            except re.error as problem:
                self.error = f"invalid regular expression: {problem}"
            return

        if looks_like_glob(chunk):
            self.kind = "glob"

    def __repr__(self) -> str:
        return f"QueryPart({self.raw!r}, kind={self.kind})"

    def score(self, name: str, lowered: str, full: str, full_lower: str) -> int:
        """Score for one entry, or -1 when this part does not match it."""
        if self.kind == "regex":
            if self.regex is None:
                return -1
            target = full if self.anchored else name
            return path_score(target, name) if self.regex.search(target) else -1
        if self.kind == "glob":
            target = full_lower if self.anchored else lowered
            return path_score(target, name) if fnmatch.fnmatch(target, self.pattern) else -1
        return fuzzy_score(self.pattern, lowered)

class QueryMatcher:

    """Scores an entry against a search query.

    A query is split on ';' and every part is matched on its own, the best score
    winning, so '*.sql;*.db' finds both and '*.md;readme' mixes a glob with a
    fuzzy match. A query that is one whole '/pattern/' is never split, so a
    regex may contain ';'.

    Attributes:
        raw: The query exactly as it was typed
        parts: The parsed QueryPart objects
        error: The first part error, empty when the whole query compiled
    """

    def __init__(self, query: str):
        self.raw = (query or "").strip()
        self.parts = [QueryPart(chunk) for chunk in split_query(self.raw)]
        self.error = next((part.error for part in self.parts if part.error), "")

    def __bool__(self) -> bool:
        return bool(self.parts) and not self.error

    def __repr__(self) -> str:
        return f"QueryMatcher({self.raw!r}, {len(self.parts)} part(s))"

    @property
    def has_glob(self) -> bool:
        """True when at least one part is a glob."""
        return any(part.kind == "glob" for part in self.parts)

    @property
    def has_regex(self) -> bool:
        """True when at least one part is a regular expression."""
        return any(part.kind == "regex" for part in self.parts)

    def score(self, name: str, rel_dir: str = "") -> int:
        """Best score across every part, or -1 when nothing matches."""
        lowered = name.lower()
        full = f"{rel_dir}/{name}" if rel_dir else name
        full_lower = full.lower()
        best = -1
        for part in self.parts:
            found = part.score(name, lowered, full, full_lower)
            if found > best:
                best = found
        return best

def fuzzy_score(query: str, target: str) -> int:
    """Ordered subsequence score with a bonus for runs and for a literal hit."""
    query = query.lower()
    target = target.lower()
    index = 0
    score = 0
    consecutive = 0
    for char in target:
        if index < len(query) and char == query[index]:
            score += 1 + consecutive
            consecutive += 1
            index += 1
        else:
            consecutive = 0
    if index < len(query):
        return -1
    if query in target:
        score += 15
    return score

class FileStore:

    """The filesystem half of PyServe.

    Every path that reaches this class is resolved against the served root and
    filtered through the ignore list, so a request can never read or write
    outside of the directory that was handed to the server.

    Attributes:
        root: Absolute path of the served directory
        ignore: IgnoreList used to hide entries
        ignore_file: Name of the ignore file, hidden from listings at the root
        show_hidden: When False, dotfiles are hidden as well
        follow_symlinks: When True, symlinked entries are stat'ed through
        search_limit: Maximum number of search results returned
        cache: Optional DirectoryCache consulted before touching the disk
    """

    def __init__(
        self,
        root: str,
        ignore: Optional[IgnoreList] = None,
        ignore_file: str = ".ignore",
        show_hidden: bool = True,
        follow_symlinks: bool = False,
        search_limit: int = 300,
        cache: Optional[DirectoryCache] = None,
        use_default_ignore: bool = True,
    ):
        self.root = os.path.abspath(root)
        self.ignore_file = ignore_file
        self.show_hidden = show_hidden
        self.follow_symlinks = follow_symlinks
        self.search_limit = search_limit
        self.use_default_ignore = use_default_ignore
        self.cache = cache
        self.ignore = ignore if ignore is not None else load_ignore(
            self.root, ignore_file, use_default_ignore
        )

    @property
    def name(self) -> str:
        """The display name of the served directory."""
        return os.path.basename(self.root.rstrip(os.sep)) or self.root

    def reload_ignore(self) -> IgnoreList:
        """Re-reads the ignore file, falling back to the bundled default rules."""
        self.ignore = load_ignore(self.root, self.ignore_file, self.use_default_ignore)
        if self.cache is not None:
            self.cache.reset()
        return self.ignore

    def resolve(self, rel_path: str) -> Optional[str]:
        """Absolute path for rel_path, or None when it would escape the root."""
        return safe_join(self.root, rel_path)

    def is_hidden(self, rel_parts: Sequence[str], is_dir: bool) -> bool:
        """True when an entry must not appear in listings, searches or downloads."""
        if not rel_parts:
            return False
        if len(rel_parts) == 1 and rel_parts[0] == self.ignore_file:
            return True
        if not self.show_hidden and any(part.startswith(".") for part in rel_parts):
            return True
        return self.ignore.is_ignored(rel_parts, is_dir)

    def is_path_hidden(self, rel_path: str, is_dir: bool) -> bool:
        """Convenience wrapper around is_hidden that takes a posix path string."""
        return self.is_hidden(rel_parts_of(rel_path), is_dir)

    def entry_for(self, abs_path: str, name: str, is_dir: bool) -> Optional[Dict]:
        """Builds the JSON payload for a single entry."""
        try:
            stat = os.stat(abs_path) if self.follow_symlinks else os.lstat(abs_path)
        except OSError:
            return None
        return {
            "name": name,
            "type": "dir" if is_dir else "file",
            "size": None if is_dir else stat.st_size,
            "mtime": int(stat.st_mtime),
        }

    def listdir(self, rel_path: str = "", allow=None) -> Optional[List[Dict]]:
        """Returns the visible entries of rel_path, from the cache when it holds them.

        The cache holds unfiltered listings, so an optional allow callback is
        applied afterwards and the same cached entry stays correct for every
        user.
        """
        key = (rel_path or "").strip("/")
        entries = None
        if self.cache is not None:
            entries = self.cache.get(key)
        if entries is None:
            entries = self.scan(key)
            if entries is not None and self.cache is not None:
                self.cache.put(key, entries)
        if entries is None or allow is None:
            return entries
        return [
            entry for entry in entries
            if allow(f"{key}/{entry['name']}" if key else entry["name"], entry["type"] == "dir")
        ]

    def invalidate(self, rel_dir: str) -> None:
        """Re-scans one directory so the cache stays usable after a write."""
        if self.cache is None:
            return
        key = (rel_dir or "").strip("/")
        entries = self.scan(key)
        if entries is None:
            self.cache.invalidate(key)
        else:
            self.cache.put(key, entries)

    def invalidate_tree(self, rel_path: str) -> None:
        """Drops a directory and everything under it after a rename, move or delete."""
        if self.cache is not None:
            self.cache.drop_subtree(rel_path)

    def scan(self, rel_path: str = "") -> Optional[List[Dict]]:
        """Reads the visible entries of rel_path straight from disk, ignoring the cache."""
        abs_path = self.resolve(rel_path)
        if abs_path is None or not os.path.isdir(abs_path):
            return None
        parent = rel_parts_of(rel_path)
        entries = []
        with os.scandir(abs_path) as scan:
            for item in scan:
                is_dir = item.is_dir(follow_symlinks=self.follow_symlinks)
                if self.is_hidden(parent + (item.name,), is_dir):
                    continue
                entry = self.entry_for(item.path, item.name, is_dir)
                if entry is not None:
                    entries.append(entry)
        entries.sort(key=lambda entry: (entry["type"] != "dir", entry["name"].lower()))
        return entries

    def search(self, query: str, limit: Optional[int] = None, rel_path: str = "",
               allow=None) -> List[Dict]:
        """Matches visible entries under rel_path and returns the best hits.

        Only the subtree rooted at rel_path is looked at, and every result path
        comes back relative to it, so searching from a folder searches that
        folder rather than the whole served directory.
        """
        query = (query or "").strip()
        if not query:
            return []
        scope = (rel_path or "").strip("/")
        base = self.resolve(scope)
        if base is None or not os.path.isdir(base):
            return []
        if scope and self.is_path_hidden(scope, True):
            return []
        limit = self.search_limit if limit is None else limit
        matcher = QueryMatcher(query)
        if not matcher:
            return []
        if self.cache is not None and self.cache.complete:
            return self.search_cached(matcher, limit, scope, allow)
        return self.search_tree(matcher, limit, scope, allow)

    def search_cached(self, matcher: QueryMatcher, limit: int, scope: str = "",
                      allow=None) -> List[Dict]:
        """Matches over the warmed cache instead of walking the disk again."""
        prefix = scope + "/" if scope else ""
        matches = []
        for rel_dir, entries in self.cache.snapshot().items():
            if scope and rel_dir != scope and not rel_dir.startswith(prefix):
                continue
            if allow is not None and rel_dir and not allow(rel_dir, True):
                continue
            local = "" if rel_dir == scope else rel_dir[len(prefix):]
            parent = local.split("/") if local else []
            for entry in entries:
                score = matcher.score(entry["name"], local)
                if score < 0:
                    continue
                full = f"{rel_dir}/{entry['name']}" if rel_dir else entry["name"]
                if allow is not None and not allow(full, entry["type"] == "dir"):
                    continue
                match = dict(entry)
                match["path"] = list(parent)
                matches.append((score, match))
        matches.sort(key=lambda pair: -pair[0])
        return [entry for _, entry in matches[:limit]]

    def search_tree(self, matcher: QueryMatcher, limit: int, scope: str = "",
                    allow=None) -> List[Dict]:
        """Matches by walking the subtree from disk."""
        base = self.resolve(scope)
        if base is None or not os.path.isdir(base):
            return []
        scope_parts = rel_parts_of(scope)
        matches = []
        for dirpath, dirnames, filenames in os.walk(base, followlinks=self.follow_symlinks):
            rel_dir = os.path.relpath(dirpath, base)
            parent = () if rel_dir == "." else tuple(rel_dir.split(os.sep))
            from_root = scope_parts + parent
            rel_key = "/".join(parent)

            kept = []
            for name in dirnames:
                if self.is_hidden(from_root + (name,), True):
                    continue
                if allow is not None and not allow("/".join(from_root + (name,)), True):
                    continue
                kept.append(name)
                entry = self.entry_for(os.path.join(dirpath, name), name, True)
                score = matcher.score(name, rel_key)
                if entry is not None and score >= 0:
                    entry["path"] = list(parent)
                    matches.append((score, entry))
            dirnames[:] = kept

            for name in filenames:
                if self.is_hidden(from_root + (name,), False):
                    continue
                if allow is not None and not allow("/".join(from_root + (name,)), False):
                    continue
                score = matcher.score(name, rel_key)
                if score < 0:
                    continue
                entry = self.entry_for(os.path.join(dirpath, name), name, False)
                if entry is not None:
                    entry["path"] = list(parent)
                    matches.append((score, entry))

        matches.sort(key=lambda pair: -pair[0])
        return [entry for _, entry in matches[:limit]]


    def next_available_name(self, dirpath: str, filename: str) -> str:
        """Returns 'name (n).ext' using the first number that is free in dirpath."""
        base, ext = split_ext(filename)
        pattern = re.compile(r"^" + re.escape(base) + r" \((\d+)\)" + re.escape(ext) + r"$")
        highest = 0
        if os.path.isdir(dirpath):
            for name in os.listdir(dirpath):
                found = pattern.match(name)
                if found:
                    highest = max(highest, int(found.group(1)))
        return base + NUMBERED_COPY.format(highest + 1, ext)

    def walk_tree(self, rel_path: str):
        """Yields every visible path under rel_path, the path itself included."""
        rel_path = (rel_path or "").strip("/")
        abs_path = self.resolve(rel_path)
        if abs_path is None:
            return
        yield rel_path, os.path.isdir(abs_path)
        if not os.path.isdir(abs_path):
            return
        base_parts = rel_parts_of(rel_path)
        for dirpath, dirnames, filenames in os.walk(abs_path, followlinks=False):
            rel_dir = os.path.relpath(dirpath, abs_path)
            parent = base_parts if rel_dir == "." else base_parts + tuple(rel_dir.split(os.sep))
            kept = []
            for name in dirnames:
                if self.is_hidden(parent + (name,), True):
                    continue
                kept.append(name)
                yield "/".join(parent + (name,)), True
            dirnames[:] = kept
            for name in filenames:
                if self.is_hidden(parent + (name,), False):
                    continue
                yield "/".join(parent + (name,)), False

    def remove(self, abs_path: str) -> None:
        """Deletes a file or recursively deletes a directory."""
        if os.path.isdir(abs_path) and not os.path.islink(abs_path):
            shutil.rmtree(abs_path)
        else:
            os.remove(abs_path)
