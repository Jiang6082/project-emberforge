"""Market-data abstraction: schema, synthetic generator, loaders."""

from .loaders import load_csv_dir, load_geld_bars, load_parquet
from .schema import FIELDS, DatasetMetadata, MarketData
from .synthetic import make_synthetic

__all__ = [
    "MarketData", "DatasetMetadata", "FIELDS",
    "make_synthetic", "load_csv_dir", "load_parquet", "load_geld_bars",
]
