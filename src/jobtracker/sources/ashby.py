"""Ashby public posting API: https://api.ashbyhq.com/posting-api/job-board/<slug>"""
from .base import SourceAdapter, make_job

API = "https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=false"

class AshbyAdapter(SourceAdapter):
    name = "ashby"

    def fetch(self, session, cfg, firms):
        jobs = []
        for f in firms:
            slug = f.get("ashby_slug")
            if not slug:
                continue
            data = session.get_json(API.format(slug=slug))
            if not data or "jobs" not in data:
                continue
            for j in data["jobs"]:
                jobs.append(make_job(
                    company=f["company_name"], title=j.get("title", ""),
                    url=j.get("jobUrl") or j.get("applyUrl", ""), source=self.name,
                    location=j.get("location", ""),
                    posting_date=(j.get("publishedAt") or "")[:10]))
        return jobs
