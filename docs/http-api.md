# HTTP API

The frontend is just a client of these routes, so anything the interface can
do, a script can do too.

Every route respects the same rules the interface does: [ignore
rules](ignore.md), the global permission settings,
[authentication](authentication.md) and [IAM](iam.md). A request sent straight at the API is
refused exactly like a click would be.

## Pages

| Method | Route | Notes |
| --- | --- | --- |
| `GET` | `/` | The directory browser |
| `GET` | `/<folder>/` | The browser opened on that folder |
| `GET` | `/login` | The sign in page, form mode only |
| `GET` | `/static/<asset>` | Stylesheet, scripts, logo, favicon |
| `GET` | `/favicon.ico` | |

A folder URL is a `404` when the path does not exist, is a file, is hidden by
an ignore rule, or escapes the served root. It is a `403` when IAM denies
`list` on it.

Static assets are served without authentication, since the sign in page needs
them and they contain no data.

## Reading

### `GET /api/list`

| Parameter | Default | Meaning |
| --- | --- | --- |
| `path` | `""` | Folder to list, relative to the served root |

```json
{
  "path": "reports",
  "entries": [
    {"name": "archive", "type": "dir", "size": null, "mtime": 1712345678},
    {"name": "q1.pdf", "type": "file", "size": 91234, "mtime": 1712345678}
  ],
  "perms": {"list": true, "download": true, "search": true,
            "upload": true, "rename": true, "move": true, "delete": true}
}
```

Entries are sorted with folders first, then by name. A folder has `size: null`.
`mtime` is a Unix timestamp in seconds.

`perms` is present only when an IAM policy is configured, and describes what
the caller may do in this folder. When a policy is configured, each entry also
carries its own `perms` map covering `list`, `download`, `rename`, `move` and
`delete`.

Entries the caller may not `list` are filtered out rather than being reported.

| Status | Reason |
| --- | --- |
| `404` | Not a directory, hidden, or outside the root |
| `403` | IAM denies `list` on this folder |

### `GET /api/search`

| Parameter | Default | Meaning |
| --- | --- | --- |
| `q` | | The query |
| `path` | `""` | Folder to search from |

```json
{
  "query": "*.sql",
  "path": "src",
  "matches": [
    {"name": "queries.sql", "type": "file", "size": 812,
     "mtime": 1712345678, "path": []},
    {"name": "deep.sql", "type": "file", "size": 44,
     "mtime": 1712345678, "path": ["deep"]}
  ]
}
```

`path` on a match is the list of folders between the searched folder and the
hit, so the full relative path is `path + [name]` under the searched folder.

See [Search](search.md) for the query forms.

| Status | Reason |
| --- | --- |
| `400` | The query contains a regex that will not compile. `error` says why. |
| `403` | Search is disabled, or IAM denies `search` on this folder |
| `404` | The folder does not exist, is hidden, or escapes the root |

### `GET /dl/<path>` and `HEAD /dl/<path>`

Downloads a file. Supports `Range`, answering `206 Partial Content` with a
`Content-Range` header, so a paused download resumes rather than restarting.
An unsatisfiable range answers `416`.

```bash
curl -O localhost:8000/dl/reports/q1.pdf
curl -r 0-1023 localhost:8000/dl/large.iso
```

| Status | Reason |
| --- | --- |
| `404` | Not a file, hidden, or outside the root |
| `403` | Downloads are disabled, or IAM denies `download` |
| `416` | The requested range is not satisfiable |

### `GET /api/whoami`

```json
{"user": "alice", "authMode": "form"}
```

### `GET /api/cache`

Counters for the [directory cache](cache.md).

### `GET /api/permissions`

| Parameter | Default | Meaning |
| --- | --- | --- |
| `path` | `""` | Path to ask about |

```json
{
  "user": "alice",
  "path": "reports/q1.pdf",
  "enabled": true,
  "default": "deny",
  "permissions": {"list": true, "download": true, "search": true,
                  "upload": false, "rename": false, "move": false,
                  "delete": false},
  "rules": ["allow alice read reports/", "deny * all *.key"]
}
```

`rules` lists the rules that could apply to this user, which is the quickest
way to work out why something is refused.

## Writing

All four write routes answer `403` when the matching global setting is off, and
`403` when IAM denies the action.

### `POST /api/upload`

The raw file is the request body. Metadata travels in headers, percent encoded.

| Header | Meaning |
| --- | --- |
| `X-Target-Path` | Folder to upload into, relative to the served root |
| `X-Filename` | Name to save as |
| `X-Conflict` | `replace` or `copy`, only on a retry after `409` |

```bash
curl -X POST \
  -H 'X-Target-Path: reports' \
  -H 'X-Filename: q3.pdf' \
  --data-binary @q3.pdf \
  localhost:8000/api/upload
```

```json
{"ok": true, "name": "q3.pdf", "size": 91234,
 "mtime": 1712345678, "path": "reports"}
```

| Status | Reason |
| --- | --- |
| `409` | The name is taken. Body is `{"conflict": true, "name": "..."}`. |
| `413` | Larger than `MAX_UPLOAD_MB` |
| `400` | The filename contains a separator, or is `.` or `..` |
| `404` | The target folder does not exist, is hidden, or escapes the root |
| `500` | The write failed |

### `POST /api/rename`

```json
{"path": "reports/q1.pdf", "newName": "quarter-one.pdf"}
```

Renames within the same folder. `newName` must be a bare filename.

| Status | Reason |
| --- | --- |
| `409` | The new name is taken |
| `404` | The source does not exist or is hidden |
| `400` | Invalid request |

### `POST /api/move`

```json
{"path": "reports/q1.pdf", "targetDir": "archive", "conflict": ""}
```

| Status | Reason |
| --- | --- |
| `409` | The destination name is taken. Retry with `conflict` as `replace` or `copy`. |
| `400` | Moving a folder into itself or a descendant |
| `404` | The source or target does not exist, or is hidden |

### `POST /api/delete`

```json
{"path": "reports/old", "name": "old"}
```

Deleting a folder is recursive and requires `name` to match the folder name as
a confirmation. Deleting a file ignores `name`.

Under IAM, deleting a folder checks every entry beneath it and refuses the
whole operation if any one of them is protected.

## Sessions

### `POST /api/login`

Form mode only.

```json
{"username": "alice", "password": "hunter2"}
```

Answers `200` with a `Set-Cookie` header on success, `401` on bad credentials,
`404` when form authentication is not enabled.

### `POST /api/logout`

Destroys the current session and clears the cookie.

## Authentication behaviour

With `AUTH_MODE=basic`, an unauthenticated request answers `401` with a
`WWW-Authenticate` header, which is what makes the browser show its popup.

With `AUTH_MODE=form`, a browser navigation answers `302` to
`/login?next=<where you were>`, and anything else answers `401` with a JSON
body so a script gets a usable error rather than an HTML page.

With `AUTH_SCOPE=write`, only the four write routes require credentials.

## Errors

Errors carry a JSON body with an `error` string, except on the page routes,
which answer plain text. Internal details, paths and tracebacks are never sent
to a client; unexpected exceptions are logged and answered with a bare
`500 internal server error`.
