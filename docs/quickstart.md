# Quick start

## Serve a directory

```bash
pyserve
```

That serves the current directory on `0.0.0.0:8000`. Open
`http://localhost:8000` and you get a directory browser: click into folders,
click a file to download it, drag files onto the page to upload them.

Point it somewhere else and pick a port:

```bash
pyserve /srv/files -p 9000
```

## Keep it read only

The single most useful flag. Browsing, downloading and searching still work;
every write is refused, and the interface hides the controls to match.

```bash
pyserve /srv/files --read-only
```

## Hide things

Drop a `.ignore` file at the root of the directory you are serving. It uses
gitignore syntax and applies at any depth:

```gitignore
.env.*
!.env.example
__pycache__/
*.key
```

Anything it hides is invisible to listing, to search and to download alike. If
there is no `.ignore` file, pyserve falls back to a small bundled default that
hides `.env.*` and `__pycache__/`.

See [The .ignore file](ignore.md).

## Ask for a password

The browser popup you get from nginx:

```bash
pyserve -a basic -u alice:hunter2
```

Or a sign in page in the same design as the rest of the interface:

```bash
pyserve -a form -u alice:hunter2
```

Do not leave a plain password in a script or a config file. Generate a hash:

```bash
pyserve --hash-password
```

See [Authentication](authentication.md).

## Let people browse but not change anything

```bash
pyserve -a form -u alice:hunter2 --auth-scope write
```

Anyone can look and download. Uploading, renaming, moving and deleting ask for
credentials first.

## Give different people different access

```bash
pyserve -a form -u alice:hunter2 -u bob:s3cret \
  --iam-default deny \
  --iam-rule "allow *     read   **" \
  --iam-rule "allow alice all    **" \
  --iam-rule "deny  *     all    *.key"
```

Everyone signed in can look around, alice can change anything, and nobody
touches a key file. Policies belong in the config file rather than on the
command line once they grow past a couple of lines.

See [Access control (IAM)](iam.md).

## Make the settings stick

Copy the sample and edit it:

```bash
cp pyserve.conf.example pyserve.conf
```

A `pyserve.conf` next to the served directory, in the directory you launch
from, or in your home directory is picked up on its own. Put settings you
always want into `~/.pyserve.conf`:

```ini
DIRECTORY=/srv/files
PORT=9000
READ_ONLY=true
AUTH_MODE=form
AUTH_USERS=alice:pbkdf2$240000$...
```

See [Configuration](configuration.md).

## Search

The search box takes more than plain text:

```
report          fuzzy, finds quarterly-report.pdf
*.sql           every SQL file below the folder you are in
*.sql;*.db      two patterns at once
/^backup_/i     a regular expression
```

Search runs from the folder you are looking at, not from the top.

See [Search](search.md).

## Use it from Python

```python
from pyserve import PyServe

server = PyServe("/srv/files", port=9000, read_only=True)
server.start(block=False)
print(server.url)
server.stop()
```

See [Library use](library.md).
