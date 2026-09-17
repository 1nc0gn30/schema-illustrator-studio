"""Unit tests for cross-platform compatibility module."""

import os
from pathlib import Path
import pytest

from schema_illustrator_studio.compat import (
    atomic_write,
    ensure_directory,
    is_linux,
    is_macos,
    is_termux,
    is_windows,
    safe_normalize_path,
    safe_read_text,
    safe_write_text,
)


def test_platform_checkers():
    """Verify platform detection functions return boolean."""
    assert isinstance(is_windows(), bool)
    assert isinstance(is_macos(), bool)
    assert isinstance(is_linux(), bool)
    assert isinstance(is_termux(), bool)


def test_safe_normalize_path(tmp_path):
    """Verify path normalization handles relative, env vars, and Path objects."""
    p = safe_normalize_path(str(tmp_path))
    assert isinstance(p, Path)
    assert p.is_absolute()

    # Relative path normalization
    rel = safe_normalize_path(".")
    assert rel.is_absolute()


def test_ensure_directory(tmp_path):
    """Verify ensure_directory creates parent or directory as needed."""
    sub_dir = tmp_path / "a" / "b" / "c"
    res = ensure_directory(sub_dir)
    assert res.exists()
    assert res.is_dir()

    file_path = tmp_path / "x" / "y" / "schema.sql"
    parent_res = ensure_directory(file_path)
    assert parent_res.exists()
    assert parent_res.is_dir()


def test_atomic_and_safe_write_read_text(tmp_path):
    """Verify atomic write, safe write text, and safe read text with various encodings."""
    test_file = tmp_path / "test_schema.sql"
    content = "CREATE TABLE users (id UUID PRIMARY KEY, name VARCHAR(100));"

    # Atomic write
    atomic_write(test_file, content)
    assert test_file.exists()
    assert test_file.read_text(encoding="utf-8") == content

    # Safe read
    read_back = safe_read_text(test_file)
    assert read_back == content

    # Safe write overwrite
    new_content = "CREATE TABLE orders (id UUID PRIMARY KEY);"
    safe_write_text(test_file, new_content, atomic=True)
    assert safe_read_text(test_file) == new_content

    # Safe write non-atomic
    safe_write_text(test_file, content, atomic=False)
    assert safe_read_text(test_file) == content


def test_safe_read_nonexistent_file(tmp_path):
    """Verify FileNotFoundError on missing file."""
    with pytest.raises(FileNotFoundError):
        safe_read_text(tmp_path / "missing_file_xyz.sql")
