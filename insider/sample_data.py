"""Synthetic activity-log generator (stand-in for the preprocessed CERT dataset)."""
import numpy as np, pandas as pd

FEATURES = ["login_count", "after_hours_login", "file_access_count", "sensitive_file_access",
            "email_count", "external_email_count", "web_upload_mb", "avg_session_minutes"]

def generate(n_users=40, n_days=45, n_bad=3, seed=7):
    rng = np.random.default_rng(seed)
    start = pd.Timestamp("2025-01-06")
    names = [f"employee_{i:03d}" for i in range(1, n_users + 1)]
    bad = set(rng.choice(n_users, n_bad, replace=False))
    rows = []
    for u, name in enumerate(names):
        base = dict(login_count=rng.uniform(2, 5), after_hours_login=rng.uniform(0, .4),
                    file_access_count=rng.uniform(20, 60), sensitive_file_access=rng.uniform(0, 3),
                    email_count=rng.uniform(15, 40), external_email_count=rng.uniform(1, 6),
                    web_upload_mb=rng.uniform(5, 30), avg_session_minutes=rng.uniform(120, 300))
        drift_start = rng.integers(18, 26)
        for d in range(n_days):
            r = {"user": name, "date": (start + pd.Timedelta(days=d)).date().isoformat(),
                 "real_name": f"Person {u}", "pc": f"PC-{100+u}"}          # PII removed by privacy layer
            for f, b in base.items():
                v = max(0.0, rng.normal(b, b * 0.12 + 0.2))
                if u in bad and d >= drift_start:                            # gradual malicious drift
                    k = min(1.0, (d - drift_start + 1) / 8)
                    mult = {"after_hours_login": 12, "sensitive_file_access": 9, "file_access_count": 3,
                            "external_email_count": 6, "web_upload_mb": 10}.get(f, 1)
                    v = v * (1 + (mult - 1) * k) + rng.normal(0, 0.3)
                if rng.random() < 0.02:                                      # benign one-off spike
                    v *= rng.uniform(1.6, 2.2)
                r[f] = round(v, 2) if f in ("web_upload_mb", "avg_session_minutes") else int(round(v))
            rows.append(r)
    return pd.DataFrame(rows)
