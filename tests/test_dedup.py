from emberforge.compute import compute_factor
from emberforge.dedup import classify, is_syntactic_duplicate, novelty_report, score_correlation
from emberforge.dsl import make_factor


def test_syntactic_duplicate_via_canonicalization():
    a = make_factor("a", "add(close, volume)")
    b = make_factor("b", "add(volume, close)")
    assert is_syntactic_duplicate(a, b)


def test_not_syntactic_duplicate():
    a = make_factor("a", "ts_returns(close, 5)")
    b = make_factor("b", "ts_returns(close, 20)")
    assert not is_syntactic_duplicate(a, b)


def test_empirical_correlation_self_is_one(data):
    s = compute_factor(make_factor("m", "ts_returns(close, 20)"), data)
    corr, overlap = score_correlation(s, s)
    assert abs(corr - 1.0) < 1e-9
    assert overlap > 0


def test_classify_families():
    assert classify(make_factor("m", "ts_returns(close, 20)")) == "momentum"
    assert classify(make_factor("r", "neg(ts_returns(close, 3))")) == "reversal"
    assert classify(make_factor("v", "neg(ts_std(ts_returns(close,1), 20))")) == "volatility"


def test_novelty_report_flags_duplicate(data):
    cand = make_factor("cand", "ts_returns(close, 20)")
    existing = make_factor("existing", "ts_returns(close, 20)")
    cs = compute_factor(cand, data)
    es = compute_factor(existing, data)
    rep = novelty_report(cand, cs, [existing], {"existing": es})
    assert rep.is_duplicate
