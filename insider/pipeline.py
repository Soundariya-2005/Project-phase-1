"""Adaptive profiling -> Isolation Forest -> progressive risk -> SHAP -> early warning."""
import time
import numpy as np, pandas as pd
from sklearn.ensemble import IsolationForest
from .privacy import minimize, pseudonymize

WARMUP = 5
LEVELS = [(75, "CRITICAL"), (50, "HIGH"), (25, "MEDIUM"), (0, "LOW")]

def level_of(score):
    return next(name for th, name in LEVELS if score >= th)

def detect_columns(df):
    cols = list(df.columns)
    user = next((c for c in cols if c.lower() in ("user", "user_id", "userid", "employee", "employee_id", "uid")), None) \
        or next((c for c in cols if any(k in c.lower() for k in ("user", "employee"))), None) or cols[0]
    date = next((c for c in cols if any(k in c.lower() for k in ("date", "day", "time"))), None)
    if date is None: raise ValueError("No date column found")
    feats = [c for c in cols if c not in (user, date) and pd.api.types.is_numeric_dtype(df[c])]
    if not feats: raise ValueError("No numeric behavioural feature columns found")
    return user, date, feats

def adaptive_profile(g, feats, alpha):
    """EWMA baseline per user/feature: baseline(t) = (1-a)*baseline(t-1) + a*x(t).
    Returns the deviation (z-score) of today's value against the baseline held *before* today."""
    X = g[feats].to_numpy(float)
    dev = np.zeros_like(X)
    w = min(WARMUP, len(X))
    base, var = X[:w].mean(0), X[:w].var(0) + 1e-6
    for t in range(w, len(X)):
        sd = np.sqrt(var + (0.05 * np.abs(base)) ** 2 + 1e-6)
        dev[t] = (X[t] - base) / sd
        # Controlled learning: suspicious days (|z| > 3 on any feature) are absorbed at only 10% of the
        # learning rate, so persistent malicious drift is not silently accepted as the new normal.
        a = alpha * (0.1 if np.abs(dev[t]).max() > 3 else 1.0)
        d = np.clip(X[t] - base, -3 * sd, 3 * sd)
        base = base + a * d
        var = (1 - a) * var + a * d * d
    return dev

def run(df, alpha=0.15, contamination=0.07, decay=0.88, gain=0.13, seed=42):
    t0 = time.time()
    user_col, date_col, feats = detect_columns(df)
    df = df.copy(); df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col]).sort_values([user_col, date_col]).reset_index(drop=True)
    df[feats] = df[feats].fillna(0)

    # 1. privacy layer
    real_names = df[[user_col, "real_name"]].drop_duplicates().set_index(user_col)["real_name"].to_dict() if "real_name" in df.columns else {}
    clean, dropped = minimize(df, user_col, date_col, feats)
    anon, user_mapping = pseudonymize(clean, user_col, return_mapping=True)
    identity_lookup = {anon_id: real_names.get(real_id, real_id) for real_id, anon_id in user_mapping.items()}
    anon = anon.rename(columns={user_col: "uid", date_col: "date"})

    # 2. adaptive profiling -> personal deviation features
    D = np.zeros((len(anon), len(feats)))
    for uid, g in anon.groupby("uid", sort=False):
        D[g.index.to_numpy()] = adaptive_profile(g, feats, alpha)
    D = np.abs(np.clip(D, -10, 10))
    mask = (anon.groupby("uid").cumcount() >= WARMUP).to_numpy()

    # 3. Isolation Forest on deviation vectors (warm-up rows excluded)
    iso = IsolationForest(n_estimators=150, contamination=float(contamination), random_state=seed).fit(D[mask])
    raw = np.zeros(len(anon)); flag = np.zeros(len(anon), bool)
    raw[mask] = -iso.score_samples(D[mask]); flag[mask] = iso.predict(D[mask]) == -1
    thr = -iso.offset_
    lo = np.median(raw[mask])
    x = np.clip((raw - lo) / (thr - lo + 1e-9), 0, None)          # 0 = typical day, 1 = at threshold
    rel = np.clip((raw - thr) / (raw[mask].max() - thr + 1e-9), 0, 1)
    # flagged days give strong evidence; sub-threshold days give small graded evidence (cubic damping)
    strength = np.where(flag, 0.6 + 0.4 * rel, 0.6 * np.clip(x, 0, 1) ** 3) * mask

    # 4. SHAP explanation (fallback: normalised deviation)
    contrib, method = D.copy(), "deviation (SHAP unavailable)"
    try:
        import shap
        sv = np.asarray(shap.TreeExplainer(iso).shap_values(D))
        contrib, method = np.clip(-sv, 0, None), "SHAP"        # negative SHAP => pushes towards "anomalous"
    except Exception:
        pass
    contrib[~mask] = 0

    # 5. progressive risk: risk(t) = decay*risk(t-1) + gain*100*anomaly_strength(t), capped 0-100
    risk = np.zeros(len(anon))
    for uid, g in anon.groupby("uid", sort=False):
        r = 0.0
        for k in g.index.to_numpy():
            r = min(100.0, decay * r + gain * 100 * strength[k]); risk[k] = r  # gain scaled to 0-100

    # 6. per-user results + early warning
    users = []
    for uid, g in anon.groupby("uid", sort=False):
        idx = g.index.to_numpy(); c = contrib[idx[-14:]].sum(0)
        top = sorted(zip(feats, c / (c.sum() + 1e-9)), key=lambda x: -x[1])[:4] if c.sum() > 0 else []
        final = float(risk[idx[-1]])
        users.append(dict(id=uid, risk=round(final, 1), peak=round(float(risk[idx].max()), 1),
                          level=level_of(final), anomalous_days=int(flag[idx].sum()),
                          trend=[round(float(x), 1) for x in risk[idx]],
                          factors=[dict(feature=f, share=round(float(s), 3)) for f, s in top]))
    users.sort(key=lambda u: -u["risk"])
    dist = {n: sum(u["level"] == n for u in users) for _, n in reversed(LEVELS)}
    gf = contrib[flag].sum(0) if flag.any() else np.zeros(len(feats))
    gtop = sorted(zip(feats, gf / (gf.sum() + 1e-9)), key=lambda x: -x[1])
    days = sorted(anon["date"].unique())
    return dict(
        summary=dict(users=len(users), records=len(anon), days=len(days),
                     flagged=sum(u["level"] in ("HIGH", "CRITICAL") for u in users),
                     features=feats, user_col=user_col, date_col=date_col, dropped_pii=dropped,
                     explain_method=method, seconds=round(time.time() - t0, 1),
                     params=dict(alpha=alpha, contamination=contamination, decay=decay, gain=gain)),
        distribution=dist, users=users, days=[str(pd.Timestamp(d).date()) for d in days],
        global_factors=[dict(feature=f, share=round(float(s), 3)) for f, s in gtop],
        identity_lookup=identity_lookup)
