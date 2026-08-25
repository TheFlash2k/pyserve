# Uploads

## The panel

Files upload in parallel, three at a time by default, and each one gets a row
in a small panel in the bottom corner with a live progress bar. The header
counts through the batch and then reports the result.

Nothing reloads. When a file lands it slides straight into the listing you are
looking at, highlighted for a moment so you can see it arrive.

The panel can be collapsed or closed, and closes itself a few seconds after a
batch where everything succeeded. If anything failed or was skipped it stays
put so you can read what happened.

## How to upload

- Click **Upload** and pick files.
- Drop files anywhere on the page to upload into the folder you are in.
- Drop files onto a folder row to upload into that folder instead.

The upload control is hidden when the current folder does not allow uploading,
whether that is because of `ENABLE_UPLOAD`, `READ_ONLY`, or an
[IAM rule](iam.md).

## Parallelism

`UPLOAD_CONCURRENCY` sets how many run at once, three by default. The rest
queue and start as slots free.

```bash
pyserve --upload-concurrency 6
```

Raise it on a fast link. Lower it if the server sits behind something that
limits concurrent connections per client.

## Conflicts

If the name is already taken the server answers `409` and the browser asks
whether to replace the existing file or keep both. Keeping both lands the file
as `name (1).ext`, using the first free number rather than assuming `(1)` is
available.

Those prompts are queued one at a time even while the other uploads keep
running, so a batch never stalls behind a dialog.

Over the API, retry the request with an `X-Conflict` header set to `replace` or
`copy`.

## Size limits

`MAX_UPLOAD_MB` rejects anything larger. `0`, the default, is unlimited.

```bash
pyserve --max-upload-mb 512
```

The browser marks an oversized file as failed in the panel without sending it,
and the server refuses it with `413` even if something bypasses the interface.

## What the server does

The request body is streamed straight to disk in `CHUNK_SIZE` blocks rather
than being buffered in memory, so the size of an upload is not bounded by
available RAM.

Uploads, renames, moves and deletes are serialised behind a single process wide
lock, so two concurrent requests cannot race on the same numbered copy logic or
step on each other halfway through a move.

If the write fails partway through, because the disk is full or the mount is
read only, the partial file is removed and the request answers `500` rather
than leaving a truncated file behind.

An upload also refreshes that folder in the [directory cache](cache.md), so the
next listing is correct immediately.

## Refusals

| Status | Reason |
| --- | --- |
| `403` | Uploads are disabled, or IAM denies this path |
| `403` | The name would be hidden by an [ignore rule](ignore.md) |
| `404` | The target folder does not exist, is hidden, or is outside the root |
| `409` | The name is taken and no `X-Conflict` was given |
| `413` | Larger than `MAX_UPLOAD_MB` |
| `400` | The filename contains a separator, or is `.` or `..` |
| `500` | The write failed |

## The API

```bash
curl -X POST \
  -H 'X-Target-Path: reports' \
  -H 'X-Filename: q3.pdf' \
  --data-binary @q3.pdf \
  localhost:8000/api/upload
```

Headers are percent decoded, so a name with spaces or non ASCII characters
should be percent encoded. See [HTTP API](http-api.md).
