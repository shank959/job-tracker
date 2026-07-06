"""Seed-firm validation + enrichment.

Reads the seed CSV, and for each firm:
  1. Applies relevance heuristics (category_guess, name signals).
  2. Probes ATS endpoints (greenhouse -> lever -> ashby) with slug candidates.
  3. Falls back to any career_page_url already in the seed.
Writes data/enriched_companies.csv. Never deletes firms — rejects get a reason.

Run:  python -m jobtracker.cli validate-firms [--only-priority high] [--limit N]
Re-run any time; it only re-probes rows whose source_confidence != 'verified'
unless --force is passed.
"""
from __future__ import annotations
import csv, os, logging
from datetime import date
from .normalize import norm_company, slug_candidates
from .http import PoliteSession

log = logging.getLogger("jobtracker.validate")

ENRICHED_FIELDS = [
    "company_name", "normalized_company_name", "is_relevant", "relevance_reason",
    "company_category", "official_careers_url", "job_board_type", "job_board_query_url",
    "greenhouse_slug", "lever_slug", "ashby_slug", "workday_cxs_url",
    "supported_locations", "source_confidence", "scrape_method", "scrape_frequency",
    "last_validated_at", "validation_notes", "priority_level",
]

RELEVANT_CATEGORIES = {
    "prop trading or market making", "hedge fund or asset manager",
    "bank or broker dealer", "energy or commodities", "crypto or digital assets",
}
NAME_SIGNALS = ("trading", "capital", "securities", "asset", "quant", "markets",
                "arbitrage", "alpha", "fund", "invest", "exchange", "commodities")

# Curated slug hints for well-known firms. These are CANDIDATES ONLY —
# the probe verifies with a live 200 + valid JSON before anything is trusted.
KNOWN_HINTS: dict[str, dict] = {
    "hudson river trading": {"greenhouse": "wehrtyou"},
    "jump trading": {"greenhouse": "jumptrading"},
    "old mission": {"greenhouse": "oldmissioncapital"},
    "five rings": {"greenhouse": "fiveringsllc"},
    "tower research": {"greenhouse": "towerresearchcapital"},
    "drw": {"greenhouse": "drweng"},
    "akuna": {"greenhouse": "akunacapital"},
    "voleon": {"greenhouse": "voleon"},
    "pdt": {"greenhouse": "pdtpartners"},
    "radix trading": {"greenhouse": "radixuniversity"},
    "virtu financial": {"greenhouse": "virtu"},
    "flow traders": {"greenhouse": "flowtraders"},
    "imc": {"greenhouse": "imc"},
    "wintermute": {"lever": "wintermute-trading"},
    "keyrock": {"lever": "keyrock"},
}

def relevance(row: dict) -> tuple[bool, str, str]:
    cat = (row.get("category_guess") or "").strip().lower()
    name = norm_company(row.get("company_name", ""))
    if cat in RELEVANT_CATEGORIES:
        return True, f"seed category '{cat}'", cat
    hits = [s for s in NAME_SIGNALS if s in name]
    if hits:
        return True, f"name signals: {', '.join(hits)}", cat or "needs review"
    if cat == "tech or data provider":
        return False, "tech/data provider — include only if it serves trading; needs manual review", cat
    return False, "no category match and no quant-finance name signal — needs manual review", cat or "unknown"

def probe_firm(session: PoliteSession, name: str, hints: dict) -> dict:
    """Try greenhouse, lever, ashby slug candidates. Return first verified board."""
    cands = slug_candidates(name)
    gh = [hints["greenhouse"]] + cands if "greenhouse" in hints else cands
    for slug in gh[:4]:
        d = session.get_json(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs")
        if d and "jobs" in d:
            return {"job_board_type": "greenhouse", "greenhouse_slug": slug,
                    "job_board_query_url": f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
                    "scrape_method": "api", "source_confidence": "verified"}
    lv = [hints["lever"]] + cands if "lever" in hints else cands
    for slug in lv[:4]:
        d = session.get_json(f"https://api.lever.co/v0/postings/{slug}?mode=json")
        if isinstance(d, list):
            return {"job_board_type": "lever", "lever_slug": slug,
                    "job_board_query_url": f"https://api.lever.co/v0/postings/{slug}?mode=json",
                    "scrape_method": "api", "source_confidence": "verified"}
    for slug in cands[:4]:
        d = session.get_json(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
        if d and "jobs" in d:
            return {"job_board_type": "ashby", "ashby_slug": slug,
                    "job_board_query_url": f"https://api.ashbyhq.com/posting-api/job-board/{slug}",
                    "scrape_method": "api", "source_confidence": "verified"}
    return {}

def enrich(cfg: dict, probe: bool = True, only_priority: str = "", limit: int = 0, force: bool = False):
    seed_path, out_path = cfg["sources"]["firms_csv"], cfg["sources"]["enriched_csv"]
    existing: dict[str, dict] = {}
    if os.path.exists(out_path):
        with open(out_path) as f:
            existing = {r["normalized_company_name"]: r for r in csv.DictReader(f)}
    session = PoliteSession(cfg) if probe else None
    out, probed = [], 0
    with open(seed_path) as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        name = row["company_name"].strip()
        norm = norm_company(name)
        prev = existing.get(norm, {})
        rec = {k: prev.get(k, "") for k in ENRICHED_FIELDS}
        rec.update(company_name=name, normalized_company_name=norm,
                   priority_level=row.get("priority_level", ""))
        ok, reason, cat = relevance(row)
        rec.update(is_relevant="yes" if ok else "needs_review",
                   relevance_reason=reason, company_category=cat)
        # carry over seed-provided URLs as fallback
        if row.get("career_page_url") and not rec["official_careers_url"]:
            rec["official_careers_url"] = row["career_page_url"]
            rec["source_confidence"] = rec["source_confidence"] or "inferred"
        skip = (only_priority and row.get("priority_level") != only_priority) \
               or (limit and probed >= limit) \
               or (prev.get("source_confidence") == "verified" and not force) \
               or not ok
        if probe and not skip:
            found = probe_firm(session, name, KNOWN_HINTS.get(norm, {}))
            probed += 1
            if found:
                rec.update(found)
            else:
                rec["source_confidence"] = rec["source_confidence"] or "needs_review"
                rec["validation_notes"] = "no public ATS endpoint found; set workday_cxs_url or careers URL manually"
        rec["scrape_frequency"] = rec["scrape_frequency"] or "daily"
        rec["last_validated_at"] = date.today().isoformat()
        out.append(rec)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=ENRICHED_FIELDS)
        w.writeheader(); w.writerows(out)
    verified = sum(1 for r in out if r["source_confidence"] == "verified")
    log.info("enriched %d firms (%d verified boards, %d probed this run)", len(out), verified, probed)
    return out
