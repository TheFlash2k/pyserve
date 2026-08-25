# The directory cache

Large trees stay fast because directory listings are held in memory.

## How it works

Nothing is cached while the first listing is being served. Once that first
request is done, the cache walks the entire tree in the background on a small
pool of threads, so the deeper folders are already in memory by the time
anyone clicks into them.

Every page load resets the cache and warms it again from scratch, so a listing
is never served from a stale entry. That is the trade the design makes: rather
than trying to detect changes on disk, it simply rebuilds often enough that the
question does not arise.

The sequence for a page load is:

1. `GET /` or `GET /<folder>/` empties the cache and arms a warm.
2. The first `GET /api/list` afterwards is served from disk and starts the
   background walk.
3. Subsequent listings are served from memory.

Exactly one warm runs per page load. Extra listings while a warm is in flight
do not queue another one.

## Search

When the cache is fully warmed, search runs over it rather than walking the
disk again, which is most of what makes search usable on a large tree. If the
cache is off, incomplete, or was truncated by `CACHE_MAX_DIRS`, search falls
back to walking.

## Writes

Uploads, renames, moves and deletes refresh the folders they touched straight
away, so the next listing is correct without waiting for a reload.

- An upload or a rename in place re-scans that one folder and leaves the cache
  complete, so search keeps using it.
- A rename, move or delete of a folder drops that folder and everything under
  it and marks the cache incomplete, since paths below it have changed. Search
  falls back to walking until the next page load re-warms.

## Filtering

The cache holds unfiltered listings. Hidden entries and [IAM](iam.md) decisions
are applied after a cached listing is read, so one cached entry stays correct
for every user regardless of who they are.

## Tuning

| Key | Default | Meaning |
| --- | --- | --- |
| `CACHE_ENABLED` | `true` | Hold listings in memory at all |
| `CACHE_THREADS` | `0` | Warming pool size. `0` picks a quarter of the CPU threads. |
| `CACHE_MAX_DIRS` | `0` | Stop warming after this many directories. `0` is no limit. |

```bash
pyserve /mnt/archive --cache-threads 12
pyserve /mnt/archive --cache-max-dirs 200000
pyserve /srv/files --no-cache
```

A quarter of the machine's threads is the default because warming should not
compete with serving. Raise it for a very large tree on fast storage.

`CACHE_MAX_DIRS` is a safety valve for a tree so large that caching all of it
would be wasteful. A truncated cache is marked incomplete, which is what makes
search fall back to walking rather than quietly returning partial results.

## Inspecting it

```bash
curl -s localhost:8000/api/cache
```

```json
{
  "enabled": true,
  "dirs": 4211,
  "threads": 4,
  "complete": true,
  "warming": false,
  "truncated": false,
  "hits": 87,
  "misses": 12
}
```

| Field | Meaning |
| --- | --- |
| `dirs` | Directories currently cached |
| `complete` | The whole tree is in memory and nothing has invalidated it |
| `warming` | A background walk is running |
| `truncated` | Warming stopped early because of `CACHE_MAX_DIRS` |
| `hits`, `misses` | Lookups since the last reset |

`LOG_LEVEL=debug` logs a line when a warm finishes, with the directory count
and the pool size.

## From Python

```python
from pyserve import PyServe

server = PyServe("/srv/files", cache_threads=8)
server.start(block=False)

server.reset_cache()     # empty it and arm a warm for the next listing
server.warm_cache()      # start that warm now
server.cache_stats()     # the same dictionary the endpoint returns
```

The cache is usable on its own against a `FileStore`:

```python
from pyserve import DirectoryCache, FileStore

cache = DirectoryCache(threads=4)
store = FileStore("/srv/files", cache=cache)
cache.warm(store)
cache.complete
len(cache)
```

## When to turn it off

- The tree is small enough that it makes no difference.
- The directory changes constantly underneath pyserve from outside, and you
  would rather pay for a fresh `scandir` on every listing than wait for the
  next page load to re-warm.
- Memory is tight. Each cached directory holds one dictionary per entry.
