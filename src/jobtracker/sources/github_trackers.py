"""Parse community GitHub job trackers (raw README markdown tables + link lists)."""
from __future__ import annotations
import re
from .base import SourceAdapter, make_job

MD_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")

class GithubTrackerAdapter(SourceAdapter):
    name = "github_tracker"

    def fetch(self, session, cfg, firms):
        jobs = []
        for url in cfg["sources"].get("github_tracker_urls", []):
            r = session.get(url)
            if r is None or r.status_code != 200:
                continue
            jobs += parse_markdown_jobs(r.text, source_url=url)
        return jobs

def parse_markdown_jobs(md: str, source_url: str = "") -> list:
    """Extract jobs from markdown tables of the shape | Company | Role | Location | Link |."""
    jobs, last_company = [], ""
    for line in md.splitlines():
        line = line.strip()
        if not line.startswith("|") or set(line) <= {"|", "-", " ", ":"}:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2 or cells[0].lower() in ("company", "name", "firm"):
            continue
        company = _clean(cells[0]) or last_company     # "↳" continuation rows
        if cells[0] in ("↳", "") or "↳" in cells[0]:
            company = last_company
        last_company = company
        title = _clean(cells[1])
        location = _clean(cells[2]) if len(cells) > 2 else ""
        link = ""
        for c in cells:
            m = MD_LINK.search(c) or re.search(r"href=[\"'](https?://[^\"']+)", c)
            if m:
                link = m.group(2) if m.re is MD_LINK else m.group(1)
                if "apply" in c.lower() or c is cells[-1] or c is cells[-2]:
                    break
        if company and title and link:
            jobs.append(make_job(company=company, title=title, url=link,
                                 source="github_tracker", location=location, source_url=source_url))
    return jobs

def _clean(cell: str) -> str:
    cell = MD_LINK.sub(r"\1", cell)                    # keep link text
    cell = re.sub(r"<[^>]+>", "", cell)                # strip html
    cell = re.sub(r"[*_`~]", "", cell)
    return cell.replace("**", "").strip(" -–—")
