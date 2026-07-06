from jobtracker.db import DB
from jobtracker.sources.base import make_job

def test_lifecycle(tmp_path):
    db = DB(str(tmp_path / "t.db"))
    j = make_job("Optiver", "Quant Trader", "https://a.com/1", "greenhouse", "Chicago")
    assert db.upsert(j) == "new"
    assert db.upsert(j) == "seen"
    db.mark_disappeared(set(), {"greenhouse"})
    assert db.upsert(j) == "reappeared"
    rows = db.unalerted(("high", "medium", "low"))
    assert len(rows) == 1
    db.mark_alerted([j.job_uid])
    assert not db.unalerted(("high", "medium", "low"))
