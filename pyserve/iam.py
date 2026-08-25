import re
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

ALLOW = "allow"
DENY = "deny"
EFFECTS = (ALLOW, DENY)

LIST = "list"
DOWNLOAD = "download"
SEARCH = "search"
UPLOAD = "upload"
RENAME = "rename"
MOVE = "move"
DELETE = "delete"

ACTIONS: Tuple[str, ...] = (LIST, DOWNLOAD, SEARCH, UPLOAD, RENAME, MOVE, DELETE)
READ_ACTIONS: Tuple[str, ...] = (LIST, DOWNLOAD, SEARCH)
WRITE_ACTIONS: Tuple[str, ...] = (UPLOAD, RENAME, MOVE, DELETE)
ACTION_ALIASES: Dict[str, Tuple[str, ...]] = {
    "read": READ_ACTIONS,
    "write": WRITE_ACTIONS,
    "all": ACTIONS,
    "*": ACTIONS,
}

EVERYONE = "*"
EXCLUDE = "!"
UPLOAD_PROBE = "*"
ANONYMOUS = "anonymous"
DEFAULT_DIRECTIVE = "default"

def glob_to_regex(pattern: str) -> str:
    """Translates a glob into a regex where '*' stops at a separator and '**' does not."""
    out: List[str] = []
    index = 0
    length = len(pattern)
    while index < length:
        char = pattern[index]
        if char == "*":
            if pattern.startswith("**/", index):
                out.append("(?:.*/)?")
                index += 3
                continue
            if pattern.startswith("**", index):
                out.append(".*")
                index += 2
                continue
            out.append("[^/]*")
            index += 1
            continue
        if char == "?":
            out.append("[^/]")
            index += 1
            continue
        if char == "[":
            close = pattern.find("]", index + 1)
            if close > index + 1:
                body = pattern[index + 1:close]
                if body.startswith("!"):
                    body = "^" + body[1:]
                out.append("[" + body + "]")
                index = close + 1
                continue
        out.append(re.escape(char))
        index += 1
    return "".join(out)

class Target:

    """What a rule applies to.

    A pattern with no separator is matched against the entry name alone, so
    '*.key' covers every key file anywhere. A pattern with a separator is
    matched against the path relative to the served root. A trailing slash
    makes it a folder, covering the folder itself and everything beneath it.
    Matching is case insensitive, so a deny rule cannot be slipped past with a
    different spelling.

    Attributes:
        raw: The pattern exactly as it was written
        pattern: The pattern after the leading and trailing slashes are stripped
        subtree: True when the pattern ended with '/'
        on_name: True when the entry name is the match target
    """

    def __init__(self, pattern: str):
        self.raw = pattern
        text = (pattern or "").strip()
        self.subtree = text.endswith("/")
        text = text.strip("/")
        self.pattern = text
        self.on_name = "/" not in text and not self.subtree
        source = glob_to_regex(text)
        if self.subtree:
            source += "(?:/.*)?"
        self.regex = re.compile("(?:" + source + ")$", re.IGNORECASE)

    def __repr__(self) -> str:
        return f"Target({self.raw!r})"

    def matches(self, rel_path: str, name: str) -> bool:
        """True when this target covers the given path."""
        return bool(self.regex.match(name if self.on_name else rel_path))

