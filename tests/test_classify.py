from jobtracker.classify import classify, categorize

def test_high_confidence(cfg):
    conf, kws, _ = classify("Quantitative Researcher", True, cfg)
    assert conf == "high" and "quantitative researcher" in kws

def test_medium_when_firm_unverified(cfg):
    conf, _, _ = classify("Quantitative Researcher", False, cfg)
    assert conf == "medium"

def test_medium_generic_title_at_quant_firm(cfg):
    conf, _, _ = classify("Software Engineer", True, cfg)
    assert conf == "medium"

def test_excluded(cfg):
    conf, _, reason = classify("Quantitative Marketing Analyst", True, cfg)
    assert conf == "low" and "excluded" in reason

def test_categorize():
    assert categorize("Quant Trader") == "trader"
    assert categorize("Low Latency C++ Engineer") == "developer"
    assert categorize("Risk Quant") == "risk"
