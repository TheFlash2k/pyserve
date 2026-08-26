import os
from typing import Any, Dict, List, Optional

from .auth import MODES, SCOPES, parse_users
from .iam import EFFECTS as IAM_EFFECTS
from .utils.helpers import parse_bool, parse_int, read_config_file

ENV_PREFIX = "PYSERVE_"
IAM_BLOCK = "iam"
ACCUMULATING = ("iam_rules",)
DEFAULT_CONFIG_NAMES = ("pyserve.conf", ".pyserve.conf")

FIELDS: Dict[str, Any] = {
    "directory": ".",
    "host": "0.0.0.0",
    "port": 8000,
    "title": "",
    "page_title": "",
    "ignore_file": ".ignore",
    "default_ignore": True,
    "show_hidden": True,
    "follow_symlinks": False,
    "read_only": False,
    "enable_upload": True,
    "enable_rename": True,
    "enable_move": True,
    "enable_delete": True,
    "enable_search": True,
    "enable_download": True,
    "max_upload_mb": 0,
    "search_limit": 300,
    "chunk_size": 262144,
    "upload_concurrency": 3,
    "cache_enabled": True,
    "cache_threads": 0,
    "cache_max_dirs": 0,
    "auth_mode": "none",
    "auth_users": {},
    "auth_users_file": "",
    "auth_realm": "pyserve",
    "auth_scope": "all",
    "session_ttl": 86400,
    "session_cookie": "pyserve_session",
    "cookie_secure": False,
    "iam_default": "allow",
    "iam_rules": [],
    "iam_rules_file": "",
    "tls_cert": "",
    "tls_key": "",
    "access_log": True,
    "log_level": "info",
    "server_header": "pyserve",
}

