<p align="center">
  <img src="pyserve.png" alt="pyserve" width="620">
</p>

<p align="center">A glorified <code>python3 -m http.server</code> alternative.</p>

Same one command reflex, except it comes with a real directory browser,
gitignore style hiding rules, resumable downloads, parallel uploads with a live
progress panel, fuzzy and pattern search, a background warmed cache for large
trees, authentication, and per user access control over files, extensions,
globs and folders.

Standard library only. No dependencies, no build step.

It is also a library: `PyServe` is a normal class you can import, configure and
run inside your own code.

---

## Install

```bash
git clone https://github.com/theflash2k/pyserve
cd pyserve
pip install .
```

Or run it straight out of the directory, since there is nothing to install:

```bash
python3 pyserve.py
python3 -m pyserve
```

See [docs/installation.md](docs/installation.md).

## Quick start

```bash
# serve the current directory on 0.0.0.0:8000
pyserve

# serve /srv/files on port 9000, read only
pyserve /srv/files -p 9000 --read-only

# the browser basic auth popup
pyserve -a basic -u alice:hunter2

# a sign in page instead
pyserve -a form -u alice:hunter2

# anyone may browse, credentials are needed before any write
pyserve -a form -u alice:hunter2 --auth-scope write

# alice runs the place, nobody touches a key file
pyserve -a form -u alice:hunter2 -u bob:s3cret \
  --iam-default deny \
  --iam-rule "allow *     read  **" \
  --iam-rule "allow alice all   **" \
  --iam-rule "deny  *     all   *.key"
```

See [docs/quickstart.md](docs/quickstart.md).

## Documentation

Everything is documented in [docs/](docs/README.md).

| Page | What it covers |
| --- | --- |
| [Installation](docs/installation.md) | Requirements, installing, upgrading, uninstalling |
| [Quick start](docs/quickstart.md) | A first run and the options worth knowing on day one |
| [Command line](docs/cli.md) | Every flag, grouped, with what it maps to |
| [Configuration](docs/configuration.md) | The four layers, the file format, every key |
| [Browsing](docs/browsing.md) | Folder URLs, the listing, file type icons, editing |
| [Search](docs/search.md) | Fuzzy queries, glob patterns, regular expressions, scoping |
| [Uploads](docs/uploads.md) | The progress panel, parallelism, conflicts, size limits |
| [The .ignore file](docs/ignore.md) | Hiding files, gitignore semantics, negation, defaults |
| [The directory cache](docs/cache.md) | Warming, resets, tuning for a large tree |
| [Authentication](docs/authentication.md) | Basic auth, the sign in form, sessions, hashing |
| [Access control (IAM)](docs/iam.md) | Per user rules over files, extensions, globs, folders |
| [Library use](docs/library.md) | The `PyServe` class and the pieces underneath it |
| [HTTP API](docs/http-api.md) | Every route, its parameters and its responses |
| [Deployment](docs/deployment.md) | TLS, reverse proxies, systemd, containers, hardening |
| [Tests](docs/testing.md) | What is covered and how to run it |

## What it does

**Browsing.** Every folder has its own URL, so a link can be copied, bookmarked
or opened in a new tab. Navigation uses the History API, so nothing reloads and
back and forward work. Files carry a colour coded type badge covering around
330 extensions. Press and hold a row to rename, move or delete.

**Uploads.** Three files at a time by default, each with a live progress bar in
a panel in the corner. Finished files appear in the listing without a reload.
Drop files anywhere on the page, or onto a folder row to upload into it.

**Search.** Runs from the folder you are in rather than from the top. Takes a
fuzzy query, a glob like `*.sql`, several at once with `*.sql;*.db`, or a
regular expression as `/^backup_/i`. Results come back as a tree.

**Hiding.** A gitignore style `.ignore` file at the served root, with `!`
negation, applied to listing, search and download alike. Falls back to a small
bundled default when the directory has none.

**Speed.** Directory listings are held in memory and the tree is warmed in the
background after the first request, on a quarter of the machine's threads.
Every page load rebuilds the cache, so a listing is never stale.

**Permissions.** `READ_ONLY` and individual `ENABLE_*` settings cap what the
server can do at all. Each is enforced server side, so a request sent straight
at the API is refused exactly like a click would be.

**Authentication.** `basic` gives the usual browser popup. `form` gives a sign
in page and a session cookie. `AUTH_SCOPE=write` leaves browsing open and only
guards writes. Passwords may be plain, sha256 or pbkdf2, with
`pyserve --hash-password` to generate the last.

**Access control.** Rules of the form `effect users actions target` decide who
may do what, where:

```ini
IAM_DEFAULT=deny

[iam]
allow *      read           **
deny  *      all            *.key
allow dana   all            finance/
allow bob    upload         dropbox/
deny  bob    delete,move    **
[end]
```

Targets cover an exact file, a name pattern like `*.key` at any depth, a folder
and its contents with `reports/`, or just the contents with `reports/**`. An
explicit deny always wins whatever the order. Listings are filtered rather than
refused, so nobody sees something they cannot open, and deleting or moving a
folder checks every path inside it.

## Configuration

Four layers, each overriding the last:

```
built-in defaults  ->  PYSERVE_* environment  ->  pyserve.conf  ->  CLI flags
```

Start from the shipped sample, which documents every key inline:

```bash
cp pyserve.conf.example pyserve.conf
```

A `pyserve.conf` next to the served directory, in the working directory, or in
your home directory is picked up on its own. `~/.pyserve.conf` is the place for
personal defaults; a config next to a particular directory wins over it.

## As a library

```python
from pyserve import PyServe

server = PyServe(
    "/srv/files",
    port=9000,
    auth_mode="form",
    auth_users={"alice": "hunter2"},
    iam_rules=["deny * all *.key"],
)
server.serve_forever()
```

Run it on a background thread instead, which is what you want when the server
is one part of a larger program:

```python
server = PyServe("/srv/files", port=0, read_only=True)
server.start(block=False)
print(server.url)      # port 0 picks a free one
server.stop()
```

See [docs/library.md](docs/library.md).

## Tests

No dependencies, same as the server:

```bash
python3 tests/test_config.py
python3 tests/test_ignore.py
python3 tests/test_iam.py
```

## Notes

Every path that reaches the filesystem is resolved against the served root and
rejected when it escapes it, so `..` in a URL, in an upload header or in a JSON
body goes nowhere. Symlinks are not followed by default. Ignored entries are
invisible to every route, not just to listings.

Uploads, renames, moves and deletes are serialised behind a single lock, so two
concurrent requests cannot race on the same numbered copy logic or step on each
other halfway through a move.

If the served directory is mounted read only at the OS level, set
`READ_ONLY=true` so the interface reflects that instead of every write failing
with a storage error.

## License

[Apache-2.0](LICENSE)
