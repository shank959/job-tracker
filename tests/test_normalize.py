from jobtracker.normalize import norm_company, norm_title, norm_location, seniority_from_title

def test_company_suffixes():
    assert norm_company("Jane Street Capital, LLC") == norm_company("Jane Street")
    assert norm_company("IMC Trading B.V.") == norm_company("IMC Trading")

def test_title_noise():
    assert norm_title("Quantitative Trader (2026 Start)") == "quantitative trader"
    assert norm_title("Sr. Quant Developer") == "senior quant developer"

def test_location_alias():
    assert norm_location("NYC") == "new york"
    assert norm_location("Singapore, SG") == "singapore"

def test_seniority():
    assert seniority_from_title("Quant Trading Intern") == "internship"
    assert seniority_from_title("Graduate Quantitative Researcher") == "new_grad"
    assert seniority_from_title("Senior C++ Engineer") == "experienced"
    assert seniority_from_title("Quantitative Developer") == "full_time"
