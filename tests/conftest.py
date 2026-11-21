"""Offline fixtures only. Written in phase 8; not executed."""
from pathlib import Path
import socket
import sys

import numpy as np
import pandas as pd
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture
def config():
    return yaml.safe_load((ROOT / 'config.yaml').read_text(encoding='utf-8'))


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError('Offline tests must not access the network')
    monkeypatch.setattr(socket.socket, 'connect', blocked)
    monkeypatch.setattr(socket, 'create_connection', blocked)


@pytest.fixture
def synthetic_prices(config):
    from src.preprocessing import session_grid
    sessions, reference = session_grid(config)
    dates = pd.DatetimeIndex([reference]).append(sessions)
    t = np.arange(len(dates), dtype=float)
    return pd.DataFrame({'AAA': 100 * np.exp(0.0002 * t + 0.01 * np.sin(t)),
                         'BBB': 80 * np.exp(0.0001 * t + 0.02 * np.cos(t))}, index=dates)
