"""Offline provider failover tests. No live credentials or model calls."""
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
import httpx
import pytest
from app.config import Settings
from app.providers.actions import ActionProvider, FallbackExhaustedError
from app.research_schemas import ResearchRequest, ResearchCriteria
from app.orchestration.engine import ResearchEngine
from app.repositories.research import ResearchStore
from app.science import ScientificData

ACTION = {"action": "abstain", "summary": "Insufficient evidence; no finding asserted."}


def harness(monkeypatch, tmp_path, google_error=None, google_text=None, status=200, router_action=None, **overrides):
    settings = Settings(local_data_dir=tmp_path, google_api_key="test-google", openrouter_api_key="test-router", openrouter_model="test-fallback", worker_mode="external", **overrides)
    create = AsyncMock(side_effect=google_error, return_value=SimpleNamespace(id="remote-test", status="completed", output_text=google_text or json.dumps(ACTION), usage=None))
    remote = SimpleNamespace(aio=SimpleNamespace(interactions=SimpleNamespace(create=create, cancel=AsyncMock()), aclose=AsyncMock()))
    monkeypatch.setattr("google.genai.Client", lambda **kw: remote)
    calls = []
    def reply(request):
        calls.append(json.loads(request.content))
        return httpx.Response(status, json={"model": "router/actual", "choices": [{"message": {"content": json.dumps(router_action or ACTION)}}], "usage": {"cost": .002}})
    real_client = httpx.AsyncClient
    monkeypatch.setattr("app.providers.actions.httpx.AsyncClient", lambda **kw: real_client(transport=httpx.MockTransport(reply), **kw))
    return settings, remote, calls


def test_healthy_argon_never_calls_fallback(tmp_path, monkeypatch):
    settings, remote, calls = harness(monkeypatch, tmp_path)
    async def run():
        p = ActionProvider(settings, "google")
        try:
            action, usage = await p.generate_action("test")
            assert action.action == "abstain" and usage["provider"] == "google"
            assert "fallback" not in usage
        finally:
            await p.close()
    asyncio.run(run())
    assert calls == []
    remote.aio.aclose.assert_awaited_once()


@pytest.mark.parametrize("error", [TimeoutError("private timeout"), PermissionError("private credentials"), RuntimeError("private quota failure")])
def test_failures_switch_once_for_remaining_actions(tmp_path, monkeypatch, error):
    settings, remote, calls = harness(monkeypatch, tmp_path, google_error=error)
    async def run():
        p = ActionProvider(settings, "google")
        failures, reserved = [], []
        p.on_attempt, p.before_fallback = failures.append, reserved.append
        try:
            _, first = await p.generate_action("test")
            _, second = await p.generate_action("test again")
            assert first["provider"] == "openrouter" and first["model"] == "router/actual"
            assert len(first["attempts"]) == 2 and len(second["attempts"]) == 1
            assert first["fallback"]["failure_type"] == type(error).__name__
            assert len(failures) == len(reserved) == 1
            assert "private" not in json.dumps(first)
        finally:
            await p.close()
    asyncio.run(run())
    assert len(calls) == 2 and all(c["model"] == "test-fallback" for c in calls)
    remote.aio.interactions.create.assert_awaited_once()


def test_invalid_json_falls_back_and_cancels_remote(tmp_path, monkeypatch):
    settings, remote, calls = harness(monkeypatch, tmp_path, google_text="not valid JSON")
    async def run():
        p = ActionProvider(settings, "google")
        try:
            _, usage = await p.generate_action("test")
            assert usage["fallback"]["failure_type"] == "ValidationError"
        finally:
            await p.close()
    asyncio.run(run())
    remote.aio.interactions.cancel.assert_awaited_once()
    assert len(calls) == 1


def test_bounded_timeout_and_cancellation_never_falls_back(tmp_path, monkeypatch):
    settings, remote, calls = harness(monkeypatch, tmp_path, llm_timeout_seconds=.01)
    async def slow(**kwargs):
        await asyncio.sleep(5)
    remote.aio.interactions.create.side_effect = slow
    async def run():
        p = ActionProvider(settings, "google")
        try:
            _, usage = await p.generate_action("test")
            assert usage["fallback"]["failure_type"] == "TimeoutError"
        finally:
            await p.close()
        p = ActionProvider(settings, "google")
        settings.llm_timeout_seconds = 5
        try:
            task = asyncio.create_task(p.generate_action("test"))
            await asyncio.sleep(.01)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        finally:
            await p.close()
    asyncio.run(run())
    assert len(calls) == 1


def test_missing_credentials_disabled_and_unconfigured_fallback(tmp_path, monkeypatch):
    settings, _, calls = harness(monkeypatch, tmp_path, google_error=RuntimeError("private error"))
    settings.google_api_key = ""
    async def run():
        p = ActionProvider(settings, "google")
        _, usage = await p.generate_action("test")
        assert usage["fallback"]["failure_type"] == "MissingGoogleCredentials"
        await p.close()
    asyncio.run(run())
    assert len(calls) == 1
    for key, value in [("llm_fallback_provider", "none"), ("openrouter_model", "")]:
        original = getattr(settings, key)
        setattr(settings, key, value)
        with pytest.raises(ValueError, match="Google credentials"):
            ActionProvider(settings, "google")
        setattr(settings, key, original)


