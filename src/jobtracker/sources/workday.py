"""Workday CxS search API.

Workday career sites expose a JSON endpoint:
  POST https://<tenant>.<dc>.myworkdayjobs.com/wday/cxs/<tenant>/<site>/jobs
The enriched CSV stores the full endpoint in `workday_cxs_url`.
"""
import json
from .base import SourceAdapter, make_job

class WorkdayAdapter(SourceAdapter):
    name = "workday"

    def fetch(self, session, cfg, firms):
        jobs = []
        for f in firms:
            url = f.get("workday_cxs_url")
            if not url:
                continue
            offset, base = 0, url.split("/wday/")[0]
            while offset <= 100:  # cap pagination; quant roles rarely exceed this per firm
                try:
                    r = session.session.post(url, json={"limit": 20, "offset": offset,
                                                        "searchText": "quantitative"},
                                             timeout=session.timeout)
                    data = r.json() if r.status_code == 200 else None
                except Exception:
                    data = None
                if not data or not data.get("jobPostings"):
                    break
                for j in data["jobPostings"]:
                    path = j.get("externalPath", "")
                    jobs.append(make_job(
                        company=f["company_name"], title=j.get("title", ""),
                        url=f"{base}{path}", source=self.name,
                        location=j.get("locationsText", ""),
                        posting_date=""))
                offset += 20
        return jobs
