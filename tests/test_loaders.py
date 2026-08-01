"""The CSV and Parquet loaders are exercised end-to-end against checked-in
fixtures under examples/data/, so the provider-neutral data path is covered by a
real round-trip, not just synthetic generation."""

from pathlib import Path

from emberforge.compute import compute_factor
from emberforge.data import load_csv_dir, load_parquet
from emberforge.dsl import make_factor

EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "data"


def test_csv_loader_round_trip():
    data = load_csv_dir(EXAMPLES / "csv")
    assert len(data.symbols) == 6
    assert data.metadata.fingerprint
    for field in ("open", "high", "low", "close", "volume", "vwap"):
        assert data.has_field(field)


def test_parquet_loader_round_trip():
    data = load_parquet(EXAMPLES / "panel.parquet")
    assert len(data.symbols) == 6
    assert data.metadata.source == "local_parquet"


def test_loaded_data_computes_a_factor():
    data = load_parquet(EXAMPLES / "panel.parquet")
    scores = compute_factor(make_factor("m", "ts_returns(close, 5)"), data)
    assert scores.shape == (len(data.index), len(data.symbols))
    assert scores.notna().any().any()


def test_csv_and_parquet_agree_on_close():
    csv_data = load_csv_dir(EXAMPLES / "csv")
    pq_data = load_parquet(EXAMPLES / "panel.parquet")
    a = csv_data.field("close").reset_index(drop=True)
    b = pq_data.field("close").reset_index(drop=True)
    # same underlying panel written two ways — closes should match closely
    assert ((a - b).abs().max().max()) < 1e-6
