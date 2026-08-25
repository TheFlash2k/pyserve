#!/usr/bin/env python3

"""Recursive tests for the .ignore handling.

Builds a tree with ignorable entries at every depth, then checks that the rules
hold from three directions at once: the FileStore predicate, every HTTP route
that can reach a path, and a full crawl of the served tree that proves nothing
hidden is reachable from anywhere and everything visible is.

Run it with:

    python3 tests/test_ignore.py
"""

import json
import os
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pyserve import PyServe

IGNORE_RULES = """
.env.*
!.env.example
*.key
build/
/root-only.md
tmp/cache/*
"""

DIRS = [
    ("build", False),
    ("build/nested", False),
    ("notes", True),
    ("notes/build", False),
    ("notes/deep", True),
    ("notes/deep/deeper", True),
    ("notes/deep/deeper/deepest", True),
    ("notes/deep/deeper/deepest/build", False),
    ("tmp", True),
    ("tmp/cache", True),
]

FILES = [
    (".ignore", False),
    (".env.local", False),
    (".env.example", True),
    ("keep.txt", True),
    ("secret.key", False),
    ("build.txt", True),
    ("root-only.md", False),
    ("build/out.txt", False),
    ("build/nested/deep.txt", False),
    ("notes/.env.staging", False),
    ("notes/.env.example", True),
    ("notes/secret.key", False),
    ("notes/keep.md", True),
    ("notes/root-only.md", True),
    ("notes/build/x.txt", False),
    ("notes/deep/deeper/deepest/.env.prod", False),
    ("notes/deep/deeper/deepest/.env.example", True),
    ("notes/deep/deeper/deepest/secret.key", False),
    ("notes/deep/deeper/deepest/keep.log", True),
    ("notes/deep/deeper/deepest/build/y.txt", False),
    ("tmp/cache/a.bin", False),
    ("tmp/other.txt", True),
]

class Checks:

    """Counts assertions and reports at the end."""

    def __init__(self):
        self.passed = 0
        self.failed = []

    def ok(self, condition, label):
        """Records one assertion."""
        if condition:
            self.passed += 1
        else:
            self.failed.append(label)
            print("FAIL " + label)

    def report(self):
        """Prints the summary and returns a process exit code."""
        print(f"\n{self.passed} passed, {len(self.failed)} failed")
        return 1 if self.failed else 0

