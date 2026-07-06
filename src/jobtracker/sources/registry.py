"""Which adapters run, in what order."""
from .greenhouse import GreenhouseAdapter
from .lever import LeverAdapter
from .ashby import AshbyAdapter
from .workday import WorkdayAdapter
from .github_trackers import GithubTrackerAdapter
from .openquant import OpenQuantAdapter

def enabled_adapters(cfg: dict):
    s = cfg["sources"]
    order = [("greenhouse", GreenhouseAdapter), ("lever", LeverAdapter), ("ashby", AshbyAdapter),
             ("workday", WorkdayAdapter), ("github_trackers", GithubTrackerAdapter),
             ("openquant", OpenQuantAdapter)]
    return [cls() for key, cls in order if s.get(key)]
