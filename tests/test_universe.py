import numpy as np
import pandas as pd

from emberforge.compute import compute_factor
from emberforge.dsl import make_factor
from emberforge.universe import (
    point_in_time_universe,
    static_universe,
    survivorship_stressed,
)


def test_static_universe_all_eligible_after_first_bar(data):
    u = static_universe(data.index, data.symbols)
    elig = u.eligibility(data.index, data.symbols)
    # first bar has no prior knowledge -> ineligible; rest eligible
    assert not elig.iloc[0].any()
    assert elig.iloc[1:].all().all()


def test_pit_membership_change_is_lagged():
    idx = pd.bdate_range("2021-01-04", periods=6, tz="UTC")
    syms = ["A", "B"]
    membership = pd.DataFrame(True, index=idx, columns=syms)
    membership.loc[idx[3], "B"] = False  # B leaves the index at t=3
    u = point_in_time_universe(membership)
    elig = u.eligibility(idx, syms)
    # observed at t=3, so it may only affect t=4 onward, not t=3 itself
    assert elig.loc[idx[3], "B"] == True   # still eligible on the observation bar
    assert elig.loc[idx[4], "B"] == False  # effect applies next permissible bar


def test_apply_masks_ineligible_cells():
    idx = pd.bdate_range("2021-01-04", periods=5, tz="UTC")
    syms = ["A", "B"]
    membership = pd.DataFrame(True, index=idx, columns=syms)
    membership["B"] = False
    u = point_in_time_universe(membership)
    scores = pd.DataFrame(1.0, index=idx, columns=syms)
    masked = u.apply(scores)
    assert masked["B"].isna().all()


def test_survivorship_removes_after_death():
    idx = pd.bdate_range("2021-01-04", periods=6, tz="UTC")
    syms = ["A", "B"]
    membership = pd.DataFrame(True, index=idx, columns=syms)
    u = survivorship_stressed(membership, {"B": idx[3]})
    # B dead from t=3 onward in membership
    assert u.membership.loc[idx[2], "B"] == True
    assert u.membership.loc[idx[3], "B"] == False


def test_fingerprint_stable_and_sensitive():
    idx = pd.bdate_range("2021-01-04", periods=4, tz="UTC")
    m1 = pd.DataFrame(True, index=idx, columns=["A", "B"])
    m2 = m1.copy(); m2.loc[idx[2], "A"] = False
    assert point_in_time_universe(m1).fingerprint == point_in_time_universe(m1).fingerprint
    assert point_in_time_universe(m1).fingerprint != point_in_time_universe(m2).fingerprint


def test_universe_restricts_computation(data):
    # drop half the symbols from the universe; scores there must be NaN
    keep = data.symbols[:6]
    membership = pd.DataFrame(False, index=data.index, columns=data.symbols)
    membership[keep] = True
    u = point_in_time_universe(membership)
    elig = u.eligibility(data.index, data.symbols)
    scores = compute_factor(make_factor("m", "ts_returns(close,20)"), data, eligibility=elig)
    dropped = [s for s in data.symbols if s not in keep]
    assert scores[dropped].isna().all().all()
