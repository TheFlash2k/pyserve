# Authentication

Three modes, picked with `-a` or `AUTH_MODE`. With `none`, the default, every
visitor is anonymous and no credentials are asked for.

## basic

The browser popup you get from nginx or caddy.

```bash
pyserve -a basic -u alice:hunter2 --realm "internal files"
```

Credentials travel on every request in an `Authorization` header, base64
encoded but not encrypted, so put it behind HTTPS if it leaves localhost. See
[Deployment](deployment.md).

## form

A sign in page in the same design as the rest of the interface.

```bash
pyserve -a form -u alice:hunter2 --session-ttl 3600 --secure-cookie
```

A successful sign in issues an opaque random token, stored server side and sent
back in a cookie that is `HttpOnly`, `SameSite=Strict` and `Path=/`. The header
of the browser gains the username and a sign out button.

Sessions live in memory. Restarting the server invalidates every one of them.
Expired sessions are pruned when a new one is created.

`--secure-cookie` adds the `Secure` flag so the cookie is only ever sent over
HTTPS. Turn it on whenever the server is reachable over TLS, directly or
through a proxy. Leaving it on over plain HTTP means the browser drops the
cookie and nobody can stay signed in.

## Scope

By default credentials guard every route. `--auth-scope write` lets anyone
browse, download and search, and only asks before an upload, a rename, a move
or a delete:

```bash
pyserve -a form -u alice:hunter2 --auth-scope write
```

Under `write` scope, read requests are treated as coming from `anonymous`,
which matters when writing [IAM rules](iam.md).

## Users and secrets

Credentials are `user:secret` pairs. A secret may be:

| Form | Example |
| --- | --- |
| A plain password | `alice:hunter2` |
| A sha256 digest | `alice:sha256$9f86d081...` |
| A pbkdf2 string | `alice:pbkdf2$240000$1f0c...$9ad4...` |

Generate the pbkdf2 form, which is what you want anywhere the value might be
read by someone else:

```bash
$ pyserve --hash-password
Password:
Confirm:
pbkdf2$240000$8e1f0c4a...$9ad4b17c...
```

It prompts twice, prints the hash and exits without starting a server.

Then in `pyserve.conf`:

```ini
AUTH_MODE=form
AUTH_USERS=alice:pbkdf2$240000$8e1f0c4a...$9ad4b17c...
```

Or keep credentials in their own file, one `user:secret` per line with `#` for
comments:

```ini
AUTH_USERS_FILE=/etc/pyserve/users
```

Entries in that file are merged on top of `AUTH_USERS`, so a name in both takes
its value from the file. Keep it outside the served directory, or hide it with
an [ignore rule](ignore.md).

## Implementation notes

Passwords are compared with `hmac.compare_digest`, so the comparison does not
leak information through its timing. A sign in attempt for a username that does
not exist still runs a hash, so a missing user and a wrong password take
comparable time.

pbkdf2 uses 240000 rounds of SHA-256 by default. That is deliberate: a sign in
should cost something.

Failed sign ins are logged at `warning` with the username attempted. Successful
ones are logged at `info`.

## From Python

```python
from pyserve import PyServe, hash_password

server = PyServe(
    "/srv/files",
    auth_mode="form",
    auth_users={"alice": hash_password("hunter2")},
    session_ttl=3600,
)
server.add_user("bob", hash_password("s3cret"))
server.remove_user("alice")
```

`remove_user` stops new sign ins. Existing sessions for that user run to their
expiry unless you clear them:

```python
server.auth.sessions.clear()
```

The pieces are usable on their own:

```python
from pyserve import Authenticator, hash_password, verify_password

auth = Authenticator(mode="form", users={"alice": hash_password("hunter2")})
token = auth.login("alice", "hunter2")
auth.sessions.get(token)          # 'alice'
auth.logout(f"pyserve_session={token}")

verify_password(hash_password("x"), "x")   # True
```

## Next

Authentication decides who someone is. To decide what they may touch, see
[Access control (IAM)](iam.md).