class IAMRule:

    """One line of policy: an effect, who it covers, what it covers and where.

    A username may be prefixed with '!' to exclude it, which is how a deny is
    written with an exception. Since an explicit deny always wins, a later
    allow can never carve someone back out of a blanket deny, so the exception
    has to be part of the deny itself.

    Attributes:
        effect: Either 'allow' or 'deny'
        users: The usernames it applies to, or {'*'} for everyone
        excluded: The usernames it explicitly does not apply to
        actions: The action names it applies to
        target: The Target it applies to
        source: Where the rule was read from, used in error messages
    """

    def __init__(self, effect: str, users, actions, target, source: str = "",
                 excluded=None):
        self.effect = effect
        self.users = set(users)
        self.excluded = set(excluded or ())
        self.actions = set(actions)
        self.target = target if isinstance(target, Target) else Target(target)
        self.source = source

    @property
    def users_text(self) -> str:
        """The users field written the way it was configured."""
        parts = sorted(self.users) + [EXCLUDE + name for name in sorted(self.excluded)]
        return ",".join(parts)

    def __repr__(self) -> str:
        return f"IAMRule({self.effect} {self.users_text} " \
               f"{','.join(sorted(self.actions))} {self.target.raw})"

    def __str__(self) -> str:
        return f"{self.effect} {self.users_text} " \
               f"{','.join(sorted(self.actions))} {self.target.raw}"

    @classmethod
    def parse(cls, line: str, source: str = "") -> "IAMRule":
        """Parses 'effect users actions target' into a rule."""
        parts = line.split(None, 3)
        if len(parts) < 4:
            raise ValueError(
                f"IAM rule needs four fields, 'effect users actions target', got {line!r}"
            )
        effect, users_text, actions_text, target = parts
        effect = effect.lower()
        if effect not in EFFECTS:
            raise ValueError(f"IAM rule effect has to be allow or deny, got {effect!r}")

        users = set()
        excluded = set()
        for part in users_text.split(","):
            part = part.strip()
            if not part:
                continue
            if part.startswith(EXCLUDE):
                name = part[1:].strip()
                if not name:
                    raise ValueError(f"IAM rule has an empty exclusion: {line!r}")
                excluded.add(name)
            else:
                users.add(part)
        if not users and not excluded:
            raise ValueError(f"IAM rule names no user: {line!r}")
        if not users:
            users = {EVERYONE}

        actions = set()
        for part in actions_text.split(","):
            part = part.strip().lower()
            if not part:
                continue
            if part in ACTION_ALIASES:
                actions.update(ACTION_ALIASES[part])
            elif part in ACTIONS:
                actions.add(part)
            else:
                known = ", ".join(ACTIONS + tuple(sorted(ACTION_ALIASES)))
                raise ValueError(f"Unknown IAM action {part!r}. Known actions: {known}")
        if not actions:
            raise ValueError(f"IAM rule names no action: {line!r}")

        return cls(effect, users, actions, Target(target.strip()), source=source,
                   excluded=excluded)

    def covers_user(self, user: str) -> bool:
        """True when the rule applies to this username."""
        if user in self.excluded:
            return False
        return EVERYONE in self.users or user in self.users

    def matches(self, user: str, action: str, rel_path: str, name: str) -> bool:
        """True when the rule applies to this user, action and path."""
        return (
            action in self.actions
            and self.covers_user(user)
            and self.target.matches(rel_path, name)
        )

