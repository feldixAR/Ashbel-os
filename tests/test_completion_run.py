import io
import os
import sys
import types
from pathlib import Path

import pytest


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("OS_API_KEY", "testkey")
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.setenv("ENV", "test")
    from api.app import create_app

    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


H = {"X-API-Key": "testkey"}


def _csv_bytes(phone="0501234567"):
    return (
        "name,phone,email,city,work type,project stage,budget,address,decision maker,photos,plans,measurements,notes\n"
        f"Test Lead,{phone},lead@example.com,Ariel,belgian window,ready,55000,Main 1,Test Lead,yes,yes,yes,urgent project\n"
    ).encode("utf-8")


def test_health_returns_db_status(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.get_json()
    assert body["success"] is True
    assert body["data"]["status"] == "ok"
    assert body["data"]["db"] is True


def test_intake_upload_is_dry_run_preview(client):
    r = client.post(
        "/api/intake/upload",
        headers=H,
        data={"file": (io.BytesIO(_csv_bytes("0501000001")), "sample.csv")},
        content_type="multipart/form-data",
    )
    assert r.status_code == 200
    data = r.get_json()["data"]
    assert data["dry_run"] is True
    assert data["raw_count"] == 1
    assert data["approved_count"] == 1
    assert data["import_run_id"]
    assert data["records"][0]["ready_for_proposal"] is True


def test_intake_commit_requires_then_honors_approval(client):
    upload = client.post(
        "/api/intake/upload",
        headers=H,
        data={"file": (io.BytesIO(_csv_bytes("0501000002")), "approval.csv")},
        content_type="multipart/form-data",
    ).get_json()["data"]
    record = upload["records"][0]

    pending = client.post("/api/intake/commit", headers=H, json={
        "source_file": upload["source_file"],
        "import_run_id": upload["import_run_id"],
        "records": [record],
    })
    assert pending.status_code == 202
    approval_id = pending.get_json()["data"]["approval_id"]

    approved = client.post(f"/api/approvals/{approval_id}", headers=H, json={"action": "approve"})
    assert approved.status_code == 200

    committed = client.post("/api/intake/commit", headers=H, json={
        "source_file": upload["source_file"],
        "import_run_id": upload["import_run_id"],
        "approval_id": approval_id,
        "records": [record],
    })
    assert committed.status_code == 200
    data = committed.get_json()["data"]
    assert data["created"] == 1
    assert data["sent_outreach"] is False
    assert data["lead_ids"]
    lead_id = data["lead_ids"][0]

    reports = client.get("/api/intake/reports", headers=H).get_json()["data"]["reports"]
    assert reports[0]["status"] == "committed"
    assert reports[0]["approval_id"] == approval_id

    activities = client.get(f"/api/crm/leads/{lead_id}/activities", headers=H).get_json()["data"]["activities"]
    assert any("outreach_sent=false" in (a.get("notes") or "") for a in activities)

    queue = client.get("/api/daily_revenue_queue", headers=H).get_json()
    assert any(row["lead_id"] == lead_id for row in queue["queue"])


def test_lead_status_change_writes_activity(client):
    created = client.post("/api/leads", headers=H, json={
        "name": "Status Activity Lead",
        "phone": "0501999999",
        "city": "Ariel",
    }).get_json()["data"]["lead"]
    r = client.patch(f"/api/leads/{created['id']}", headers=H, json={"status": "hot"})
    assert r.status_code == 200
    activities = client.get(f"/api/crm/leads/{created['id']}/activities", headers=H).get_json()["data"]["activities"]
    assert any(a["subject"] == "Lead status changed" for a in activities)


def test_csv_docx_xlsx_parsers_supported(tmp_path):
    from skills.document_intelligence import parse_document

    csv_result = parse_document(_csv_bytes("0501000003"), "leads.csv")
    assert csv_result.records[0]["work_type"]

    docx = pytest.importorskip("docx")
    doc = docx.Document()
    table = doc.add_table(rows=2, cols=3)
    table.rows[0].cells[0].text = "name"
    table.rows[0].cells[1].text = "phone"
    table.rows[0].cells[2].text = "work type"
    table.rows[1].cells[0].text = "Docx Lead"
    table.rows[1].cells[1].text = "0501000004"
    table.rows[1].cells[2].text = "balcony"
    docx_path = tmp_path / "leads.docx"
    doc.save(docx_path)
    docx_result = parse_document(docx_path.read_bytes(), "leads.docx")
    assert docx_result.records[0]["name"] == "Docx Lead"

    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["name", "phone", "project stage"])
    ws.append(["Xlsx Lead", "0501000005", "ready"])
    xlsx_path = tmp_path / "leads.xlsx"
    wb.save(xlsx_path)
    xlsx_result = parse_document(xlsx_path.read_bytes(), "leads.xlsx")
    assert xlsx_result.records[0]["project_stage"] == "ready"


def test_pdf_parser_supported_with_safe_stub(monkeypatch):
    class _Page:
        def extract_text(self):
            return ""

        def extract_tables(self):
            return [[["name", "phone"], ["Pdf Lead", "0501000006"]]]

    class _Pdf:
        pages = [_Page()]

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    fake_pdfplumber = types.SimpleNamespace(open=lambda *_args, **_kwargs: _Pdf())
    monkeypatch.setitem(sys.modules, "pdfplumber", fake_pdfplumber)

    from skills.document_intelligence import parse_document
    result = parse_document(b"%PDF-safe-test", "leads.pdf")
    assert result.records[0]["name"] == "Pdf Lead"


