"""SQLite persistence layer."""
from __future__ import annotations
import sqlite3, csv, shutil, os
from datetime import date, datetime
from .models import Job

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
  job_uid TEXT PRIMARY KEY, title TEXT, company TEXT, role_category TEXT,
  source TEXT, source_url TEXT, application_url TEXT, location TEXT,
  remote_status TEXT, seniority TEXT, posting_date TEXT,
  first_seen TEXT, last_seen TEXT, status TEXT, raw_snippet TEXT,
  matched_keywords TEXT, confidence TEXT, match_reason TEXT,
  duplicate_group_id TEXT, notes TEXT, alerted INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS run_log (
  run_at TEXT, source TEXT, ok INTEGER, jobs_found INTEGER, error TEXT
);
CREATE INDEX IF NOT EXISTS idx_company ON jobs(company);
CREATE INDEX IF NOT EXISTS idx_status ON jobs(status);
"""

class DB:
    def __init__(self, path: str):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def upsert(self, job: Job) -> str:
        """Insert or refresh a job. Returns 'new' | 'seen' | 'reappeared'."""
        row = self.conn.execute("SELECT status FROM jobs WHERE job_uid=?", (job.job_uid,)).fetchone()
        today = date.today().isoformat()
        if row is None:
            self.conn.execute(
                "INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)",
                tuple(job.to_dict().values()))
            return "new"
        if row["status"] == "disappeared":
            self.conn.execute("UPDATE jobs SET status='reappeared', last_seen=?, alerted=0 WHERE job_uid=?",
                              (today, job.job_uid))
            return "reappeared"
        self.conn.execute("UPDATE jobs SET last_seen=?, status='active' WHERE job_uid=?", (today, job.job_uid))
        return "seen"

    def mark_disappeared(self, seen_uids: set[str], sources: set[str]):
        """Jobs from a scraped source not seen this run -> disappeared."""
        if not sources:
            return
        q = f"SELECT job_uid FROM jobs WHERE status IN ('new','active','reappeared') AND source IN ({','.join('?'*len(sources))})"
        for r in self.conn.execute(q, tuple(sources)).fetchall():
            if r["job_uid"] not in seen_uids:
                self.conn.execute("UPDATE jobs SET status='disappeared' WHERE job_uid=?", (r["job_uid"],))

    def unalerted(self, confidences: tuple[str, ...]) -> list[sqlite3.Row]:
        q = (f"SELECT * FROM jobs WHERE alerted=0 AND status IN ('new','reappeared') "
             f"AND confidence IN ({','.join('?'*len(confidences))}) ORDER BY company, title")
        return self.conn.execute(q, confidences).fetchall()

    def mark_alerted(self, uids: list[str]):
        self.conn.executemany("UPDATE jobs SET alerted=1 WHERE job_uid=?", [(u,) for u in uids])

    def log_run(self, source: str, ok: bool, n: int, error: str = ""):
        self.conn.execute("INSERT INTO run_log VALUES (?,?,?,?,?)",
                          (datetime.now().isoformat(timespec="seconds"), source, int(ok), n, error))

    def consecutive_failures(self, source: str) -> int:
        rows = self.conn.execute(
            "SELECT ok FROM run_log WHERE source=? ORDER BY run_at DESC LIMIT 10", (source,)).fetchall()
        n = 0
        for r in rows:
            if r["ok"]: break
            n += 1
        return n

    def export_csv(self, path: str):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        rows = self.conn.execute("SELECT * FROM jobs ORDER BY first_seen DESC").fetchall()
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            if rows:
                w.writerow(rows[0].keys())
                w.writerows([tuple(r) for r in rows])

    def backup(self, backup_dir: str):
        os.makedirs(backup_dir, exist_ok=True)
        shutil.copy2(self.path, os.path.join(backup_dir, f"tracker_{date.today().isoformat()}.db"))

    def commit(self):
        self.conn.commit()
