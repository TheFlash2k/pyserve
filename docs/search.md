# Search

## Scope

Search runs from the folder you are looking at, not from the served root.
Standing in `src/` and searching only ever returns things under `src/`, and the
result tree is rooted there. Go back to the top and the same query covers
everything.

Over the API that is the `path` parameter:

```bash
curl -s 'localhost:8000/api/search?q=*.sql&path=src'
```

Result paths come back relative to that folder, so a hit in `src/deep/` is
reported as `deep/deep.sql`.

## Query forms

The box takes a fuzzy query, a shell style pattern, or a regular expression.

| Query | Matches |
| --- | --- |
| `report` | Fuzzy, so `quarterly-report.pdf` comes back |
| `rport` | Fuzzy is a subsequence match, so this finds `report.txt` too |
| `*.sql` | Every SQL file at any depth below here |
| `*.sql;*.db` | Several patterns at once, separated by `;` |
| `deep/*.py` | A pattern containing `/` matches the path relative to this folder |
| `test_?.py` | `?` matches exactly one character |
| `[abc]*.log` | Character classes work |
| `/\.sql$/` | A regular expression, wrapped in slashes |
| `/^test_/i` | The `i` flag makes it case insensitive |
| `/deep/.*\.py/` | A regex holding a `/` matches the relative path, same as a glob |

A part counts as a regex when it is wrapped in slashes, as a glob when it holds
`*`, `?` or `[`, and stays fuzzy otherwise.

## Fuzzy matching

A fuzzy query is an ordered subsequence match, the same idea as a fuzzy file
finder in an editor. Every character of the query has to appear in the name, in
order, but not necessarily next to each other.

- `rport` matches `report.txt`, because r-p-o-r-t appear in that order.
- `shto` does **not** match `shot.png`, because the `t` comes after the `o`.

Results are scored: runs of consecutive matches score higher, and a name that
contains the query outright gets a bonus, so exact-ish hits rise to the top.

## Case sensitivity

Globs and fuzzy queries are case insensitive. A regex is case sensitive unless
you add the `i` flag, which is what `/re/i` means everywhere else. Being
consistent with regex convention seemed more useful than being consistent with
the other two, since anyone reaching for a regex will expect it.

## Combining

Parts are separated by `;` and the best score wins, so kinds can be mixed:

```
*.md;readme        every markdown file, plus anything fuzzy-matching "readme"
*.sql;*.db;*.csv   three extensions at once
```

A query that is one whole `/pattern/` is never split on `;`, so a regex may
contain one:

```
/foo;bar/
```

## Errors

A regex that will not compile comes back as a `400` with the reason, and the
interface prints it under the search box rather than silently returning
nothing:

```json
{"error": "invalid regular expression: unterminated character set at position 0"}
```

Regex sources are capped at 200 characters.

## Results

Results come back as a tree, so you can see where each hit lives rather than
just its name. Folders in the tree are links that take you there; files are
download links.

`SEARCH_LIMIT` caps how many results are returned, 300 by default. Lower it on
a very large tree to keep the tree view readable.

## What search can see

Search respects everything else the server enforces:

- Entries hidden by the [ignore file](ignore.md) never appear.
- Entries an [IAM rule](iam.md) denies to this user never appear.
- `ENABLE_SEARCH=false` turns the endpoint off entirely, returning `403`.

## Performance

When the [directory cache](cache.md) is fully warmed, search runs over it
rather than walking the disk again, which is what keeps it usable on a large
tree. If the cache is off, incomplete, or was truncated by `CACHE_MAX_DIRS`,
search falls back to walking, which is slower but always correct.

## A note on regular expressions

A regex is evaluated on the server, against every visible name below the folder
being searched. Python's `re` has no timeout, so a deliberately pathological
pattern could occupy a request thread. Filenames are short, which bounds the
practical risk, and sources are length capped, but if that is not a trade you
want to make on an exposed server then turn search off with
`ENABLE_SEARCH=false` or require credentials with `AUTH_MODE`.

## From Python

```python
from pyserve import FileStore

store = FileStore("/srv/files")
store.search("report")                       # fuzzy, whole tree
store.search("*.sql", rel_path="src")        # glob, scoped to src/
store.search("/\\.sql$/", limit=10)          # regex, top 10
```

The matcher is usable on its own:

```python
from pyserve.fs import QueryMatcher

m = QueryMatcher("*.sql;*.db")
m.score("schema.sql")        # >= 0 means it matched
m.has_glob                   # True
QueryMatcher("/[/").error    # the compile error, as a string
```
