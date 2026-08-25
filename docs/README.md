# pyserve documentation

A glorified `python3 -m http.server` alternative: a directory browser with
gitignore style hiding rules, resumable downloads, parallel uploads, fuzzy and
pattern search, a background warmed cache for large trees, authentication, and
per user access control. Standard library only, no dependencies.

## Getting started

| Page | What it covers |
| --- | --- |
| [Installation](installation.md) | Requirements, installing, running, upgrading, uninstalling |
| [Quick start](quickstart.md) | A first run, then the handful of options worth knowing on day one |

## Using it

| Page | What it covers |
| --- | --- |
| [Command line](cli.md) | Every flag, grouped, with what it maps to |
| [Configuration](configuration.md) | The four layers, the file format, every key |
| [Browsing](browsing.md) | Folder URLs, the listing, file type icons, editing |
| [Search](search.md) | Fuzzy queries, glob patterns, regular expressions, scoping |
| [Uploads](uploads.md) | The progress panel, parallelism, conflicts, size limits |
| [The .ignore file](ignore.md) | Hiding files, gitignore semantics, negation, the bundled rules |
| [The directory cache](cache.md) | How warming works, when it resets, tuning it |

## Access

| Page | What it covers |
| --- | --- |
| [Authentication](authentication.md) | Basic auth, the sign in form, sessions, password hashing |
| [Access control (IAM)](iam.md) | Per user rules over files, extensions, globs and folders |

## Building on it

| Page | What it covers |
| --- | --- |
| [Library use](library.md) | The `PyServe` class and the pieces underneath it |
| [HTTP API](http-api.md) | Every route, its parameters and its responses |
| [Deployment](deployment.md) | TLS, reverse proxies, systemd, containers, hardening |
| [Tests](testing.md) | What is covered and how to run it |

## Where things live

```
pyserve/
├── pyserve.py            entry point shim, python3 pyserve.py
├── pyserve.conf.example  fully commented sample configuration
├── .ignore               sample ignore rules
├── setup.py
├── docs/                 this documentation
├── tests/                test suites, no dependencies
└── pyserve/
    ├── __init__.py       public exports
    ├── __main__.py       python3 -m pyserve
    ├── cli.py            argument parsing and the CLI entry point
    ├── config.py         Config, the four layer settings resolver
    ├── server.py         PyServe, the class you embed
    ├── handler.py        PyServeHandler, every HTTP route
    ├── auth.py           Authenticator, SessionStore, password hashing
    ├── iam.py            IAMPolicy, IAMRule, target matching
    ├── cache.py          DirectoryCache, the background warmed listing cache
    ├── fs.py             FileStore, path safety, listing and search
    ├── ignore.py         IgnoreList, gitignore semantics with negation
    ├── assets/           the frontend, served from /static
    └── utils/            logger and small parsing helpers
```
