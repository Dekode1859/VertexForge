import importlib
import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient


def load_sample_config() -> dict:
    return json.loads(Path("config.json").read_text(encoding="utf-8"))


def load_api_module(monkeypatch, tmp_path):
    monkeypatch.setenv("PHOENIX_COLLECTOR_ENDPOINT", "")
    monkeypatch.setenv("PHOENIX_PROJECT_NAME", "vertexforge-tests")

    if "api" in sys.modules:
        del sys.modules["api"]

    api = importlib.import_module("api")
    api.DB_PATH = tmp_path / "vertexforge-test.db"
    api.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    api.init_db()
    return api


def test_create_pipeline_rejects_invalid_config(monkeypatch, tmp_path) -> None:
    api = load_api_module(monkeypatch, tmp_path)
    client = TestClient(api.app)

    data = load_sample_config()
    data["edges"].append({"from": "ghost", "to": "END"})

    response = client.post(
        "/api/pipelines",
        json={"name": "Invalid", "description": "bad", "config": data},
    )

    assert response.status_code == 400
    assert "undefined node IDs" in response.json()["detail"]


def test_create_pipeline_accepts_valid_config(monkeypatch, tmp_path) -> None:
    api = load_api_module(monkeypatch, tmp_path)
    client = TestClient(api.app)

    response = client.post(
        "/api/pipelines",
        json={"name": "Valid", "description": "ok", "config": load_sample_config()},
    )

    body = response.json()

    assert response.status_code == 200
    assert body["name"] == "Valid"
    assert body["config"]["graph_name"] == "research_pipeline"
