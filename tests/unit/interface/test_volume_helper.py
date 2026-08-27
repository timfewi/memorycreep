"""Project-vault preparation and versioning tests."""

from pathlib import Path

import pytest

from pentestagent import volume_helper


def _configure_helper(monkeypatch, tmp_path):
    projects = tmp_path / "projects"
    snapshots = tmp_path / "snapshots"
    runtime = tmp_path / "run"
    subvolumes = set()
    commands = []

    monkeypatch.setattr(volume_helper, "_PROJECTS", projects)
    monkeypatch.setattr(volume_helper, "_SNAPSHOTS", snapshots)
    monkeypatch.setattr(volume_helper, "_RUNTIME", runtime)
    monkeypatch.setattr(volume_helper.os, "geteuid", lambda: 0)

    def sparse(path: Path, _size: int, _label: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"ext4")

    def run(argv: list[str]) -> None:
        commands.append(argv)
        operation = argv[1:3]
        if operation == ["subvolume", "create"]:
            path = Path(argv[-1])
            path.mkdir()
            subvolumes.add(path)
        elif operation == ["subvolume", "show"]:
            if Path(argv[-1]) not in subvolumes:
                raise RuntimeError("not a Btrfs subvolume")
        elif operation == ["subvolume", "snapshot"]:
            source = Path(argv[-2])
            destination = Path(argv[-1])
            if source not in subvolumes:
                raise RuntimeError("not a Btrfs subvolume")
            destination.mkdir()
            subvolumes.add(destination)
        elif operation == ["subvolume", "delete"]:
            path = Path(argv[-1])
            path.rmdir()
            subvolumes.discard(path)

    monkeypatch.setattr(volume_helper, "_sparse_ext4", sparse)
    monkeypatch.setattr(volume_helper, "_run", run)
    return projects, snapshots, runtime, subvolumes, commands


def test_ensure_creates_and_then_snapshots_project_vault(monkeypatch, tmp_path):
    projects, snapshots, runtime, _subvolumes, _commands = _configure_helper(
        monkeypatch, tmp_path
    )

    volume_helper.ensure("customer-a")

    image = projects / "customer-a" / "project.ext4"
    assert image.read_bytes() == b"ext4"
    assert not runtime.exists()

    volume_helper.ensure("customer-a")

    assert len(list(snapshots.iterdir())) == 1


def test_ensure_rejects_an_ordinary_project_directory(monkeypatch, tmp_path):
    projects, _snapshots, _runtime, _subvolumes, _commands = _configure_helper(
        monkeypatch, tmp_path
    )
    project = projects / "customer-a"
    project.mkdir(parents=True)
    (project / "project.ext4").write_bytes(b"ext4")

    with pytest.raises(RuntimeError, match="Btrfs"):
        volume_helper.ensure("customer-a")


def test_prepare_adds_only_ephemeral_runtime_state(monkeypatch, tmp_path):
    projects, _snapshots, runtime, _subvolumes, _commands = _configure_helper(
        monkeypatch, tmp_path
    )

    volume_helper.prepare("customer-a")

    assert (runtime / "overlays" / "pentest-store.ext4").is_file()
    assert (runtime / "project.img").resolve() == (
        projects / "customer-a" / "project.ext4"
    ).resolve()
