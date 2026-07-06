"""Cross-source deduplication."""
from __future__ import annotations
import hashlib, re
from difflib import SequenceMatcher
from .normalize import norm_company, norm_title, norm_location

def job_uid(company: str, title: str, location: str, url: str = "") -> str:
    url_id = extract_url_job_id(url)
    if url_id:
        basis = f"{norm_company(company)}|{url_id}"
    else:
        basis = f"{norm_company(company)}|{norm_title(title)}|{norm_location(location)}"
    return hashlib.sha1(basis.encode()).hexdigest()[:16]

def extract_url_job_id(url: str) -> str:
    if not url:
        return ""
    m = (re.search(r"/jobs?/(\d{5,})", url)
         or re.search(r"gh_jid=(\d+)", url)
         or re.search(r"/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", url)  # lever/ashby uuid
         or re.search(r"_(R?-?\d{4,})(?:\?|$)", url))  # workday req id
    return m.group(1) if m else ""

def duplicate_group(company: str, title: str) -> str:
    return hashlib.sha1(f"{norm_company(company)}|{norm_title(title)}".encode()).hexdigest()[:12]

def is_fuzzy_dup(title_a: str, title_b: str, threshold: float = 0.92) -> bool:
    return SequenceMatcher(None, norm_title(title_a), norm_title(title_b)).ratio() >= threshold

def dedupe_batch(jobs: list) -> list:
    """Collapse dupes inside a single run: exact uid, then fuzzy title within same company."""
    seen_uid, kept = {}, []
    for j in jobs:
        if j.job_uid in seen_uid:
            continue
        fuzzy_hit = next((k for k in kept
                          if norm_company(k.company) == norm_company(j.company)
                          and norm_location(k.location) == norm_location(j.location)
                          and is_fuzzy_dup(k.title, j.title)), None)
        if fuzzy_hit:
            j.duplicate_group_id = fuzzy_hit.duplicate_group_id
            continue
        j.duplicate_group_id = duplicate_group(j.company, j.title)
        seen_uid[j.job_uid] = True
        kept.append(j)
    return kept
