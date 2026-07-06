"""Greenhouse public board API: https://boards-api.greenhouse.io/v1/boards/<slug>/jobs"""
from .base import SourceAdapter, make_job

API = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"

class GreenhouseAdapter(SourceAdapter):
    name = "greenhouse"

    def fetch(self, session, cfg, firms):
        jobs = []
        for f in firms:
            slug = f.get("greenhouse_slug")
            if not slug:
                continue
            data = session.get_json(API.format(slug=slug))
            if not data or "jobs" not in data:
                continue
            for j in data["jobs"]:
                jobs.append(make_job(
                    company=f["company_name"], title=j.get("title", ""),
                    url=j.get("absolute_url", ""), source=self.name,
                    location=(j.get("location") or {}).get("name", ""),
                    snippet=(j.get("content") or "")[:800],
                    posting_date=(j.get("updated_at") or "")[:10]))
        return jobs
