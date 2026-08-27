"""Central runtime factory tests."""

from pathlib import Path

import pytest

from pentestagent.runtime.factory import RuntimeFactory
from pentestagent.runtime.policy import (
    NetworkProfile,
    PolicyRuntime,
    RuntimeProfile,
)
from pentestagent.runtime.runtime import LocalRuntime


def test_vm_profile_requires_declarative_attestation(monkeypatch, tmp_path):
    monkeypatch.delenv("PENTESTAGENT_VM_ATTESTED", raising=False)

    with pytest.raises(RuntimeError, match="ATTESTED"):
        RuntimeFactory.create(
            profile=RuntimeProfile.PENTEST_VM,
            scope=["192.0.2.0/24"],
            project_root=tmp_path,
        )


def test_factory_binds_scope_network_and_project(monkeypatch, tmp_path):
    monkeypatch.setenv("PENTESTAGENT_VM_ATTESTED", "1")

    runtime = RuntimeFactory.create(
        profile=RuntimeProfile.PENTEST_VM,
        scope=["192.0.2.0/24", "target.example", "192.0.2.0/24"],
        network_profile=NetworkProfile.VPN,
        project_root=tmp_path,
        backend=LocalRuntime(),
    )

    assert isinstance(runtime, PolicyRuntime)
    assert runtime.policy.scope == ("192.0.2.0/24", "target.example")
    assert runtime.policy.network_profile is NetworkProfile.VPN
    assert runtime.policy.project_root == tmp_path
    assert runtime.policy.output_root == tmp_path


def test_host_factory_is_offline_and_shell_disabled(tmp_path):
    runtime = RuntimeFactory.create(
        profile=RuntimeProfile.HOST,
        scope=[],
        project_root=tmp_path,
        backend=LocalRuntime(),
    )

    assert runtime.policy.runtime_profile is RuntimeProfile.HOST
    assert runtime.policy.network_profile is NetworkProfile.OFFLINE
    assert runtime.policy.shell_allowed is False


def test_audit_path_cannot_be_below_runtime_secrets(tmp_path):
    with pytest.raises(RuntimeError, match="secrets"):
        RuntimeFactory.create(
            profile=RuntimeProfile.HOST,
            audit_path=Path("/run/secrets/agent-audit"),
            backend=LocalRuntime(),
        )
