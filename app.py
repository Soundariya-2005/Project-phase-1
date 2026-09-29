import io
import json
import os
import uuid
import pandas as pd
from flask import Flask, jsonify, send_from_directory, request
from insider import pipeline, assistant
from insider.sample_data import generate
from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, MetaData, String, Table, create_engine, func, select, text
from sqlalchemy.engine import URL
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder='frontend/dist', static_url_path='/')
STATE = {"result": None}
IDENTITY_PASSWORD = "insider-secure-2026"
DATABASE_ENGINE = None
METADATA = MetaData()
dataset_runs = Table(
    "dataset_runs",
    METADATA,
    Column("run_id", String(36), primary_key=True),
    Column("table_name", String(64), nullable=False, unique=True),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    Column("row_count", Integer, nullable=False),
)
analysis_results = Table(
    "analysis_results",
    METADATA,
    Column("run_id", String(36), ForeignKey("dataset_runs.run_id", ondelete="CASCADE"), primary_key=True),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    Column("results_json", JSON, nullable=False),
)


def _sqlite_path():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    db_dir = os.path.join(root_dir, "data")
    os.makedirs(db_dir, exist_ok=True)
    return os.path.join(db_dir, "insider_activity.sqlite3")


def _database_engine():
    global DATABASE_ENGINE
    if DATABASE_ENGINE is not None:
        METADATA.create_all(DATABASE_ENGINE)
        return DATABASE_ENGINE

    try:
        username = os.environ.get("MYSQL_USER", "root")
        password = os.environ.get("MYSQL_PASSWORD", "")
        host = os.environ.get("MYSQL_HOST", "127.0.0.1")
        port = int(os.environ.get("MYSQL_PORT", "3306"))
        database = os.environ.get("MYSQL_DATABASE", "insider_threat")

        server_url = URL.create(
            "mysql+pymysql", username=username, password=password, host=host, port=port
        )
        server_engine = create_engine(server_url, pool_pre_ping=True)
        quoted_database = server_engine.dialect.identifier_preparer.quote(database)
        try:
            with server_engine.begin() as connection:
                connection.execute(text(
                    f"CREATE DATABASE IF NOT EXISTS {quoted_database} "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                ))
        finally:
            server_engine.dispose()

        database_url = URL.create(
            "mysql+pymysql", username=username, password=password, host=host,
            port=port, database=database,
        )
        DATABASE_ENGINE = create_engine(database_url, pool_pre_ping=True)
    except Exception:
        sqlite_path = _sqlite_path().replace("\\", "/")
        sqlite_url = f"sqlite:///{sqlite_path}"
        DATABASE_ENGINE = create_engine(sqlite_url, pool_pre_ping=True)

    METADATA.create_all(DATABASE_ENGINE)
    return DATABASE_ENGINE


def _store_and_load_dataset(df, run_id):
    engine = _database_engine()
    table_name = f"activity_{run_id.replace('-', '')}"
    df.to_sql(table_name, engine, if_exists="fail", index=False, chunksize=1000)
    with engine.begin() as connection:
        connection.execute(dataset_runs.insert().values(
            run_id=run_id, table_name=table_name, row_count=len(df)
        ))
    quoted_table = engine.dialect.identifier_preparer.quote(table_name)
    return pd.read_sql_query(text(f"SELECT * FROM {quoted_table}"), engine)


def _store_analysis_result(run_id, result):
    engine = _database_engine()
    with engine.begin() as connection:
        connection.execute(analysis_results.insert().values(run_id=run_id, results_json=result))


def _load_latest_result():
    engine = _database_engine()
    with engine.connect() as connection:
        result = connection.execute(
            select(analysis_results.c.results_json)
            .order_by(analysis_results.c.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()
    if isinstance(result, str):
        return json.loads(result)
    return result

def _f(name, default):
    try: return float(request.form.get(name, default))
    except ValueError: return default

@app.route("/")
def index(): return send_from_directory('frontend/dist', 'index.html')

@app.route("/api/analyze", methods=["POST"])
def analyze():
    try:
        if request.form.get("sample") == "1": df = generate()
        else:
            f = request.files.get("file")
            if not f: return jsonify(error="No file uploaded"), 400
            df = pd.read_csv(io.BytesIO(f.read()))
        run_id = str(uuid.uuid4())
        df = _store_and_load_dataset(df, run_id)
        res = pipeline.run(df, alpha=_f("alpha", .15), contamination=min(.3, max(.005, _f("contamination", .07))),
                           decay=_f("decay", .88), gain=_f("gain", .13))
        res["summary"]["analysis_id"] = run_id
        _store_analysis_result(run_id, res)
        STATE["result"] = res
        public_result = dict(res)
        public_result.pop("identity_lookup", None)
        return jsonify(public_result)
    except Exception as e:
        return jsonify(error=str(e)), 400


@app.route("/api/identity-name", methods=["POST"])
def identity_name():
    payload = request.get_json(silent=True) or {}
    password = str(payload.get("password", ""))
    user_id = str(payload.get("user_id", "")).strip()

    if password != IDENTITY_PASSWORD:
        return jsonify({"authorized": False, "message": "Invalid password."}), 401

    result = STATE.get("result") or _load_latest_result()
    if not result:
        return jsonify({"authorized": False, "message": "No analysis is loaded yet."}), 404
    STATE["result"] = result

    identity_lookup = result.get("identity_lookup", {})
    employee_name = identity_lookup.get(user_id)
    if not employee_name:
        return jsonify({"authorized": False, "message": "Employee not found in the active risk set."}), 404

    return jsonify({"authorized": True, "user_id": user_id, "name": employee_name})

@app.route("/api/ask", methods=["POST"])
def ask():
    q = (request.get_json(silent=True) or {}).get("question", "")
    result = STATE.get("result") or _load_latest_result()
    STATE["result"] = result
    return jsonify(answer=assistant.answer(q, result))

if __name__ == "__main__":
    app.run(debug=False, port=5000)
