# Command line

Every flag maps onto a configuration key, and the command line is the last
layer to be applied, so a flag always beats the config file and the
environment. See [Configuration](configuration.md) for how the layers stack.

Flags that are not given are not applied at all, rather than being applied as
their default. That is what lets `pyserve -p 9000` change the port without
resetting everything else the config file said.

## Full usage

```
usage: pyserve [-h] [-H HOST] [-p PORT] [-c CONFIG] [--no-config] [--no-env] [-i IGNORE_FILE]
               [-t TITLE] [--page-title PAGE_TITLE] [--no-default-ignore] [-r] [--no-upload]
               [--no-rename] [--no-move] [--no-delete] [--no-search] [--no-download] [--no-hidden]
               [--follow-symlinks] [-m MAX_UPLOAD_MB] [--upload-concurrency UPLOAD_CONCURRENCY]
               [--no-cache] [--cache-threads CACHE_THREADS] [--cache-max-dirs CACHE_MAX_DIRS]
               [-a {none,basic,form}] [-u USER:SECRET] [--users-file AUTH_USERS_FILE]
               [--realm AUTH_REALM] [--auth-scope {all,write}] [--session-ttl SESSION_TTL]
               [--secure-cookie] [--hash-password] [--iam-rule RULE]
               [--iam-rules-file IAM_RULES_FILE] [--iam-default {allow,deny}]
               [--tls-cert TLS_CERT] [--tls-key TLS_KEY] [-l LOG_LEVEL] [-q] [--no-access-log]
               [-v]
               [directory]

Serve a directory over HTTP with browsing, resumable downloads, upload, rename, move, delete,
search and authentication.

positional arguments:
  directory             Directory to serve [default: .]

options:
  -h, --help            show this help message and exit
  -H HOST, --host HOST  Bind address [default: 0.0.0.0]
  -p PORT, --port PORT  Bind port [default: 8000]
  -c CONFIG, --config CONFIG
                        Path to a pyserve.conf file
  --no-config           Skip the pyserve.conf autodiscovery
  --no-env              Ignore every PYSERVE_ environment variable
  -i IGNORE_FILE, --ignore-file IGNORE_FILE
                        Ignore file name resolved at the served root [default: .ignore]
  -t TITLE, --title TITLE
                        Name shown in the breadcrumb and on the sign in page [default: the
                        directory name]
  --page-title PAGE_TITLE
                        Text in the browser tab [default: pyserve: <title>]
  --no-default-ignore   Do not fall back to the ignore rules bundled with pyserve

permissions:
  -r, --read-only       Refuse every write, whatever the config says
  --no-upload           Disable uploading
  --no-rename           Disable renaming
  --no-move             Disable moving
  --no-delete           Disable deleting
  --no-search           Disable the search endpoint
  --no-download         Disable file downloads
  --no-hidden           Hide dotfiles as well as ignored entries
  --follow-symlinks     Follow symlinks when listing and walking
  -m MAX_UPLOAD_MB, --max-upload-mb MAX_UPLOAD_MB
                        Reject uploads larger than this [0 = unlimited]
  --upload-concurrency UPLOAD_CONCURRENCY
                        How many files the browser uploads at once [default: 3]

cache:
  --no-cache            Do not keep directory listings in memory
  --cache-threads CACHE_THREADS
                        Warming pool size [0 = a quarter of the CPU threads]
  --cache-max-dirs CACHE_MAX_DIRS
                        Stop warming after this many directories [0 = no limit]

authentication:
  -a {none,basic,form}, --auth {none,basic,form}
                        Authentication mode [default: none]
  -u USER:SECRET, --user USER:SECRET
                        Add a credential, repeatable
  --users-file AUTH_USERS_FILE
                        htpasswd style file of USER:SECRET lines
  --realm AUTH_REALM    Realm shown in the basic auth popup
  --auth-scope {all,write}
                        Guard everything, or only the write routes [default: all]
  --session-ttl SESSION_TTL
                        Session lifetime in seconds for the sign in form
  --secure-cookie       Add the Secure flag to the session cookie
  --hash-password       Print a pbkdf2 hash for a password and exit

access control:
  --iam-rule RULE       Add a policy rule, 'effect users actions target', repeatable
  --iam-rules-file IAM_RULES_FILE
                        File of policy rules, one per line
  --iam-default {allow,deny}
                        What happens when no rule matches [default: allow]

tls:
  --tls-cert TLS_CERT   Path to a PEM certificate
  --tls-key TLS_KEY     Path to the matching private key

output:
  -l LOG_LEVEL, --log-level LOG_LEVEL
                        debug, info, warning, error or quiet [default: info]
  -q, --quiet           Only log errors
  --no-access-log       Stop logging every request
  -v, --version         show program's version number and exit
```

## Positional

| Flag | Key | Notes |
| --- | --- | --- |
| `directory` | `DIRECTORY` | Defaults to the current directory. `~` is expanded. |

## General

