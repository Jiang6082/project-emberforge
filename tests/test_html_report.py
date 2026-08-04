from emberforge.report import family_report_html


def _rows():
    return [
        {"factor_id": "momentum_20", "family": "momentum", "decision": "research_survivor",
         "metrics": {"mean_ic": 0.073, "ic_t_stat": 4.68, "sharpe": 2.53, "turnover": 0.17},
         "statistics": {"p_fdr": 0.0001, "fdr_reject": True, "dsr": 0.71, "pbo": 0.21,
                        "white_rc_p": 0.03, "spa_p": 0.04}},
        {"factor_id": "noise_1bar", "family": "momentum", "decision": "rejected_in_development",
         "metrics": {"mean_ic": -0.002, "ic_t_stat": -0.13, "sharpe": -0.74, "turnover": 0.9},
         "statistics": {"p_fdr": 0.9, "fdr_reject": False, "dsr": 0.0}},
        {"factor_id": "momentum_20_dup", "family": "momentum", "decision": "duplicate",
         "metrics": {"mean_ic": 0.06, "ic_t_stat": 3.9, "sharpe": 1.6, "turnover": 0.2},
         "statistics": {"p_fdr": 0.0015, "fdr_reject": True, "dsr": 0.29}},
    ]


def test_html_is_self_contained_and_valid():
    doc = family_report_html("momentum_family", _rows(), meta={"trial_count": 3, "data": "synthetic"})
    assert doc.startswith("<!doctype html>")
    assert "<style>" in doc and "</html>" in doc
    assert "http://" not in doc and "https://" not in doc.split("</head>")[0]  # no external assets in head


def test_html_marks_survivor_and_separates_evidence():
    doc = family_report_html("fam", _rows())
    assert "momentum_20" in doc
    assert "research_survivor" in doc
    assert 'class="grp-raw"' in doc and 'class="grp-adj"' in doc  # raw vs adjusted columns
    assert "survivor" in doc  # survivor styling class present


def test_html_handles_empty_rows():
    doc = family_report_html("empty", [])
    assert "<table>" in doc and "Survivors: none" in doc
