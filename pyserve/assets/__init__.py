import os
from typing import Dict

try:
    from importlib.resources import files as resource_files
except ImportError:
    resource_files = None

try:
    from importlib.resources import read_binary as resource_read_binary
except ImportError:
    resource_read_binary = None

PACKAGE = __name__
ASSETS_DIR = os.path.dirname(os.path.abspath(__file__))

CONTENT_TYPES: Dict[str, str] = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
}

def asset_name(name: str) -> str:
    """Validates that name is a bare filename so it can never point elsewhere."""
    if not name or name in (".", "..") or "/" in name or "\\" in name or os.sep in name:
        raise ValueError(f"Asset outside of the assets directory: {name}")
    return name

def asset_path(name: str) -> str:
    """Filesystem path of a bundled asset, which does not exist inside a zipped install."""
    return os.path.join(ASSETS_DIR, asset_name(name))

def read_asset_bytes(name: str) -> bytes:
    """Reads a bundled asset as raw bytes, from a directory or from a zipped install."""
    name = asset_name(name)
    if resource_files is not None:
        return resource_files(PACKAGE).joinpath(name).read_bytes()
    if resource_read_binary is not None:
        return resource_read_binary(PACKAGE, name)
    with open(asset_path(name), "rb") as handle:
        return handle.read()

def read_asset(name: str) -> str:
    """Reads a bundled asset as text."""
    return read_asset_bytes(name).decode("utf-8")

def content_type_for(name: str) -> str:
    """Content type of a bundled asset based on its extension."""
    return CONTENT_TYPES.get(os.path.splitext(name)[1].lower(), "application/octet-stream")