class IAMPolicy:

    """Per user access control over paths, names, globs and folders.

    Rules are evaluated the way they are in most access control systems rather
    than the way the ignore file works: an explicit deny always wins, whatever
    order the rules are written in. A request is allowed when no deny matches
    and at least one allow does, or when nothing matches at all and the default
    is 'allow'.

    A policy with no rules allows everything, so the server behaves exactly as
    it did before any policy was written.

    Attributes:
        rules: The parsed IAMRule objects, in the order they were read
        default: What happens when no rule matches, 'allow' or 'deny'
    """

    def __init__(self, rules: Optional[Iterable[IAMRule]] = None, default: str = ALLOW):
        self.rules: List[IAMRule] = list(rules or [])
        default = (default or ALLOW).strip().lower()
        if default not in EFFECTS:
            raise ValueError(f"IAM default has to be allow or deny, got {default!r}")
        self.default = default

    def __len__(self) -> int:
        return len(self.rules)

    def __bool__(self) -> bool:
        return bool(self.rules)

    def __repr__(self) -> str:
        return f"IAMPolicy({len(self.rules)} rules, default={self.default})"

    @property
    def enabled(self) -> bool:
        """True when any rule was configured."""
        return bool(self.rules)

    @classmethod
    def from_lines(cls, lines: Iterable[str], default: str = ALLOW,
                   source: str = "") -> "IAMPolicy":
        """Builds a policy from rule lines, honouring a 'default' directive."""
        rules: List[IAMRule] = []
        for number, raw in enumerate(lines, start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            where = f"{source}:{number}" if source else f"line {number}"
            head = line.split(None, 1)
            if head[0].lower() == DEFAULT_DIRECTIVE:
                if len(head) < 2:
                    raise ValueError(f"{where}: 'default' needs allow or deny")
                value = head[1].strip().lstrip("=").strip().lower()
                if value not in EFFECTS:
                    raise ValueError(f"{where}: 'default' has to be allow or deny, got {value!r}")
                default = value
                continue
            try:
                rules.append(IAMRule.parse(line, source=where))
            except ValueError as problem:
                raise ValueError(f"{where}: {problem}") from None
        return cls(rules, default=default)

    def allows(self, user: Optional[str], action: str, rel_path: str = "") -> bool:
        """True when user may perform action on rel_path."""
        if not self.rules:
            return True
        name = user or ANONYMOUS
        path = (rel_path or "").strip("/")
        basename = path.rsplit("/", 1)[-1]
        allowed = self.default == ALLOW
        for rule in self.rules:
            if not rule.matches(name, action, path, basename):
                continue
            if rule.effect == DENY:
                return False
            allowed = True
        return allowed

    def denies(self, user: Optional[str], action: str, rel_path: str = "") -> bool:
        """The opposite of allows(), for readability at call sites."""
        return not self.allows(user, action, rel_path)

    def permissions(self, user: Optional[str], rel_path: str = "") -> Dict[str, bool]:
        """Every action, and whether user may perform it on rel_path."""
        return {action: self.allows(user, action, rel_path) for action in ACTIONS}

    def folder_permissions(self, user: Optional[str], rel_dir: str = "") -> Dict[str, bool]:
        """Permissions for a folder, with upload asked about the files inside it.

        Uploading is the one action that is really about creating a child, so a
        rule written as 'reports/**' has to count even though that pattern
        covers the contents of the folder rather than the folder itself.
        """
        perms = self.permissions(user, rel_dir)
        if not perms[UPLOAD]:
            probe = f"{rel_dir}/{UPLOAD_PROBE}" if rel_dir else UPLOAD_PROBE
            perms[UPLOAD] = self.allows(user, UPLOAD, probe)
        return perms

    def visible(self, user: Optional[str]):
        """A callable the filesystem layer can use to skip entries a user cannot list."""
        if not self.rules:
            return None

        def allowed(rel_path: str, is_dir: bool) -> bool:
            return self.allows(user, LIST, rel_path)

        return allowed

    def filter_entries(self, user: Optional[str], rel_dir: str,
                       entries: Sequence[Dict]) -> List[Dict]:
        """Drops the entries of a listing that user is not allowed to see."""
        if not self.rules:
            return list(entries)
        kept = []
        for entry in entries:
            child = f"{rel_dir}/{entry['name']}" if rel_dir else entry["name"]
            if self.allows(user, LIST, child):
                kept.append(entry)
        return kept

    def annotate(self, user: Optional[str], rel_dir: str,
                 entries: Sequence[Dict]) -> List[Dict]:
        """Adds a per entry permission map so the UI can hide what is not allowed."""
        if not self.rules:
            return list(entries)
        annotated = []
        for entry in entries:
            child = f"{rel_dir}/{entry['name']}" if rel_dir else entry["name"]
            item = dict(entry)
            item["perms"] = {
                action: self.allows(user, action, child)
                for action in (DOWNLOAD, RENAME, MOVE, DELETE, LIST)
            }
            annotated.append(item)
        return annotated

    def describe(self, user: Optional[str]) -> List[str]:
        """The rules that could apply to one user, as readable lines."""
        name = user or ANONYMOUS
        return [str(rule) for rule in self.rules if rule.covers_user(name)]
