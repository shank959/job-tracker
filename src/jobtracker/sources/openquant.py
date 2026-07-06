"""OpenQuant adapter.

OpenQuant has no public API. We fetch the public jobs listing page and parse
embedded structured data (Next.js __NEXT_DATA__ JSON or JSON-LD) when present.
Honors robots.txt via PoliteSession; degrades gracefully to zero results —
never falls back to aggressive scraping.
"""
from __future__ import annotations
import json, re
from .base import SourceAdapter, make_job

class OpenQuantAdapter(SourceAdapter):
    name = "openquant"

    def fetch(self, session, cfg, firms):
        url = cfg["sources"].get("openquant_url", "https://openquant.co/jobs")
        r = session.get(url)
        if r is None or r.status_code != 200:
            return []
        return parse_openquant_html(r.text, url)

def parse_openquant_html(html: str, page_url: str) -> list:
    jobs = []
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if m:
        try:
            data = json.loads(m.group(1))
            jobs += _walk_for_jobs(data, page_url)
        except (ValueError, KeyError):
            pass
    for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        try:
            d = json.loads(m.group(1))
            items = d if isinstance(d, list) else [d]
            for it in items:
                if it.get("@type") == "JobPosting":
                    jobs.append(make_job(
                        company=(it.get("hiringOrganization") or {}).get("name", ""),
                        title=it.get("title", ""), url=it.get("url", page_url),
                        source="openquant",
                        location=_ld_location(it), posting_date=(it.get("datePosted") or "")[:10],
                        source_url=page_url))
        except (ValueError, AttributeError):
            continue
    return [j for j in jobs if j.company and j.title]

def _walk_for_jobs(node, page_url, depth=0):
    """Heuristic walk of __NEXT_DATA__ for job-shaped dicts."""
    out = []
    if depth > 8:
        return out
    if isinstance(node, dict):
        keys = set(node.keys())
        if {"title"} <= keys and ({"company", "companyName", "company_name"} & keys):
            company = node.get("company") or node.get("companyName") or node.get("company_name")
            if isinstance(company, dict):
                company = company.get("name", "")
            url = node.get("applyUrl") or node.get("url") or node.get("slug") or page_url
            if isinstance(url, str) and url.startswith("/"):
                url = "https://openquant.co" + url
            out.append(make_job(company=str(company), title=str(node["title"]), url=str(url),
                                source="openquant", location=str(node.get("location", "")),
                                source_url=page_url))
        for v in node.values():
            out += _walk_for_jobs(v, page_url, depth + 1)
    elif isinstance(node, list):
        for v in node:
            out += _walk_for_jobs(v, page_url, depth + 1)
    return out

def _ld_location(it) -> str:
    loc = it.get("jobLocation")
    if isinstance(loc, list) and loc:
        loc = loc[0]
    if isinstance(loc, dict):
        addr = loc.get("address") or {}
        return ", ".join(x for x in (addr.get("addressLocality"), addr.get("addressCountry")) if x)
    return ""
