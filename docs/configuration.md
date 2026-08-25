# Configuration

## The four layers

Settings are resolved in four layers, and each one overrides the one before it:

```
built-in defaults  ->  PYSERVE_* environment  ->  config file  ->  CLI flags
```

So a value in the config file beats an environment variable, and a command line
flag beats both. A flag that is not given is not applied at all, which is why
`pyserve -p 9000` changes the port and leaves everything else alone.

One setting breaks the pattern deliberately. IAM rules accumulate rather than
replace, so rules from the config file, from `IAM_RULES_FILE` and from
`--iam-rule` are all combined. Because an explicit deny always wins, a later
layer can only ever tighten the policy. See [Access control](iam.md).

## Finding the config file

Without `-c`, pyserve looks for `pyserve.conf` and then `.pyserve.conf`, first
next to the directory being served and then in the working directory. The first
one found is used.

```bash
pyserve                      # autodiscovery
pyserve -c /etc/pyserve.conf # this file and no other
pyserve --no-config          # no file at all
```

Naming a file with `-c` turns autodiscovery off.

Start from the shipped sample, which documents every key inline:

```bash
cp pyserve.conf.example pyserve.conf
```

## File format

```ini
# a comment
KEY=VALUE
KEY = VALUE
KEY="quoted value"

[iam]
allow alice read reports/
[end]
```

- One setting per line. Whitespace around `=` is ignored.
- A line starting with `#` is a comment, as is a blank line.
- One layer of matching single or double quotes is stripped from a value.
- Unknown keys are ignored, so a config written for a newer pyserve still loads.
- `[name]` opens a block. Every line after it is kept verbatim for that block,
  comments included, until `[end]` or the next block header. Blocks let a
  section carry its own format rather than being forced into `KEY=VALUE`.

Booleans accept `true`/`false`, `yes`/`no`, `on`/`off`, `1`/`0` and
`enabled`/`disabled`. Anything unrecognised falls back to the default rather
than raising.

## Environment variables

Every key is also an environment variable, prefixed with `PYSERVE_`:

```bash
PYSERVE_PORT=9000 PYSERVE_READ_ONLY=true pyserve /srv/files
```

Handy in a container or a systemd unit, where a config file would be one more
thing to mount. Turn the whole layer off with `--no-env`.

## Every key

### What to serve

| Key | Default | Meaning |
| --- | --- | --- |
| `DIRECTORY` | `.` | Directory to serve. Relative to the working directory, not to this file. `~` expands. |
| `HOST` | `0.0.0.0` | Bind address. `127.0.0.1` keeps it reachable only from this machine. |
| `PORT` | `8000` | Bind port. `0` asks the OS for a free one. |
| `TITLE` | directory name | Name in the breadcrumb and on the sign in page. |
| `PAGE_TITLE` | `pyserve: <TITLE>` | Text in the browser tab. |

### Hiding files

| Key | Default | Meaning |
| --- | --- | --- |
| `IGNORE_FILE` | `.ignore` | Ignore file resolved at the served root. |
| `DEFAULT_IGNORE` | `true` | Fall back to the bundled rules when that file is absent. |
| `SHOW_HIDDEN` | `true` | Set false to hide dotfiles on top of the ignore rules. |
| `FOLLOW_SYMLINKS` | `false` | Off by default so a link cannot read past the root. |

See [The .ignore file](ignore.md).

### Permissions

| Key | Default | Meaning |
| --- | --- | --- |
| `READ_ONLY` | `false` | Forces the four write settings below to false. |
| `ENABLE_UPLOAD` | `true` | |
| `ENABLE_RENAME` | `true` | |
| `ENABLE_MOVE` | `true` | |
| `ENABLE_DELETE` | `true` | |
| `ENABLE_SEARCH` | `true` | The search endpoint. |
| `ENABLE_DOWNLOAD` | `true` | The download route. Browsing still works without it. |
| `MAX_UPLOAD_MB` | `0` | Upload ceiling in MB. `0` is unlimited. |

Each is enforced on the server, so a request sent straight at the API is turned
down exactly like a click in the interface would be.

### Search and uploads

