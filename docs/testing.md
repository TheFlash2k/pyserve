# Tests

The suites use the standard library only, the same as the server. There is
nothing to install and no test runner to configure.

```bash
python3 tests/test_ignore.py
python3 tests/test_iam.py
```

Each prints a line per failure and a summary, and exits non zero if anything
failed.

## What is covered

### `tests/test_ignore.py`

The ignore rules are what everything else leans on, so they get the most
thorough treatment. The suite builds a tree with ignorable entries at every
depth and checks the rules from three directions at once:

- The `FileStore` predicate, for every path in the fixture.
- Every HTTP route that can reach a path: listing, direct listing of a folder,
  download, search, rename, move, delete and upload.
- A full crawl of the served tree, proving that nothing hidden is reachable
  from anywhere and everything visible is.

It runs the whole battery twice, once with the directory cache warmed and once
with it off, since those are different code paths. It then checks the bundled
default rules against a tree that has no ignore file of its own.

### `tests/test_iam.py`

- Rule parsing: the four fields, comma separated users and actions, the three
  aliases, targets containing spaces, and the errors raised for malformed
  input with the file and line named.
- Target matching for all four forms, including case insensitivity and the
  difference between `reports/` and `reports/**`.
- Evaluation: deny winning regardless of order, the default effect, the `*`
  user, and `anonymous` for unauthenticated requests.
- The `[iam]` config block, including settings before and after it, comments
  inside it, and rules accumulating across layers.
- Every guarded route, with the cache on and off.
- Anonymous access when no authentication is configured.

## Writing a test

Both suites use the same shape. A `Checks` object counts assertions, servers
are started on port `0` so they never collide, and `env=False` keeps stray
`PYSERVE_` variables from changing the result:

```python
from pyserve import PyServe

srv = PyServe(root, port=0, env=False, access_log=False, log_level="warning")
srv.start(block=False)
try:
    ...
finally:
    srv.stop()
```

`port=0` means `srv.url` is the address actually bound, so tests can run in
parallel and on a busy machine.

## Manual checks

Some things are easier to look at than to assert. To drive the interface by
hand:

```bash
python3 pyserve.py /tmp/demo -p 8000 --no-config
```

Worth exercising after a frontend change:

- Upload several large files at once and watch the progress panel.
- Press and hold a row for two seconds to enter edit mode.
- Search with a fuzzy query, a glob and a regex, from a subfolder.
- Navigate into folders and use the browser back and forward buttons.
- Configure a policy and confirm the controls that should be hidden are.
