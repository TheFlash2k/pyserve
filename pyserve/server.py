import os
import socket
import ssl
import threading
from http.server import ThreadingHTTPServer
from typing import Optional

from .auth import Authenticator
from .cache import DirectoryCache
from .config import Config
from .fs import FileStore
from .handler import PyServeHandler
from .iam import IAMPolicy
from .ignore import IgnoreList
from .utils.logger import Logger, logger

class PyServeHTTPServer(ThreadingHTTPServer):

    """ThreadingHTTPServer that carries the PyServe instance for its handlers."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, handler_class, app):
        self.app = app
        ThreadingHTTPServer.__init__(self, address, handler_class)

class PyServe:

    """A configurable directory server that can be embedded or run from the shell.

    Attributes:
        config: The resolved Config
        store: FileStore rooted at the served directory
        cache: DirectoryCache warmed in the background after the first listing
        auth: Authenticator built from the auth settings
        iam: IAMPolicy applied to every route that touches a path
        write_lock: Serializes upload, rename, move and delete

    Example:
        server = PyServe("/srv/files", port=9000, auth_mode="form",
                         auth_users={"alice": "hunter2"})
        server.start()
    """

    def __init__(
        self,
        directory: Optional[str] = None,
        config: Optional[Config] = None,
        config_file: Optional[str] = None,
        env: bool = True,
        autodiscover: bool = False,
        **options,
    ):
        if directory is not None:
            options["directory"] = directory

        if config is not None:
            self.config = config.update(options).finalize()
        else:
            self.config = Config.load(
                config_file=config_file,
                overrides=options,
                env=env,
                autodiscover=autodiscover,
            )

        Logger.set_level(self.config.log_level)

        self.write_lock = threading.Lock()
        self.cache = DirectoryCache(
            enabled=self.config.cache_enabled,
            threads=self.config.cache_threads,
            max_dirs=self.config.cache_max_dirs,
        )
        self.store = FileStore(
            root=self.config.directory,
            ignore_file=self.config.ignore_file,
            show_hidden=self.config.show_hidden,
            follow_symlinks=self.config.follow_symlinks,
            search_limit=self.config.search_limit,
            cache=self.cache,
            use_default_ignore=self.config.default_ignore,
        )
        self.auth = Authenticator(
            mode=self.config.auth_mode,
            users=self.config.auth_users,
            users_file=self.config.auth_users_file,
            realm=self.config.auth_realm,
            scope=self.config.auth_scope,
            session_ttl=self.config.session_ttl,
            cookie_name=self.config.session_cookie,
            cookie_secure=self.config.cookie_secure,
        )
        self.iam = IAMPolicy.from_lines(
            self.config.iam_rules,
            default=self.config.iam_default,
            source=self.config.iam_rules_file or self.config.config_file or "iam",
        )
        self._server: Optional[PyServeHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def __repr__(self) -> str:
        return f"PyServe(root={self.config.directory!r}, url={self.url!r})"

    def __enter__(self) -> "PyServe":
        self.start(block=False)
        return self

    def __exit__(self, *_) -> None:
        self.stop()

    @property
    def scheme(self) -> str:
        """Either http or https depending on whether TLS was configured."""
        return "https" if self.config.tls_cert else "http"

    @property
    def port(self) -> int:
        """The bound port, which is the real one when port 0 was requested."""
        if self._server is not None:
            return self._server.server_address[1]
        return self.config.port

    @property
    def url(self) -> str:
        """The address the server can be reached at."""
        host = self.config.host
        if host in ("0.0.0.0", "::", ""):
            host = "127.0.0.1"
        return f"{self.scheme}://{host}:{self.port}"

    @property
    def running(self) -> bool:
        """True while the server is accepting connections."""
        return self._server is not None

    @property
    def ignore(self) -> IgnoreList:
        """The ignore list currently applied to every request."""
        return self.store.ignore

    def reload_ignore(self) -> IgnoreList:
        """Re-reads the ignore file so pattern changes apply without a restart."""
        return self.store.reload_ignore()

    def reset_cache(self) -> None:
        """Empties the directory cache and queues a fresh warm for the next listing."""
        self.cache.reset()

    def warm_cache(self) -> bool:
        """Starts the background walk if one is queued, which is what the first listing does."""
        return self.cache.warm(self.store)

    def cache_stats(self) -> dict:
        """Counters for the directory cache."""
        return self.cache.stats()

    def may(self, user: Optional[str], action: str, rel_path: str = "") -> bool:
        """True when the policy lets user perform action on rel_path."""
        return self.iam.allows(user, action, rel_path)

    def add_user(self, username: str, secret: str) -> None:
        """Adds or replaces a credential at runtime."""
        self.auth.users[username] = secret

    def remove_user(self, username: str) -> None:
        """Drops a credential and leaves existing sessions to expire on their own."""
        self.auth.users.pop(username, None)

    def build_server(self) -> PyServeHTTPServer:
        """Creates the socket server and wraps it in TLS when a certificate is set."""
        if ":" in self.config.host and not self.config.host.startswith("["):
            PyServeHTTPServer.address_family = socket.AF_INET6
        server = PyServeHTTPServer((self.config.host, self.config.port), PyServeHandler, self)
        if self.config.tls_cert:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(self.config.tls_cert, self.config.tls_key)
            server.socket = context.wrap_socket(server.socket, server_side=True)
        return server

    def summary(self) -> str:
        """A one line description of what the server is about to do."""
        bits = []
        if self.config.read_only:
            bits.append("read-only")
        else:
            for enabled, label in (
                (self.config.enable_upload, "upload"),
                (self.config.enable_rename, "rename"),
                (self.config.enable_move, "move"),
                (self.config.enable_delete, "delete"),
            ):
                if not enabled:
                    bits.append(f"no-{label}")
        if not self.config.enable_search:
            bits.append("no-search")
        if not self.config.enable_download:
            bits.append("no-download")
        if self.config.cache_enabled:
            bits.append(f"cache:{self.cache.threads} thread(s)")
        else:
            bits.append("no-cache")
        if self.auth.enabled:
            bits.append(f"auth:{self.auth.mode}/{self.auth.scope}")
        if self.iam.enabled:
            bits.append(f"iam:{len(self.iam)} rules/default {self.iam.default}")
        return ", ".join(bits) if bits else "full access"

    def start(self, block: bool = True) -> "PyServe":
        """Starts serving, either blocking or on a daemon thread."""
        if self._server is not None:
            raise RuntimeError("This PyServe instance is already running")
        self._server = self.build_server()

        source = self.store.ignore.source or "no ignore file"
        logger.info(f"Serving {self.config.directory} on {self.url}")
        logger.info(f"{len(self.store.ignore)} ignore pattern(s) from {source}, {self.summary()}")

        if not block:
            self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
            self._thread.start()
            return self

        try:
            self._server.serve_forever()
        except KeyboardInterrupt:
            logger.info("Shutting down")
        finally:
            self.stop()
        return self

    def serve_forever(self) -> "PyServe":
        """Blocking alias for start()."""
        return self.start(block=True)

    def stop(self) -> None:
        """Stops the server and releases the socket."""
        if self._server is None:
            return
        self.cache.stop()
        server, self._server = self._server, None
        server.shutdown()
        server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
