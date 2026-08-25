import os
from typing import Any, Dict, List, Optional, Tuple

TRUTHY = ("1", "true", "yes", "on", "y", "enabled")
FALSY = ("0", "false", "no", "off", "n", "disabled")

def parse_bool(value: Any, default: bool = False) -> bool:
    """Turns anything a config file or an environment variable can hold into a bool."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in TRUTHY:
        return True
    if text in FALSY:
        return False
    return default

def parse_int(value: Any, default: int = 0) -> int:
    """Same idea as parse_bool, for integers."""
    if value is None:
        return default
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default

def get_env(key: str, curr: Any = None, default: Any = None, err_msg: str = None) -> Any:
    """Returns curr when it is set, otherwise the environment value, otherwise default."""
    if curr is not None:
        return curr
    value = os.getenv(key, default)
    if value is None and err_msg:
        raise Exception(err_msg)
    return value

BLOCK_END = "end"

def strip_quotes(value: str) -> str:
    """Removes one layer of matching quotes from a config value."""
    if len(value) > 1 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value

def read_config_file(path: str) -> Tuple[Dict[str, str], Dict[str, List[str]]]:
    """Reads a config file into its KEY=VALUE settings and its named blocks.

    A line of the form '[name]' opens a block and every line after it is kept
    verbatim for that block, comments and all, until '[end]' or the next block
    header. Everything outside a block is read as KEY=VALUE.
    """
    values: Dict[str, str] = {}
    blocks: Dict[str, List[str]] = {}
    current: Optional[str] = None
    if not path or not os.path.isfile(path):
        return values, blocks
    with open(path, "r", encoding="utf-8", errors="ignore") as handle:
        for raw in handle:
            line = raw.strip()
            if line.startswith("[") and line.endswith("]"):
                name = line[1:-1].strip().lower()
                current = None if name == BLOCK_END else name
                if current is not None:
                    blocks.setdefault(current, [])
                continue
            if current is not None:
                blocks[current].append(raw.rstrip("\n"))
                continue
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[key.strip().upper()] = strip_quotes(value.strip())
    return values, blocks

def read_kv_file(path: str) -> Dict[str, str]:
    """Reads only the KEY=VALUE settings of a config file."""
    return read_config_file(path)[0]

def human_size(size: Optional[int]) -> str:
    """Formats a byte count the same way the frontend does."""
    if size is None:
        return "-"
    units = ("B", "KB", "MB", "GB", "TB", "PB")
    value = float(size)
    index = 0
    while value >= 1000 and index < len(units) - 1:
        value /= 1024
        index += 1
    if index == 0:
        return f"{int(value)} {units[0]}"
    return f"{value:.1f} {units[index]}"
