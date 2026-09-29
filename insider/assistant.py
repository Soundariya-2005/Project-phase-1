"""Privacy-preserving Risk Assistant: rule-based, answers only with pseudonymous IDs."""
import re

def _fac(u): return ", ".join(f"{f['feature']} ({f['share']*100:.0f}%)" for f in u["factors"][:3]) or "no dominant factor"

def answer(q, res):
    if not res: return "No data analysed yet. Upload a CSV or try the sample data."
    ql = q.lower().strip(); users = res["users"]
    m = re.search(r"u-[0-9a-f]{4,}", ql)
    if m:
        u = next((x for x in users if x["id"].lower() == m.group(0)), None)
        if not u: return "I could not find that pseudonymous ID."
        return (f"{u['id']} is {u['level']} risk (score {u['risk']}, peak {u['peak']}) with {u['anomalous_days']} anomalous days. "
                f"Main contributing factors: {_fac(u)}. Review the activity timeline and verify the business justification.")
    if any(k in ql for k in ("highest", "riskiest", "most risky", "top")):
        u = users[0]; return f"The highest-risk user is {u['id']} ({u['level']}, score {u['risk']}). Main factors: {_fac(u)}."
    if any(k in ql for k in ("critical", "high", "flagged", "anomalous", "who")):
        hi = [u for u in users if u["level"] in ("HIGH", "CRITICAL")]
        return "HIGH/CRITICAL users: " + "; ".join(f"{u['id']} ({u['level']}, {u['risk']})" for u in hi) if hi else "No users are currently HIGH or CRITICAL."
    if any(k in ql for k in ("why", "factor", "reason", "explain")):
        return "Across flagged days the main drivers are " + ", ".join(f"{x['feature']} ({x['share']*100:.0f}%)" for x in res["global_factors"][:3]) + "."
    if any(k in ql for k in ("summary", "overview", "how many")):
        s, d = res["summary"], res["distribution"]
        return f"{s['users']} users, {s['records']} records over {s['days']} days. " + ", ".join(f"{k} {v}" for k, v in d.items()) + "."
    return "Try: 'Who is the highest-risk employee?', 'Which users are critical?', 'Why is U-XXXX risky?' or 'Summary'."
