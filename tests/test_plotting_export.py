"""Exercise all four render/export paths with explicitly synthetic observations."""
from types import SimpleNamespace
import matplotlib
matplotlib.use('Agg')
import pandas as pd
from PIL import Image

from src.backtest import STRATEGIES
from src.plotting import export_figures


def test_four_png_exports(tmp_path, config):
    dates = pd.to_datetime(['2011-01-03', '2011-01-04', '2011-01-05'])
    values, weights, metrics, drawdowns = [], [], [], []
    for strategy in STRATEGIES:
        for date, wealth in zip(dates, [9990., 10020., 10010.]):
            values.append({'date': date, 'strategy': strategy, 'portfolio_value': wealth, 'cash': 0.})
            weights.extend([{'date': date, 'strategy': strategy, 'asset': 'A', 'weight': .6},
                            {'date': date, 'strategy': strategy, 'asset': 'B', 'weight': .4}])
            drawdowns.append({'date': date, 'strategy': strategy, 'drawdown': min(wealth/10020-1, 0)})
        metrics.append({'strategy': strategy, 'annualized_volatility': .1, 'cagr': .05})
    result = SimpleNamespace(portfolio_values=pd.DataFrame(values), weight_history=pd.DataFrame(weights),
                             metadata={'bias_label': 'synthetic test only', 'fee_rate': .001,
                                       'rf_mode': 'zero-sensitivity', 'initial_external_capital_usd': 10000})
    metric_result = SimpleNamespace(portfolio_metrics=pd.DataFrame(metrics), drawdowns=pd.DataFrame(drawdowns))
    export_figures(result, metric_result, config, tmp_path)
    assert {p.name for p in tmp_path.glob('*.png')} == {
        'portfolio_growth.png', 'risk_return.png', 'drawdowns.png', 'weight_evolution.png'}
    for path in tmp_path.glob('*.png'):
        with Image.open(path) as image:
            assert image.width > 500 and image.height > 500
            image.verify()


def test_weight_archive_is_lossless_and_deterministic(tmp_path):
    import gzip
    from run_analysis import compress_weight_history
    payload = b'date,strategy,asset,weight\n2011-01-03,annual,A,1\n'
    (tmp_path / 'weight_history.csv').write_bytes(payload)
    archive = compress_weight_history(tmp_path)
    first = archive.read_bytes()
    assert gzip.decompress(first) == payload
    assert compress_weight_history(tmp_path).read_bytes() == first
