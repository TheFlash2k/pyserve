import json
import mimetypes
import os
import re
import shutil
import traceback
import urllib.parse
from email.utils import formatdate
from http.server import BaseHTTPRequestHandler
from typing import Optional

from .assets import content_type_for, read_asset, read_asset_bytes
from .auth import MODE_BASIC, MODE_FORM
from .fs import QueryMatcher, is_safe_name
from . import iam as iam_actions
from .ignore import rel_parts_of
from .utils.logger import logger

RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)")
STATIC_PREFIX = "/static/"
DOWNLOAD_PREFIX = "/dl/"
STATIC_ASSETS = ("style.css", "app.js", "login.js", "logo.png", "favicon.ico")
WRITE_ROUTES = ("/api/upload", "/api/rename", "/api/move", "/api/delete")
PUBLIC_ROUTES = ("/login", "/api/login", "/api/logout", "/favicon.ico")

class PyServeHandler(BaseHTTPRequestHandler):

    """Request handler wired to a PyServe instance through its server object.

    Nothing is configured on the class itself, every setting is read from the
    PyServe instance the socket server carries, so several servers can run in
    the same process with different roots, permissions and credentials.
    """

    protocol_version = "HTTP/1.1"

    @property
    def app(self):
        """The PyServe instance this request belongs to."""
        return self.server.app

    @property
    def config(self):
        """Shortcut to the active Config."""
        return self.server.app.config

    @property
    def store(self):
        """Shortcut to the active FileStore."""
        return self.server.app.store

    @property
    def auth(self):
        """Shortcut to the active Authenticator."""
        return self.server.app.auth

    @property
    def iam(self):
        """Shortcut to the active IAMPolicy."""
        return self.server.app.iam

    def may(self, action: str, rel_path: str = "") -> bool:
        """True when the signed in user may perform action on rel_path."""
        return self.iam.allows(self.user, action, rel_path)

    def may_subtree(self, action: str, rel_path: str) -> bool:
        """True when action is allowed on rel_path and on everything beneath it.

        Deleting or moving a folder changes every path inside it, so a rule that
        protects one file down there has to block the whole operation rather
        than being quietly stepped over.
        """
        if not self.iam.enabled:
            return True
        for path, _ in self.store.walk_tree(rel_path):
            if not self.may(action, path):
                return False
        return True

    def send_denied(self, action: str, rel_path: str = "") -> None:
        """Refuses a request the policy does not allow."""
        self.drain_body()
        self.close_connection = True
        logger.warning(
            f"IAM denied {action} on {rel_path or '/'} for {self.user or iam_actions.ANONYMOUS}"
        )
        self.send_json(403, {"error": f"access denied: not allowed to {action} this path"})

    def visible(self):
        """The listing filter for the signed in user, or None when no policy applies."""
        return self.iam.visible(self.user)

    def setup(self) -> None:
        BaseHTTPRequestHandler.setup(self)
        self._response_sent = False
        self._body_consumed = False
        self.user = None
        self.route = ""
        self.query = {}

    def version_string(self) -> str:
        return self.config.server_header

    def log_message(self, fmt, *args) -> None:
        if self.config.access_log:
            logger.info(f"{self.address_string()} {fmt % args}")

    def log_error(self, fmt, *args) -> None:
        logger.warning(f"{self.address_string()} {fmt % args}")

    def do_HEAD(self) -> None:
        self._dispatch(self._route_head)

    def do_GET(self) -> None:
        self._dispatch(self._route_get)

    def do_POST(self) -> None:
        self._dispatch(self._route_post)

    def _dispatch(self, route) -> None:
        parsed = urllib.parse.urlsplit(self.path)
        self.route = parsed.path
        self.query = urllib.parse.parse_qs(parsed.query)
        try:
            if not self._authorize():
                return
            route()
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception:
            logger.error(f"Unhandled exception on {self.command} {self.path}\n{traceback.format_exc()}")
            if not self._response_sent:
                try:
                    self.close_connection = True
                    self.send_json(500, {"error": "internal server error"})
                except Exception:
                    pass

    def _route_head(self) -> None:
        if self.route.startswith(DOWNLOAD_PREFIX):
            self.serve_file(head_only=True)
        else:
            self.send_plain(405, "Method not allowed")

    def _route_get(self) -> None:
        route = self.route
        if route in ("/", "/index.html"):
            self.serve_index()
        elif route == "/login":
            self.serve_login()
        elif route.startswith(STATIC_PREFIX):
            self.serve_static(route[len(STATIC_PREFIX):])
        elif route == "/favicon.ico":
            self.serve_static("favicon.ico")
        elif route == "/api/list":
            self.serve_listing()
        elif route == "/api/search":
            self.serve_search()
        elif route == "/api/whoami":
            self.send_json(200, {"user": self.user, "authMode": self.auth.mode})
        elif route == "/api/cache":
            self.send_json(200, self.app.cache_stats())
        elif route == "/api/permissions":
            self.serve_permissions()
        elif route.startswith(DOWNLOAD_PREFIX):
            self.serve_file(head_only=False)
        elif route.startswith("/api/"):
            self.send_plain(404, "Not found")
        else:
            self.serve_folder(route)

    def _route_post(self) -> None:
        route = self.route
        if route == "/api/login":
            self.handle_login()
        elif route == "/api/logout":
            self.handle_logout()
        elif route == "/api/upload":
            self.handle_upload()
        elif route == "/api/rename":
            self.handle_rename()
        elif route == "/api/move":
            self.handle_move()
        elif route == "/api/delete":
            self.handle_delete()
        else:
            self.send_plain(404, "Not found")

    def _authorize(self) -> bool:
        auth = self.auth
        if not auth.enabled:
            return True
        if self.route.startswith(STATIC_PREFIX) or self.route in PUBLIC_ROUTES:
            return True
        if not auth.protects(self.route in WRITE_ROUTES):
            return True
        user = auth.identify(self.headers)
        if user:
            self.user = user
            return True
        self.send_challenge()
        return False

    def send_challenge(self) -> None:
        """Answers an unauthenticated request the way the active auth mode expects."""
        self.drain_body()
        if self.auth.mode == MODE_BASIC:
            payload = b"Authentication required"
            self.send_response(401)
            self.send_header("WWW-Authenticate", self.auth.challenge())
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self._response_sent = True
            self.wfile.write(payload)
            return
        if self.auth.mode == MODE_FORM and self.wants_html():
            self.send_redirect("/login?next=" + urllib.parse.quote(self.path))
            return
        self.send_json(401, {"error": "authentication required"})

    def wants_html(self) -> bool:
        """True when the client is a browser navigating rather than a script."""
        return self.command in ("GET", "HEAD") and "text/html" in self.headers.get("Accept", "")

    def send_redirect(self, location: str) -> None:
        """Sends a 302 with no body."""
        self.send_response(302)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()
        self._response_sent = True

    def send_bytes(self, status: int, data: bytes, content_type: str, headers=None) -> None:
        """Sends a complete response in one go."""
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self._response_sent = True
        if self.command != "HEAD":
            self.wfile.write(data)

    def send_json(self, status: int, payload, headers=None) -> None:
        """Sends a JSON response."""
        self.send_bytes(status, json.dumps(payload).encode("utf-8"), "application/json", headers)

    def send_plain(self, status: int, message: str) -> None:
        """Sends a plain text response."""
        self.send_bytes(status, message.encode("utf-8"), "text/plain; charset=utf-8")

    def read_json_body(self):
        """Parses a JSON request body, returning None when it is malformed."""
        length = self.content_length()
        raw = self.rfile.read(length) if length else b""
        self._body_consumed = True
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return None

    def content_length(self) -> int:
        """The Content-Length of the request, or 0."""
        try:
            return max(0, int(self.headers.get("Content-Length", 0) or 0))
        except ValueError:
            return 0

    def drain_body(self, length: Optional[int] = None) -> None:
        """Reads and discards an unused request body so keep alive stays usable.

        Draining twice would block forever waiting on bytes that were already
        read, so a body is only ever consumed once.
        """
        if self._body_consumed:
            return
        self._body_consumed = True
        remaining = self.content_length() if length is None else length
        if remaining <= 0:
            return
        chunk_size = self.config.chunk_size
        try:
            while remaining > 0:
                chunk = self.rfile.read(min(chunk_size, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
        except OSError:
            self.close_connection = True

    def header_value(self, name: str) -> str:
        """Percent decoded value of a request header."""
        return urllib.parse.unquote(self.headers.get(name, "") or "")

    def render(self, asset: str, state: dict, heading: str = "") -> bytes:
        """Fills the placeholders of a bundled page and returns it as bytes."""
        page = read_asset(asset)
        page = page.replace("__TITLE__", self.config.page_title)
        page = page.replace("__HEADING__", heading or self.config.title)
        page = page.replace("__STATE_JSON__", json.dumps(state))
        return page.encode("utf-8")

    def serve_index(self, rel_path: str = "") -> None:
        """The directory browser page, opened on rel_path."""
        self.app.reset_cache()
        state = {
            "rootName": self.config.title,
            "path": rel_path,
            "caps": self.config.capabilities,
            "user": self.user,
            "authMode": self.auth.mode,
            "iam": self.iam.enabled,
        }
        self.send_bytes(200, self.render("index.html", state), content_type_for("index.html"))

    def serve_permissions(self) -> None:
        """What the signed in user may do at one path, and the rules behind it."""
        rel_path = (self.query.get("path", [""])[0] or "").strip("/")
        self.send_json(200, {
            "user": self.user or iam_actions.ANONYMOUS,
            "path": rel_path,
            "enabled": self.iam.enabled,
            "default": self.iam.default,
            "permissions": self.iam.permissions(self.user, rel_path),
            "rules": self.iam.describe(self.user),
        })

    def serve_folder(self, route: str) -> None:
        """Serves the browser page for a folder URL such as /docs/notes/.

        Every folder has a real address, so a link can be copied, bookmarked or
        opened in a new tab and lands on the same folder.
        """
        rel_path = "/".join(
            urllib.parse.unquote(part) for part in route.split("/") if part
        )
        abs_path = self.store.resolve(rel_path)
        if abs_path is None or not os.path.isdir(abs_path):
            self.send_plain(404, "Not found")
            return
        if rel_path and self.store.is_path_hidden(rel_path, True):
            self.send_plain(404, "Not found")
            return
        if not self.may(iam_actions.LIST, rel_path):
            self.send_plain(403, "Access denied")
            return
        self.serve_index(rel_path)

    def serve_login(self) -> None:
        """The sign in page, only reachable in form mode."""
        if not self.auth.uses_form:
            self.send_redirect("/")
            return
        if self.auth.check_session(self.headers.get("Cookie", "")):
            self.send_redirect("/")
            return
        next_url = (self.query.get("next", ["/"])[0] or "/").strip()
        if not next_url.startswith("/") or next_url.startswith("//"):
            next_url = "/"
        page = self.render("login.html", {"next": next_url}, heading=self.config.title)
        self.send_bytes(200, page, content_type_for("login.html"))

    def serve_static(self, name: str) -> None:
        """Serves one of the bundled stylesheets or scripts."""
        if name not in STATIC_ASSETS:
            self.send_plain(404, "Not found")
            return
        self.send_bytes(200, read_asset_bytes(name), content_type_for(name), {"Cache-Control": "no-cache"})

    def handle_login(self) -> None:
        """Validates the sign in form and hands out a session cookie."""
        if not self.auth.uses_form:
            self.send_json(404, {"error": "form authentication is not enabled"})
            return
        body = self.read_json_body()
        if body is None:
            self.send_json(400, {"error": "invalid JSON"})
            return
        token = self.auth.login(str(body.get("username") or ""), str(body.get("password") or ""))
        if not token:
            self.send_json(401, {"error": "invalid credentials"})
            return
        self.send_json(200, {"ok": True}, {"Set-Cookie": self.auth.cookie_value(token)})

    def handle_logout(self) -> None:
        """Destroys the current session."""
        self.drain_body()
        if not self.auth.uses_form:
            self.send_json(404, {"error": "form authentication is not enabled"})
            return
        self.auth.logout(self.headers.get("Cookie", ""))
        self.send_json(200, {"ok": True}, {"Set-Cookie": self.auth.cookie_value("", max_age=0)})

    def serve_listing(self) -> None:
        """Directory contents as JSON."""
        rel_path = (self.query.get("path", [""])[0] or "").strip("/")
        if rel_path and self.store.is_path_hidden(rel_path, True):
            self.send_plain(404, "Directory not found")
            return
        if not self.may(iam_actions.LIST, rel_path):
            self.send_denied(iam_actions.LIST, rel_path)
            return
        entries = self.store.listdir(rel_path, allow=self.visible())
        if entries is None:
            self.send_plain(404, "Directory not found")
            return
        payload = {
            "path": rel_path,
            "entries": self.iam.annotate(self.user, rel_path, entries),
        }
        if self.iam.enabled:
            payload["perms"] = self.iam.folder_permissions(self.user, rel_path)
        self.send_json(200, payload)
        self.app.warm_cache()

    def serve_search(self) -> None:
        """Search results as JSON, scoped to the folder the request came from."""
        query = (self.query.get("q", [""])[0] or "").strip()
        rel_path = (self.query.get("path", [""])[0] or "").strip("/")
        if not self.config.enable_search:
            self.send_json(403, {"error": "search is disabled on this server"})
            return
        if rel_path and self.store.is_path_hidden(rel_path, True):
            self.send_json(404, {"error": "folder not found"})
            return
        if self.store.resolve(rel_path) is None:
            self.send_json(404, {"error": "folder not found"})
            return
        if not self.may(iam_actions.SEARCH, rel_path):
            self.send_denied(iam_actions.SEARCH, rel_path)
            return
        if not query:
            self.send_json(200, {"query": query, "path": rel_path, "matches": []})
            return
        matcher = QueryMatcher(query)
        if matcher.error:
            self.send_json(400, {"error": matcher.error, "query": query, "path": rel_path})
            return
        matches = self.store.search(query, rel_path=rel_path, allow=self.visible())
        prefix = rel_path + "/" if rel_path else ""
        annotated = [
            dict(match, perms=self.iam.permissions(
                self.user, prefix + "/".join(match["path"] + [match["name"]])
            )) if self.iam.enabled else match
            for match in matches
        ]
        self.send_json(200, {"query": query, "path": rel_path, "matches": annotated})

    def serve_file(self, head_only: bool) -> None:
        """Streams a file with Range support so paused downloads can resume."""
        if not self.config.enable_download:
            self.send_plain(403, "Downloads are disabled on this server")
            return

        rel_path = urllib.parse.unquote(self.route[len(DOWNLOAD_PREFIX):])
        abs_path = self.store.resolve(rel_path)
        parts = rel_parts_of(rel_path)

        if abs_path is None or not os.path.isfile(abs_path) or self.store.is_hidden(parts, False):
            self.send_plain(404, "File not found")
            return

        if not self.may(iam_actions.DOWNLOAD, rel_path):
            self.send_plain(403, "Access denied")
            return

        file_size = os.path.getsize(abs_path)
        content_type = mimetypes.guess_type(abs_path)[0] or "application/octet-stream"
        start, end = 0, file_size - 1
        status = 200

        range_header = self.headers.get("Range")
        if range_header:
            found = RANGE_RE.match(range_header)
            if found:
                start_text, end_text = found.groups()
                if start_text == "" and end_text != "":
                    span = min(int(end_text), file_size)
                    start, end = file_size - span, file_size - 1
                else:
                    start = int(start_text) if start_text else 0
                    end = int(end_text) if end_text else file_size - 1
                end = min(end, file_size - 1)
                if start > end or start >= file_size:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{file_size}")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    self._response_sent = True
                    return
                status = 206

        length = end - start + 1
        filename = os.path.basename(abs_path).replace('"', "")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        self.send_header("Last-Modified", formatdate(os.path.getmtime(abs_path), usegmt=True))
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
        self.end_headers()
        self._response_sent = True

        if head_only:
            return

        chunk_size = self.config.chunk_size
        with open(abs_path, "rb") as source:
            source.seek(start)
            remaining = length
            try:
                while remaining > 0:
                    chunk = source.read(min(chunk_size, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
            except OSError:
                self.close_connection = True

    def refuse_write(self, status: int, message: str, length: int = 0) -> None:
        """Drains the body and answers a write that is not allowed."""
        self.drain_body(length)
        self.close_connection = True
        self.send_json(status, {"error": message})

    def handle_upload(self) -> None:
        """Streams the request body straight into a file inside the served tree."""
        length = self.content_length()

        if not self.config.enable_upload:
            self.refuse_write(403, "uploads are disabled on this server", length)
            return

        limit = self.config.max_upload_bytes
        if limit and length > limit:
            self.refuse_write(413, "file exceeds the maximum upload size", length)
            return

        target_rel = self.header_value("X-Target-Path")
        filename = self.header_value("X-Filename")
        conflict = self.headers.get("X-Conflict", "")

        if not is_safe_name(filename):
            self.refuse_write(400, "invalid filename", length)
            return

        abs_target = self.store.resolve(target_rel)
        if abs_target is None or not os.path.isdir(abs_target) or self.store.is_path_hidden(target_rel, True):
            self.refuse_write(404, "target folder not found", length)
            return

        destination = f"{target_rel}/{filename}".strip("/")
        if self.store.is_path_hidden(destination, False):
            self.refuse_write(403, "that name is hidden by the ignore file", length)
            return

        if not self.may(iam_actions.UPLOAD, destination):
            self.send_denied(iam_actions.UPLOAD, destination)
            return

        with self.app.write_lock:
            dest = os.path.join(abs_target, filename)
            if os.path.exists(dest):
                if not conflict:
                    self.drain_body(length)
                    self.close_connection = True
                    self.send_json(409, {"conflict": True, "name": filename})
                    return
                if conflict == "replace" and os.path.isdir(dest):
                    self.refuse_write(400, "a folder with that name already exists", length)
                    return
                if conflict == "copy":
                    filename = self.store.next_available_name(abs_target, filename)
                    dest = os.path.join(abs_target, filename)

            chunk_size = self.config.chunk_size
            try:
                with open(dest, "wb") as out:
                    remaining = length
                    while remaining > 0:
                        chunk = self.rfile.read(min(chunk_size, remaining))
                        if not chunk:
                            break
                        out.write(chunk)
                        remaining -= len(chunk)
                self._body_consumed = True
                stat = os.stat(dest)
            except OSError as error:
                logger.error(f"Upload write failed for {filename!r}: {error}")
                try:
                    if os.path.exists(dest):
                        os.remove(dest)
                except OSError:
                    pass
                self.close_connection = True
                self.send_json(500, {"error": "could not write file to storage"})
                return

        self.store.invalidate(target_rel)
        self.send_json(200, {
            "ok": True,
            "name": filename,
            "size": stat.st_size,
            "mtime": int(stat.st_mtime),
            "path": target_rel,
        })

    def handle_rename(self) -> None:
        """Renames a file or folder inside its own parent directory."""
        if not self.config.enable_rename:
            self.refuse_write(403, "renaming is disabled on this server")
            return

        body = self.read_json_body()
        if body is None:
            self.send_json(400, {"error": "invalid JSON"})
            return

        rel_path = (body.get("path") or "").strip("/")
        new_name = body.get("newName") or ""
        if not rel_path or not is_safe_name(new_name):
            self.send_json(400, {"error": "invalid request"})
            return

        abs_path = self.store.resolve(rel_path)
        if abs_path is None or not os.path.exists(abs_path):
            self.send_json(404, {"error": "not found"})
            return
        if self.store.is_path_hidden(rel_path, os.path.isdir(abs_path)):
            self.send_json(404, {"error": "not found"})
            return

        parent = "/".join(rel_parts_of(rel_path)[:-1])
        renamed = f"{parent}/{new_name}".strip("/")
        if not self.may_subtree(iam_actions.RENAME, rel_path):
            self.send_denied(iam_actions.RENAME, rel_path)
            return
        if not self.may(iam_actions.RENAME, renamed):
            self.send_denied(iam_actions.RENAME, renamed)
            return

        with self.app.write_lock:
            new_abs = os.path.join(os.path.dirname(abs_path), new_name)
            if os.path.exists(new_abs) and os.path.normcase(new_abs) != os.path.normcase(abs_path):
                self.send_json(409, {"conflict": True, "name": new_name})
                return
            try:
                os.rename(abs_path, new_abs)
            except OSError as error:
                logger.error(f"Rename failed for {rel_path!r}: {error}")
                self.close_connection = True
                self.send_json(500, {"error": "could not rename (storage error)"})
                return
        self.store.invalidate_tree(rel_path)
        self.store.invalidate("/".join(rel_parts_of(rel_path)[:-1]))
        self.send_json(200, {"ok": True, "name": new_name})

    def handle_move(self) -> None:
        """Moves a file or folder into another folder of the served tree."""
        if not self.config.enable_move:
            self.refuse_write(403, "moving files is disabled on this server")
            return

        body = self.read_json_body()
        if body is None:
            self.send_json(400, {"error": "invalid JSON"})
            return

        rel_path = (body.get("path") or "").strip("/")
        target_rel = (body.get("targetDir") or "").strip("/")
        conflict = body.get("conflict") or ""
        if not rel_path:
            self.send_json(400, {"error": "invalid request"})
            return

        abs_src = self.store.resolve(rel_path)
        if abs_src is None or not os.path.exists(abs_src):
            self.send_json(404, {"error": "source not found"})
            return
        if self.store.is_path_hidden(rel_path, os.path.isdir(abs_src)):
            self.send_json(404, {"error": "source not found"})
            return

        abs_target = self.store.resolve(target_rel)
        if abs_target is None or not os.path.isdir(abs_target) or self.store.is_path_hidden(target_rel, True):
            self.send_json(404, {"error": "target folder not found"})
            return

        if abs_target == abs_src or abs_target.startswith(abs_src + os.sep):
            self.send_json(400, {"error": "cannot move a folder into itself"})
            return

        moved = f"{target_rel}/{os.path.basename(abs_src)}".strip("/")
        if not self.may_subtree(iam_actions.MOVE, rel_path):
            self.send_denied(iam_actions.MOVE, rel_path)
            return
        if not self.may(iam_actions.MOVE, moved):
            self.send_denied(iam_actions.MOVE, moved)
            return

        with self.app.write_lock:
            basename = os.path.basename(abs_src)
            dest = os.path.join(abs_target, basename)

            if os.path.exists(dest) and os.path.normcase(dest) != os.path.normcase(abs_src):
                if not conflict:
                    self.send_json(409, {"conflict": True, "name": basename})
                    return
                if conflict == "replace":
                    try:
                        self.store.remove(dest)
                    except OSError as error:
                        logger.error(f"Move (replace) failed for {rel_path!r}: {error}")
                        self.close_connection = True
                        self.send_json(500, {"error": "could not replace existing item (storage error)"})
                        return
                elif conflict == "copy":
                    basename = self.store.next_available_name(abs_target, basename)
                    dest = os.path.join(abs_target, basename)

            try:
                shutil.move(abs_src, dest)
            except OSError as error:
                logger.error(f"Move failed for {rel_path!r} to {target_rel!r}: {error}")
                self.close_connection = True
                self.send_json(500, {"error": "could not move item (storage error)"})
                return
        self.store.invalidate_tree(rel_path)
        self.store.invalidate("/".join(rel_parts_of(rel_path)[:-1]))
        self.store.invalidate(target_rel)
        self.send_json(200, {"ok": True, "name": basename})

    def handle_delete(self) -> None:
        """Deletes a file, or recursively deletes a folder after a name confirmation."""
        if not self.config.enable_delete:
            self.refuse_write(403, "deleting is disabled on this server")
            return

        body = self.read_json_body()
        if body is None:
            self.send_json(400, {"error": "invalid JSON"})
            return

        rel_path = (body.get("path") or "").strip("/")
        confirm_name = body.get("name") or ""
        if not rel_path:
            self.send_json(400, {"error": "invalid request"})
            return

        abs_path = self.store.resolve(rel_path)
        if abs_path is None or not os.path.exists(abs_path):
            self.send_json(404, {"error": "not found"})
            return
        if self.store.is_path_hidden(rel_path, os.path.isdir(abs_path)):
            self.send_json(404, {"error": "not found"})
            return

        if not self.may_subtree(iam_actions.DELETE, rel_path):
            self.send_denied(iam_actions.DELETE, rel_path)
            return

        with self.app.write_lock:
            if os.path.isdir(abs_path) and not os.path.islink(abs_path):
                if confirm_name != os.path.basename(abs_path):
                    self.send_json(400, {"error": "name confirmation did not match"})
                    return
            try:
                self.store.remove(abs_path)
            except OSError as error:
                logger.error(f"Delete failed for {rel_path!r}: {error}")
                self.close_connection = True
                self.send_json(500, {"error": "could not delete (storage error)"})
                return
        self.store.invalidate_tree(rel_path)
        self.store.invalidate("/".join(rel_parts_of(rel_path)[:-1]))
        self.send_json(200, {"ok": True})
