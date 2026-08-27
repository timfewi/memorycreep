"""Host launcher scope pinning and nftables rendering tests."""

import socket

import pytest
import typer

from pentestagent.host_cli import (
    HostCommandError,
    _copy_sparse_file,
    _resolve_scope,
    _sha256_file,
    render_nftables,
)


def test_sparse_result_images_remain_byte_identical(tmp_path):
    source = tmp_path / "results.img"
    target = tmp_path / "exported.img"
    with source.open("wb") as handle:
        handle.write(b"PTA")
        handle.seek(8 * 1024 * 1024)
        handle.write(b"Z")

    _copy_sparse_file(source, target)

    assert target.stat().st_size == source.stat().st_size
    assert target.read_bytes() == source.read_bytes()


def test_hashing_rejects_symlinks_and_oversized_files(tmp_path):
    source = tmp_path / "sample.bin"
    source.write_bytes(b"1234")
    link = tmp_path / "sample-link.bin"
    link.symlink_to(source)

    with pytest.raises(HostCommandError, match="opened safely"):
        _sha256_file(link, max_bytes=4)
    with pytest.raises(HostCommandError, match="size limit"):
        _sha256_file(source, max_bytes=3)


def test_rejects_global_ipv4_and_ipv6_scopes():
    with pytest.raises(typer.BadParameter):
        _resolve_scope(["0.0.0.0/0"])
    with pytest.raises(typer.BadParameter):
        _resolve_scope(["::/0"])


def test_dns_answers_are_pinned_once(monkeypatch):
    calls = 0

    def answers(*args, **kwargs):
        nonlocal calls
        calls += 1
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.0.2.10", 0)),
            (
                socket.AF_INET6,
                socket.SOCK_STREAM,
                6,
                "",
                ("2001:db8::10", 0, 0, 0),
            ),
        ]

    monkeypatch.setattr(socket, "getaddrinfo", answers)
    scope = _resolve_scope(["Target.Example."])

    assert calls == 1
    assert scope.dns_pins == {
        "target.example": ("192.0.2.10", "2001:db8::10")
    }
    assert scope.firewall_ipv4 == ("192.0.2.10",)
    assert scope.firewall_ipv6 == ("2001:db8::10",)


def test_offline_profile_has_no_target_forwarding():
    scope = _resolve_scope(["192.0.2.0/24"])

    rules = render_nftables(scope, "offline")

    assert "192.0.2.0/24" not in rules
    assert "169.254.77.1 tcp dport 17443" in rules
    assert 'iifname "pta-pentest" drop' in rules


def test_online_rules_are_bound_to_uplink_source_scope_and_mark():
    scope = _resolve_scope(["192.0.2.0/24", "2001:db8::/48"])

    rules = render_nftables(scope, "vpn", "wg0")

    assert 'iifname "pta-pentest" oifname "wg0"' in rules
    assert "ip saddr 169.254.77.2" in rules
    assert "ip6 saddr fd42:7074:6100::2" in rules
    assert "ip daddr { 192.0.2.0/24 }" in rules
    assert "ip6 daddr { 2001:db8::/48 }" in rules
    assert "meta mark set 0x505441 accept" in rules
    assert "table inet pta_session_nat" in rules
    assert "masquerade" in rules


def test_online_profile_requires_declarative_uplink():
    scope = _resolve_scope(["192.0.2.0/24"])

    with pytest.raises(HostCommandError):
        render_nftables(scope, "lan")
