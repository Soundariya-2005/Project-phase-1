import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, select
from sqlalchemy.engine import URL

load_dotenv()

username = os.environ.get("MYSQL_USER", "root")
password = os.environ.get("MYSQL_PASSWORD", "")
host = os.environ.get("MYSQL_HOST", "127.0.0.1")
port = int(os.environ.get("MYSQL_PORT", "3306"))
database = os.environ.get("MYSQL_DATABASE", "insider_threat")

database_url = URL.create(
    "mysql+pymysql", username=username, password=password, host=host,
    port=port, database=database,
)
engine = create_engine(database_url, pool_pre_ping=True)

print("=" * 60)
print("INSIDER THREAT DATABASE - STORED DATA VIEWER")
print("=" * 60)
print()

# Query dataset_runs
print("1. DATASET RUNS")
print("-" * 60)
with engine.connect() as conn:
    result = conn.execute(text("SELECT * FROM dataset_runs ORDER BY created_at DESC LIMIT 10"))
    rows = result.fetchall()
    if rows:
        columns = result.keys()
        print(f"{'Run ID':<38} {'Table Name':<20} {'Rows':<10} {'Created At'}")
        print("-" * 60)
        for row in rows:
            print(f"{row[0]:<38} {row[1]:<20} {row[3]:<10} {row[2]}")
    else:
        print("No dataset runs found yet.")
print()

# Query analysis_results
print("2. ANALYSIS RESULTS")
print("-" * 60)
with engine.connect() as conn:
    result = conn.execute(text("SELECT run_id, created_at, JSON_LENGTH(results_json) as size FROM analysis_results ORDER BY created_at DESC LIMIT 10"))
    rows = result.fetchall()
    if rows:
        print(f"{'Run ID':<38} {'Created At':<25} {'Result Size (bytes)'}")
        print("-" * 60)
        for row in rows:
            print(f"{row[0]:<38} {row[1]:<25} {row[2]}")
    else:
        print("No analysis results found yet.")
print()

# Query activity tables
print("3. ACTIVITY TABLES (Uploaded Datasets)")
print("-" * 60)
with engine.connect() as conn:
    result = conn.execute(text("SHOW TABLES LIKE 'activity_%'"))
    tables = result.fetchall()
    if tables:
        print(f"Found {len(tables)} activity table(s):")
        for table in tables:
            table_name = table[0]
            result2 = conn.execute(text(f"SELECT COUNT(*) FROM `{table_name}`"))
            count = result2.scalar()
            print(f"  - {table_name}: {count} rows")
    else:
        print("No activity tables found yet.")
print()

print("=" * 60)
print("To view detailed analysis results, run the dashboard and upload data.")
print("=" * 60)

engine.dispose()
