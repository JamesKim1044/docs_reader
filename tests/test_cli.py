from __future__ import annotations

import json

from typer.testing import CliRunner

from docs_reader.cli import app

runner = CliRunner()


def test_dry_run_reports_route(text_pdf, schema_py):
    result = runner.invoke(
        app, ["extract", str(text_pdf), "--schema", str(schema_py), "--dry-run"]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["document"]["route"] == "text"
    assert payload["schema"]["has_pydantic"] is True
    assert payload["provider"] == "opensource"


def test_extract_with_mock_provider(text_pdf, schema_py, tmp_path, monkeypatch):
    canned = tmp_path / "canned.json"
    canned.write_text(json.dumps({"invoice_number": "INV-CLI-1", "total": 5.0, "line_items": []}))
    monkeypatch.setenv("DOCS_READER_MOCK_JSON", str(canned))
    out = tmp_path / "out.json"
    result = runner.invoke(
        app,
        [
            "extract", str(text_pdf), "--schema", str(schema_py),
            "--provider", "mock", "--no-verify", "--keep-hallucinations",  # canned data isn't in the doc
            "--output", str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(out.read_text())
    assert payload["data"]["invoice_number"] == "INV-CLI-1"
    assert payload["meta"]["provider"] == "mock"


def test_providers_command_runs():
    result = runner.invoke(app, ["providers"])
    assert result.exit_code == 0
    assert "Default provider: opensource" in result.output