def build_tree(root):
    """Writes the fixture tree and returns the expected visibility map."""
    expected = {}
    for path, visible in DIRS:
        os.makedirs(os.path.join(root, path), exist_ok=True)
        expected[path] = visible
    for path, visible in FILES:
        full = os.path.join(root, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as handle:
            handle.write(IGNORE_RULES if path == ".ignore" else f"contents of {path}\n")
        expected[path] = visible
    return expected

def request(url, method="GET", headers=None, body=None):
    """Returns (status, bytes) and never raises on an HTTP error."""
    req = urllib.request.Request(url, method=method, data=body, headers=headers or {})
    try:
        response = urllib.request.urlopen(req)
        return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()

def listing(base, rel_path):
    """Names returned by /api/list for one directory, or None on a refusal."""
    status, body = request(f"{base}/api/list?path={urllib.parse.quote(rel_path)}")
    if status != 200:
        return None
    return [entry["name"] for entry in json.loads(body)["entries"]]

def crawl(base, rel_path="", seen=None):
    """Every path reachable by walking the served tree from the root."""
    seen = set() if seen is None else seen
    status, body = request(f"{base}/api/list?path={urllib.parse.quote(rel_path)}")
    if status != 200:
        return seen
    for entry in json.loads(body)["entries"]:
        child = f"{rel_path}/{entry['name']}" if rel_path else entry["name"]
        seen.add(child)
        if entry["type"] == "dir":
            crawl(base, child, seen)
    return seen

def check_predicate(checks, store, expected):
    """The FileStore predicate agrees with the expected visibility, at every depth."""
    for path, visible in sorted(expected.items()):
        is_dir = os.path.isdir(os.path.join(store.root, path))
        hidden = store.is_path_hidden(path, is_dir)
        checks.ok(hidden != visible, f"predicate: {path} should be {'visible' if visible else 'hidden'}")

def check_listings(checks, base, expected):
    """Every visible directory lists exactly its visible children."""
    for path, visible in sorted(expected.items()):
        if not visible or path not in dict(DIRS):
            continue
        names = listing(base, path)
        checks.ok(names is not None, f"listing: {path or 'root'} is reachable")
        if names is None:
            continue
        for child, child_visible in expected.items():
            if os.path.dirname(child) != path:
                continue
            name = os.path.basename(child)
            if child_visible:
                checks.ok(name in names, f"listing: {path}/{name} should be listed")
            else:
                checks.ok(name not in names, f"listing: {path}/{name} should be hidden")

def check_root_listing(checks, base, expected):
    """The root listing hides what it should and shows what it should."""
    names = listing(base, "")
    checks.ok(names is not None, "listing: root is reachable")
    for path, visible in expected.items():
        if "/" in path:
            continue
        if visible:
            checks.ok(path in names, f"listing: root/{path} should be listed")
        else:
            checks.ok(path not in names, f"listing: root/{path} should be hidden")

def check_downloads(checks, base, expected):
    """Hidden files are not downloadable, visible ones are."""
    for path, visible in sorted(expected.items()):
        if path in dict(DIRS):
            continue
        quoted = "/".join(urllib.parse.quote(part) for part in path.split("/"))
        status, _ = request(f"{base}/dl/{quoted}")
        if visible:
            checks.ok(status == 200, f"download: {path} should be served, got {status}")
        else:
            checks.ok(status == 404, f"download: {path} should 404, got {status}")

def check_search(checks, base, expected):
    """No hidden entry ever surfaces in a search, fuzzy or glob."""
    hidden_names = {os.path.basename(p) for p, v in expected.items() if not v}
    visible_names = {os.path.basename(p) for p, v in expected.items() if v}
    for query in ["*", "*.key", "*.txt", "env", "keep", "build", "*.md;*.log", "deep/*"]:
        status, body = request(f"{base}/api/search?q={urllib.parse.quote(query)}")
        checks.ok(status == 200, f"search: {query!r} answered 200, got {status}")
        if status != 200:
            continue
        found = json.loads(body)["matches"]
        paths = {"/".join(m["path"] + [m["name"]]) for m in found}
        leaked = {p for p in paths if not expected.get(p, True)}
        checks.ok(not leaked, f"search: {query!r} leaked hidden entries {sorted(leaked)}")
        for path in paths:
            checks.ok(expected.get(path) is not False, f"search: {query!r} returned hidden {path}")

    status, body = request(f"{base}/api/search?q=*.key")
    checks.ok(json.loads(body)["matches"] == [], "search: '*.key' finds nothing, every key file is hidden")

    status, body = request(f"{base}/api/search?q=.env.example")
    names = {m["name"] for m in json.loads(body)["matches"]}
    checks.ok(names == {".env.example"}, f"search: the re-included name is findable at every depth, got {names}")
    count = len(json.loads(body)["matches"])
    checks.ok(count == 3, f"search: all three .env.example copies found, got {count}")

def check_writes(checks, base, expected):
    """Every write route refuses a hidden path."""
    headers = {"Content-Type": "application/json"}
    for path, visible in sorted(expected.items()):
        if visible or path == ".ignore":
            continue
        status, _ = request(f"{base}/api/rename", "POST", headers,
                            json.dumps({"path": path, "newName": "taken.txt"}).encode())
        checks.ok(status == 404, f"rename: {path} should 404, got {status}")

        status, _ = request(f"{base}/api/delete", "POST", headers,
                            json.dumps({"path": path, "name": os.path.basename(path)}).encode())
        checks.ok(status == 404, f"delete: {path} should 404, got {status}")

        status, _ = request(f"{base}/api/move", "POST", headers,
                            json.dumps({"path": path, "targetDir": "notes"}).encode())
        checks.ok(status == 404, f"move: {path} should 404, got {status}")

    status, _ = request(f"{base}/api/upload", "POST",
                        {"X-Target-Path": "build", "X-Filename": "sneak.txt"}, b"x")
    checks.ok(status == 404, f"upload: into a hidden folder should 404, got {status}")

    status, _ = request(f"{base}/api/upload", "POST",
                        {"X-Target-Path": "notes", "X-Filename": ".env.sneak"}, b"x")
    checks.ok(status == 403, f"upload: creating a hidden name should 403, got {status}")

    status, _ = request(f"{base}/api/upload", "POST",
                        {"X-Target-Path": "notes/deep/deeper/deepest", "X-Filename": "sneak.key"}, b"x")
    checks.ok(status == 403, f"upload: creating a hidden name deep down should 403, got {status}")

    status, _ = request(f"{base}/api/move", "POST", headers,
                        json.dumps({"path": "keep.txt", "targetDir": "build"}).encode())
    checks.ok(status == 404, f"move: into a hidden folder should 404, got {status}")

def check_direct_listing(checks, base, expected):
    """A hidden directory cannot be listed by asking for it directly either."""
    for path, visible in sorted(expected.items()):
        if path not in dict(DIRS) or visible:
            continue
        status, _ = request(f"{base}/api/list?path={urllib.parse.quote(path)}")
        checks.ok(status == 404, f"direct listing: {path} should 404, got {status}")

def check_crawl(checks, base, expected):
    """Walking the served tree reaches every visible path and nothing else."""
    reachable = crawl(base)
    should_reach = {p for p, v in expected.items() if v}
    missing = sorted(should_reach - reachable)
    extra = sorted(reachable - should_reach)
    checks.ok(not missing, f"crawl: unreachable visible paths {missing}")
    checks.ok(not extra, f"crawl: reachable hidden paths {extra}")
    checks.ok(len(reachable) == len(should_reach),
              f"crawl: reached {len(reachable)} paths, expected {len(should_reach)}")

def run_suite(checks, base, srv, expected, label):
    """The whole battery against one server, cached or not."""
    print(f"\n--- {label}")
    before = checks.passed
    check_predicate(checks, srv.store, expected)
    check_root_listing(checks, base, expected)
    check_listings(checks, base, expected)
    check_downloads(checks, base, expected)
    check_search(checks, base, expected)
    check_direct_listing(checks, base, expected)
    check_crawl(checks, base, expected)
    check_writes(checks, base, expected)
    print(f"{checks.passed - before} checks ran")

def main():
    """Builds the tree, runs every check with the cache on and off, and reports."""
    checks = Checks()
    root = tempfile.mkdtemp(prefix="pyserve-ignore-")
    try:
        expected = build_tree(root)

        srv = PyServe(root, port=0, env=False, access_log=False, log_level="warning")
        srv.start(block=False)
        request(f"{srv.url}/")
        request(f"{srv.url}/api/list")
        for _ in range(100):
            if srv.cache.complete:
                break
            time.sleep(0.05)
        checks.ok(srv.cache.complete, "cache warmed before the cached pass")
        run_suite(checks, srv.url, srv, expected, "cache warmed")
        srv.stop()

        srv = PyServe(root, port=0, env=False, cache_enabled=False,
                      access_log=False, log_level="warning")
        srv.start(block=False)
        run_suite(checks, srv.url, srv, expected, "cache disabled")
        srv.stop()

        print("\n--- bundled default rules")
        bare = tempfile.mkdtemp(prefix="pyserve-default-")
        os.makedirs(os.path.join(bare, "pkg", "__pycache__"))
        for path in ["pkg/__pycache__/mod.pyc", "pkg/.env.local", "pkg/.env.example", "pkg/main.py"]:
            with open(os.path.join(bare, path), "w", encoding="utf-8") as handle:
                handle.write("x")
        srv = PyServe(bare, port=0, env=False, access_log=False, log_level="warning")
        srv.start(block=False)
        checks.ok(srv.store.ignore.source == "default.ignore", "bundled rules used when no .ignore exists")
        names = listing(srv.url, "pkg")
        checks.ok(".env.local" not in names, "bundled rules hide .env.local one level down")
        checks.ok(".env.example" in names, "bundled rules re-include .env.example one level down")
        checks.ok("main.py" in names, "bundled rules leave ordinary files alone")
        checks.ok("__pycache__" not in names, "bundled rules hide __pycache__ at depth")
        checks.ok(listing(srv.url, "pkg/__pycache__") is None,
                  "bundled rules make __pycache__ unreachable at depth")
        status, _ = request(srv.url + "/dl/pkg/__pycache__/mod.pyc")
        checks.ok(status == 404, f"bundled rules block downloads from __pycache__ at depth, got {status}")
        srv.stop()
        shutil.rmtree(bare, ignore_errors=True)
    finally:
        shutil.rmtree(root, ignore_errors=True)

    return checks.report()

if __name__ == "__main__":
    sys.exit(main())
