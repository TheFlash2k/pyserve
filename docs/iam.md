# Access control (IAM)

Authentication answers *who are you*. IAM answers *what may you touch*.

With no rules configured, pyserve behaves exactly as it did before IAM existed:
every signed in user may do whatever the global permission settings allow.
Adding rules narrows that down per user and per path.

## A rule

Four whitespace separated fields:

```
effect  users  actions  target
```

```
allow   alice  read     reports/
deny    *      all      *.key
allow   bob    upload   dropbox/
deny    bob    delete   **
```

The target is the rest of the line, so it may contain spaces:

```
allow alice download quarterly report.pdf
```

### effect

`allow` or `deny`.

### users

A username, several separated by commas, or `*` for everyone.

```
allow alice        read  **
allow alice,bob    read  **
allow *            read  **
```

A name prefixed with `!` is excluded, so the rule applies to everyone except
them:

```
deny  !dana        all   finance/
deny  *,!alice     all   *.key
```

This is the only way to make an exception to a deny. Because an explicit deny
always wins, writing a broad deny and then a narrower allow does not work:

```
deny  *     all  finance/
allow dana  all  finance/     <- never takes effect, the deny already won
```

Put the exception on the deny instead:

```
deny  !dana all  finance/
allow dana  all  finance/
```

Or, with `IAM_DEFAULT=deny`, drop the blanket deny entirely and let the default
do the work:

```
default deny
allow dana all finance/
```

A visitor who is not signed in is called `anonymous`. That includes every
visitor when `AUTH_MODE=none`, and read requests when `AUTH_SCOPE=write`.

```
deny anonymous write **
```

`*` covers `anonymous` as well as every named user.

### actions

One or more of:

| Action | What it covers |
| --- | --- |
| `list` | Seeing an entry in a listing, and opening a folder |
| `download` | Fetching a file over `/dl/` |
| `search` | Running a search from a folder |
| `upload` | Creating a file |
| `rename` | Renaming an entry |
| `move` | Moving an entry into another folder |
| `delete` | Deleting a file, or a folder and its contents |

Three aliases save typing:

| Alias | Expands to |
| --- | --- |
| `read` | `list`, `download`, `search` |
| `write` | `upload`, `rename`, `move`, `delete` |
| `all` (or `*`) | everything above |

Combine them with commas: `delete,move`, `read,upload`.

### target

What the rule covers, in one of four forms.

| Form | Example | Matches |
| --- | --- | --- |
| A name pattern | `*.key` | Any entry whose **name** matches, at any depth |
| A folder | `reports/` | The folder entry itself **and** everything beneath it |
| A folder's contents | `reports/**` | Everything beneath the folder, but not the folder entry |
| An exact path | `reports/q1.pdf` | That one path, relative to the served root |

A leading `/` is allowed and ignored, so `/reports/` and `reports/` are the
same thing. Targets are always relative to the served root.

Pattern syntax:

| Token | Meaning |
| --- | --- |
| `*` | Any characters, stopping at a `/` |
| `**` | Any characters, crossing `/` |
| `**/` | Any number of leading folders, including none |
| `?` | Exactly one character, not a `/` |
| `[abc]` | One character from the set. `[!abc]` negates it. |

A pattern with no `/` in it is matched against the entry name alone, which is
what makes `*.key` reach every key file in the tree. A pattern containing a `/`
is matched against the whole relative path.

Matching is **case insensitive**, so a deny rule cannot be slipped past by
spelling a name differently. `deny * all *.key` also covers `SECRET.KEY`.

## How a request is decided

1. If no rules are configured at all, allow.
2. If any rule matching this user, action and path says `deny`, refuse.
   An explicit deny always wins, whatever order the rules are written in.
3. Otherwise, if any matching rule says `allow`, permit.
4. Otherwise fall back to `IAM_DEFAULT`.

Deny winning outright is the important part. It means you can write a broad
allow and a narrow deny without worrying about which line came first, and a
later configuration layer can never quietly re-grant something an earlier one
took away.

The flip side is that a deny cannot be undone by a later allow. To make an
exception, exclude the user on the deny itself with `!`, or use
`IAM_DEFAULT=deny` and grant rather than revoke. See the `users` field above.

## The default effect

`IAM_DEFAULT` decides what happens when nothing matches.

**`allow`** (the default) makes your rules a blocklist. Everything stays open
except what you deny. Good for carving a few things out of an otherwise open
server:

```ini
IAM_DEFAULT=allow

[iam]
deny * all secrets/
deny * all *.key
[end]
```

**`deny`** makes your rules an allowlist. Nothing is permitted until a rule
grants it. Good for a shared server where people should only see their own
things:

```ini
IAM_DEFAULT=deny

[iam]
allow alice all team-a/
allow bob   all team-b/
[end]
```

## Folder targets: `reports/` or `reports/**`

This is the one place the two forms behave differently enough to matter.

- `reports/` covers the folder entry **and** its contents.
- `reports/**` covers the contents but **not** the folder entry.

With `IAM_DEFAULT=deny`, a rule written as `allow alice read reports/**` grants
alice the files but not the folder they live in, so she cannot open `reports`
to reach them. Prefer the trailing slash form when you mean "this folder":

```
allow alice read reports/
```

Use `reports/**` when you deliberately want the contents treated differently
from the folder itself.

Uploading is the exception, because creating a file is inherently about a child
path rather than the folder. A rule of either form enables the upload control
for that folder, and the upload itself is checked against the destination file
path, so `deny * upload *.key` still blocks a key file being dropped into a
folder you may otherwise write to.

## Where rules are enforced

Every route that touches a path checks the policy.

