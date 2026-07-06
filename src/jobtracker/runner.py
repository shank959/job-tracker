"""Daily run orchestration."""
from __future__ import annotations
import csv, logging, os
from .db import DB
from .http import PoliteSession
from .classify import classify, llm_second_pass
from .dedupe import dedupe_batch
from .alerts import format_alert, send
from .normalize import norm_company
from .sources.registry import enabled_adapters

log = logging.getLogger("jobtracker.runner")

def load_firms(cfg) -> list[dict]:
    path = cfg["sources"]["enriched_csv"]
    if not os.path.exists(path):
        log.warning("no enriched CSV at %s — run `validate-firms` first; company adapters will be idle", path)
        return []
    with open(path) as f:
        firms = [r for r in csv.DictReader(f) if r.get("is_relevant") == "yes"]
    prio = {"high": 0, "medium": 1, "": 2, "review": 3}
    firms.sort(key=lambda r: prio.get(r.get("priority_level", ""), 2))
    return firms

def passes_filters(job, cfg) -> bool:
    f = cfg["filters"]
    if job.seniority != "unknown" and job.seniority not in f["seniority"]:
        return False
    if job.remote_status == "remote" and not f.get("include_remote", True):
        return False
    locs = f.get("locations") or []
    if locs and job.location:
        if not any(l.lower() in job.location.lower() for l in locs) and job.remote_status != "remote":
            return False
    return True

def run(cfg, dry_run: bool = False) -> dict:
    db = DB(cfg["database"]["path"])
    session = PoliteSession(cfg)
    firms = load_firms(cfg)
    relevant_names = {norm_company(f["company_name"]) for f in firms}
    blocklist = {norm_company(b) for b in cfg.get("blocklist_companies") or []}
    allowlist = {norm_company(a) for a in cfg.get("allowlist_companies") or []}

    all_jobs, seen_uids, scraped_sources, failed_sources = [], set(), set(), []
    for adapter in enabled_adapters(cfg):
        try:
            jobs = adapter.fetch(session, cfg, firms)
            db.log_run(adapter.name, True, len(jobs))
            scraped_sources.add(adapter.name)
            all_jobs += jobs
            log.info("%s: %d jobs", adapter.name, len(jobs))
        except Exception as e:
            db.log_run(adapter.name, False, 0, str(e)[:300])
            log.exception("source %s failed", adapter.name)
            if db.consecutive_failures(adapter.name) >= cfg["scraping"]["error_alert_after_consecutive_failures"]:
                failed_sources.append(adapter.name)

    for job in all_jobs:
        if norm_company(job.company) in blocklist:
            continue
        is_rel = norm_company(job.company) in relevant_names or job.source in ("openquant", "github_tracker")
        conf, kws, reason = classify(job.title, is_rel, cfg)
        if norm_company(job.company) in allowlist:
            conf, reason = "high", reason + " | allowlisted company"
        job.confidence, job.matched_keywords, job.match_reason = conf, ";".join(kws), reason

    all_jobs = [j for j in all_jobs if not j.validate() and passes_filters(j, cfg)]
    all_jobs = dedupe_batch(all_jobs)
    llm_second_pass(all_jobs, cfg)

    counts = {"new": 0, "seen": 0, "reappeared": 0}
    for job in all_jobs:
        seen_uids.add(job.job_uid)
        if not dry_run:
            counts[db.upsert(job)] += 1
    if not dry_run:
        db.mark_disappeared(seen_uids, scraped_sources)
        db.commit()

    confidences = ("high", "medium") if cfg["alerts"]["include_medium_confidence"] else ("high",)
    to_alert = [] if dry_run else db.unalerted(confidences)
    text = format_alert([dict(r) for r in to_alert], cfg)
    if failed_sources:
        text = (text + "\n\n" if text else "") + \
               f"⚠️ sources failing {cfg['scraping']['error_alert_after_consecutive_failures']}+ runs: {', '.join(failed_sources)}"
    if dry_run:
        print(f"[dry-run] fetched={len(all_jobs)} (nothing written, nothing sent)")
        for j in all_jobs[:20]:
            print(f"  [{j.confidence}] {j.company} — {j.title} ({j.source})")
    else:
        if send(text, cfg):
            db.mark_alerted([r["job_uid"] for r in to_alert])
            db.commit()
        db.export_csv(cfg["database"]["export_csv"])
        db.backup(cfg["database"]["backup_dir"])
    return {"fetched": len(all_jobs), **counts, "alerted": len(to_alert), "failed_sources": failed_sources}
