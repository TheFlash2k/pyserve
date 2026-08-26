#!/usr/bin/env python3

"""Tests for configuration resolution.

Covers the four layers, the file format including blocks, and where
autodiscovery looks for a config file.

Run it with:

    python3 tests/test_config.py
"""

import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pyserve import Config

CONFIG_NAMES = ("pyserve.conf", ".pyserve.conf")

class Checks:

    """Counts assertions and reports at the end."""

    def __init__(self):
        self.passed = 0
        self.failed = []

    def ok(self, condition, label):
        """Records one assertion."""
        if condition:
            self.passed += 1
        else:
            self.failed.append(label)
            print("FAIL " + label)

    def report(self):
        """Prints the summary and returns a process exit code."""
        print(f"\n{self.passed} passed, {len(self.failed)} failed")
        return 1 if self.failed else 0

def write(base, name, body):
    """Writes one config file."""
    with open(os.path.join(base, name), "w", encoding="utf-8") as handle:
        handle.write(body)

def clear(*bases):
    """Removes every config file from the given directories."""
    for base in bases:
        for name in CONFIG_NAMES:
            path = os.path.join(base, name)
            if os.path.exists(path):
                os.remove(path)

def port_for(directory):
    """The port autodiscovery ends up choosing for a served directory."""
    return Config.load(overrides={"directory": directory}, env=False, autodiscover=True).port

def check_discovery(checks, home, served, work):
    """Autodiscovery looks in the served directory, the cwd and then home."""
    checks.ok(Config.discover(served) == "", "discovery: nothing anywhere means no config")

    write(home, ".pyserve.conf", "PORT=7001\n")
    checks.ok(Config.discover(served) == os.path.join(home, ".pyserve.conf"),
              f"discovery: ~/.pyserve.conf is found, got {Config.discover(served)}")
    checks.ok(port_for(served) == 7001, "discovery: and its settings are applied")
    clear(home)

    write(home, "pyserve.conf", "PORT=7002\n")
    checks.ok(port_for(served) == 7002, "discovery: ~/pyserve.conf is found as well")

    write(work, "pyserve.conf", "PORT=7003\n")
    checks.ok(port_for(served) == 7003, "discovery: the working directory beats home")

    write(served, "pyserve.conf", "PORT=7004\n")
    checks.ok(port_for(served) == 7004, "discovery: the served directory beats both")
    checks.ok(Config.discover(served) == os.path.join(served, "pyserve.conf"),
              "discovery: discover() reports the file that won")

    config = Config.load(overrides={"directory": served, "port": 7005},
                         env=False, autodiscover=True)
    checks.ok(config.port == 7005, "discovery: an explicit override still beats every file")

    config = Config.load(overrides={"directory": served}, env=False, autodiscover=False)
    checks.ok(config.port == 8000, "discovery: autodiscover=False ignores all of them")

    clear(home, served, work)
    write(home, "pyserve.conf", "PORT=7006\n")
    write(home, ".pyserve.conf", "PORT=7007\n")
    checks.ok(port_for(served) == 7006,
              "discovery: pyserve.conf is preferred over .pyserve.conf in the same place")
    clear(home)

    checks.ok(Config.search_path(served) == [served, work, home],
              f"discovery: search order, got {Config.search_path(served)}")
    checks.ok(Config.search_path(work) == [work, home],
              f"discovery: a served directory that is the cwd is not searched twice, "
              f"got {Config.search_path(work)}")

def check_layers(checks, served):
    """Defaults, then environment, then file, then explicit overrides."""
    path = os.path.join(served, "layers.conf")
    write(served, "layers.conf", "PORT=9123\nTITLE=Vault\nREAD_ONLY=true\n")

    config = Config.load(overrides={"directory": served}, env=False)
    checks.ok(config.port == 8000, "layers: defaults apply with nothing else set")

    config = Config.load(config_file=path, overrides={"directory": served}, env=False)
    checks.ok(config.port == 9123 and config.title == "Vault", "layers: the file is read")
    checks.ok(config.read_only and not config.enable_delete,
              "layers: READ_ONLY forces the write settings off")

    environ = {"PYSERVE_PORT": "7777", "PYSERVE_LOG_LEVEL": "debug"}
    config = Config()
    config.update(Config.from_env(environ))
    config.update({"directory": served})
    config = config.finalize()
    checks.ok(config.port == 7777 and config.log_level == "debug", "layers: the environment is read")

    config = Config()
    config.update(Config.from_env(environ))
    config.update(Config.from_file(path))
    config.update({"directory": served})
    config = config.finalize()
    checks.ok(config.port == 9123, "layers: the file beats the environment")

    config.update({"port": 4444})
    checks.ok(config.port == 4444, "layers: an override beats the file")

