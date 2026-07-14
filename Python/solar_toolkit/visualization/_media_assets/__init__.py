"""Internal access to bundled browser-media assets."""

from __future__ import annotations

from importlib.resources import files as _resource_files

ASSET_MIME_TYPES = {
    "browser_media.js": "application/javascript",
    "mediabunny-1.50.8.cjs": "application/javascript",
    "mediabunny-MPL-2.0.txt": "text/plain; charset=utf-8",
    "NOTICE.txt": "text/plain; charset=utf-8",
}


def read_asset_bytes(name: str) -> bytes:
    """Read one allow-listed bundled media asset."""

    if name not in ASSET_MIME_TYPES:
        raise FileNotFoundError(f"Unknown media asset: {name}")
    return _resource_files(__package__).joinpath(name).read_bytes()


def read_asset_text(name: str) -> str:
    """Read one allow-listed text media asset as UTF-8."""

    return read_asset_bytes(name).decode("utf-8")


def asset_mimetype(name: str) -> str:
    """Return the HTTP content type for an allow-listed media asset."""

    if name not in ASSET_MIME_TYPES:
        raise FileNotFoundError(f"Unknown media asset: {name}")
    return ASSET_MIME_TYPES[name]


__all__ = [
    "ASSET_MIME_TYPES",
    "asset_mimetype",
    "read_asset_bytes",
    "read_asset_text",
]
