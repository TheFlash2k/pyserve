# Installation

## Requirements

Python 3.7 or newer. Nothing else. pyserve uses only the standard library, so
there is no dependency list to audit and no virtualenv to keep in sync.

The frontend loads one font from Google Fonts and falls back to whatever
monospace font is available, so it degrades cleanly on a machine with no
outbound network access.

## Running without installing

The repository runs as it is:

```bash
git clone https://github.com/theflash2k/pyserve
cd pyserve
python3 pyserve.py
```

`pyserve.py` at the root is a three line shim around the package next to it.
The package is also runnable on its own:

```bash
python3 -m pyserve
```

Both accept exactly the same arguments as the installed command.

## Installing

```bash
pip install .
```

That puts a `pyserve` command on your `PATH`:

```bash
pyserve --version
pyserve /srv/files -p 9000
```

Installing for every user on the machine needs the usual elevation:

```bash
sudo pip install .
```

On a Debian or Ubuntu system with an externally managed Python, pip refuses to
write into the system site packages. Either install into a virtualenv, which is
the better habit:

```bash
python3 -m venv ~/.local/share/pyserve-venv
~/.local/share/pyserve-venv/bin/pip install .
ln -s ~/.local/share/pyserve-venv/bin/pyserve ~/.local/bin/pyserve
```

or override the guard if you know what you are doing:

```bash
sudo pip install . --break-system-packages
```

Use `pip install .` rather than `python3 setup.py install`. The latter is
deprecated, and on some setups it produces a zipped egg, which used to break
asset loading. Assets are read through `importlib.resources` now so a zipped
install works either way, but the deprecated path is still worth avoiding.

## Editable install

For working on pyserve itself:

```bash
pip install -e .
```

Changes to the Python files take effect on the next start. Changes to the files
under `pyserve/assets/` take effect on the next request, because they are read
from disk each time rather than cached in memory.

## Upgrading

```bash
git pull
pip install .
pyserve --version
```

If an old copy was installed with `setup.py install`, remove the egg before
reinstalling, since pip will not clean it up for you:

```bash
sudo rm -rf /usr/local/lib/python3*/dist-packages/pyserve-*.egg
sudo pip install .
```

## Uninstalling

```bash
pip uninstall pyserve
```

pyserve writes nothing outside the directory it is told to serve, so there is
no state to clean up afterwards. Sessions live in memory and disappear when the
process exits.

## Next

- [Quick start](quickstart.md) for a first run
- [Configuration](configuration.md) to make the settings stick
