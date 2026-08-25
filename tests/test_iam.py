#!/usr/bin/env python3

"""Tests for the IAM policy.

Covers rule parsing, the four target forms, deny precedence, the default
effect, and every HTTP route the policy guards, with and without the cache.

Run it with:

    python3 tests/test_iam.py
"""

import base64
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

from pyserve import Config, PyServe
from pyserve.iam import ACTIONS, IAMPolicy, IAMRule

TREE = [
    "public/notes.txt",
    "public/readme.md",
    "public/deep/inner.txt",
    "reports/q1.pdf",
    "reports/q2.pdf",
    "reports/archive/old.pdf",
    "secrets/server.key",
    "secrets/token.txt",
    "mixed/data.csv",
    "mixed/backup.key",
    "top.txt",
]

USERS = "alice:pw,bob:pw,carol:pw"

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
    """Writes the fixture tree."""
    for path in TREE:
        full = os.path.join(root, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as handle:
            handle.write(f"contents of {path}\n")

def auth_header(user):
    """A basic auth header for one of the fixture users."""
    token = base64.b64encode(f"{user}:pw".encode()).decode()
    return {"Authorization": "Basic " + token}

def request(url, user=None, method="GET", headers=None, body=None):
    """Returns (status, bytes) and never raises on an HTTP error."""
    merged = dict(headers or {})
    if user:
        merged.update(auth_header(user))
    req = urllib.request.Request(url, method=method, data=body, headers=merged)
    try:
        response = urllib.request.urlopen(req)
        return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()

def listing(base, user, rel_path=""):
    """Names in a listing, or None when the route refused."""
    status, body = request(f"{base}/api/list?path={urllib.parse.quote(rel_path)}", user)
    if status != 200:
        return None
    return sorted(entry["name"] for entry in json.loads(body)["entries"])

def search(base, user, query, rel_path=""):
    """Result paths for a search, or None when the route refused."""
    url = f"{base}/api/search?q={urllib.parse.quote(query)}&path={urllib.parse.quote(rel_path)}"
    status, body = request(url, user)
    if status != 200:
        return None
    return sorted("/".join(m["path"] + [m["name"]]) for m in json.loads(body)["matches"])

def check_parsing(checks):
    """Rules parse, aliases expand, and bad input is rejected with a reason."""
    rule = IAMRule.parse("allow alice read reports/**")
    checks.ok(rule.effect == "allow" and rule.users == {"alice"}, "parse: effect and user")
    checks.ok(rule.actions == {"list", "download", "search"}, f"parse: read alias, got {rule.actions}")

    rule = IAMRule.parse("deny bob,carol write **")
    checks.ok(rule.users == {"bob", "carol"}, "parse: a comma separated user list")
    checks.ok(rule.actions == {"upload", "rename", "move", "delete"}, "parse: write alias")

    rule = IAMRule.parse("deny * all *.key")
    checks.ok(rule.actions == set(ACTIONS), "parse: all alias covers every action")

    rule = IAMRule.parse("deny !dana all finance/")
    checks.ok(rule.excluded == {"dana"} and rule.users == {"*"},
              "parse: an exclusion implies everyone else")
    checks.ok(not rule.covers_user("dana") and rule.covers_user("alice"),
              "parse: the excluded user is not covered")

    rule = IAMRule.parse("deny *,!alice all *.key")
    checks.ok(not rule.covers_user("alice") and rule.covers_user("bob"),
              "parse: a star with an exclusion")

    rule = IAMRule.parse("allow alice download my report.pdf")
    checks.ok(rule.target.raw == "my report.pdf", f"parse: a target with a space, got {rule.target.raw!r}")

    for line, why in [
        ("allow alice read", "too few fields"),
        ("maybe alice read **", "an unknown effect"),
        ("allow alice fly **", "an unknown action"),
        ("allow  read **", "no user"),
        ("allow ! read **", "an empty exclusion"),
    ]:
        try:
            IAMRule.parse(line)
            checks.ok(False, f"parse: {why} should be rejected")
        except ValueError:
            checks.ok(True, f"parse: {why} is rejected")

    policy = IAMPolicy.from_lines([
        "# a comment",
        "",
        "default deny",
        "allow alice read **",
    ])
    checks.ok(policy.default == "deny", "parse: the default directive is honoured")
    checks.ok(len(policy) == 1, "parse: comments and blank lines are skipped")

    try:
        IAMPolicy.from_lines(["allow alice read **", "nonsense"], source="conf")
        checks.ok(False, "parse: a bad line reports where it is")
    except ValueError as problem:
        checks.ok("conf:2" in str(problem), f"parse: a bad line reports where it is, got {problem}")

def check_evaluation(checks):
    """Deny precedence, the default effect, and the wildcard user."""
    policy = IAMPolicy.from_lines([
        "allow * read **",
        "deny * read secrets/",
    ])
    checks.ok(policy.allows("alice", "list", "public"), "eval: an allow with no deny lets it through")
    checks.ok(not policy.allows("alice", "list", "secrets"), "eval: deny wins on the folder")
    checks.ok(not policy.allows("alice", "download", "secrets/server.key"), "eval: deny covers the subtree")

    policy = IAMPolicy.from_lines([
        "deny * download *.key",
        "allow * download **",
    ])
    checks.ok(not policy.allows("bob", "download", "a/b/c.key"),
              "eval: deny wins even when the allow comes after it")

    policy = IAMPolicy.from_lines(["default deny", "allow alice read reports/**"])
    checks.ok(policy.allows("alice", "download", "reports/q1.pdf"), "eval: default deny with a matching allow")
    checks.ok(not policy.allows("alice", "download", "top.txt"), "eval: default deny with no match")
    checks.ok(not policy.allows("bob", "download", "reports/q1.pdf"), "eval: the rule is user scoped")

    policy = IAMPolicy.from_lines(["deny anonymous write **"])
    checks.ok(not policy.allows(None, "delete", "top.txt"), "eval: an unauthenticated user is 'anonymous'")
    checks.ok(policy.allows("alice", "delete", "top.txt"), "eval: named users are unaffected by it")

    policy = IAMPolicy.from_lines(["deny !dana all finance/", "allow dana all finance/"])
    checks.ok(policy.allows("dana", "download", "finance/x.pdf"),
              "eval: the excluded user keeps access through the deny")
    checks.ok(not policy.allows("alice", "download", "finance/x.pdf"),
              "eval: everyone else is denied")
    checks.ok(not policy.allows(None, "download", "finance/x.pdf"),
              "eval: anonymous is denied by an exclusion rule too")

    policy = IAMPolicy.from_lines(["deny * all finance/", "allow dana all finance/"])
    checks.ok(not policy.allows("dana", "download", "finance/x.pdf"),
              "eval: a later allow cannot undo a blanket deny, which is why '!' exists")

    empty = IAMPolicy.from_lines([])
    checks.ok(all(empty.allows("alice", action, "anything") for action in ACTIONS),
              "eval: an empty policy allows everything")
    checks.ok(not empty.enabled, "eval: an empty policy reports itself disabled")

def check_config_block(checks, root):
    """The [iam] block is read from the config file and layers accumulate."""
    path = os.path.join(root, "block.conf")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(
            "PORT=9999\n"
            "IAM_DEFAULT=deny\n"
            "[iam]\n"
            "# only alice gets the reports\n"
            "allow alice read reports/**\n"
            "deny  *     all  *.key\n"
            "[end]\n"
            "TITLE=Blocked\n"
        )
    config = Config.load(config_file=path, overrides={"directory": root}, env=False)
    checks.ok(config.port == 9999 and config.title == "Blocked",
              "block: settings before and after the block are still read")
    checks.ok(len(config.iam_rules) == 3, f"block: rule lines captured, got {config.iam_rules}")
    checks.ok(config.iam_default == "deny", "block: IAM_DEFAULT is read as a normal key")

    policy = IAMPolicy.from_lines(config.iam_rules, default=config.iam_default)
    checks.ok(len(policy) == 2, "block: comments inside the block are skipped")
    checks.ok(policy.allows("alice", "download", "reports/q1.pdf"), "block: the allow works")
    checks.ok(not policy.allows("alice", "download", "secrets/server.key"), "block: the deny works")

    config = Config.load(config_file=path, overrides={
        "directory": root, "iam_rules": ["deny alice download reports/q2.pdf"],
    }, env=False)
    checks.ok(len(config.iam_rules) == 4, "block: a CLI rule is added to the file's rules")
    policy = IAMPolicy.from_lines(config.iam_rules, default=config.iam_default)
    checks.ok(policy.allows("alice", "download", "reports/q1.pdf")
              and not policy.allows("alice", "download", "reports/q2.pdf"),
              "block: a later layer can tighten but not loosen")

def check_routes(checks, root, cached):
    """Every guarded route, against a running server."""
    label = "cached" if cached else "walked"
    rules = [
        "default deny",
        "allow * read **",
        "allow alice all **",
        "deny * all secrets/",
        "deny * all *.key",
        "allow bob write public/**",
        "deny bob delete public/deep/",
    ]
    srv = PyServe(root, port=0, env=False, cache_enabled=cached,
                  auth_mode="basic", auth_users=USERS, iam_rules=rules,
                  access_log=False, log_level="error")
    srv.start(block=False)
    base = srv.url
    if cached:
        request(f"{base}/", "alice")
        request(f"{base}/api/list", "alice")
        for _ in range(100):
            if srv.cache.complete:
                break
            time.sleep(0.05)
        checks.ok(srv.cache.complete, f"[{label}] cache warmed")

    names = listing(base, "alice")
    checks.ok(names == ["mixed", "public", "reports", "top.txt"],
              f"[{label}] the secrets folder is filtered out of the root listing: {names}")

    names = listing(base, "alice", "mixed")
    checks.ok(names == ["data.csv"], f"[{label}] a denied extension is filtered out: {names}")

    checks.ok(listing(base, "alice", "secrets") is None,
              f"[{label}] listing the denied folder directly is refused")
    status, _ = request(f"{base}/api/list?path=secrets", "alice")
    checks.ok(status == 403, f"[{label}] and it is a 403, got {status}")

    status, _ = request(f"{base}/dl/secrets/token.txt", "alice")
    checks.ok(status == 403, f"[{label}] downloading from the denied folder is refused, got {status}")
    status, _ = request(f"{base}/dl/mixed/backup.key", "alice")
    checks.ok(status == 403, f"[{label}] downloading a denied extension is refused, got {status}")
    status, _ = request(f"{base}/dl/public/notes.txt", "alice")
    checks.ok(status == 200, f"[{label}] an allowed download still works, got {status}")

    status, _ = request(f"{base}/secrets/", "alice")
    checks.ok(status == 403, f"[{label}] the folder URL is refused too, got {status}")
    status, _ = request(f"{base}/public/", "alice")
    checks.ok(status == 200, f"[{label}] an allowed folder URL works, got {status}")

    hits = search(base, "alice", "*")
    checks.ok(hits is not None and not any(h.startswith("secrets") for h in hits),
              f"[{label}] search never returns the denied folder: {hits}")
    checks.ok(hits is not None and not any(h.endswith(".key") for h in hits),
              f"[{label}] search never returns a denied extension: {hits}")

    status, _ = request(f"{base}/api/upload", "bob", "POST",
                        {"X-Target-Path": "public", "X-Filename": "bob.txt"}, b"hi")
    checks.ok(status == 200, f"[{label}] bob may upload where he is allowed, got {status}")
    status, _ = request(f"{base}/api/upload", "bob", "POST",
                        {"X-Target-Path": "reports", "X-Filename": "bob.txt"}, b"hi")
    checks.ok(status == 403, f"[{label}] bob may not upload elsewhere, got {status}")
    status, _ = request(f"{base}/api/upload", "bob", "POST",
                        {"X-Target-Path": "public", "X-Filename": "sneak.key"}, b"hi")
    checks.ok(status == 403, f"[{label}] the extension deny blocks the upload name, got {status}")

    status, _ = request(f"{base}/api/upload", "carol", "POST",
                        {"X-Target-Path": "public", "X-Filename": "carol.txt"}, b"hi")
    checks.ok(status == 403, f"[{label}] carol has read only, uploads refused, got {status}")

    headers = {"Content-Type": "application/json"}
    status, _ = request(f"{base}/api/rename", "bob", "POST", headers,
                        json.dumps({"path": "public/bob.txt", "newName": "renamed.txt"}).encode())
    checks.ok(status == 200, f"[{label}] bob may rename inside public, got {status}")
    status, _ = request(f"{base}/api/rename", "bob", "POST", headers,
                        json.dumps({"path": "public/renamed.txt", "newName": "renamed.key"}).encode())
    checks.ok(status == 403, f"[{label}] renaming into a denied name is refused, got {status}")

    status, _ = request(f"{base}/api/delete", "bob", "POST", headers,
                        json.dumps({"path": "public/deep", "name": "deep"}).encode())
    checks.ok(status == 403,
              f"[{label}] deleting a folder bob is denied inside is refused, got {status}")
    checks.ok(os.path.isdir(os.path.join(root, "public", "deep")),
              f"[{label}] and the folder is still there")

    status, _ = request(f"{base}/api/delete", "bob", "POST", headers,
                        json.dumps({"path": "public/renamed.txt"}).encode())
    checks.ok(status == 200, f"[{label}] deleting an allowed file works, got {status}")

    status, body = request(f"{base}/api/permissions?path=mixed/backup.key", "alice")
    perms = json.loads(body)["permissions"]
    checks.ok(status == 200 and perms["download"] is False and perms["list"] is False,
              f"[{label}] /api/permissions reports the denial: {perms}")

    status, body = request(f"{base}/api/list?path=mixed", "alice")
    entry = json.loads(body)["entries"][0]
    checks.ok("perms" in entry and entry["perms"]["download"] is True,
              f"[{label}] entries carry a permission map: {entry}")
    checks.ok(json.loads(body)["perms"]["upload"] is True,
              f"[{label}] the listing carries the folder's permissions")

    srv.stop()

def check_anonymous(checks, root):
    """A policy still applies when nobody is signed in."""
    srv = PyServe(root, port=0, env=False,
                  iam_rules=["deny anonymous write **", "deny anonymous read secrets/"],
                  access_log=False, log_level="error")
    srv.start(block=False)
    base = srv.url
    names = listing(base, None)
    checks.ok(names is not None and "secrets" not in names, f"anonymous: the deny applies: {names}")
    status, _ = request(f"{base}/api/upload", None, "POST",
                        {"X-Target-Path": "", "X-Filename": "x.txt"}, b"hi")
    checks.ok(status == 403, f"anonymous: writes are refused, got {status}")
    status, _ = request(f"{base}/dl/top.txt", None)
    checks.ok(status == 200, f"anonymous: reads still work, got {status}")
    srv.stop()

def main():
    """Runs every check and reports."""
    checks = Checks()
    root = tempfile.mkdtemp(prefix="pyserve-iam-")
    try:
        build_tree(root)
        print("--- parsing")
        check_parsing(checks)
        print("--- evaluation")
        check_evaluation(checks)
        print("--- config block")
        scratch = tempfile.mkdtemp(prefix="pyserve-iam-conf-")
        try:
            check_config_block(checks, scratch)
        finally:
            shutil.rmtree(scratch, ignore_errors=True)
        for cached in (True, False):
            print(f"--- routes, cache {'on' if cached else 'off'}")
            check_routes(checks, root, cached)
        print("--- anonymous")
        check_anonymous(checks, root)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return checks.report()

if __name__ == "__main__":
    sys.exit(main())
