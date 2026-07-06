"""Source adapter contract. Every adapter: fetch(session, cfg, firms) -> list[Job]."""
from __future__ import annotations
from abc import ABC, abstractmethod
from ..models import Job

class SourceAdapter(ABC):
    name: str = "base"

    @abstractmethod
    def fetch(self, session, cfg: dict, firms: list[dict]) -> list[Job]:
        ...

def make_job(company, title, url, source, location="", snippet="", posting_date="", source_url="") -> Job:
    from ..dedupe import job_uid
    from ..normalize import seniority_from_title, remote_from_text
    from ..classify import categorize
    return Job(
        job_uid=job_uid(company, title, location, url),
        title=title.strip(), company=company.strip(),
        role_category=categorize(title),
        source=source, source_url=source_url or url, application_url=url,
        location=location.strip(), remote_status=remote_from_text(f"{title} {location} {snippet}"),
        seniority=seniority_from_title(title),
        posting_date=posting_date, raw_snippet=snippet[:800],
    )