def test_both_fail_without_fixture_output_or_sensitive_text(tmp_path, monkeypatch):
    settings, _, calls = harness(monkeypatch, tmp_path, google_error=RuntimeError("private prompt"), status=503)
    async def run():
        p = ActionProvider(settings, "google")
        failures = []
        p.on_attempt = failures.append
        try:
            with pytest.raises(FallbackExhaustedError) as result:
                await p.generate_action("test")
            assert [a["provider"] for a in result.value.attempts] == ["google", "openrouter"]
            assert len(failures) == 2
            assert "private" not in str(result.value)
        finally:
            await p.close()
    asyncio.run(run())
    assert len(calls) == 1


@pytest.mark.parametrize("limit,expected_calls", [(1, 0), (2, 1)])
def test_investigation_counts_attempts_and_enforces_budget(tmp_path, monkeypatch, limit, expected_calls):
    settings, _, calls = harness(monkeypatch, tmp_path, google_error=RuntimeError("private quota failure"), max_model_requests=limit)
    data = ScientificData()
    store = ResearchStore(settings)
    store.seed(data.workspace())
    engine = ResearchEngine(store, data, settings)
    req = ResearchRequest(question="Inspect the source evidence before asserting any finding.", criteria=ResearchCriteria(**{k:v for k,v in data.workspace()["defaults"].items() if k in ResearchCriteria.model_fields}), selected_ids=[data.workspace()["variants"][0]["id"]], max_seconds=30)
    async def run():
        doc = engine.start(req)
        store.claim(engine.worker_id)
        await engine.execute(doc["run_id"])
        return store.get(doc["run_id"])
    doc = asyncio.run(run())
    assert doc["budget"]["model_requests"] == limit
    assert len(calls) == expected_calls
    assert doc["findings"] == []
    assert doc["budget"]["usage"][0]["status"] == "failed_attempt"
    assert "private" not in json.dumps(doc)
    if limit == 1:
        assert doc["status"] == "abstained"
    if limit == 2:
        assert doc["provider"] == "openrouter" and doc["model"] == "router/actual"
        assert doc["requested_provider"] == "google"
        assert len(doc["budget"]["usage"]) == 2
        assert any(e["type"] == "model.fallback" for e in doc["events"])
        assert doc["budget"]["cost_usd"] is None


@pytest.mark.parametrize("kind", ["reading", "translation"])
def test_paper_results_preserve_fallback_provenance(tmp_path, monkeypatch, kind):
    import base64
    from app.papers import PaperLibrary, PaperUpload, PaperRead, PaperTranslate
    text = "Les résultats sont préliminaires."
    args = {"summary": "Preliminary results.", "claims": [{"text": "Validation is required.", "chunk_id": "p1-c1", "quote": text}], "limitations": ["Selected passages only."]} if kind == "reading" else {"passages": [{"chunk_id": "p1-c1", "text": "The results are preliminary."}], "limitations": ["Model translation."]}
    action = {"action": "invoke_tool", "summary": "Selected passages processed.", "tool": "paper_reading" if kind == "reading" else "paper_translation", "arguments": args}
    settings, _, calls = harness(monkeypatch, tmp_path, google_error=PermissionError("private quota"), router_action=action)
    lib = PaperLibrary(settings)
    paper = lib.upload(PaperUpload(filename="étude.txt", content_base64=base64.b64encode(text.encode()).decode()))
    result = asyncio.run(lib.read(paper["id"], PaperRead())) if kind == "reading" else asyncio.run(lib._translate(paper["id"], PaperTranslate(chunk_ids=["p1-c1"])))
    assert result["provider"]["provider"] == "openrouter"
    assert len(result["provider"]["attempts"]) == 2
    assert lib.get(paper["id"])["chunks"][0]["text"] == text
    assert len(calls) == 1


def test_failed_paper_review_counts_both_provider_attempts(tmp_path, monkeypatch):
    import base64
    from app.papers import PaperLibrary, PaperUpload
    from app.paper_review import PaperReviewEngine, PaperReviewRequest
    settings, _, calls = harness(monkeypatch, tmp_path, google_error=PermissionError("private quota"), status=503)
    paper = PaperLibrary(settings).upload(PaperUpload(filename="source.txt", content_base64=base64.b64encode(b"The evidence requires independent review.").decode()))
    store = ResearchStore(settings)
    engine = PaperReviewEngine(store, settings)
    doc = engine.start("project-"+"a"*32, {"origin_id": paper["id"]}, PaperReviewRequest(question="What does this source actually report?", source_id="source-test", source_version=paper["sha256"], chunk_ids=["p1-c1"]))
    asyncio.run(engine.execute(doc["run_id"]))
    result = engine.store.get(doc["run_id"])
    assert result["status"] == "failed" and result["findings"] == []
    assert result["budget"]["model_requests"] == 2
    assert [u["provider"] for u in result["budget"]["usage"]] == ["google", "openrouter"]
    assert len(calls) == 1


def test_openrouter_receives_action_envelope_schema(tmp_path, monkeypatch):
    settings, _, calls = harness(monkeypatch, tmp_path)
    async def run():
        client = ActionProvider(settings, "openrouter")
        try:
            await client.generate_action('{"arguments_schema": {"properties": {"claims": {"type": "array"}}}}')
        finally:
            await client.close()
    asyncio.run(run())
    system = calls[0]["messages"][0]["content"]
    assert 'ENVELOPE schema' in system and '"action"' in system and '"arguments"' in system
    assert "never return those fields at the top level" in system
