"""Job record schema + validation."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import date

REQUIRED = ("job_uid", "title", "company", "source", "application_url")

@dataclass
class Job:
    job_uid: str                 # stable unique id (hash or source id)
    title: str
    company: str
    role_category: str = ""      # trader / researcher / developer / risk / support / other
    source: str = ""             # greenhouse | lever | ashby | workday | github_tracker | openquant
    source_url: str = ""
    application_url: str = ""
    location: str = ""
    remote_status: str = ""      # onsite | remote | hybrid | unknown
    seniority: str = "unknown"   # internship | new_grad | full_time | experienced | unknown
    posting_date: str = ""       # ISO date if the source exposes it
    first_seen: str = field(default_factory=lambda: date.today().isoformat())
    last_seen: str = field(default_factory=lambda: date.today().isoformat())
    status: str = "new"          # new | active | disappeared | reappeared
    raw_snippet: str = ""
    matched_keywords: str = ""   # semicolon-joined
    confidence: str = "low"      # high | medium | low
    match_reason: str = ""
    duplicate_group_id: str = ""
    notes: str = ""

    def validate(self) -> list[str]:
        errs = [f"missing {f}" for f in REQUIRED if not getattr(self, f)]
        if self.confidence not in ("high", "medium", "low"):
            errs.append(f"bad confidence {self.confidence}")
        return errs

    def to_dict(self) -> dict:
        return asdict(self)
