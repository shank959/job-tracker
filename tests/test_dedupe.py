from jobtracker.dedupe import job_uid, is_fuzzy_dup, dedupe_batch, extract_url_job_id
from jobtracker.sources.base import make_job

def test_uid_stable_across_sources():
    a = job_uid("Jane Street Capital LLC", "Quantitative Trader (2026)", "New York, NY")
    b = job_uid("Jane Street", "Quantitative Trader", "NYC")
    assert a == b

def test_url_job_id():
    assert extract_url_job_id("https://boards.greenhouse.io/x/jobs/4012345") == "4012345"
    assert extract_url_job_id("https://x.com/careers?gh_jid=987654") == "987654"

def test_fuzzy():
    assert is_fuzzy_dup("Quantitative Developer - Low Latency", "Quantitative Developer – Low-Latency")
    assert not is_fuzzy_dup("Quantitative Developer", "Quantitative Researcher")

def test_dedupe_batch():
    j1 = make_job("Optiver", "Quant Trader", "https://a.com/1", "greenhouse", "Chicago")
    j2 = make_job("Optiver US LLC", "Quant Trader (2026)", "https://b.com/2", "openquant", "Chicago, IL")
    j3 = make_job("Optiver", "Quant Researcher", "https://a.com/3", "greenhouse", "Chicago")
    kept = dedupe_batch([j1, j2, j3])
    assert len(kept) == 2
