"""Company / title / location normalization used by dedup and matching."""
import re

# Tokens stripped only from the END of a name, iteratively.
# "Jane Street Capital, LLC" -> "jane street"; "Optiver US LLC" -> "optiver".
# Deliberately does NOT strip "trading"/"securities" mid-name identity words ambiguity is worse.
_TRAILING = {"llc", "llp", "lp", "ltd", "limited", "inc", "incorporated", "corp",
             "corporation", "plc", "gmbh", "bv", "sa", "ag", "pte", "pty", "co",
             "company", "group", "holdings", "holding", "partners", "partner",
             "capital", "management", "asset", "assets", "investments", "investment",
             "us", "usa", "uk", "europe", "americas", "international", "global"}

def norm_company(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[&]", " and ", s)
    s = re.sub(r"[^a-z0-9 ]", "", s)
    tokens = s.split()
    while len(tokens) > 1 and tokens[-1] in _TRAILING:
        tokens.pop()
    return " ".join(tokens)

def norm_title(title: str) -> str:
    s = title.lower().strip()
    s = re.sub(r"\(.*?\)", " ", s)                       # drop parentheticals (req ids, locations)
    s = re.sub(r"\b(20\d\d|q[1-4])\b", " ", s)           # drop years/quarters
    s = re.sub(r"[^a-z0-9+ ]", " ", s)
    s = re.sub(r"\b(sr|senior)\b", "senior", s)
    s = re.sub(r"\b(jr|junior)\b", "junior", s)
    return re.sub(r"\s+", " ", s).strip()

def norm_location(loc: str) -> str:
    s = (loc or "").lower().strip()
    s = re.sub(r"[^a-z0-9, ]", " ", s)
    s = s.split(",")[0].strip()                          # city only
    aliases = {"nyc": "new york", "ny": "new york", "sf": "san francisco", "hk": "hong kong", "sg": "singapore"}
    return aliases.get(s, s)

def slug_candidates(company: str) -> list[str]:
    """Guess ATS board slugs for a company name (verified later by probing)."""
    base = norm_company(company)
    tight = base.replace(" ", "")
    dashed = base.replace(" ", "-")
    first = base.split(" ")[0] if base else ""
    out, seen = [], set()
    for c in (tight, dashed, base.replace(" ", ""), first):
        if c and c not in seen:
            seen.add(c); out.append(c)
    return out

def seniority_from_title(title: str) -> str:
    t = title.lower()
    if any(k in t for k in ("intern", "internship", "co-op", "coop", "summer analyst", "off-cycle", "off cycle")):
        return "internship"
    if any(k in t for k in ("new grad", "graduate", "campus", "entry level", "entry-level", "junior", "early career", "analyst program")):
        return "new_grad"
    if any(k in t for k in ("senior", "staff", "principal", "lead", "head of", "director", "vp", "vice president", "managing")):
        return "experienced"
    return "full_time"

def remote_from_text(text: str) -> str:
    t = text.lower()
    if "hybrid" in t: return "hybrid"
    if "remote" in t: return "remote"
    return "unknown"