| Key | Default | Meaning |
| --- | --- | --- |
| `SEARCH_LIMIT` | `300` | Maximum results a single search returns. |
| `UPLOAD_CONCURRENCY` | `3` | How many files the browser uploads at once. |
| `CHUNK_SIZE` | `262144` | Read and write chunk size in bytes. |

### Cache

| Key | Default | Meaning |
| --- | --- | --- |
| `CACHE_ENABLED` | `true` | Hold directory listings in memory. |
| `CACHE_THREADS` | `0` | Warming pool size. `0` picks a quarter of the CPU threads. |
| `CACHE_MAX_DIRS` | `0` | Stop warming after this many directories. `0` is no limit. |

See [The directory cache](cache.md).

### Authentication

| Key | Default | Meaning |
| --- | --- | --- |
| `AUTH_MODE` | `none` | `none`, `basic` or `form`. |
| `AUTH_SCOPE` | `all` | `all` guards everything, `write` guards only the write routes. |
| `AUTH_USERS` | empty | `user:secret` pairs separated by commas. |
| `AUTH_USERS_FILE` | empty | htpasswd style file, merged on top of `AUTH_USERS`. |
| `AUTH_REALM` | `pyserve` | Realm shown in the basic auth popup. |
| `SESSION_TTL` | `86400` | Session lifetime in seconds, form mode only. |
| `SESSION_COOKIE` | `pyserve_session` | Name of the session cookie. |
| `COOKIE_SECURE` | `false` | Add the `Secure` flag to the session cookie. |

See [Authentication](authentication.md).

### Access control

| Key | Default | Meaning |
| --- | --- | --- |
| `IAM_DEFAULT` | `allow` | What happens when no rule matches. |
| `IAM_RULES_FILE` | empty | File of rules, one per line, added to the block. |
| `[iam]` block | empty | The policy itself. |

See [Access control (IAM)](iam.md).

### TLS

| Key | Default | Meaning |
| --- | --- | --- |
| `TLS_CERT` | empty | PEM certificate. Both halves are required together. |
| `TLS_KEY` | empty | Matching private key. |

### Output

| Key | Default | Meaning |
| --- | --- | --- |
| `LOG_LEVEL` | `info` | `debug`, `info`, `warning`, `error`, `quiet`. |
| `ACCESS_LOG` | `true` | Log a line for every request. |
| `SERVER_HEADER` | `pyserve` | Value of the `Server` response header. |

The Python and operating system versions are never advertised, whatever
`SERVER_HEADER` is set to.

## Validation

Bad configuration fails at startup with a message rather than at the first
request:

- A `DIRECTORY` that is not a directory.
- An `AUTH_MODE`, `AUTH_SCOPE` or `IAM_DEFAULT` that is not one of the allowed
  values.
- `TLS_CERT` without `TLS_KEY`, or the other way round.
- An auth mode with no users configured.
- An `IAM_RULES_FILE` that does not exist, or an IAM rule that does not parse.
  The error names the file and line.

## Worked examples

A public read only mirror behind a reverse proxy:

```ini
HOST=127.0.0.1
DIRECTORY=/srv/mirror
READ_ONLY=true
ACCESS_LOG=false
```

A private drop box that accepts files but never gives them up:

```ini
DIRECTORY=/srv/inbox
AUTH_MODE=form
AUTH_USERS_FILE=/etc/pyserve/users
COOKIE_SECURE=true
MAX_UPLOAD_MB=2048
ENABLE_DOWNLOAD=false
ENABLE_RENAME=false
ENABLE_MOVE=false
ENABLE_DELETE=false
```

A large archive tuned for browsing:

```ini
DIRECTORY=/mnt/archive
READ_ONLY=true
CACHE_THREADS=12
CACHE_MAX_DIRS=200000
SEARCH_LIMIT=100
```

A shared server where each team only sees its own folder:

```ini
AUTH_MODE=form
AUTH_USERS_FILE=/etc/pyserve/users
IAM_DEFAULT=deny

[iam]
allow alice,bob   all   team-a/
allow carol,dana  all   team-b/
deny  *           all   *.key
[end]
```
