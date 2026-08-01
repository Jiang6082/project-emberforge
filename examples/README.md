# Example data fixtures

Small, deterministic market-data fixtures (6 symbols × 40 daily bars, from
`make_synthetic(seed=11)`) used to exercise the provider-neutral loaders
end-to-end (`tests/test_loaders.py`).

* `data/csv/{open,high,low,close,volume,vwap}.csv` — one CSV per field, timestamp
  index + one column per symbol. Load with `emberforge.data.load_csv_dir`.
* `data/panel.parquet` — long-form `[timestamp, symbol, field, value]`. Load with
  `emberforge.data.load_parquet`.

Try the CLI against the CSV fixtures:

```bash
emberforge data validate --csv-dir examples/data/csv
emberforge factor evaluate "ts_returns(close, 5)" --csv-dir examples/data/csv
```
