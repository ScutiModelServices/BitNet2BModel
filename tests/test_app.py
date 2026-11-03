import asyncio
import time

import httpx
import pytest
from fastapi.testclient import TestClient

import settings
from app import create_app
from conftest import make_engine
from engine import EngineError
from options import SETTINGS
from tokens import TokenStore

BODY = {"messages": [{"role": "user", "content": "hi"}]}


def client(engine=None, admin_password=None, **options):
    return TestClient(create_app(engine or make_engine(), admin_password, **options))


def test_chat_passes_options_and_reports_usage():
    engine = make_engine()
    body = client(engine).post("/v1/chat", json={**BODY, "temperature": 0.3, "max_tokens": 50}).json()
    assert body["content"] == "hello" and body["finish_reason"] == "stop"
    assert body["model"] == "m" and body["fallback"] is False
    assert body["usage"] == {"input_tokens": 3, "output_tokens": 5} and "duration_ms" in body
    call = engine.loads and engine._base.calls[0]
    assert call == {"messages": [{"role": "user", "content": "hi"}], "temperature": 0.3, "max_tokens": 50}


@pytest.mark.parametrize("extra", [{"tools": []}, {"schema": {"type": "object"}}, {"thinking": False}])
def test_features_the_model_lacks_are_refused_not_ignored(extra):
    assert client().post("/v1/chat", json={**BODY, **extra}).status_code == 422


def test_request_is_validated():
    c = client()
    assert c.post("/v1/chat", json={"messages": []}).status_code == 422
    assert c.post("/v1/chat", json={"messages": [{"role": "tool", "content": "x"}]}).status_code == 422
    assert c.post("/v1/chat", json={**BODY, "project": "Bad Name"}).status_code == 422
    assert c.post("/v1/chat", json={**BODY, "max_tokens": 99999}).status_code == 422


def test_a_long_conversation_is_422_and_a_crash_is_500():
    class Broken:
        async def chat(self, *args, **kwargs):
            raise error

        async def close(self):
            pass

        model, num_thread, ready = "m", None, False

    for error, status in ((EngineError("too long", 400), 422), (RuntimeError("boom"), 500)):
        assert client(Broken()).post("/v1/chat", json=BODY).status_code == status


def test_health_reports_readiness_and_projects(tmp_path):
    (tmp_path / "garrison").mkdir()
    (tmp_path / "garrison" / "config.json").write_text("{}")
    engine = make_engine(projects_dir=str(tmp_path))
    c = client(engine)
    assert c.get("/health").json() == {"status": "ok", "model": "m", "ready": False, "num_thread": None,
                                       "project_models": ["garrison"]}
    c.post("/v1/chat", json=BODY)
    assert c.get("/health").json()["ready"] is True


def test_a_project_model_answers_and_a_missing_one_falls_back(tmp_path):
    (tmp_path / "garrison").mkdir()
    (tmp_path / "garrison" / "config.json").write_text("{}")
    c = client(make_engine(projects_dir=str(tmp_path)))
    assert c.post("/v1/chat", json={**BODY, "project": "garrison"}).json()["model"] == "garrison"
    other = c.post("/v1/chat", json={**BODY, "project": "nobody"}).json()
    assert other["model"] == "m" and other["fallback"] is True


def test_each_project_gets_its_own_revocable_token(tmp_path):
    c = client(admin_password="admin", tokens=TokenStore(tmp_path / "t.json"))
    admin = {"X-Internal-Token": "admin"}
    assert c.post("/v1/chat", json=BODY).status_code == 401
    made = c.post("/admin/tokens", json={"name": "Garrison"}, headers=admin).json()
    assert made["token"].startswith("bitnet_")
    use = {"X-Internal-Token": made["token"]}
    assert c.post("/v1/chat", json=BODY, headers=use).status_code == 200
    assert c.delete(f"/admin/tokens/{made['id']}", headers=admin).status_code == 200
    assert c.post("/v1/chat", json=BODY, headers=use).status_code == 401
    assert c.get("/health").status_code == 200  # /health needs no token


def test_a_token_limited_to_projects_refuses_other_projects(tmp_path):
    c = client(admin_password="admin", tokens=TokenStore(tmp_path / "t.json"))
    admin = {"X-Internal-Token": "admin"}
    assert c.post("/admin/tokens", json={"name": "x", "projects": ["Bad Name"]}, headers=admin).status_code == 422
    made = c.post("/admin/tokens", json={"name": "p", "projects": ["app-b", "app-a"]}, headers=admin).json()
    assert made["projects"] == ["app-a", "app-b"]
    use = {"X-Internal-Token": made["token"]}
    assert c.post("/v1/chat", json={**BODY, "project": "app-a"}, headers=use).status_code == 200
    assert c.post("/v1/chat", json={**BODY, "project": "other"}, headers=use).status_code == 403
    assert c.post("/v1/chat", json=BODY, headers=use).status_code == 200  # no project is always allowed


def test_rate_limit_edit_stats_and_metrics(tmp_path):
    store = TokenStore(tmp_path / "t.json")
    c = client(admin_password="admin", tokens=store)
    admin = {"X-Internal-Token": "admin"}
    made = c.post("/admin/tokens", json={"name": "p", "rate": 1}, headers=admin).json()
    use = {"X-Internal-Token": made["token"]}
    assert c.post("/v1/chat", json=BODY, headers=use).status_code == 200
    limited = c.post("/v1/chat", json=BODY, headers=use)
    assert limited.status_code == 429 and int(limited.headers["Retry-After"]) >= 1
    assert c.put(f"/admin/tokens/{made['id']}", json={"projects": ["a"], "rate": None}, headers=admin).status_code == 200
    assert c.post("/v1/chat", json=BODY, headers=use).status_code == 200  # the limit is gone
    assert c.put("/admin/tokens/nope", json={}, headers=admin).status_code == 404
    assert store.list()[0]["timed"] >= 1
    assert c.get("/metrics").status_code == 401
    assert 'bitnet_requests_total{token="p"}' in c.get("/metrics", headers=admin).text


