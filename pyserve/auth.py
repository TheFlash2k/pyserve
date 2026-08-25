import base64
import binascii
import hashlib
import hmac
import os
import secrets
import threading
import time
from typing import Dict, Optional, Tuple

from .utils.logger import logger

PBKDF2_ROUNDS = 240000
PBKDF2_ALGO = "sha256"
MODE_NONE = "none"
MODE_BASIC = "basic"
MODE_FORM = "form"
MODES = (MODE_NONE, MODE_BASIC, MODE_FORM)
SCOPE_ALL = "all"
SCOPE_WRITE = "write"
SCOPES = (SCOPE_ALL, SCOPE_WRITE)

def hash_password(password: str, rounds: int = PBKDF2_ROUNDS) -> str:
    """Returns a 'pbkdf2$rounds$salt$digest' string for the given password."""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(PBKDF2_ALGO, password.encode("utf-8"), salt, rounds)
    return f"pbkdf2${rounds}${salt.hex()}${digest.hex()}"

def verify_password(stored: str, password: str) -> bool:
    """Checks a password against a plain, 'sha256$' or 'pbkdf2$' secret."""
    if not stored:
        return False
    try:
        if stored.startswith("pbkdf2$"):
            _, rounds, salt, digest = stored.split("$", 3)
            candidate = hashlib.pbkdf2_hmac(
                PBKDF2_ALGO, password.encode("utf-8"), bytes.fromhex(salt), int(rounds)
            )
            return hmac.compare_digest(candidate.hex(), digest)
        if stored.startswith("sha256$"):
            digest = stored.split("$", 1)[1]
            candidate = hashlib.sha256(password.encode("utf-8")).hexdigest()
            return hmac.compare_digest(candidate, digest)
    except (ValueError, binascii.Error):
        return False
    return hmac.compare_digest(stored, password)

def parse_users(value) -> Dict[str, str]:
    """Parses 'user:secret,other:secret' or a mapping into a username to secret dict."""
    if not value:
        return {}
    if isinstance(value, dict):
        return {str(k): str(v) for k, v in value.items()}
    users: Dict[str, str] = {}
    entries = value if isinstance(value, (list, tuple)) else str(value).split(",")
    for entry in entries:
        entry = str(entry).strip()
        if not entry or ":" not in entry:
            continue
        username, _, secret = entry.partition(":")
        username = username.strip()
        if username:
            users[username] = secret.strip()
    return users

def load_users_file(path: str) -> Dict[str, str]:
    """Reads a htpasswd style file of 'user:secret' lines."""
    users: Dict[str, str] = {}
    if not path or not os.path.isfile(path):
        return users
    with open(path, "r", encoding="utf-8", errors="ignore") as handle:
        for raw in handle:
            line = raw.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            username, _, secret = line.partition(":")
            username = username.strip()
            if username:
                users[username] = secret.strip()
    return users

class SessionStore:

    """In memory session table for the sign in form.

    Attributes:
        ttl: Lifetime of a session in seconds
    """

    def __init__(self, ttl: int = 86400):
        self.ttl = ttl
        self._sessions: Dict[str, Tuple[str, float]] = {}
        self._lock = threading.Lock()

    def create(self, username: str) -> str:
        """Issues a new opaque token for username and returns it."""
        token = secrets.token_urlsafe(32)
        with self._lock:
            self._prune()
            self._sessions[token] = (username, time.time() + self.ttl)
        return token

    def get(self, token: str) -> Optional[str]:
        """Returns the username behind a token, or None when it is unknown or expired."""
        if not token:
            return None
        with self._lock:
            entry = self._sessions.get(token)
            if not entry:
                return None
            username, expires = entry
            if expires < time.time():
                self._sessions.pop(token, None)
                return None
            return username

    def destroy(self, token: str) -> None:
        """Drops a token so the cookie stops working immediately."""
        with self._lock:
            self._sessions.pop(token, None)

    def clear(self) -> None:
        """Drops every session."""
        with self._lock:
            self._sessions.clear()

    def _prune(self) -> None:
        now = time.time()
        for token in [t for t, (_, exp) in self._sessions.items() if exp < now]:
            self._sessions.pop(token, None)