class Config:

    """Every knob PyServe exposes, resolved from four layers.

    The layers are applied in this order and each one overrides the last:
    built in defaults, environment variables, the config file, then explicit
    arguments. Config file keys are the uppercase form of the attribute names,
    and environment variables are the same keys with a PYSERVE_ prefix.
    """

    def __init__(self, **values):
        for key, default in FIELDS.items():
            setattr(self, key, dict(default) if isinstance(default, dict) else default)
        self.config_file = ""
        self.update(values)

    def __repr__(self) -> str:
        return f"Config(directory={self.directory!r}, host={self.host!r}, port={self.port})"

    @staticmethod
    def coerce(key: str, value: Any) -> Any:
        """Turns a raw string from a file, an environment variable or a flag into a field value."""
        default = FIELDS[key]
        if key == "auth_users":
            return parse_users(value)
        if isinstance(default, list):
            if isinstance(value, str):
                return [line for line in value.splitlines() if line.strip()]
            return [str(item) for item in value]
        if isinstance(default, bool):
            return parse_bool(value, default)
        if isinstance(default, int):
            return parse_int(value, default)
        return str(value)

    def update(self, values: Optional[Dict[str, Any]]) -> "Config":
        """Applies a layer of values, ignoring unknown keys and None entries.

        Most fields are replaced outright. IAM rules accumulate instead, so a
        later layer can only ever add to the policy. Since an explicit deny
        always wins, that means a layer can tighten access but never loosen it.
        """
        for key, value in (values or {}).items():
            key = str(key).lower()
            if key not in FIELDS or value is None:
                continue
            coerced = self.coerce(key, value)
            if key in ACCUMULATING:
                setattr(self, key, list(getattr(self, key)) + list(coerced))
            else:
                setattr(self, key, coerced)
        return self

    def to_dict(self) -> Dict[str, Any]:
        """Returns every field as a plain dictionary."""
        return {key: getattr(self, key) for key in FIELDS}

    @staticmethod
    def from_env(env: Optional[Dict[str, str]] = None, prefix: str = ENV_PREFIX) -> Dict[str, Any]:
        """Collects the PYSERVE_ prefixed environment variables into a layer."""
        env = os.environ if env is None else env
        values = {}
        for key in FIELDS:
            name = prefix + key.upper()
            if name in env:
                values[key] = env[name]
        return values

    @staticmethod
    def from_file(path: str) -> Dict[str, Any]:
        """Reads a pyserve.conf style file, including its [iam] block, into a layer."""
        if not path:
            return {}
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Config file not found: {path}")
        raw, blocks = read_config_file(path)
        values: Dict[str, Any] = {
            key: raw[key.upper()] for key in FIELDS if key.upper() in raw
        }
        if IAM_BLOCK in blocks:
            values["iam_rules"] = blocks[IAM_BLOCK]
        return values

    @staticmethod
    def discover(directory: str = ".") -> str:
        """Finds the config file to use, or an empty string when there is none.

        Three places are searched, in order, and the first file found wins:
        next to the served directory, in the working directory, then in the
        home directory. That last one is where personal defaults live, so a
        config sitting next to a particular directory always takes precedence
        over them.
        """
        for base in Config.search_path(directory):
            for name in DEFAULT_CONFIG_NAMES:
                candidate = os.path.join(base, name)
                if os.path.isfile(candidate):
                    return os.path.abspath(candidate)
        return ""

    @staticmethod
    def search_path(directory: str = ".") -> List[str]:
        """The directories autodiscovery looks in, in order, without duplicates."""
        bases = [
            os.path.abspath(os.path.expanduser(directory or ".")),
            os.getcwd(),
            os.path.expanduser("~"),
        ]
        seen = []
        for base in bases:
            if base and base not in seen:
                seen.append(base)
        return seen

    @classmethod
    def load(
        cls,
        config_file: Optional[str] = None,
        overrides: Optional[Dict[str, Any]] = None,
        env: bool = True,
        autodiscover: bool = False,
    ) -> "Config":
        """Builds a Config from defaults, environment, a config file and overrides."""
        config = cls()
        if env:
            config.update(cls.from_env())
        if not config_file and autodiscover:
            config_file = cls.discover((overrides or {}).get("directory") or config.directory)
        if config_file:
            config.update(cls.from_file(config_file))
            config.config_file = os.path.abspath(config_file)
        config.update(overrides)
        return config.finalize()

    def finalize(self) -> "Config":
        """Resolves derived values and enforces the settings that depend on each other."""
        self.directory = os.path.abspath(os.path.expanduser(self.directory))
        if not os.path.isdir(self.directory):
            raise NotADirectoryError(f"Not a directory: {self.directory}")

        if not self.title:
            self.title = os.path.basename(self.directory.rstrip(os.sep)) or self.directory
        if not self.page_title:
            self.page_title = f"pyserve: {self.title}"

        self.auth_mode = self.auth_mode.strip().lower()
        if self.auth_mode not in MODES:
            raise ValueError(f"Unknown AUTH_MODE: {self.auth_mode}. Pick one of {', '.join(MODES)}")
        self.auth_scope = self.auth_scope.strip().lower()
        if self.auth_scope not in SCOPES:
            raise ValueError(f"Unknown AUTH_SCOPE: {self.auth_scope}. Pick one of {', '.join(SCOPES)}")
        if self.auth_users_file:
            self.auth_users_file = os.path.abspath(os.path.expanduser(self.auth_users_file))

        self.iam_default = self.iam_default.strip().lower()
        if self.iam_default not in IAM_EFFECTS:
            raise ValueError(
                f"Unknown IAM_DEFAULT: {self.iam_default}. Pick one of {', '.join(IAM_EFFECTS)}"
            )
        if self.iam_rules_file:
            self.iam_rules_file = os.path.abspath(os.path.expanduser(self.iam_rules_file))
            if not os.path.isfile(self.iam_rules_file):
                raise FileNotFoundError(f"IAM rules file not found: {self.iam_rules_file}")
            with open(self.iam_rules_file, "r", encoding="utf-8") as handle:
                self.iam_rules = list(self.iam_rules) + handle.read().splitlines()

        if self.read_only:
            self.enable_upload = False
            self.enable_rename = False
            self.enable_move = False
            self.enable_delete = False

        if bool(self.tls_cert) != bool(self.tls_key):
            raise ValueError("TLS_CERT and TLS_KEY have to be set together")

        self.max_upload_mb = max(0, self.max_upload_mb)
        self.chunk_size = max(4096, self.chunk_size)
        self.search_limit = max(1, self.search_limit)
        self.upload_concurrency = max(1, self.upload_concurrency)
        self.cache_threads = max(0, self.cache_threads)
        self.cache_max_dirs = max(0, self.cache_max_dirs)
        return self

    @property
    def max_upload_bytes(self) -> int:
        """The upload ceiling in bytes, 0 meaning unlimited."""
        return self.max_upload_mb * 1024 * 1024

    @property
    def writable(self) -> bool:
        """True when at least one write route is still enabled."""
        return any((self.enable_upload, self.enable_rename, self.enable_move, self.enable_delete))

    @property
    def capabilities(self) -> Dict[str, bool]:
        """The capability flags handed to the frontend."""
        return {
            "readOnly": self.read_only,
            "upload": self.enable_upload,
            "rename": self.enable_rename,
            "move": self.enable_move,
            "delete": self.enable_delete,
            "search": self.enable_search,
            "download": self.enable_download,
            "uploadConcurrency": self.upload_concurrency,
            "maxUploadBytes": self.max_upload_bytes,
        }
