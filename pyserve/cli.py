import argparse
import getpass
import sys
from typing import Dict, List, Optional

from . import __version__
from .auth import MODES, SCOPES, hash_password
from .config import Config
from .server import PyServe
from .utils.logger import logger

def build_parser() -> argparse.ArgumentParser:
    """Builds the argument parser. Every flag defaults to None so the config layers stay intact."""
    parser = argparse.ArgumentParser(
        prog="pyserve",
        description="Serve a directory over HTTP with browsing, resumable downloads, "
                    "upload, rename, move, delete, search and authentication.",
    )
    parser.add_argument("directory", nargs="?", default=None, help="Directory to serve [default: .]")
    parser.add_argument("-H", "--host", default=None, help="Bind address [default: 0.0.0.0]")
    parser.add_argument("-p", "--port", type=int, default=None, help="Bind port [default: 8000]")
    parser.add_argument("-c", "--config", default=None, help="Path to a pyserve.conf file")
    parser.add_argument("--no-config", action="store_true", help="Skip the pyserve.conf autodiscovery")
    parser.add_argument("--no-env", action="store_true", help="Ignore every PYSERVE_ environment variable")
    parser.add_argument("-i", "--ignore-file", default=None, help="Ignore file name resolved at the served root [default: .ignore]")
    parser.add_argument("-t", "--title", default=None, help="Name shown in the breadcrumb and on the sign in page [default: the directory name]")
    parser.add_argument("--page-title", default=None, help="Text in the browser tab [default: pyserve: <title>]")
    parser.add_argument("--no-default-ignore", action="store_true", help="Do not fall back to the ignore rules bundled with pyserve")

    perms = parser.add_argument_group("permissions")
    perms.add_argument("-r", "--read-only", action="store_true", help="Refuse every write, whatever the config says")
    perms.add_argument("--no-upload", action="store_true", help="Disable uploading")
    perms.add_argument("--no-rename", action="store_true", help="Disable renaming")
    perms.add_argument("--no-move", action="store_true", help="Disable moving")
    perms.add_argument("--no-delete", action="store_true", help="Disable deleting")
    perms.add_argument("--no-search", action="store_true", help="Disable the search endpoint")
    perms.add_argument("--no-download", action="store_true", help="Disable file downloads")
    perms.add_argument("--no-hidden", action="store_true", help="Hide dotfiles as well as ignored entries")
    perms.add_argument("--follow-symlinks", action="store_true", help="Follow symlinks when listing and walking")
    perms.add_argument("-m", "--max-upload-mb", type=int, default=None, help="Reject uploads larger than this [0 = unlimited]")
    perms.add_argument("--upload-concurrency", type=int, default=None, help="How many files the browser uploads at once [default: 3]")

    cache = parser.add_argument_group("cache")
    cache.add_argument("--no-cache", action="store_true", help="Do not keep directory listings in memory")
    cache.add_argument("--cache-threads", type=int, default=None, help="Warming pool size [0 = a quarter of the CPU threads]")
    cache.add_argument("--cache-max-dirs", type=int, default=None, help="Stop warming after this many directories [0 = no limit]")

    auth = parser.add_argument_group("authentication")
    auth.add_argument("-a", "--auth", dest="auth_mode", choices=MODES, default=None, help="Authentication mode [default: none]")
    auth.add_argument("-u", "--user", dest="users", action="append", default=None, metavar="USER:SECRET", help="Add a credential, repeatable")
    auth.add_argument("--users-file", dest="auth_users_file", default=None, help="htpasswd style file of USER:SECRET lines")
    auth.add_argument("--realm", dest="auth_realm", default=None, help="Realm shown in the basic auth popup")
    auth.add_argument("--auth-scope", choices=SCOPES, default=None, help="Guard everything, or only the write routes [default: all]")
    auth.add_argument("--session-ttl", type=int, default=None, help="Session lifetime in seconds for the sign in form")
    auth.add_argument("--secure-cookie", action="store_true", help="Add the Secure flag to the session cookie")
    auth.add_argument("--hash-password", action="store_true", help="Print a pbkdf2 hash for a password and exit")

    iam = parser.add_argument_group("access control")
    iam.add_argument("--iam-rule", dest="iam_rules", action="append", default=None,
                     metavar="RULE", help="Add a policy rule, 'effect users actions target', repeatable")
    iam.add_argument("--iam-rules-file", dest="iam_rules_file", default=None,
                     help="File of policy rules, one per line")
    iam.add_argument("--iam-default", dest="iam_default", choices=["allow", "deny"], default=None,
                     help="What happens when no rule matches [default: allow]")

    tls = parser.add_argument_group("tls")
    tls.add_argument("--tls-cert", default=None, help="Path to a PEM certificate")
    tls.add_argument("--tls-key", default=None, help="Path to the matching private key")

    output = parser.add_argument_group("output")
    output.add_argument("-l", "--log-level", default=None, help="debug, info, warning, error or quiet [default: info]")
    output.add_argument("-q", "--quiet", action="store_true", help="Only log errors")
    output.add_argument("--no-access-log", action="store_true", help="Stop logging every request")
    output.add_argument("-v", "--version", action="version", version=f"pyserve {__version__}")
    return parser