| Route | Action checked | On refusal |
| --- | --- | --- |
| `GET /<folder>/` | `list` on the folder | `403` |
| `GET /api/list` | `list` on the folder | `403` |
| entries in a listing | `list` on each entry | filtered out silently |
| `GET /dl/<path>` | `download` on the file | `403` |
| `GET /api/search` | `search` on the folder | `403` |
| search results | `list` on each entry | filtered out silently |
| `POST /api/upload` | `upload` on the destination path | `403` |
| `POST /api/rename` | `rename` on the source subtree and the new path | `403` |
| `POST /api/move` | `move` on the source subtree and the destination path | `403` |
| `POST /api/delete` | `delete` on the path and everything beneath it | `403` |

Two behaviours are worth calling out.

**Listings are filtered, not refused.** An entry you may not `list` simply is
not there, the same way an ignored file is not there. You never see something
in the interface that you cannot then open.

**Folder operations check the whole subtree.** Deleting or moving a folder
changes every path inside it, so pyserve walks it first and refuses the whole
operation if a single entry inside is protected. A rule like

```
deny bob delete public/deep/
```

stops bob deleting `public` outright, rather than letting the recursive delete
step over the protected part.

## IAM narrows, it never widens

The global permission settings are a hard ceiling. `ENABLE_DELETE=false` means
nobody deletes anything, however generous a rule looks. `READ_ONLY=true` turns
all four write actions off before IAM is consulted at all.

Think of it as: the settings decide what the server can do, and IAM decides who
gets to do it.

## Writing the policy

### In the config file

The natural home. A `[iam]` block keeps the whole policy in one place:

```ini
IAM_DEFAULT=deny

[iam]
# Everyone signed in can look around
allow *      read           **

# Nobody ever touches a key file, wherever it turns up
deny  *      all            *.key

# Finance keeps its own folder. The exception lives on the deny, because a
# later allow could not undo it.
deny  !dana  all            finance/
allow dana   all            finance/

# Alice runs the place
allow alice  all            **

# Bob may only add files to the drop box, and never remove anything
allow bob    upload         dropbox/
deny  bob    delete,move    **

# Unauthenticated visitors get the public folder, read only
allow anonymous read        public/
[end]
```

`default deny` may also be written as the first line inside the block, which
keeps the policy self contained:

```ini
[iam]
default deny
allow alice all **
[end]
```

Comments and blank lines inside the block are ignored.

### In a separate file

```ini
IAM_RULES_FILE=/etc/pyserve/policy
```

Same syntax, one rule per line. Useful when the policy is managed separately
from the rest of the configuration, for instance by a different team or a
different deployment step. Its rules are added to whatever the block declared.

### On the command line

```bash
pyserve /srv/files \
  --iam-default deny \
  --iam-rule "allow * read **" \
  --iam-rule "allow alice all **"
```

Repeatable. Rules given here are added to the config file's rules rather than
replacing them, so a command line rule can tighten a deployed policy but never
loosen it.

## Checking a policy

`GET /api/permissions?path=<path>` reports what the signed in user may do at a
path, and which rules could apply to them:

```bash
curl -s -u alice:hunter2 'localhost:8000/api/permissions?path=reports/q1.pdf'
```

```json
{
  "user": "alice",
  "path": "reports/q1.pdf",
  "enabled": true,
  "default": "deny",
  "permissions": {
    "list": true, "download": true, "search": true,
    "upload": false, "rename": false, "move": false, "delete": false
  },
  "rules": ["allow alice read reports/", "deny * all *.key"]
}
```

A denial is logged at `warning`, naming the action, the path and the user, so a
policy that is too tight shows up in the log rather than as a silent failure.

From Python:

```python
from pyserve import PyServe

server = PyServe("/srv/files", iam_rules=["deny bob delete **"])
server.may("bob", "delete", "notes.txt")   # False
server.may("bob", "download", "notes.txt") # True
server.iam.permissions("bob", "notes.txt")
server.iam.describe("bob")
```

## Interaction with the ignore file

They are separate mechanisms and both apply.

- The `.ignore` file hides paths from everybody, regardless of who is signed in.
  It is a property of the directory.
- IAM hides paths from particular people. It is a property of the user.

An ignored path is invisible even to a user an IAM rule would allow. Use the
ignore file for things nobody should ever see, and IAM for things some people
should see and others should not.

## Recipes

**Carve one folder out of an open server.**

```
default allow
deny * all private/
```

**Carve one folder out for one person, on an otherwise open server.**

```
default allow
deny !dana all finance/
```

**Everyone reads, one person writes.**

```
default deny
allow *     read  **
allow alice all   **
```

**Per team folders.**

```
default deny
allow alice,bob   all  team-a/
allow carol,dana  all  team-b/
```

**A drop box that only accepts.**

```
default deny
allow *  upload  dropbox/
allow *  list    dropbox/
```

**Never serve credentials, whatever else is configured.**

```
deny * all *.key
deny * all *.pem
deny * all id_rsa*
deny * all .env*
```

**Let anonymous visitors see one public folder, and nothing else.**

```
default deny
allow anonymous read public/
allow alice     all  **
```

## Limits

A policy is evaluated per entry, so a listing of *n* entries runs *n* times the
number of rules pattern matches. That is fine for the rule counts a
configuration file realistically holds, and the patterns are compiled once at
startup. A policy with thousands of rules over a directory with thousands of
entries would be worth measuring before deploying.

Rules are read at startup. Changing the config file needs a restart, in
contrast to the ignore file which can be reloaded with `reload_ignore()`.

Sessions are not re-checked against the policy mid request: a signed in user's
identity is established once per request from the credentials or cookie, and
every check in that request uses it.