def test_requests_over_the_in_flight_limit_get_429():
    async def main():
        engine = make_engine()
        release = asyncio.Event()
        real = engine.chat

        async def slow(*args, **kwargs):
            await release.wait()
            return await real(*args, **kwargs)

        engine.chat = slow
        app = create_app(engine, max_inflight=1)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://svc") as http:
            first = asyncio.create_task(http.post("/v1/chat", json=BODY))
            await asyncio.sleep(0.2)
            second = await http.post("/v1/chat", json=BODY)
            release.set()
            return second, await first

    second, first = asyncio.run(main())
    assert second.status_code == 429 and second.headers["Retry-After"] == "5"
    assert first.status_code == 200


def test_workers_are_read_only_and_admin_only(monkeypatch):
    monkeypatch.setenv("BITNET_REPLICAS", "3")
    c = client(admin_password="admin")
    assert c.get("/admin/workers").status_code == 401
    assert c.get("/admin/workers", headers={"X-Internal-Token": "admin"}).json() == {"replicas": 3, "parallel": 1}


def test_num_thread_is_reported_and_set_by_the_admin(tmp_path):
    seen = []
    engine = make_engine(set_threads=seen.append)
    c = client(engine, "admin", tokens=TokenStore(tmp_path / "t.json"))
    admin = {"X-Internal-Token": "admin"}
    assert c.put("/admin/threads", json={"num_thread": 0}, headers=admin).status_code == 422
    assert c.put("/admin/threads", json={"num_thread": 3}, headers=admin).json() == {"num_thread": 3}
    assert seen == [3] and c.get("/health").json()["num_thread"] == 3
    assert settings.load(tmp_path / "settings.json")["num_thread"] == 3


def test_settings_are_admin_only_checked_and_apply_live(tmp_path):
    store = TokenStore(tmp_path / "t.json")
    config = settings.Config(store.settings_path, SETTINGS)
    config.set({"update_check_hours": 0, "warm": False})
    c = client(admin_password="admin", tokens=store, config=config)
    admin = {"X-Internal-Token": "admin"}
    assert c.get("/admin/settings").status_code == 401
    assert c.put("/admin/settings", json={"values": {"max_inflight": -1}}, headers=admin).status_code == 422
    assert c.put("/admin/settings", json={"values": {"max_inflight": 7}}, headers=admin).status_code == 200
    saved = {item["key"]: item for item in c.get("/admin/settings", headers=admin).json()["settings"]}
    assert saved["max_inflight"]["value"] == 7
    assert client(admin_password="admin").put("/admin/settings", json={"values": {}}, headers=admin).status_code == 409


def test_what_another_replica_saved_reaches_this_one(tmp_path):
    store = TokenStore(tmp_path / "t.json")
    config = settings.Config(store.settings_path, SETTINGS)
    config.set({"update_check_hours": 0, "warm": False})
    seen = []
    engine = make_engine(set_threads=seen.append)
    with TestClient(create_app(engine, "admin", tokens=store, config=config)):
        settings.save(store.settings_path, num_thread=5, project_models_dir=str(tmp_path), max_project_models=3)
        for _ in range(300):  # the loop looks every second
            if engine.max_projects == 3:
                break
            time.sleep(0.02)
    assert seen == [5] and engine.projects_dir == str(tmp_path) and engine.max_projects == 3


def test_startup_warms_the_model():
    engine = make_engine()
    with TestClient(create_app(engine, warm=True)) as c:
        for _ in range(100):
            if c.get("/health").json()["ready"]:
                break
            time.sleep(0.02)
        assert engine.loads == ["m"] and c.get("/health").json()["ready"] is True


def test_health_answers_while_the_model_is_still_loading():
    import threading
    release = threading.Event()

    def slow(source):
        release.wait(5)
        return make_engine()._loader(source)

    with TestClient(create_app(make_engine(loader=slow), warm=True)) as c:
        assert c.get("/health").json()["ready"] is False
        release.set()


def test_warmup_failure_is_logged_without_stopping_service(caplog):
    def failing(source):
        raise RuntimeError("no weights")

    with TestClient(create_app(make_engine(loader=failing), warm=True)) as c:
        assert c.get("/health").status_code == 200
        for _ in range(100):
            if "warm-up failed" in caplog.text:
                break
            time.sleep(0.02)
    assert "warm-up failed" in caplog.text


def test_warmup_is_optional():
    engine = make_engine()
    with TestClient(create_app(engine)):
        assert engine.loads == []


def test_main_builds_the_engine_from_settings(monkeypatch, tmp_path):
    import app as module

    monkeypatch.setenv("BITNET_TOKENS_FILE", str(tmp_path / "tokens.json"))
    monkeypatch.setenv("BITNET_NUM_THREAD", "2")
    monkeypatch.setenv("BITNET_PROJECT_MODELS_DIR", "/models/projects")
    monkeypatch.setenv("BITNET_PORT", "9999")
    monkeypatch.setattr(module.BitNetEngine, "num_thread", property(lambda self: None, lambda self, count: seen.append(count)))
    seen, started = [], {}
    monkeypatch.setattr("uvicorn.run", lambda app, host, port: started.update(app=app, host=host, port=port))
    module.main()
    assert started["port"] == 9999 and started["host"] == "127.0.0.1" and seen == [2]
