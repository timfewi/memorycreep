"""Mandatory policy-bound runtime security tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pentestagent.runtime.policy import (
    AuditLog,
    NetworkProfile,
    PolicyRuntime,
    PolicyViolation,
    RiskClass,
    RuntimeProfile,
    SessionPolicy,
)
from pentestagent.runtime.runtime import CommandResult, EnvironmentInfo, Runtime
from pentestagent.tools.registry import Tool, ToolSchema


class RecordingRuntime(Runtime):
    def __init__(self) -> None:
        super().__init__()
        self.commands: list[str] = []
        self.browser_actions: list[str] = []
        self.starts = 0
        self.stops = 0

    @property
    def environment(self) -> EnvironmentInfo:
        return EnvironmentInfo("Linux", "test", "sh", "x86_64", [])

    async def start(self) -> None:
        self.starts += 1

    async def stop(self) -> None:
        self.stops += 1

    async def execute_command(
        self, command: str, timeout: int = 300
    ) -> CommandResult:
        self.commands.append(command)
        return CommandResult(0, "ok", "")

    async def browser_action(self, action: str, **kwargs) -> dict:
        self.browser_actions.append(action)
        return {"action": action}

    async def proxy_action(self, action: str, **kwargs) -> dict:
        return {"action": action}

    async def is_running(self) -> bool:
        return True

    async def get_status(self) -> dict:
        return {"type": "recording", "running": True}


async def _terminal_execute(arguments: dict, runtime: Runtime) -> str:
    await runtime.execute_command(arguments["command"])
    return "completed"


def _terminal_tool() -> Tool:
    return Tool(
        name="terminal",
        description="test terminal",
        schema=ToolSchema(),
        execute_fn=_terminal_execute,
        metadata={
            "policy": {
                "risk_class": "recon",
                "network_purpose": "test",
                "network_access": False,
                "target_fields": ["network_target"],
                "input_path_fields": ["input_paths", "working_dir"],
                "output_path_fields": ["output_paths"],
                "requires_declaration": True,
            }
        },
    )


async def _browser_execute(arguments: dict, runtime: Runtime) -> str:
    await runtime.browser_action(arguments["action"])
    return "completed"


def _browser_tool() -> Tool:
    return Tool(
        name="browser",
        description="test browser",
        schema=ToolSchema(),
        execute_fn=_browser_execute,
        metadata={
            "policy": {
                "risk_class": "active",
                "network_purpose": "test browser",
                "network_access": True,
                "target_fields": ["network_target", "url"],
            }
        },
    )


def _arguments(command: str, targets: list[str] | None = None) -> dict:
    return {
        "command": command,
        "risk_class": "recon",
        "network_purpose": "authorized security test" if targets else "none",
        "network_target": targets or [],
        "input_paths": [],
        "output_paths": [],
    }


def _runtime(
    tmp_path: Path,
    *,
    profile: RuntimeProfile = RuntimeProfile.PENTEST_VM,
    scope: tuple[str, ...] = ("10.20.0.0/24", "target.example"),
) -> tuple[PolicyRuntime, RecordingRuntime]:
    backend = RecordingRuntime()
    policy = SessionPolicy(
        scope=scope,
        runtime_profile=profile,
        network_profile=NetworkProfile.LAN,
        project_root=tmp_path,
        output_root=tmp_path,
        audit_log=AuditLog(tmp_path / "audit.jsonl"),
    )
    return PolicyRuntime(backend, policy), backend


def test_audit_chain_is_verified_and_resumed(tmp_path):
    path = tmp_path / "audit.jsonl"
    first = AuditLog(path)
    first_event = first.append({"event": "first"})

    resumed = AuditLog(path)
    second_event = resumed.append({"event": "second"})

    assert second_event["previous_hash"] == first_event["event_hash"]


def test_tampered_audit_chain_fails_closed(tmp_path):
    path = tmp_path / "audit.jsonl"
    audit = AuditLog(path)
    audit.append({"event": "original"})
    path.write_text(
        path.read_text(encoding="utf-8").replace("original", "tampered"),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="audit"):
        AuditLog(path)


def test_audit_log_rejects_symlink_path(tmp_path):
    path = tmp_path / "audit.jsonl"
    AuditLog(path).append({"event": "original"})
    link = tmp_path / "linked-audit.jsonl"
    link.symlink_to(path)

    with pytest.raises(RuntimeError, match="audit"):
        AuditLog(link)


@pytest.mark.asyncio
async def test_raw_ip_in_command_cannot_hide_behind_declared_scope(tmp_path):
    runtime, backend = _runtime(tmp_path)

    with pytest.raises(PolicyViolation) as denied:
        await _terminal_tool().execute(
            _arguments("nmap 203.0.113.8", ["10.20.0.5"]), runtime
        )

    assert denied.value.decision.code == "out-of-scope"
    assert backend.commands == []


@pytest.mark.asyncio
async def test_bracketed_ipv6_in_command_cannot_hide_behind_scope(tmp_path):
    runtime, backend = _runtime(tmp_path)

    with pytest.raises(PolicyViolation) as denied:
        await _terminal_tool().execute(
            _arguments("nc [2001:db8:ffff::1] 443", ["10.20.0.5"]),
            runtime,
        )

    assert denied.value.decision.code == "out-of-scope"
    assert backend.commands == []


@pytest.mark.asyncio
async def test_url_hostname_in_command_cannot_hide_behind_declaration(tmp_path):
    runtime, backend = _runtime(tmp_path)

    with pytest.raises(PolicyViolation) as denied:
        await _terminal_tool().execute(
            _arguments("curl https://outside.example/path", ["target.example"]),
            runtime,
        )

    assert denied.value.decision.code == "out-of-scope"
    assert backend.commands == []


@pytest.mark.asyncio
async def test_ssh_style_hostname_cannot_hide_behind_declaration(tmp_path):
    runtime, backend = _runtime(tmp_path)

    with pytest.raises(PolicyViolation) as denied:
        await _terminal_tool().execute(
            _arguments("ssh user@outside.example", ["target.example"]),
            runtime,
        )

    assert denied.value.decision.code == "out-of-scope"
    assert backend.commands == []


@pytest.mark.asyncio
async def test_local_dotted_filename_is_not_treated_as_network_target(tmp_path):
    runtime, backend = _runtime(tmp_path)

    assert (
        await _terminal_tool().execute(_arguments("cat report.txt"), runtime)
        == "completed"
    )
    assert backend.commands == ["cat report.txt"]


@pytest.mark.parametrize(
    ("command", "expected_risk"),
    [
        ("nmap --script smb-brute target.example", RiskClass.CREDENTIAL),
        ("nmap --script vuln target.example", RiskClass.EXPLOIT),
        ("crontab -e", RiskClass.PERSISTENCE),
        ("hping3 --flood 10.20.0.5", RiskClass.DOS),
    ],
)
@pytest.mark.asyncio
async def test_high_risk_strings_cannot_claim_recon(
    tmp_path, command, expected_risk
):
    targets = ["10.20.0.5"] if "10.20.0.5" in command else ["target.example"]
    runtime, backend = _runtime(tmp_path)

    with pytest.raises(PolicyViolation) as denied:
        await _terminal_tool().execute(_arguments(command, targets), runtime)

    assert denied.value.decision.code == "approval-required"
    assert denied.value.decision.risk_class is expected_risk
    assert backend.commands == []


@pytest.mark.asyncio
async def test_opaque_shell_is_escalated_before_runtime(tmp_path):
    runtime, backend = _runtime(tmp_path)

    with pytest.raises(PolicyViolation) as denied:
        await _terminal_tool().execute(
            _arguments("sh -c 'echo harmless-looking'"), runtime
        )

    assert denied.value.decision.code == "approval-required"
    assert denied.value.decision.risk_class is RiskClass.EXPLOIT
    assert backend.commands == []


@pytest.mark.asyncio
async def test_denied_approval_never_reaches_backend(tmp_path):
    runtime, backend = _runtime(tmp_path)
    arguments = _arguments("sh -c 'id'")

    with pytest.raises(PolicyViolation) as first:
        await _terminal_tool().execute(arguments, runtime)
    assert runtime.approvals.deny(first.value.decision.request_id or "")

    with pytest.raises(PolicyViolation):
        await _terminal_tool().execute(arguments, runtime)
    assert backend.commands == []


@pytest.mark.asyncio
async def test_one_time_approval_allows_only_matching_action(tmp_path):
    runtime, backend = _runtime(tmp_path)
    arguments = _arguments("sh -c 'id'")

    with pytest.raises(PolicyViolation) as first:
        await _terminal_tool().execute(arguments, runtime)
    assert runtime.approvals.approve(first.value.decision.request_id or "")

    assert await _terminal_tool().execute(arguments, runtime) == "completed"
    assert backend.commands == ["sh -c 'id'"]

    with pytest.raises(PolicyViolation) as third:
        await _terminal_tool().execute(arguments, runtime)
    assert third.value.decision.code == "approval-required"


@pytest.mark.asyncio
async def test_browser_javascript_requires_exploit_approval(tmp_path):
    runtime, backend = _runtime(tmp_path)

    with pytest.raises(PolicyViolation) as denied:
        await _browser_tool().execute(
            {
                "action": "execute_js",
                "javascript": "document.title",
                "network_target": "target.example",
            },
            runtime,
        )

    assert denied.value.decision.code == "approval-required"
    assert denied.value.decision.risk_class is RiskClass.EXPLOIT
    assert backend.commands == []
    assert backend.browser_actions == []


@pytest.mark.asyncio
async def test_host_profile_has_no_free_shell_path(tmp_path):
    runtime, backend = _runtime(tmp_path, profile=RuntimeProfile.HOST)

    with pytest.raises(PolicyViolation) as denied:
        await _terminal_tool().execute(_arguments("echo test"), runtime)

    assert denied.value.decision.code == "host-shell-disabled"
    assert backend.commands == []


@pytest.mark.asyncio
async def test_direct_runtime_call_is_rejected(tmp_path):
    runtime, backend = _runtime(tmp_path)

    with pytest.raises(PolicyViolation) as denied:
        await runtime.execute_command("echo bypass")

    assert denied.value.decision.code == "direct-runtime-call"
    assert backend.commands == []


@pytest.mark.asyncio
async def test_declared_paths_cannot_escape_project(tmp_path):
    runtime, backend = _runtime(tmp_path)
    arguments = _arguments("cat /etc/shadow")
    arguments["input_paths"] = ["/etc/shadow"]

    with pytest.raises(PolicyViolation) as denied:
        await _terminal_tool().execute(arguments, runtime)

    assert denied.value.decision.code == "path-denied"
    assert backend.commands == []


@pytest.mark.asyncio
async def test_audit_contains_no_command_prompt_or_secret(tmp_path):
    runtime, backend = _runtime(tmp_path)
    secret = "sk-test-never-log"
    prompt = "full private operator prompt"
    arguments = _arguments(f"echo {secret}")
    arguments["operator_prompt"] = prompt

    await _terminal_tool().execute(arguments, runtime)

    serialized = json.dumps(runtime.audit_log.events())
    on_disk = (tmp_path / "audit.jsonl").read_text(encoding="utf-8")
    assert secret not in serialized + on_disk
    assert prompt not in serialized + on_disk
    assert "echo" not in serialized + on_disk
    assert backend.commands == [f"echo {secret}"]