def check_format(checks, served):
    """Comments, quoting, unknown keys and blocks."""
    write(served, "format.conf",
          "# a comment\n"
          "\n"
          "PORT = 9001\n"
          'TITLE="Quoted Name"\n'
          "NOT_A_REAL_KEY=whatever\n"
          "[iam]\n"
          "# a comment inside the block\n"
          "allow alice read **\n"
          "[end]\n"
          "READ_ONLY=true\n")
    path = os.path.join(served, "format.conf")
    config = Config.load(config_file=path, overrides={"directory": served}, env=False)
    checks.ok(config.port == 9001, "format: whitespace around '=' is ignored")
    checks.ok(config.title == "Quoted Name", f"format: quotes are stripped, got {config.title!r}")
    checks.ok(config.read_only, "format: settings after a block are still read")
    checks.ok(len(config.iam_rules) == 2, f"format: the block is captured, got {config.iam_rules}")
    checks.ok(not hasattr(config, "not_a_real_key"), "format: unknown keys are ignored")

def check_validation(checks, served):
    """Bad configuration fails at startup with a reason."""
    cases = [
        ({"directory": "/definitely/not/here"}, NotADirectoryError, "a missing directory"),
        ({"directory": served, "auth_mode": "weird"}, ValueError, "an unknown auth mode"),
        ({"directory": served, "auth_scope": "weird"}, ValueError, "an unknown auth scope"),
        ({"directory": served, "iam_default": "maybe"}, ValueError, "an unknown IAM default"),
        ({"directory": served, "tls_cert": "only-one-half"}, ValueError, "half a TLS pair"),
        ({"directory": served, "iam_rules_file": "/nope"}, FileNotFoundError, "a missing rules file"),
    ]
    for overrides, expected, label in cases:
        try:
            Config.load(overrides=overrides, env=False)
            checks.ok(False, f"validation: {label} should be rejected")
        except expected:
            checks.ok(True, f"validation: {label} is rejected")
        except Exception as problem:
            checks.ok(False, f"validation: {label} raised {type(problem).__name__}")

    try:
        Config.load(config_file="/definitely/not/here.conf", overrides={"directory": served}, env=False)
        checks.ok(False, "validation: a missing config file should be rejected")
    except FileNotFoundError:
        checks.ok(True, "validation: a missing config file is rejected")

def check_derived(checks, served):
    """Values worked out from the others."""
    config = Config.load(overrides={"directory": served}, env=False)
    checks.ok(config.title == os.path.basename(served),
              f"derived: the title falls back to the directory name, got {config.title}")
    checks.ok(config.page_title == f"pyserve: {config.title}",
              f"derived: the page title, got {config.page_title}")

    config = Config.load(overrides={"directory": served, "max_upload_mb": 50}, env=False)
    checks.ok(config.max_upload_bytes == 50 * 1024 * 1024, "derived: the upload ceiling in bytes")

    config = Config.load(overrides={"directory": served, "read_only": True}, env=False)
    checks.ok(not config.writable, "derived: a read only server is not writable")
    checks.ok(config.capabilities["readOnly"] is True, "derived: the capability map")

def main():
    """Runs every check against throwaway directories and reports."""
    checks = Checks()
    home = tempfile.mkdtemp(prefix="pyserve-home-")
    served = tempfile.mkdtemp(prefix="pyserve-served-")
    work = tempfile.mkdtemp(prefix="pyserve-work-")
    previous_home = os.environ.get("HOME")
    previous_cwd = os.getcwd()
    try:
        os.environ["HOME"] = home
        os.chdir(work)
        print("--- discovery")
        check_discovery(checks, home, served, work)
        clear(home, served, work)
        print("--- layers")
        check_layers(checks, served)
        print("--- file format")
        check_format(checks, served)
        print("--- validation")
        check_validation(checks, served)
        print("--- derived values")
        check_derived(checks, served)
    finally:
        os.chdir(previous_cwd)
        if previous_home is not None:
            os.environ["HOME"] = previous_home
        for path in (home, served, work):
            shutil.rmtree(path, ignore_errors=True)
    return checks.report()

if __name__ == "__main__":
    sys.exit(main())
