"""Privacy-preserving layer: data minimization + salted pseudonymization."""
import hashlib, hmac, os

def minimize(df, user_col, date_col, features):
    """Keep only the fields required for behavioural analysis; everything else (PII) is dropped."""
    keep = [user_col, date_col] + features
    dropped = [c for c in df.columns if c not in keep]
    return df[keep].copy(), dropped

def pseudonymize(df, user_col, salt=None, return_mapping=False):
    """Replace real IDs by anonymous IDs (U-XXXX) using HMAC-SHA256 with a per-run random salt.

    If return_mapping=True, also returns a dict of real_user -> pseudonymized_user.
    """
    salt = salt or os.urandom(16)
    real = df[user_col].astype(str)
    mapping, used = {}, set()
    for uid in sorted(real.unique()):
        h = hmac.new(salt, uid.encode(), hashlib.sha256).hexdigest().upper()
        n = 4
        while f"U-{h[:n]}" in used: n += 1
        mapping[uid] = f"U-{h[:n]}"; used.add(mapping[uid])
    out = df.copy(); out[user_col] = real.map(mapping)
    if return_mapping:
        return out, mapping
    return out   # the mapping is intentionally not exposed as a public API result