class Authenticator:

    """Credential checking for PyServe.

    Three modes are supported. 'none' lets everything through, 'basic' answers
    with a WWW-Authenticate challenge so the browser shows the usual popup, and
    'form' hands out a signed session cookie from a sign in page. The scope
    decides whether the credentials guard the whole server or only the routes
    that modify the served directory.

    Attributes:
        mode: One of 'none', 'basic' or 'form'
        users: Mapping of username to plain, 'sha256$' or 'pbkdf2$' secret
        realm: Realm shown in the basic auth popup
        scope: Either 'all' or 'write'
        sessions: SessionStore backing the form mode
        cookie_name: Name of the session cookie
        cookie_secure: Adds the Secure flag to the session cookie
    """

    def __init__(
        self,
        mode: str = MODE_NONE,
        users=None,
        realm: str = "pyserve",
        scope: str = SCOPE_ALL,
        session_ttl: int = 86400,
        cookie_name: str = "pyserve_session",
        cookie_secure: bool = False,
        users_file: str = "",
    ):
        self.mode = (mode or MODE_NONE).strip().lower()
        if self.mode not in MODES:
            raise ValueError(f"Unknown auth mode: {mode}. Pick one of {', '.join(MODES)}")
        self.scope = (scope or SCOPE_ALL).strip().lower()
        if self.scope not in SCOPES:
            raise ValueError(f"Unknown auth scope: {scope}. Pick one of {', '.join(SCOPES)}")
        self.users = parse_users(users)
        if users_file:
            self.users.update(load_users_file(users_file))
        self.realm = realm or "pyserve"
        self.cookie_name = cookie_name or "pyserve_session"
        self.cookie_secure = cookie_secure
        self.sessions = SessionStore(ttl=session_ttl)
        if self.enabled and not self.users:
            raise ValueError(f"Auth mode '{self.mode}' was requested but no users were configured")

    @property
    def enabled(self) -> bool:
        """True when any credential checking is active."""
        return self.mode != MODE_NONE

    @property
    def uses_form(self) -> bool:
        """True when the sign in page is in use."""
        return self.mode == MODE_FORM

    def protects(self, is_write: bool) -> bool:
        """True when a request of this kind has to be authenticated."""
        if not self.enabled:
            return False
        return True if self.scope == SCOPE_ALL else is_write

    def check_credentials(self, username: str, password: str) -> bool:
        """Constant time credential check that does not leak whether a user exists."""
        stored = self.users.get(username or "")
        if stored is None:
            verify_password(hash_password("pyserve", rounds=1), password or "")
            return False
        return verify_password(stored, password or "")

    def check_basic(self, header: str) -> Optional[str]:
        """Validates an Authorization header and returns the username on success."""
        if not header or not header.lower().startswith("basic "):
            return None
        try:
            raw = base64.b64decode(header.split(" ", 1)[1].strip()).decode("utf-8")
        except (ValueError, binascii.Error, UnicodeDecodeError):
            return None
        username, _, password = raw.partition(":")
        return username if self.check_credentials(username, password) else None

    def check_session(self, cookie_header: str) -> Optional[str]:
        """Returns the username behind the session cookie, or None."""
        token = self.read_cookie(cookie_header)
        return self.sessions.get(token) if token else None

    def read_cookie(self, cookie_header: str) -> Optional[str]:
        """Pulls the session token out of a raw Cookie header."""
        if not cookie_header:
            return None
        for chunk in cookie_header.split(";"):
            name, _, value = chunk.strip().partition("=")
            if name == self.cookie_name:
                return value.strip()
        return None

    def identify(self, headers) -> Optional[str]:
        """Returns the username for a request, or None when it is not signed in."""
        if not self.enabled:
            return None
        if self.mode == MODE_BASIC:
            return self.check_basic(headers.get("Authorization", ""))
        return self.check_session(headers.get("Cookie", ""))

    def login(self, username: str, password: str) -> Optional[str]:
        """Validates credentials and returns a fresh session token on success."""
        if not self.check_credentials(username, password):
            logger.warning(f"Failed sign in attempt for user {username!r}")
            return None
        logger.info(f"User {username!r} signed in")
        return self.sessions.create(username)

    def logout(self, cookie_header: str) -> None:
        """Destroys the session behind a Cookie header."""
        token = self.read_cookie(cookie_header)
        if token:
            self.sessions.destroy(token)

    def cookie_value(self, token: str, max_age: Optional[int] = None) -> str:
        """Builds the Set-Cookie value for a token, or for clearing it."""
        max_age = self.sessions.ttl if max_age is None else max_age
        parts = [
            f"{self.cookie_name}={token}",
            "Path=/",
            "HttpOnly",
            "SameSite=Strict",
            f"Max-Age={max_age}",
        ]
        if self.cookie_secure:
            parts.append("Secure")
        return "; ".join(parts)

    def challenge(self) -> str:
        """The WWW-Authenticate value for basic mode."""
        realm = self.realm.replace('"', "")
        return f'Basic realm="{realm}", charset="UTF-8"'