def overrides_from(args: argparse.Namespace) -> Dict:
    """Turns the parsed flags into a config layer, leaving out everything untouched."""
    values: Dict = {
        "directory": args.directory,
        "host": args.host,
        "port": args.port,
        "ignore_file": args.ignore_file,
        "title": args.title,
        "page_title": args.page_title,
        "max_upload_mb": args.max_upload_mb,
        "upload_concurrency": args.upload_concurrency,
        "cache_threads": args.cache_threads,
        "cache_max_dirs": args.cache_max_dirs,
        "auth_mode": args.auth_mode,
        "auth_users_file": args.auth_users_file,
        "auth_realm": args.auth_realm,
        "auth_scope": args.auth_scope,
        "session_ttl": args.session_ttl,
        "iam_rules": args.iam_rules,
        "iam_rules_file": args.iam_rules_file,
        "iam_default": args.iam_default,
        "tls_cert": args.tls_cert,
        "tls_key": args.tls_key,
        "log_level": args.log_level,
    }
    flags = {
        "read_only": args.read_only,
        "cookie_secure": args.secure_cookie,
        "follow_symlinks": args.follow_symlinks,
    }
    negations = {
        "enable_upload": args.no_upload,
        "enable_rename": args.no_rename,
        "enable_move": args.no_move,
        "enable_delete": args.no_delete,
        "enable_search": args.no_search,
        "enable_download": args.no_download,
        "show_hidden": args.no_hidden,
        "access_log": args.no_access_log,
        "cache_enabled": args.no_cache,
        "default_ignore": args.no_default_ignore,
    }
    for key, enabled in flags.items():
        if enabled:
            values[key] = True
    for key, disabled in negations.items():
        if disabled:
            values[key] = False
    if args.quiet:
        values["log_level"] = "error"
        values["access_log"] = False
    if args.users:
        values["auth_users"] = args.users
        if not args.auth_mode:
            values["auth_mode"] = "basic"
    return {key: value for key, value in values.items() if value is not None}

def prompt_password_hash() -> int:
    """Asks for a password twice and prints a pbkdf2 hash for pyserve.conf."""
    password = getpass.getpass("Password: ")
    if password != getpass.getpass("Confirm: "):
        logger.error("Passwords did not match")
        return 1
    if not password:
        logger.error("Password cannot be empty")
        return 1
    print(hash_password(password))
    return 0

def main(argv: Optional[List[str]] = None) -> int:
    """Entry point used by both 'pyserve' and 'python3 -m pyserve'."""
    args = build_parser().parse_args(argv)

    if args.hash_password:
        return prompt_password_hash()

    try:
        config = Config.load(
            config_file=args.config,
            overrides=overrides_from(args),
            env=not args.no_env,
            autodiscover=not (args.no_config or args.config),
        )
        PyServe(config=config).serve_forever()
    except (ValueError, OSError) as error:
        logger.error(str(error))
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