| Flag | Key | Notes |
| --- | --- | --- |
| `-H`, `--host` | `HOST` | `0.0.0.0` accepts from anywhere, `127.0.0.1` keeps it local |
| `-p`, `--port` | `PORT` | `0` asks the operating system for a free port |
| `-c`, `--config` | | Path to a config file. Turns autodiscovery off. |
| `--no-config` | | Skip autodiscovery without naming a file |
| `--no-env` | | Ignore every `PYSERVE_` environment variable |
| `-i`, `--ignore-file` | `IGNORE_FILE` | Name of the ignore file at the served root |
| `-t`, `--title` | `TITLE` | Name in the breadcrumb and on the sign in page |
| `--page-title` | `PAGE_TITLE` | Browser tab text, defaults to `pyserve: <title>` |
| `--no-default-ignore` | `DEFAULT_IGNORE` | Do not fall back to the bundled ignore rules |
| `-v`, `--version` | | Print the version and exit |

## Permissions

| Flag | Key | Notes |
| --- | --- | --- |
| `-r`, `--read-only` | `READ_ONLY` | Refuses every write. Forces the four below off. |
| `--no-upload` | `ENABLE_UPLOAD` | |
| `--no-rename` | `ENABLE_RENAME` | |
| `--no-move` | `ENABLE_MOVE` | |
| `--no-delete` | `ENABLE_DELETE` | |
| `--no-search` | `ENABLE_SEARCH` | Turns the search endpoint off entirely |
| `--no-download` | `ENABLE_DOWNLOAD` | Browsing still works, downloading does not |
| `--no-hidden` | `SHOW_HIDDEN` | Hide dotfiles as well as ignored entries |
| `--follow-symlinks` | `FOLLOW_SYMLINKS` | Off by default, so a link cannot escape the root |
| `-m`, `--max-upload-mb` | `MAX_UPLOAD_MB` | `0` is unlimited |
| `--upload-concurrency` | `UPLOAD_CONCURRENCY` | How many files the browser sends at once |

These are global caps. A user can never do more than they allow, whatever an
IAM rule says.

## Cache

| Flag | Key | Notes |
| --- | --- | --- |
| `--no-cache` | `CACHE_ENABLED` | Do not hold listings in memory |
| `--cache-threads` | `CACHE_THREADS` | `0` picks a quarter of the CPU threads |
| `--cache-max-dirs` | `CACHE_MAX_DIRS` | `0` is no limit |

See [The directory cache](cache.md).

## Authentication

| Flag | Key | Notes |
| --- | --- | --- |
| `-a`, `--auth` | `AUTH_MODE` | `none`, `basic` or `form` |
| `-u`, `--user` | `AUTH_USERS` | `USER:SECRET`, repeatable. Implies `-a basic` if no mode is given. |
| `--users-file` | `AUTH_USERS_FILE` | htpasswd style file, merged on top of `-u` |
| `--realm` | `AUTH_REALM` | Shown in the basic auth popup |
| `--auth-scope` | `AUTH_SCOPE` | `all` guards everything, `write` guards only writes |
| `--session-ttl` | `SESSION_TTL` | Seconds, form mode only |
| `--secure-cookie` | `COOKIE_SECURE` | Add `Secure` to the session cookie |
| `--hash-password` | | Prompt for a password, print a pbkdf2 hash, exit |

See [Authentication](authentication.md).

## Access control

| Flag | Key | Notes |
| --- | --- | --- |
| `--iam-rule` | `[iam]` block | One rule, repeatable. Added to the config file's rules. |
| `--iam-rules-file` | `IAM_RULES_FILE` | File of rules, one per line |
| `--iam-default` | `IAM_DEFAULT` | `allow` or `deny` when no rule matches |

Unlike every other setting, IAM rules accumulate across layers rather than
replacing one another. Since an explicit deny always wins, a command line rule
can tighten the policy a config file declared but never loosen it.

See [Access control (IAM)](iam.md).

## TLS

| Flag | Key | Notes |
| --- | --- | --- |
| `--tls-cert` | `TLS_CERT` | PEM certificate |
| `--tls-key` | `TLS_KEY` | Matching private key |

Both are required together. See [Deployment](deployment.md).

## Output

| Flag | Key | Notes |
| --- | --- | --- |
| `-l`, `--log-level` | `LOG_LEVEL` | `debug`, `info`, `warning`, `error`, `quiet` |
| `-q`, `--quiet` | | Errors only, and no access log |
| `--no-access-log` | `ACCESS_LOG` | Stop logging every request |

`debug` adds cache warming detail. IAM denials are logged at `warning`.

## Notes on a few flags

**`--read-only` only tightens.** It can turn read only mode on, never off. A
config file that set `READ_ONLY=true` cannot be overridden back to writable
from the command line.

**`-u` implies basic auth.** Passing `-u alice:hunter2` without `-a` turns on
basic auth, because credentials with no mode would otherwise do nothing.

**`--hash-password` ignores everything else.** It prompts twice, prints the
hash and exits without starting a server.

**`-c` disables autodiscovery.** Naming a config file means that file and no
other. Without `-c`, pyserve looks for `pyserve.conf` then `.pyserve.conf`,
first next to the served directory, then in the working directory, then in your
home directory. The first file found is the only one read. `~/.pyserve.conf` is
the natural home for personal defaults.
