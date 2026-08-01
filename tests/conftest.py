import pytest

from emberforge.data import make_synthetic


@pytest.fixture(scope="session")
def data():
    return make_synthetic(n_symbols=12, n_days=300, seed=7)


@pytest.fixture(scope="session")
def small_data():
    return make_synthetic(n_symbols=8, n_days=120, seed=3)
