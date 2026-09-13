"""Data, causal computation, and evidence-boundary regressions."""

import json

import numpy as np
import pandas as pd
import pytest

from emberforge.compute import PreprocessConfig, compute_factor
from emberforge.data.schema import DatasetMetadata, MarketData
from emberforge.dsl import make_factor
from emberforge.export import from_native_bundle, validate_bundle
from emberforge.registry.holdout import split_by_fraction
from emberforge.stats.multiple_testing import benjamini_hochberg, holm


def _data(columns=("A", "B", "C", "D"), **metadata):
    index = pd.date_range("2020-01-01", periods=5, tz="UTC")
    close = pd.DataFrame([[1., 3., 2., 100.]] * 5, index=index, columns=columns)
    return MarketData({"close": close}, DatasetMetadata(source="audit", **metadata))


def test_fingerprint_binds_symbol_labels_and_adjustment():
    assert _data().metadata.fingerprint != _data(columns=("W", "X", "Y", "Z")).metadata.fingerprint
    assert _data().metadata.fingerprint != _data(adjustment="split").metadata.fingerprint


def test_returns_do_not_fill_missing_prices():
    data = _data()
    data.panels["close"].iloc[2, 0] = np.nan
    assert data.field("returns").iloc[2:4, 0].isna().all()


@pytest.mark.parametrize("horizon", [0, -1, 1.5, True])
def test_forward_return_horizon_is_positive_integer(horizon):
    with pytest.raises(ValueError):
        _data().forward_returns(horizon)


def test_timezone_aware_date_subset():
    data = _data()
    subset = data.subset_by_date(start=data.index[1], end=data.index[3])
    assert subset.index.equals(data.index[1:4])


@pytest.mark.parametrize("kwargs", [{"execution_lag": -1}, {"execution_lag": 1.5},
    {"min_coverage": 1.1}, {"winsorize_p": 0.6}])
def test_invalid_preprocessing_fails(kwargs):
    with pytest.raises(ValueError):
        PreprocessConfig(**kwargs)


def test_nested_cross_section_uses_only_eligible_names():
    data = _data()
    elig = pd.DataFrame([[True, True, False, False]] * 5, index=data.index, columns=data.symbols)
    config = PreprocessConfig(normalize=False, winsorize_p=None)
    score = compute_factor(make_factor("rank", "ts_mean(cs_rank(close), 2)"), data, config, elig)
    assert score.iloc[-1]["B"] == 2.0


def test_coverage_denominator_is_current_eligible_universe():
    data = _data()
    elig = pd.DataFrame([[True, False, False, False]] * 5, index=data.index, columns=data.symbols)
    score = compute_factor(make_factor("raw", "close"), data,
                           PreprocessConfig(normalize=False, winsorize_p=None), elig)
    assert score["A"].notna().all()


@pytest.mark.parametrize("function", [benjamini_hochberg, holm])
def test_missing_pvalue_does_not_poison_valid_tests(function):
    result = function([0.001, np.nan, 0.8])
    assert result[0].reject
    assert result[0].p_adjusted == pytest.approx(0.003)
    assert result[1].p_adjusted == 1.0


@pytest.mark.parametrize("train,valid", [(0., .2), (.8, .3), (-.2, .2), (np.nan, .2)])
def test_invalid_data_split_fails(train, valid):
    with pytest.raises(ValueError):
        split_by_fraction(_data().index, train=train, valid=valid)


def test_malformed_checksums_return_validation_failure(tmp_path):
    from test_validator import _export
    out = _export(tmp_path)
    (out / "checksums.txt").write_text("malformed\n", encoding="utf-8")
    assert not validate_bundle(out).ok


def test_array_json_returns_validation_failure(tmp_path):
    from test_validator import _export
    out = _export(tmp_path)
    (out / "factor.json").write_text("[]", encoding="utf-8")
    assert not validate_bundle(out).ok


