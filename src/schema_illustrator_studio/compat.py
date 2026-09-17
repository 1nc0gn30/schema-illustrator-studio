"""Cross-platform compatibility utilities for schema-illustrator-studio.

Provides platform-safe file operations, atomic writes, encoding fallbacks,
and path normalization across Linux, macOS, Windows, and Termux/Android.
Zero third-party runtime dependencies.
"""

from __future__ import annotations

import os
import platform
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Sequence


def is_windows() -> bool:
    """Check if the current runtime environment is Windows."""
    return sys.platform.startswith("win") or os.name == "nt"


def is_macos() -> bool:
    """Check if the current runtime environment is macOS."""
    return sys.platform == "darwin"


def is_linux() -> bool:
    """Check if the current runtime environment is Linux."""
    return sys.platform.startswith("linux")


def is_termux() -> bool:
    """Check if running inside Android Termux."""
    return "TERMUX_VERSION" in os.environ or bool(os.environ.get("PREFIX", "").startswith("/data/data/com.termux"))


def safe_normalize_path(path: str | Path) -> Path:
    """Safely normalize and resolve a filesystem path across platforms.

    Handles:
    - User home directory expansion (~)
    - Environment variable expansion ($VAR or %VAR%)
    - Relative and redundant path segments (., ..)
    - Termux prefix quirks
    - Windows drive letters and UNC paths
    """
    if isinstance(path, Path):
        path_str = str(path)
    else:
        path_str = str(path)

    # Expand environment variables
    expanded = os.path.expandvars(path_str)
    # Expand user home
    expanded = os.path.expanduser(expanded)

    p = Path(expanded)
    try:
        return p.resolve()
    except (OSError, RuntimeError):
        # Fallback to absolute if resolve fails (e.g. permissions or symlink loops)
        return p.absolute()


def ensure_directory(path: str | Path) -> Path:
    """Ensure that the directory for the given path exists, creating parents if necessary.

    If path has a file extension or represents a file, its parent directory is created.
    If path is intended as a directory, the directory itself is created.
    """
    target = safe_normalize_path(path)
    # If the path exists and is a directory, return it
    if target.exists() and target.is_dir():
        return target

    # Determine if target should be treated as a directory or file
    if target.suffix:
        # Has extension -> assume file, create parent
        target.parent.mkdir(parents=True, exist_ok=True)
        return target.parent
    else:
        target.mkdir(parents=True, exist_ok=True)
        return target


def safe_read_text(
    filepath: str | Path,
    encodings: Sequence[str] = ("utf-8", "utf-8-sig", "latin-1", "cp1252"),
) -> str:
    """Read a text file with multiple encoding fallbacks.

    Tries utf-8, utf-8 with BOM, latin-1, and cp1252 in order to prevent decoding crashes
    when reading schemas from diverse legacy or cross-platform sources.
    """
    resolved_path = safe_normalize_path(filepath)
    if not resolved_path.exists() or not resolved_path.is_file():
        raise FileNotFoundError(f"File not found: {resolved_path}")

    raw_bytes = resolved_path.read_bytes()

    last_error: Exception | None = None
    for enc in encodings:
        try:
            return raw_bytes.decode(enc)
        except (UnicodeDecodeError, LookupError) as e:
            last_error = e
            continue

    # Final fallback: decode with replacement characters
    return raw_bytes.decode("utf-8", errors="replace")


def atomic_write(
    filepath: str | Path,
    content: str | bytes,
    encoding: str = "utf-8",
) -> None:
    """Write content to a file atomically to avoid partial writes or race conditions.

    Writes to a temporary file in the destination directory and renames it over the target.
    Handles Windows file replacement locks safely.
    """
    target_path = safe_normalize_path(filepath)
    parent_dir = target_path.parent
    parent_dir.mkdir(parents=True, exist_ok=True)

    # Use the same directory for the temp file to ensure atomic rename across filesystem boundaries
    prefix = f".tmp_{target_path.name}_"
    tmp_file = tempfile.NamedTemporaryFile(
        mode="wb",
        dir=parent_dir,
        prefix=prefix,
        delete=False,
    )

    try:
        if isinstance(content, str):
            tmp_file.write(content.encode(encoding))
        else:
            tmp_file.write(content)
        tmp_file.flush()
        os.fsync(tmp_file.fileno())
        tmp_file.close()

        # On Windows, os.replace replaces existing files atomically if on same drive
        os.replace(tmp_file.name, str(target_path))
    except Exception:
        # Clean up temporary file on failure
        if os.path.exists(tmp_file.name):
            try:
                os.remove(tmp_file.name)
            except OSError:
                pass
        raise


def safe_write_text(
    filepath: str | Path,
    content: str,
    atomic: bool = True,
    encoding: str = "utf-8",
) -> None:
    """Write text content to file, optionally using atomic write."""
    if atomic:
        atomic_write(filepath, content, encoding=encoding)
    else:
        target_path = safe_normalize_path(filepath)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(content, encoding=encoding)
