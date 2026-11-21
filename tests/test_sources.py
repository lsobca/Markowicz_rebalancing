import json
import pandas as pd
import pytest

from src.download_data import SnapshotStore, Downloader, extract_adjusted_close, parse_fred
from src.universe import (require_supported_mode, SourceUnavailableError, DataQualityError,
                          select_survivors, coverage_record, parse_current_roster)


@pytest.mark.parametrize('mode', ['historical_top_cap_2010', 'historical_roster_2010'])
def test_historical_source_unavailable(mode):
    with pytest.raises(SourceUnavailableError, match='No automatic'):
        require_supported_mode(mode)


def test_cache_request_checksum_and_vintage(tmp_path):
    store = SnapshotStore(tmp_path, True)
    request = {'ticker': 'A', 'start': '2004-12-20'}
    first = store.write(request, b'first vintage', 'synthetic://source')
    second = store.write(request, b'second vintage', 'synthetic://source')
    assert first['sha256'] != second['sha256']
    assert (tmp_path / 'objects' / first['sha256']).read_bytes() == b'first vintage'
    assert store.read(request)[0] == b'second vintage'
    assert store.read({'ticker': 'B'}) is None
    (tmp_path / 'objects' / second['sha256']).write_bytes(b'corrupt')
    with pytest.warns(UserWarning, match='Checksum'):
        assert store.read(request) is None


def test_adj_close_required_and_multiindex():
    dates = pd.date_range('2020-01-01', periods=2)
    columns = pd.MultiIndex.from_tuples([('Close', 'A'), ('Adj Close', 'A')])
    frame = pd.DataFrame([[100, 50], [102, 51]], index=dates, columns=columns)
    assert extract_adjusted_close(frame, 'A', 1).tolist() == [50, 51]
    with pytest.raises(DataQualityError, match='not a substitute'):
        extract_adjusted_close(pd.DataFrame({'Close': [100, 102]}, index=dates), 'A', 1)


def test_survivors_screen_before_round_robin():
    roster = pd.DataFrame({'original_ticker': ['A', 'B', 'C', 'D', 'E'],
                           'issuer_id': ['1', '2', '2', '3', '4'],
                           'sector': ['Alpha', 'Alpha', 'Alpha', 'Beta', 'Beta']})
    available = pd.DataFrame({'original_ticker': roster.original_ticker,
                              'eligible_history': [False, True, True, True, True]})
    selected, audit, counts = select_survivors(roster, available, per_sector=2, maximum_total=3)
    assert selected.original_ticker.tolist() == ['B', 'D', 'E']
    assert audit.set_index('original_ticker').loc['C', 'selection_reason'] == 'duplicate_issuer_share_class'
    assert counts.selected_count.sum() == 3
    with pytest.raises(DataQualityError):
        select_survivors(roster, available.iloc[1:])


def test_no_invented_ipo_or_delisting():
    sessions = pd.to_datetime(['2010-12-31', '2011-01-03'])
    prices = pd.Series([100.], index=sessions[:1])
    report = coverage_record(prices, sessions, pd.Timestamp('2010-12-30'))
    assert not report['eligible_history']
    assert report['early_end_or_missing_recent_history']
    assert report['delisting_status'] == report['ipo_status'] == 'unknown_not_verified'


def test_roster_mapping_and_schema():
    html = '<table><tr><th>Symbol</th><th>Security</th><th>GICS Sector</th><th>CIK</th></tr><tr><td>BRK.B</td><td>Example</td><td>Financials</td><td>1067983</td></tr></table>'
    roster = parse_current_roster(html, 'synthetic://roster', 'test-only', expected_sectors=1)
    assert roster.iloc[0].original_ticker == 'BRK.B'
    assert roster.iloc[0].yahoo_ticker == 'BRK-B'
    with pytest.raises(DataQualityError):
        parse_current_roster(html, 'synthetic://roster', 'test-only', expected_sectors=11)


def test_http_backoff_and_cached_fred_failure(config, tmp_path, monkeypatch):
    import requests
    sleeps = []
    downloader = Downloader(config, tmp_path, sleep=sleeps.append)
    def fail(*args, **kwargs):
        raise requests.ConnectionError('synthetic outage')
    monkeypatch.setattr(downloader.session, 'get', fail)
    with pytest.raises(SourceUnavailableError):
        downloader.http('https://example.invalid', lambda payload: payload, 'test')
    assert sleeps == [2, 4, 8, 16]
    payload = b'observation_date,DGS3MO\n2004-12-17,2.1\n2025-12-30,3.1\n'
    url = config['risk_free']['url']
    downloader.store.write({'url': url, 'transport': 'http', 'schema_version': 1}, payload, url)
    downloader.refresh = True
    with pytest.warns(UserWarning, match='validated cache'):
        actual, _ = downloader.http(url, lambda b: parse_fred(b, '2004-12-20', '2025-12-31'), 'FRED')
    assert actual == payload
