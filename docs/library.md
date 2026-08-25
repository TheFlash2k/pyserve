# Library use

Everything the command line does is available as a class. `PyServe` is a normal
object you construct, start and stop.

## The basics

```python
from pyserve import PyServe

server = PyServe(
    "/srv/files",
    port=9000,
    title="Vault",
    read_only=True,
)
server.serve_forever()
```

Any configuration key can be passed as a keyword argument, in its lowercase
form: `read_only`, `max_upload_mb`, `auth_mode`, `cache_threads` and so on. See
[Configuration](configuration.md) for the full list.

## Running in the background

```python
server = PyServe("/srv/files", port=0)
server.start(block=False)

print(server.url)     # http://127.0.0.1:41337

server.stop()
```

`port=0` asks the operating system for a free port, which is what you want in
tests. `server.port` reports the one actually bound.

It is a context manager too:

```python
with PyServe("/srv/files", port=0) as server:
    print(server.url)
```

## Configuration objects

```python
from pyserve import Config, PyServe

config = Config.load(
    config_file="pyserve.conf",
    overrides={"port": 9000, "read_only": True},
)

print(config.capabilities)
print(config.max_upload_bytes)

PyServe(config=config).serve_forever()
```

By default `PyServe(...)` also reads the `PYSERVE_*` environment. Pass
`env=False` to build a server that only listens to what you handed it, which
matters in tests where a stray variable would change the result.

```python
PyServe("/srv/files", env=False, autodiscover=False)
```

## Properties and methods

| Member | What it does |
| --- | --- |
| `config` | The resolved `Config` |
| `store` | The `FileStore` rooted at the served directory |
| `cache` | The `DirectoryCache` |
| `auth` | The `Authenticator` |
| `iam` | The `IAMPolicy` |
| `write_lock` | The lock serialising writes |
| `url` | The address the server can be reached at |
| `port` | The bound port |
| `scheme` | `http` or `https` |
| `running` | True while accepting connections |
| `start(block=True)` | Start serving |
| `serve_forever()` | Blocking alias for `start()` |
| `stop()` | Stop and release the socket |
| `summary()` | One line describing the active permissions |
| `reload_ignore()` | Re-read the ignore file |
| `reset_cache()` | Empty the cache and arm a warm |
| `warm_cache()` | Start that warm now |
| `cache_stats()` | Cache counters |
| `may(user, action, path)` | Ask the IAM policy a question |
| `add_user(name, secret)` | Add a credential at runtime |
| `remove_user(name)` | Drop a credential |

## Access control

```python
from pyserve import PyServe, hash_password

server = PyServe(
    "/srv/files",
    auth_mode="form",
    auth_users={"alice": hash_password("hunter2")},
    iam_default="deny",
    iam_rules=[
        "allow *     read  **",
        "allow alice all   **",
        "deny  *     all   *.key",
    ],
)

server.may("alice", "delete", "notes.txt")   # True
server.may("bob", "delete", "notes.txt")     # False
server.iam.permissions("bob", "notes.txt")
server.iam.describe("bob")
```

See [Access control (IAM)](iam.md).

## The pieces on their own

Each layer is usable without the server.

### Ignore rules

```python
from pyserve import IgnoreList

rules = IgnoreList.from_lines([".env.*", "!.env.example", "__pycache__/"])
rules.is_path_ignored(".env.local", is_dir=False)     # True
rules.is_path_ignored(".env.example", is_dir=False)   # False

rules = IgnoreList.from_file("/srv/files/.ignore")
len(rules), rules.source
```

### The filesystem layer

```python
from pyserve import FileStore

store = FileStore("/srv/files", show_hidden=False)
store.listdir("sub/folder")
store.search("report")
store.search("*.sql", rel_path="src")
store.resolve("../etc/passwd")            # None, it escapes the root
store.is_path_hidden(".env.local", False)
list(store.walk_tree("reports"))
```

`resolve` returning `None` is the path safety boundary: every path that reaches
the filesystem goes through it.

### The cache

```python
from pyserve import DirectoryCache, FileStore

cache = DirectoryCache(threads=4)
store = FileStore("/srv/files", cache=cache)
cache.warm(store)
cache.complete, len(cache)
cache.stats()
```

### Authentication

```python
from pyserve import Authenticator, hash_password, verify_password

auth = Authenticator(mode="form", users={"alice": hash_password("hunter2")})
token = auth.login("alice", "hunter2")
auth.sessions.get(token)         # 'alice'
auth.logout(f"pyserve_session={token}")
```

### The policy

```python
from pyserve import IAMPolicy
from pyserve.iam import IAMRule

policy = IAMPolicy.from_lines([
    "default deny",
    "allow alice read reports/",
])
policy.allows("alice", "download", "reports/q1.pdf")   # True
policy.allows("bob", "download", "reports/q1.pdf")     # False
policy.permissions("alice", "reports")
policy.filter_entries("alice", "", [{"name": "reports", "type": "dir"}])

IAMRule.parse("deny * all *.key")
```

### The search matcher

```python
from pyserve.fs import QueryMatcher

m = QueryMatcher("*.sql;*.db")
m.score("schema.sql") >= 0       # matched
m.has_glob, m.has_regex
QueryMatcher("/[/").error
```

## Custom handlers

The handler reads everything from the `PyServe` instance the socket server
carries, so several servers can run in one process with different roots,
permissions and credentials without interfering:

```python
from pyserve import PyServe

public = PyServe("/srv/public", port=8000, read_only=True)
private = PyServe("/srv/private", port=8001, auth_mode="basic",
                  auth_users={"alice": "hunter2"})

public.start(block=False)
private.start(block=False)
```

To extend the routes, subclass the handler and hand it to your own server; the
handler resolves `self.server.app` for its configuration, so anything you build
on it gets the same behaviour.

```python
from pyserve.handler import PyServeHandler

class MyHandler(PyServeHandler):
    def _route_get(self):
        if self.route == "/healthz":
            self.send_json(200, {"ok": True})
            return
        super()._route_get()
```

## Logging

pyserve logs through a named logger, so it does not touch the root logger or
anyone else's configuration:

```python
from pyserve import Logger, logger

Logger.set_level("debug")
logger.info("something")
```

Pass `log_level` and `access_log` when constructing the server to control it
declaratively instead.
