import json, os
from jobtracker.sources.github_trackers import parse_markdown_jobs
from jobtracker.sources.base import make_job

FIX = os.path.join(os.path.dirname(__file__), "fixtures")

def test_markdown_table_parse():
    md = open(os.path.join(FIX, "sample_tracker.md")).read()
    jobs = parse_markdown_jobs(md)
    assert len(jobs) == 4
    assert jobs[0].company == "Jane Street" and "Trader" in jobs[0].title
    assert jobs[1].company == "Jane Street"          # ↳ continuation row
    assert jobs[2].company == "Optiver" and jobs[2].application_url.endswith("12345")

def test_greenhouse_fixture_shape():
    data = json.load(open(os.path.join(FIX, "sample_greenhouse.json")))
    jobs = [make_job("Example", j["title"], j["absolute_url"], "greenhouse",
                     j["location"]["name"], j["content"]) for j in data["jobs"]]
    assert jobs[0].role_category == "developer"
    assert jobs[0].seniority == "full_time"
