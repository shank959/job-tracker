"""Role classification: keyword rules first, optional LLM second pass."""
from __future__ import annotations
from .normalize import norm_title

CATEGORY_MAP = [
    ("trader",     ("trader", "trading desk", "market mak", "algo trad", "execution")),
    ("researcher", ("research", "alpha", "signal", "portfolio manager")),
    ("developer",  ("developer", "engineer", "c++", "software", "infrastructure", "low latency", "low-latency", "fpga", "sre", "devops")),
    ("risk",       ("risk",)),
    ("analyst",    ("analyst",)),
    ("data_ml",    ("data scien", "machine learning", "ml ")),
]

def categorize(title: str) -> str:
    t = norm_title(title)
    for cat, keys in CATEGORY_MAP:
        if any(k in t for k in keys):
            return cat
    return "other"

def classify(title: str, company_is_relevant: bool, cfg: dict) -> tuple[str, list[str], str]:
    """Return (confidence, matched_keywords, reason)."""
    t = norm_title(title)
    c = cfg["classifier"]
    excluded = [k for k in c["exclude_title_terms"] if k in t]
    if excluded:
        return "low", excluded, f"excluded term(s): {', '.join(excluded)}"
    strong = [k for k in c["strong_title_terms"] if k in t]
    if strong and company_is_relevant:
        return "high", strong, f"strong quant title at quant-finance firm: {', '.join(strong)}"
    if strong:
        return "medium", strong, f"strong quant title, firm relevance unverified: {', '.join(strong)}"
    medium = [k for k in c["medium_title_terms"] if k in t]
    if medium and company_is_relevant:
        return "medium", medium, f"technical title at quant-finance firm: {', '.join(medium)}"
    if medium:
        return "low", medium, "technical title, firm not validated as quant finance"
    return "low", [], "no matching keywords"

def llm_second_pass(jobs: list, cfg: dict) -> None:
    """Optional: upgrade/downgrade medium-confidence jobs with an LLM. No-op without API key."""
    import os, json, requests
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key or not cfg["classifier"].get("llm_second_pass"):
        return
    for job in jobs:
        if job.confidence != "medium":
            continue
        prompt = (f"Company: {job.company}\nTitle: {job.title}\nSnippet: {job.raw_snippet[:500]}\n\n"
                  "Is this a quant-finance role (trading, research, dev, risk at a trading firm, "
                  "hedge fund, market maker, bank markets desk, crypto trading, or energy trading)? "
                  'Answer ONLY JSON: {"quant": true|false, "reason": "..."}')
        try:
            r = requests.post("https://api.anthropic.com/v1/messages",
                headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={"model": cfg["classifier"]["llm_model"], "max_tokens": 200,
                      "messages": [{"role": "user", "content": prompt}]}, timeout=30)
            txt = r.json()["content"][0]["text"].strip().strip("`")
            verdict = json.loads(txt[txt.find("{"):txt.rfind("}") + 1])
            if verdict.get("quant"):
                job.confidence = "high"
                job.match_reason += f" | LLM: {verdict.get('reason','')}"
            else:
                job.confidence = "low"
                job.match_reason += f" | LLM rejected: {verdict.get('reason','')}"
        except Exception:
            pass  # keep keyword verdict on any failure
