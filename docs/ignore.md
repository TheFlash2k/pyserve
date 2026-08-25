# The .ignore file

pyserve reads an ignore file at the root of the served directory and hides
anything matching it, at any depth, from listings, from search and from
downloads alike. Writes are refused on ignored paths too, so a hidden file
cannot be renamed, moved or deleted through the API.

## Syntax

gitignore semantics. The last rule that matches an entry wins, so a `!` rule
placed after a broader rule brings that entry back into view.

| Form | Meaning |
| --- | --- |
| `secrets.txt` | Matches that name at any depth |
| `*.log` | Glob against the entry name |
| `build/` | Directories only, at any depth |
| `/notes.md` | Anchored at the served root |
| `docs/private/*` | Anchored too, because it contains a separator |
| `!keep.txt` | Re-includes an entry an earlier rule hid |
| `# comment` | Ignored, as are blank lines |

## Anchoring

A pattern containing a `/` anywhere inside it is anchored to the served root.
That is gitignore's rule and pyserve follows it exactly, which surprises people
often enough to be worth stating plainly:

```gitignore
__pycache__/*      only matches at the top level
__pycache__/       matches at any depth
```

The first has a separator in the middle, so it is anchored and only ever
matches `__pycache__/...` directly under the served root. The second is a
directory rule with no separator inside it, so it matches wherever the folder
turns up. When you mean "this folder, wherever it is", write the trailing slash
form.

## Negation

```gitignore
.env.*
!.env.example
```

Every `.env.*` file is hidden, then `.env.example` is put back. Order matters:
the last matching rule decides. A negation also overrides an ignored ancestor,
so an explicitly re-included file remains reachable even inside a hidden
folder.

## The bundled default

When the served directory has no ignore file of its own, pyserve falls back to
the rules shipped with it:

```gitignore
.env.*
!.env.example
__pycache__/
```

Turn that off with `DEFAULT_IGNORE=false` or `--no-default-ignore`, and the
server runs with no rules at all in that case.

The startup log says which source was used:

```
[INFO] 3 ignore pattern(s) from default.ignore, full access
[INFO] 3 ignore pattern(s) from /srv/files/.ignore, full access
```

## Changing the file name

```bash
pyserve /srv/files -i .hidden
```

Whatever the name, that file never appears in a listing and is not
downloadable.

## Dotfiles

Dotfiles are shown by default, on the grounds that an ignore rule is the
intended way to hide things. `SHOW_HIDDEN=false` hides every entry whose name
starts with a dot, on top of whatever the ignore file already hides.

## Reloading

Rules are read at startup. To pick up a change without restarting:

```python
server.reload_ignore()
```

That also resets the directory cache, since the set of visible entries has
changed.

## From Python

```python
from pyserve import IgnoreList

rules = IgnoreList.from_lines([".env.*", "!.env.example", "__pycache__/"])
rules.is_path_ignored(".env.local", is_dir=False)          # True
rules.is_path_ignored(".env.example", is_dir=False)        # False
rules.is_path_ignored("pkg/__pycache__", is_dir=True)      # True

rules = IgnoreList.from_file("/srv/files/.ignore")
len(rules)
rules.source
```

## Ignore rules or IAM?

They are separate mechanisms and both apply.

- The ignore file hides paths from everybody. It is a property of the
  directory.
- [IAM](iam.md) hides paths from particular people. It is a property of the
  user.

An ignored path stays invisible even to a user an IAM rule would allow.
