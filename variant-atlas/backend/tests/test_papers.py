import asyncio
import base64
import json
import pytest
from app.config import Settings
from app.papers import PaperLibrary, PaperUpload, PaperRead
from app.research_schemas import AgentAction


def upload(library, text, filename="étude.txt"):
    return library.upload(
        PaperUpload(
            filename=filename, content_base64=base64.b64encode(text.encode()).decode()
        )
    )


def test_original_language_and_duplicate_storage(tmp_path):
    library = PaperLibrary(Settings(local_data_dir=tmp_path))
    text = "Étude de PTEN : les résultats sont préliminaires. 蛋白质研究。"
    paper = upload(library, text)
    assert paper["chunks"][0]["text"] == text
    assert upload(library, text)["id"] == paper["id"]
    assert len(library.list()) == 1
    assert (library.root / (paper["id"] + ".original")).read_bytes() == text.encode()
    assert PaperLibrary(library.settings).get(paper["id"]) == paper
    with pytest.raises(ValueError):
        library.get("../escape")
    with pytest.raises(ValueError):
        upload(library, "hello", "bad.exe")


@pytest.mark.parametrize("google", [False, True])
def test_reading_checks_original_quotes_and_stores_coverage(
    tmp_path, monkeypatch, google
):
    library = PaperLibrary(
        Settings(
            local_data_dir=tmp_path,
            openrouter_api_key="test",
            openrouter_model="test",
            google_api_key="test" if google else "",
        )
    )
    paper = upload(library, "Les résultats sont préliminaires et doivent être validés.")

    async def valid(self, prompt):
        assert self.provider == ("google" if google else "openrouter")
        return AgentAction(
            action="invoke_tool",
            summary="Read source passages.",
            tool="paper_reading",
            arguments={
                "summary": "Preliminary results.",
                "claims": [
                    {
                        "text": "Validation is required.",
                        "chunk_id": "p1-c1",
                        "quote": "Les résultats sont préliminaires",
                    }
                ],
                "limitations": ["Interpretation requires review."],
            },
        ), {"model": "test"}

    monkeypatch.setattr("app.papers.ActionProvider.generate_action", valid)
    reading = asyncio.run(library.read(paper["id"], PaperRead(language="English")))
    assert reading["covered_chunk_ids"] == ["p1-c1"]
    assert (
        json.loads(next(library.root.glob("*-reading-*.json")).read_text()) == reading
    )

    async def invalid(self, prompt):
        action, usage = await valid(self, prompt)
        action.arguments["claims"][0][
            "quote"
        ] = "A fabricated quotation absent from the source"
        return action, usage

    monkeypatch.setattr("app.papers.ActionProvider.generate_action", invalid)
    with pytest.raises(ValueError, match="quotation"):
        asyncio.run(library.read(paper["id"], PaperRead()))


def test_linked_paper_and_reference_visibility_survive_journal_export(tmp_path):
    from uuid import uuid4
    from app.science import ScientificData
    from app.repositories.research import ResearchStore
    from app.explorations import (
        ExplorationJournal,
        CreateExploration,
        UpdateExploration,
    )

    settings = Settings(local_data_dir=tmp_path, worker_mode="external")
    data = ScientificData()
    store = ResearchStore(settings)
    workspace = data.workspace()
    store.seed(workspace)
    paper = upload(
        PaperLibrary(settings),
        "Recherche PTEN en français, observations préliminaires.",
    )
    journal = ExplorationJournal(store, data)
    state = {
        "selected_id": "PTEN:p.C124S",
        "criteria": {
            k: workspace["defaults"][k] for k in ("activity_cutoff", "abundance_cutoff")
        },
    }
    original = journal.create(
        CreateExploration(dataset_version=workspace["dataset_version"], state=state)
    )
    state.update(reference_visible=False, paper_ids=[paper["id"]])
    updated = journal.update(
        original["id"],
        UpdateExploration(expected_revision=0, change_id=str(uuid4()), state=state),
    )
    assert updated["state"]["reference_visible"] is False
    assert "Removed experimental reference" in updated["events"][-1]["summary"]
    exported = journal.export(updated["id"])
    assert exported["linked_papers"][0]["source"]["sha256"] == paper["id"]
    assert exported["linked_papers"][0]["source"]["chunks"][0]["text"].startswith(
        "Recherche"
    )
    assert updated["events"][-1]["reference_geometry_changed"] is False


def test_pdf_without_text_requires_ocr_and_oversized_page_count_is_refused(tmp_path):
    import io
    from pypdf import PdfWriter

    library = PaperLibrary(Settings(local_data_dir=tmp_path))
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    output = io.BytesIO()
    writer.write(output)
    body = PaperUpload(
        filename="scan.pdf", content_base64=base64.b64encode(output.getvalue()).decode()
    )
    paper = library.upload(body)
    assert paper["status"] == "needs_ocr"
    with pytest.raises(ValueError, match="OCR"):
        asyncio.run(library.read(paper["id"], PaperRead()))
    for _ in range(80):
        writer.add_blank_page(width=100, height=100)
    output = io.BytesIO()
    writer.write(output)
    with pytest.raises(ValueError, match="80 pages"):
        library.upload(
            PaperUpload(
                filename="long.pdf",
                content_base64=base64.b64encode(output.getvalue()).decode(),
            )
        )


def test_investigation_freezes_uploaded_paper_and_validates_passage_citations(tmp_path):
    from app.science import ScientificData
    from app.repositories.research import ResearchStore
    from app.orchestration.engine import ResearchEngine
    from app.research_schemas import ResearchRequest, Finding
    from app.tools.registry import Registry

    settings = Settings(
        local_data_dir=tmp_path,
        worker_mode="external",
        llm_provider="openrouter",
        openrouter_api_key="test",
        openrouter_model="test",
    )
    data = ScientificData()
    store = ResearchStore(settings)
    workspace = data.workspace()
    store.seed(workspace)
    library = PaperLibrary(settings)
    paper = upload(library, "Cette étude demande une validation indépendante.")
    request = ResearchRequest(
        question="Review the uploaded paper against selected measurements.",
        selected_ids=["PTEN:p.C124S"],
        paper_ids=[paper["id"]],
        criteria={
            k: workspace["defaults"][k] for k in ("activity_cutoff", "abundance_cutoff")
        },
    )
    run = ResearchEngine(store, data, settings).start(request)
    assert run["paper_sources"][0]["chunks"] == paper["chunks"]
    citation = paper["id"] + "#p1-c1"
    finding = Finding(
        id="f1",
        text="The paper calls for validation.",
        claim_type="hypothesis",
        evidence_refs=[citation],
        variant_ids=["PTEN:p.C124S"],
        limitations=["Source applicability requires review."],
    )
    assert Registry.check_references([finding], run, workspace)["passed"]
    finding.evidence_refs = [paper["id"] + "#invented"]
    assert not Registry.check_references([finding], run, workspace)["passed"]
    with pytest.raises(ValueError, match="not found"):
        ResearchEngine(store, data, settings).start(
            request.model_copy(update={"paper_ids": ["0" * 64]})
        )