def test_conversion_refuses_tampered_native_bundle(tmp_path):
    from test_validator import _export
    out = _export(tmp_path)
    factor = json.loads((out / "factor.json").read_text(encoding="utf-8"))
    factor["expression"] = "ts_returns(close, 1)"
    (out / "factor.json").write_text(json.dumps(factor), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid|validation"):
        from_native_bundle(out)


def test_initial_loss_counts_in_drawdown():
    from emberforge.analytics.portfolio_backtest import PortfolioSpec, backtest_portfolio
    scores = pd.DataFrame([[0., 1.]] * 3, columns=["A", "B"])
    returns = pd.DataFrame([[0., -.1], [0., .01], [0., .02]], columns=scores.columns)
    result = backtest_portfolio(scores, returns, cost_bps=0,
        spec=PortfolioSpec(quantiles=2))
    assert result.max_drawdown < 0


@pytest.mark.parametrize("method", ["pearson", "spearman"])
def test_vectorized_ic_matches_pairwise_reference(method):
    from emberforge.analytics.ic import ic_series
    rng = np.random.default_rng(15)
    scores = pd.DataFrame(rng.integers(0, 5, (30, 8)), dtype=float)
    labels = pd.DataFrame(rng.normal(size=(30, 8)))
    scores.iloc[2, :5] = np.nan
    labels.iloc[4, :4] = np.nan
    scores.iloc[7, :] = 1.0
    expected = {}
    for timestamp in scores.index:
        pair = pd.concat([scores.loc[timestamp], labels.loc[timestamp]], axis=1).dropna()
        if len(pair) >= 3:
            expected[timestamp] = pair.iloc[:, 0].corr(pair.iloc[:, 1], method=method)
    pd.testing.assert_series_equal(ic_series(scores, labels, method), pd.Series(expected).dropna(),
                                    check_names=False, atol=1e-12)


def test_declared_gross_exposure_scales_portfolio_returns():
    from emberforge.analytics.portfolio_backtest import PortfolioSpec, backtest_portfolio
    scores = pd.DataFrame([[0., 1.]] * 3, columns=["A", "B"])
    returns = pd.DataFrame([[0., .04], [0., -.01], [0., .02]], columns=scores.columns)
    full = backtest_portfolio(scores, returns, PortfolioSpec(quantiles=2), cost_bps=0)
    half = backtest_portfolio(scores, returns, PortfolioSpec(quantiles=2, gross_exposure=.5), cost_bps=0)
    assert half.ann_return == pytest.approx(full.ann_return / 2)
    assert full.total_return == pytest.approx(1.02 * .995 * 1.01 - 1)


def test_holdout_reservation_enforces_cap_concurrently(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    from emberforge.registry import ExperimentRegistry
    from emberforge.registry.holdout import BudgetExceeded, HoldoutGovernor, ResearchBudget
    reg = ExperimentRegistry(tmp_path / "r.sqlite3")
    def attempt(_):
        try:
            HoldoutGovernor(reg, "fam", ResearchBudget(max_holdout_access=1)).access_locked_test(None, "test")
            return True
        except BudgetExceeded:
            return False
    with ThreadPoolExecutor(max_workers=6) as pool:
        assert sum(pool.map(attempt, range(12))) == 1
    assert reg.holdout_access_count("fam") == 1


@pytest.mark.parametrize("value", [None, float("nan"), float("inf")])
def test_missing_statistical_evidence_never_promotes(value):
    from emberforge.research.decision import DecisionState, decide
    result = decide("x", {"mean_ic": .1, "ic_t_stat": 5., "turnover": .2},
                    is_duplicate=False, fdr_reject=True, dsr=value, nearest_corr=None)
    assert result.state != DecisionState.RESEARCH_SURVIVOR


def test_pipeline_does_not_expose_locked_test_to_study(tmp_path, monkeypatch):
    import emberforge.pipeline as pipeline
    from emberforge.research.pipeline import FamilyStudy
    data = _data()
    seen = []
    def study(family, specs, subset, registry, **kwargs):
        seen.append(subset.index[-1])
        return FamilyStudy(family, [], float("nan"), [])
    monkeypatch.setattr(pipeline, "run_family_study", study)
    summary = pipeline.run_pipeline(tmp_path, data=data, families=["momentum"], auto_approve=False)
    assert seen == [data.index[3]]
    assert pd.Timestamp(summary["locked_test_start"]) == data.index[4]


def test_current_geld_csv_loads_readonly(tmp_path):
    from emberforge.data import load_geld_csv
    path = tmp_path / "bars.csv.gz"
    rows = pd.DataFrame({"timestamp": pd.date_range("2020-01-01", periods=3), "symbol": "A",
                         "open": 1., "high": 2., "low": 1., "close": 2., "volume": 5.})
    rows.to_csv(path, index=False)
    before = path.read_bytes()
    data = load_geld_csv(path, feed="sip", adjustment="all")
    assert len(data.index) == 3 and data.metadata.feed == "sip"
    assert not data.has_field("vwap")
    assert path.read_bytes() == before


def test_family_correction_keeps_prior_failed_attempts(small_data, tmp_path, monkeypatch):
    import emberforge.research.pipeline as pipeline
    from emberforge.registry import ExperimentRecord, ExperimentRegistry
    registry = ExperimentRegistry(tmp_path / "r.sqlite3")
    for i in range(9):
        registry.record(ExperimentRecord(factor_id=f"failed{i}", family="family", expression="close",
                                          expression_hash="h", status="invalid"))
    monkeypatch.setattr(pipeline, "ic_pvalue", lambda *args: .01)
    study = pipeline.run_family_study("family", [make_factor("candidate", "ts_returns(close, 5)")],
                                     small_data, registry)
    statistics = study.results[0].report["statistics"]
    assert statistics["p_fdr"] == pytest.approx(.1)
    assert not statistics["fdr_reject"]


def test_export_preserves_custom_preprocessing(small_data, tmp_path):
    from dataclasses import asdict

    from emberforge.analytics import evaluate_factor
    from emberforge.export import export_candidate
    spec = make_factor("custom", "ts_returns(close, 5)")
    config = PreprocessConfig(min_coverage=.7, normalize=False, execution_lag=2)
    evaluation = evaluate_factor(spec, small_data, preprocess=config)
    out = export_candidate(spec, tmp_path / "bundle", evaluation_metrics=evaluation.to_metrics(),
        statistics={}, lineage=[], novelty={}, data_provenance={}, report_md="report", approved=True,
        trial_count=1, holdout_views=0)
    assert from_native_bundle(out)["preprocessing"] == asdict(config)
