from __future__ import annotations

import os
import stat

import pytest

from pentestagent.guest_setup import _secure_directory


def test_secure_directory_rejects_project_symlink(tmp_path):
    target = tmp_path / "target"
    target.mkdir(mode=0o755)
    link = tmp_path / "audit"
    link.symlink_to(target, target_is_directory=True)

    with pytest.raises(RuntimeError, match="untrusted project directory"):
        _secure_directory(link, 0o700, os.getuid(), os.getgid())

    assert stat.S_IMODE(target.stat().st_mode) == 0o755


def test_secure_directory_creates_descriptor_validated_directory(tmp_path):
    directory = tmp_path / "wasm"

    _secure_directory(directory, 0o700, os.getuid(), os.getgid())

    info = directory.lstat()
    assert stat.S_ISDIR(info.st_mode)
    assert not directory.is_symlink()
    assert stat.S_IMODE(info.st_mode) == 0o700
