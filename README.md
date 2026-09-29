# Privacy-Preserving Adaptive Insider Threat Detection and Early Warning System (Phase-I prototype)

Working prototype of the pipeline described in the project report:

    activity logs -> privacy layer -> adaptive profiling -> Isolation Forest
                  -> progressive risk -> SHAP explanation -> early warning -> dashboard

## Run
    python -m venv venv && venv\Scripts\activate      # Linux/macOS: source venv/bin/activate
    pip install -r requirements.txt
    python app.py                                      # backend only; use start_project.ps1 for the full stack
    pytest -q                                          # optional tests

## Restart after shutdown (Windows)
The MySQL database files persist under `%LOCALAPPDATA%\MySQL\InsiderThreat\data`; shutting down
stops the MySQL, Flask, and Vite processes but does not delete the database. From PowerShell in
the `proj` folder, run:

    .\start_project.ps1

If MySQL was stopped, the script starts it using the existing data directory. Wait until the
MySQL window reports `ready for connections`, then press Enter in the original PowerShell window.
The script verifies MySQL before opening the Flask and React terminals. Open
`http://127.0.0.1:5173/`. Do not run `mysqld --initialize` again for this existing database.

Click **Try with sample data**, or upload `data/sample_activity_logs.csv` / your own CSV
(one user column, one date column, numeric daily behavioural features).
The app connects to MySQL and creates the `insider_threat` database and required metadata tables.
Each upload is stored in its own `activity_<run_id>` table, read back with SQL for analysis,
and linked to its saved result in `analysis_results`.

Configure MySQL before starting Flask (PowerShell example):

    $env:MYSQL_HOST = "127.0.0.1"
    $env:MYSQL_PORT = "3306"
    $env:MYSQL_DATABASE = "insider_threat"
    $env:MYSQL_USER = "root"
    $env:MYSQL_PASSWORD = "your-local-mysql-password"
    python app.py

The configured MySQL account needs permission to create the database and tables. The app
retains each run's raw dataset and analysis result, including identifying fields and the
identity lookup; secure MySQL credentials, network access, and backups accordingly.

## Implemented (about 50 % of the full project)
| Report component | Status | File |
|---|---|---|
| Data upload + auto column detection | done | `insider/pipeline.py` |
| MySQL dataset and analysis-result persistence | done | `app.py` |
| Privacy layer: minimization + salted HMAC pseudonymization | done | `insider/privacy.py` |
| Adaptive user profiling (EWMA baseline, controlled learning) | done | `insider/pipeline.py` |
| Isolation Forest anomaly detection | done | `insider/pipeline.py` |
| Progressive risk score (decay + gain, 0-100) | done | `insider/pipeline.py` |
| SHAP-based explanation per user | done | `insider/pipeline.py` |
| Early warning Low / Medium / High / Critical | done | `insider/pipeline.py` |
| Web dashboard (parameters, summary, trend, donut, factors) | done | `app.py`, `templates/index.html` |
| Risk Assistant (pseudonymous IDs only) | basic, rule-based | `insider/assistant.py` |

## Not yet implemented (next phase)
- Persistence of profiles and alerts (datasets and analysis results are stored in MySQL)
- Real CERT r4.2 preprocessing (raw logon/file/email/http/device logs -> daily features)
- Evaluation: precision, recall, F1, false-positive analysis; comparison with One-Class SVM, Autoencoder, XGBoost
- Real-time streaming / SIEM integration, role-based access control, audit trail, encryption at rest
- Per-day SHAP timeline, counterfactual explanations, LLM-based assistant

## Notes
- `data/sample_activity_logs.csv` is **synthetic** (40 users, 45 days, 3 users with injected gradual malicious drift). It contains `real_name` and `pc` columns on purpose to demonstrate that the privacy layer removes them.
- MySQL stores raw uploaded datasets, including identifying columns, and analysis results, including the identity lookup. Apply least-privilege database access, backups, and encryption appropriate to your data.
- Adaptive profiling uses the EWMA `baseline(t) = baseline(t-1) + alpha * (x(t) - baseline(t-1))`. Days with |z| > 3 are absorbed at 10 % of the learning rate so persistent malicious drift is not learned as "normal".
- Risk: `risk(t) = decay * risk(t-1) + gain * 100 * anomaly_strength(t)`, capped at 100. Levels: <25 Low, <50 Medium, <75 High, otherwise Critical.
- The pseudonym mapping uses a random per-run salt and is never stored, so IDs change every run.
