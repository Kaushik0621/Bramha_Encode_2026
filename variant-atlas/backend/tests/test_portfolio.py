import base64
import json
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app
from app.repositories.research import ResearchStore
from app.science import ScientificData


def client(tmp_path):
    settings = Settings(
        local_data_dir=tmp_path, worker_mode="external", llm_provider="mock"
    )
    ResearchStore(settings).seed(ScientificData().workspace())
    return TestClient(create_app(settings))


def make(c, method="pten", linked=True):
    rows = c.get("/api/portfolio/sources").json()
    ids = [s["id"] for s in rows if s["method"] == method] if linked else []
    response = c.post(
        "/api/portfolio/projects",
        json={
            "title": "Research question project",
            "objective": "Investigate the supported evidence and its limits.",
            "method": method,
            "source_ids": ids,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_migration_idempotent_no_invented_projects_and_frozen_run_bytes(tmp_path):
    with client(tmp_path) as c:
        settings = Settings(local_data_dir=tmp_path)
        store = ResearchStore(settings)
        path = store.root / ("research-" + "a" * 32 + ".json")
        doc = {
            "run_id": "research-" + "a" * 32,
            "workspace_id": "pten-real",
            "request": {"question": "A historical study question.", "selected_ids": []},
            "created_at": "2026-10-01",
            "status": "abstained",
            "source_manifest": [],
        }
        path.write_text(json.dumps(doc))
        original = path.read_bytes()
        first = c.get("/api/portfolio/bootstrap").json()
        second = c.get("/api/portfolio/bootstrap").json()
        assert first["projects"] == [] and second["projects"] == []
        assert first["investigations"][0]["project_id"] is None
        assert first["sources"] == second["sources"]
        assert path.read_bytes() == original
        metadata = json.loads((tmp_path / "portfolio/metadata.json").read_text())
        before = metadata["revision"]
        c.get("/api/portfolio/bootstrap")
        assert (
            json.loads((tmp_path / "portfolio/metadata.json").read_text())["revision"]
            == before
        )


def test_linking_versions_and_unlink_do_not_delete_shared_paper(tmp_path):
    with client(tmp_path) as c:
        paper = c.post(
            "/api/portfolio/sources/import",
            json={
                "filename": "original.txt",
                "content_base64": base64.b64encode(
                    "Recherche française et observations préliminaires.".encode()
                ).decode(),
            },
        ).json()
        a = make(c)
        b = make(c)
        for project in [a, b]:
            assert (
                c.post(
                    f"/api/portfolio/projects/{project['id']}/sources",
                    json={"source_id": paper["id"]},
                ).status_code
                == 200
            )
        assert (
            len(c.get("/api/portfolio/sources/" + paper["id"]).json()["projects"]) == 2
        )
        assert not c.get("/api/portfolio/projects/" + a["id"]).json()["sources"][
            paper["id"]
        ]["included"]
        c.post(
            f"/api/portfolio/projects/{a['id']}/sources",
            json={"source_id": paper["id"], "action": "include"},
        )
        c.post(
            f"/api/portfolio/projects/{a['id']}/sources",
            json={"source_id": paper["id"], "action": "unlink"},
        )
        assert c.get("/api/portfolio/sources/" + paper["id"]).status_code == 200
        assert (
            c.get("/api/research/papers/" + paper["origin_id"])
            .json()["chunks"][0]["text"]
            .startswith("Recherche")
        )
        assert (
            len(c.get("/api/portfolio/sources/" + paper["id"]).json()["projects"]) == 1
        )


def test_readiness_method_gates_state_conflict_and_no_provider_navigation(
    tmp_path, monkeypatch
):
    def forbidden(*args, **kwargs):
        raise AssertionError("Navigation must not call a provider")

    monkeypatch.setattr(
        "app.providers.actions.ActionProvider.generate_action", forbidden
    )
    with client(tmp_path) as c:
        p = make(c, linked=False)
        assert p["readiness"] == "Source preparation required"
        assert (
            c.post(
                f"/api/portfolio/projects/{p['id']}/state",
                json={
                    "expected_revision": p["revision"],
                    "state": {"selected_ids": ["PTEN:p.C124S"]},
                },
            ).status_code
            == 200
        )
        assert (
            c.post(
                f"/api/portfolio/projects/{p['id']}/state",
                json={"expected_revision": p["revision"], "state": {}},
            ).status_code
            == 409
        )
        for route in [
            "/api/portfolio/bootstrap",
            "/api/portfolio/sources",
            "/api/portfolio/projects/" + p["id"],
        ]:
            assert c.get(route).status_code == 200
        assert (
            c.post(
                f"/api/portfolio/projects/{p['id']}/investigations",
                json={
                    "confirmed": True,
                    "pten": {
                        "question": p["objective"],
                        "selected_ids": ["PTEN:p.C124S"],
                        "criteria": {"abundance_cutoff": 0.6},
                    },
                },
            ).status_code
            == 409
        )
        ready = make(c)
        assert ready["readiness"] == "Ready to explore"
        blood = make(c, "blood")
        assert blood["method_info"]["title"].startswith("Blood-group")


def test_note_authorship_and_explicit_assignment_preserve_run(tmp_path):
    with client(tmp_path) as c:
        p = make(c)
        store = ResearchStore(Settings(local_data_dir=tmp_path))
        rid = "research-" + "b" * 32
        store.create(
            {
                "run_id": rid,
                "workspace_id": "pten-real",
                "created_at": "2026-10-01",
                "status": "abstained",
                "request": {
                    "question": "Keep the uncertainty visible.",
                    "selected_ids": [],
                },
                "source_manifest": [],
            }
        )
        snapshot = (store.root / (rid + ".json")).read_bytes()
        assert c.get("/api/portfolio/investigations/" + rid).json()["project"] is None
        c.post(
            f"/api/portfolio/projects/{p['id']}/attach-investigation",
            json={"run_id": rid},
        )
        assert (
            c.get("/api/portfolio/investigations/" + rid).json()["project"]["id"]
            == p["id"]
        )
        n = c.post(
            f"/api/portfolio/projects/{p['id']}/notes",
            json={
                "text": "This outcome needs another source.",
                "kind": "review note",
                "run_id": rid,
            },
        ).json()
        assert n["authorship"].startswith("researcher-authored")
        assert (store.root / (rid + ".json")).read_bytes() == snapshot
        assert (
            c.get("/api/portfolio/projects/" + p["id"]).json()["readiness"]
            == "Investigation needs attention"
        )


def test_project_start_uses_explicit_included_papers_and_project_id(
    tmp_path, monkeypatch
):
    with client(tmp_path) as c:
        p = make(c)
        paper = c.post(
            "/api/portfolio/sources/import",
            json={
                "filename": "note.txt",
                "content_base64": base64.b64encode(
                    b"Original source research note."
                ).decode(),
            },
        ).json()
        url = f"/api/portfolio/projects/{p['id']}/sources"
        c.post(url, json={"source_id": paper["id"]})
        c.post(url, json={"source_id": paper["id"], "action": "include"})
        captured = []

        def fake_start(self, request):
            captured.append(request)
            return {"run_id": "research-" + "d" * 32, "status": "queued"}

        monkeypatch.setattr("app.orchestration.engine.ResearchEngine.start", fake_start)
        response = c.post(
            f"/api/portfolio/projects/{p['id']}/investigations",
            json={
                "confirmed": True,
                "pten": {
                    "question": "Investigate the selected PTEN evidence.",
                    "selected_ids": ["PTEN:p.C124S"],
                    "criteria": {"abundance_cutoff": 0.6},
                    "paper_ids": [],
                },
            },
        )
        assert response.status_code == 200, response.text
        assert (
            captured[0].paper_ids == [paper["origin_id"]]
            and captured[0].project_id == p["id"]
        )


def test_historical_source_versions_are_retained_and_migration_backs_up_metadata(
    tmp_path,
):
    from app.portfolio import digest

    with client(tmp_path) as c:
        sources = c.get("/api/portfolio/sources").json()
        source = next(s for s in sources if s["family"] == "pten")
        original = {
            "id": source["origin_id"],
            "title": "Earlier source release",
            "url": source["url"],
            "release": "historical-test-version",
        }
        rid = "research-" + "e" * 32
        ResearchStore(Settings(local_data_dir=tmp_path)).create(
            {
                "run_id": rid,
                "workspace_id": "pten-real",
                "created_at": "2026-09-01",
                "status": "abstained",
                "request": {
                    "question": "Inspect an older source version.",
                    "selected_ids": [],
                },
                "source_manifest": [original],
            }
        )
        row = c.get("/api/portfolio/sources/" + source["id"]).json()
        assert digest(original) in {s["version"] for s in row["versions"]}
        detail = c.get("/api/portfolio/investigations/" + rid).json()
        assert detail["sources"][0]["cited_version"] == digest(original)
        assert list((tmp_path / "portfolio/backups").glob("*.json"))


def test_scene_links_are_project_scoped_and_rebinding_is_idempotent(tmp_path):
    with client(tmp_path) as c:
        a = make(c)
        b = make(c)
        w = ScientificData().workspace()
        scene = {
            "selected_id": "PTEN:p.C124S",
            "picked_ids": ["PTEN:p.C124S"],
            "criteria": {"abundance_cutoff": w["defaults"]["abundance_cutoff"]},
        }
        doc = c.post(
            "/api/research/explorations",
            json={"dataset_version": w["dataset_version"], "state": scene},
        ).json()
        url = "/api/portfolio/projects/" + a["id"] + "/journey"
        bound = c.post(url, json={"journey_id": doc["id"]}).json()
        repeated = c.post(url, json={"journey_id": doc["id"]}).json()
        assert repeated["revision"] == bound["revision"]
        assert (
            c.post(
                "/api/portfolio/projects/" + b["id"] + "/journey",
                json={"journey_id": doc["id"]},
            ).status_code
            == 409
        )
        assert repeated["journey_ids"] == [doc["id"]]


def test_historical_run_access_survives_missing_current_scientific_assets(tmp_path):
    settings = Settings(
        local_data_dir=tmp_path, worker_mode="external", llm_provider="mock"
    )
    store = ResearchStore(settings)
    rid = "research-" + "f" * 32
    store.create(
        {
            "run_id": rid,
            "workspace_id": "pten-real",
            "created_at": "2026-09-01",
            "status": "abstained",
            "request": {
                "question": "Keep this historical evidence accessible.",
                "selected_ids": [],
            },
            "source_manifest": [
                {
                    "id": "historical-only-source",
                    "title": "Historical evidence",
                    "release": "old",
                }
            ],
        }
    )
    snapshot = (store.root / (rid + ".json")).read_bytes()
    settings.asset_root = tmp_path / "missing-assets"
    with TestClient(create_app(settings)) as c:
        assert c.app.state.research_engine is None
        response = c.get("/api/portfolio/investigations/" + rid)
        assert response.status_code == 200, response.text
        detail = response.json()
        assert detail["run"]["status"] == "abstained"
        assert detail["project"] is None
        assert detail["sources"][0]["origin_id"] == "historical-only-source"
        assert detail["sources"][0]["preparation"] == "failed"
        assert (
            c.get("/api/portfolio/sources/" + detail["sources"][0]["id"]).status_code
            == 200
        )
        bootstrap = c.get("/api/portfolio/bootstrap").json()
        assert bootstrap["methods"]["pten"]["available"] is False
        assert bootstrap["investigations"][0]["id"] == rid
    assert (store.root / (rid + ".json")).read_bytes() == snapshot
