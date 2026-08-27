"""Cloud broker confidentiality and configuration tests."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from aiohttp import web

from pentestagent.broker import (
    BrokerConfigurationError,
    CloudKeyBroker,
    ProviderConfig,
    ProviderLimits,
)


def _broker(
    tmp_path: Path, limits: ProviderLimits | None = None
) -> CloudKeyBroker:
    provider = ProviderConfig(
        name="openai",
        base_url="https://api.openai.com",
        key_file=tmp_path / "provider-key",
        models=("gpt-5",),
        limits=limits or ProviderLimits(),
    )
    config = type(
        "Config",
        (),
        {
            "providers": {"openai": provider},
            "allowed_client_ips": ("169.254.77.2",),
            "session_token_file": tmp_path / "token",
            "usage_state_file": tmp_path / "usage.json",
        },
    )()
    return CloudKeyBroker(config)


def test_metadata_logger_drops_prompts_keys_and_unknown_fields(tmp_path, caplog):
    broker = _broker(tmp_path)
    secret = "sk-provider-secret"
    prompt = "the complete private prompt"

    with caplog.at_level(logging.INFO, logger="pentestagent.broker"):
        broker._metadata_log(
            "request",
            request_id="request-1",
            provider="openai",
            model="gpt-5",
            request_bytes=123,
            prompt=prompt,
            api_key=secret,
            arbitrary={"prompt": prompt},
        )

    assert "request-1" in caplog.text
    assert prompt not in caplog.text
    assert secret not in caplog.text
    assert "arbitrary" not in caplog.text


@pytest.mark.parametrize(
    "key_file",
    [
        "/run/secrets/../etc/shadow",
        "/tmp/provider-key",
        "run/secrets/provider-key",
    ],
)
def test_provider_key_path_cannot_escape_runtime_secrets(key_file):
    with pytest.raises(BrokerConfigurationError):
        ProviderConfig.from_mapping(
            "openai",
            {
                "base_url": "https://api.openai.com",
                "key_file": key_file,
                "models": ["gpt-5"],
            },
        )


def test_provider_error_configuration_never_embeds_key_value(tmp_path):
    secret = "sk-error-secret"
    key_file = tmp_path / "missing-key"

    provider = ProviderConfig(
        name="openai",
        base_url="https://api.openai.com",
        key_file=key_file,
        models=("gpt-5",),
        limits=ProviderLimits(),
    )
    with pytest.raises(Exception) as error:
        CloudKeyBroker._provider_headers(provider)

    assert secret not in str(error.value)
    assert str(key_file) not in str(error.value)


@pytest.mark.parametrize(
    "base_url",
    [
        "https://user:password@api.openai.com",
        "https://api.openai.com/unexpected/path",
        "https://api.openai.com?redirect=elsewhere",
    ],
)
def test_provider_origin_cannot_embed_credentials_or_paths(base_url):
    with pytest.raises(BrokerConfigurationError):
        ProviderConfig.from_mapping(
            "openai",
            {
                "base_url": base_url,
                "key_file": "/run/secrets/openai-api-key",
                "models": ["gpt-5"],
            },
        )


def test_negative_provider_cost_cannot_disable_budget_enforcement():
    with pytest.raises(BrokerConfigurationError):
        ProviderConfig.from_mapping(
            "openai",
            {
                "base_url": "https://api.openai.com",
                "key_file": "/run/secrets/openai-api-key",
                "models": ["gpt-5"],
                "limits": {"input_cost_per_million": -1},
            },
        )


def test_chat_requests_receive_a_provider_enforced_default_limit():
    payload = {"model": "gpt-5", "messages": []}

    requested = CloudKeyBroker._enforce_output_limit(
        payload, "chat/completions", 1024
    )

    assert requested == 1024
    assert payload["max_completion_tokens"] == 1024


@pytest.mark.parametrize(
    "endpoint,payload",
    [
        ("chat/completions", {"max_output_tokens": 1}),
        ("responses", {"max_tokens": 1}),
        (
            "chat/completions",
            {"max_tokens": 1, "max_completion_tokens": 2},
        ),
    ],
)
def test_mismatched_or_ambiguous_output_limits_are_rejected(endpoint, payload):
    with pytest.raises(web.HTTPBadRequest):
        CloudKeyBroker._enforce_output_limit(payload, endpoint, 1024)


@pytest.mark.asyncio
async def test_nonpositive_output_budget_is_rejected(tmp_path):
    broker = _broker(tmp_path)
    provider = broker.config.providers["openai"]

    with pytest.raises(web.HTTPBadRequest):
        await broker._reserve(provider, 100, 10, -1)


@pytest.mark.asyncio
async def test_daily_cost_budget_survives_broker_restart(tmp_path):
    limits = ProviderLimits(daily_cost_usd=1.5, cost_per_request_usd=1.0)
    broker = _broker(tmp_path, limits)
    provider = broker.config.providers["openai"]
    await broker._reserve(provider, 100, 10, 10)

    resumed = _broker(tmp_path, limits)
    resumed_provider = resumed.config.providers["openai"]
    with pytest.raises(web.HTTPPaymentRequired):
        await resumed._reserve(resumed_provider, 100, 10, 10)

    state = (tmp_path / "usage.json").read_text(encoding="utf-8")
    assert "prompt" not in state
    assert "key" not in state


@pytest.mark.asyncio
async def test_upstream_response_is_bounded_before_buffering(tmp_path):
    limits = ProviderLimits(max_response_bytes=3)
    provider = _broker(tmp_path, limits).config.providers["openai"]

    class FakeResponse:
        status_code = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def aiter_bytes(self):
            yield b"ab"
            yield b"cd"

    class FakeClient:
        def stream(self, *args, **kwargs):
            return FakeResponse()

    with pytest.raises(web.HTTPBadGateway, match="configured limit"):
        await CloudKeyBroker._post_bounded(
            FakeClient(), provider, "https://api.openai.com/v1/responses"
        )
