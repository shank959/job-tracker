"""Lever public postings API: https://api.lever.co/v0/postings/<slug>?mode=json"""
from .base import SourceAdapter, make_job

API = "https://api.lever.co/v0/postings/{slug}?mode=json"

class LeverAdapter(SourceAdapter):
    name = "lever"

    def fetch(self, session, cfg, firms):
        jobs = []
        for f in firms:
            slug = f.get("lever_slug")
            if not slug:
                continue
            data = session.get_json(API.format(slug=slug))
            if not isinstance(data, list):
                continue
            for j in data:
                cats = j.get("categories") or {}
                jobs.append(make_job(
                    company=f["company_name"], title=j.get("text", ""),
                    url=j.get("hostedUrl", ""), source=self.name,
                    location=cats.get("location", ""),
                    snippet=(j.get("descriptionPlain") or "")[:800]))
        return jobs