def test_proposal_readiness_missing_fields():
    from skills.proposal_readiness import evaluate

    result = evaluate({"name": "Lead", "city": "Ariel"})
    assert result["ready_for_proposal"] is False
    assert result["missing_budget"] is True
    assert result["missing_project_stage"] is True


def test_real_data_path_ignored_and_sample_not_real_import():
    gitignore = Path(".gitignore").read_text(encoding="utf-8")
    assert "data/" in gitignore
    docs = Path("docs/LEAD_DATA_FOLDERS.md").read_text(encoding="utf-8")
    assert "data/raw_leads" in docs
    assert "synthetic sample" in docs


def test_no_hubspot_in_active_code():
    active_roots = ["api", "engines", "services", "skills", "agents", "orchestration", "scheduler", "ui"]
    hits = []
    for root in active_roots:
        for path in Path(root).rglob("*"):
            if path.is_file() and path.suffix in {".py", ".js", ".html", ".css"}:
                text = path.read_text(encoding="utf-8", errors="ignore")
                if "hubspot" in text.lower():
                    hits.append(str(path))
    assert hits == []


def test_ui_and_routes_exist():
    app_text = Path("api/app.py").read_text(encoding="utf-8")
    upload_text = Path("ui/js/components/upload_modal.js").read_text(encoding="utf-8")
    console_text = Path("ui/js/panels/console.js").read_text(encoding="utf-8", errors="ignore")
    assert "api.routes.intake" in app_text
    assert "/api/health" in app_text
    assert "approval_id" in upload_text
    assert "intake/reports" in Path("ui/js/api.js").read_text(encoding="utf-8")
    assert "operator-safety-row" in console_text
    assert "stuckLeads" in console_text
    assert "proposalReady" in console_text


def test_drafts_require_approval_and_imports_do_not_send():
    draft_modal = Path("ui/js/components/draft_modal.js").read_text(encoding="utf-8", errors="ignore")
    intake = Path("api/routes/intake.py").read_text(encoding="utf-8")
    assert "approvalCreate" in draft_modal
    assert "execute_outreach" not in intake
    assert '"sent_outreach": False' in intake


def test_direct_outreach_routes_are_preview_only(client, monkeypatch):
    def fail_send(*_args, **_kwargs):
        raise AssertionError("direct outreach execution must not run")

    import engines.outreach_engine as outreach_engine

    monkeypatch.setattr(outreach_engine, "execute_outreach", fail_send, raising=False)

    send = client.post("/api/outreach/send", headers=H, json={
        "lead_id": "lead-1",
        "name": "Safe Lead",
        "phone": "0501234567",
        "message": "draft only",
    })
    assert send.status_code == 202
    send_data = send.get_json()
    assert send_data["dry_run"] is True
    assert send_data["approval_required"] is True
    assert send_data["sent_outreach"] is False
    assert send_data["mode"] == "draft_only"

    execute = client.post("/api/outreach/execute", headers=H, json={
        "lead_id": "lead-1",
        "lead_name": "Safe Lead",
        "phone": "0501234567",
        "message": "draft only",
    })
    assert execute.status_code == 202
    execute_data = execute.get_json()
    assert execute_data["dry_run"] is True
    assert execute_data["approval_required"] is True
    assert execute_data["sent_outreach"] is False

    daily = client.post("/api/outreach/daily", headers=H)
    assert daily.status_code == 200
    daily_data = daily.get_json()
    assert daily_data["dry_run"] is True
    assert daily_data["sent_outreach"] is False
    assert daily_data["executed"] == 0


def test_whatsapp_routes_do_not_send_messages(client, monkeypatch):
    from services.integrations.whatsapp_client import WhatsAppClient

    def fail_external_action(*_args, **_kwargs):
        raise AssertionError("WhatsApp external action must not run")

    monkeypatch.setattr(WhatsAppClient, "send_text", fail_external_action, raising=False)
    monkeypatch.setattr(WhatsAppClient, "mark_as_read", fail_external_action, raising=False)

    send = client.post("/api/whatsapp/send", headers=H, json={"to": "0501234567", "message": "draft only"})
    assert send.status_code == 202
    send_data = send.get_json()
    assert send_data["dry_run"] is True
    assert send_data["approval_required"] is True
    assert send_data["sent_outreach"] is False

    webhook = client.post("/api/whatsapp/webhook", json={
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": "0501234567",
                        "id": "wamid.safe",
                        "type": "text",
                        "text": {"body": "status"},
                    }]
                }
            }]
        }]
    })
    assert webhook.status_code == 200
    webhook_data = webhook.get_json()
    assert webhook_data["dry_run"] is True
    assert webhook_data["sent_outreach"] is False


def test_approved_outreach_task_stays_draft_only(client, monkeypatch):
    def fail_send(*_args, **_kwargs):
        raise AssertionError("approved outreach must not perform external send in local run")

    import engines.outreach_engine as outreach_engine
    from services.storage.repositories.approval_repo import ApprovalRepository

    monkeypatch.setattr(outreach_engine, "execute_outreach", fail_send, raising=False)

    approval = ApprovalRepository().create(
        action="send_outreach",
        details={
            "outreach_task": {
                "lead_id": "lead-approved-draft",
                "lead_name": "Approved Draft Lead",
                "phone": "0501234567",
                "message": "approved draft only",
                "channel": "whatsapp",
            }
        },
        risk_level=2,
        requested_by="test",
    )

    response = client.post(f"/api/approvals/{approval.id}", headers=H, json={"action": "approve"})
    assert response.status_code == 200
    execution = response.get_json()["data"]["outreach_execution"]
    assert execution["approval_granted"] is True
    assert execution["dry_run"] is True
    assert execution["sent_outreach"] is False
    assert execution["executed"] is False
