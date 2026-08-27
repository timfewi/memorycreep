"""Crew workers must inherit the primary runtime policy and scope."""

from types import SimpleNamespace

import pytest

from pentestagent.agents.crew.worker_pool import WorkerPool


class SharedRuntime:
    def __init__(self):
        self.plan = None
        self.started = 0
        self.stopped = 0

    async def start(self):
        self.started += 1

    async def stop(self):
        self.stopped += 1


@pytest.mark.asyncio
async def test_worker_uses_exact_shared_runtime_and_scope(monkeypatch):
    captured = []

    class FakeAgent:
        def __init__(self, **kwargs):
            captured.append(kwargs)

        async def agent_loop(self, task):
            yield SimpleNamespace(
                content="done",
                tool_calls=[],
                usage={},
                metadata={},
            )

    import pentestagent.agents.pa_agent as pa_agent

    monkeypatch.setattr(pa_agent, "PentestAgentAgent", FakeAgent)
    runtime = SharedRuntime()
    scope = ["192.0.2.0/24", "target.example"]
    pool = WorkerPool(
        llm=object(),
        tools=[],
        runtime=runtime,
        target="192.0.2.10",
        scope=scope,
    )

    worker_id = await pool.spawn("passive inventory")
    result = await pool.wait_for([worker_id])

    assert result[worker_id]["status"] == "complete"
    assert captured[0]["runtime"] is runtime
    assert captured[0]["scope"] == scope
    assert runtime.started == 0
    assert runtime.stopped == 0
