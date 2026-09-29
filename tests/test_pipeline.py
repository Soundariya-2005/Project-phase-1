import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import uuid
import app as app_module
from app import app
from insider.sample_data import generate
from insider import pipeline
from insider.privacy import pseudonymize
from sqlalchemy import create_engine


def test_uploaded_dataset_and_result_round_trip_through_sql(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'analysis.sqlite3'}")
    monkeypatch.setattr(app_module, "DATABASE_ENGINE", engine)
    source = generate(n_users=2, n_days=3)
    run_id = str(uuid.uuid4())

    restored = app_module._store_and_load_dataset(source, run_id)
    result = {"summary": {"records": len(source)}, "identity_lookup": {"U-1234": "Employee"}}
    app_module._store_analysis_result(run_id, result)
    stored_result = app_module._load_latest_result()

    assert restored.to_dict("records") == source.to_dict("records")
    assert stored_result == result


def test_privacy():
    out = pseudonymize(generate(5, 10), "user")
    assert out["user"].str.startswith("U-").all()

def test_detects_drifting_users():
    res = pipeline.run(generate())
    assert res["users"][0]["risk"] > 50 and res["summary"]["flagged"] >= 2
    assert "real_name" in res["summary"]["dropped_pii"] and res["users"][0]["factors"]


def test_identity_lookup_requires_valid_password():
    client = app.test_client()
    response = client.post("/api/identity-name", json={"password": "wrong-password", "user_id": "U-0001"})
    assert response.status_code == 401
    payload = response.get_json()
    assert payload["authorized"] is False


def test_database_falls_back_to_sqlite_when_mysql_is_unavailable(monkeypatch, tmp_path):
    sqlite_path = tmp_path / "fallback.sqlite3"
    monkeypatch.setenv("MYSQL_HOST", "127.0.0.1")
    monkeypatch.setenv("MYSQL_PORT", "3306")
    monkeypatch.setenv("MYSQL_DATABASE", "insider_threat")
    monkeypatch.setenv("MYSQL_USER", "root")
    monkeypatch.setenv("MYSQL_PASSWORD", "wrongpassword")
    monkeypatch.setattr(app_module, "DATABASE_ENGINE", None)
    monkeypatch.setattr(app_module, "METADATA", app_module.MetaData())
    monkeypatch.setattr(app_module, "dataset_runs", app_module.Table(
        "dataset_runs",
        app_module.METADATA,
        app_module.Column("run_id", app_module.String(36), primary_key=True),
        app_module.Column("table_name", app_module.String(64), nullable=False, unique=True),
        app_module.Column("created_at", app_module.DateTime, nullable=False, server_default=app_module.func.current_timestamp()),
        app_module.Column("row_count", app_module.Integer, nullable=False),
    ))
    monkeypatch.setattr(app_module, "analysis_results", app_module.Table(
        "analysis_results",
        app_module.METADATA,
        app_module.Column("run_id", app_module.String(36), app_module.ForeignKey("dataset_runs.run_id", ondelete="CASCADE"), primary_key=True),
        app_module.Column("created_at", app_module.DateTime, nullable=False, server_default=app_module.func.current_timestamp()),
        app_module.Column("results_json", app_module.JSON, nullable=False),
    ))
    monkeypatch.setattr(app_module, "_sqlite_path", lambda: sqlite_path)

    engine = app_module._database_engine()

    assert str(engine.url).startswith("sqlite")
    assert engine is not None
