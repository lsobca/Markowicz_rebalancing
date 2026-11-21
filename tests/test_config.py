def test_agreed_defaults(config):
    expected = {
        'universe_mode': 'current_survivors_only', 'download_start': '2004-12-20',
        'initial_capital_usd': 10000, 'fee_rate': 0.001, 'initial_purchase_fee': True,
        'initial_fee_policy': 'charge_all_portfolios',
        'signal_convention': 'period_last_session_close',
        'execution_convention': 'next_session_close',
        'material_rebalance_turnover_threshold': 0.0001,
        'weight_filter_threshold': 0.0001, 'rolling_window_years': 5,
        'initial_training_calendar_years': 6, 'rf_mode': 'fred_dgs3mo',
        'fractional_shares': True, 'allow_shorting': False,
        'maximum_stock_weight': None, 'post_fee_absolute_tolerance_usd': 1e-8,
        'initial_training_start': '2005-01-01', 'initial_training_end': '2010-12-31',
        'initial_execution_date': '2011-01-03', 'backtest_end': '2025-12-31',
        'benchmarks_enabled': False,
    }
    for key, value in expected.items():
        assert config[key] == value
    assert config['calendar']['start'] == '2004-12-01'
    assert config['calendar']['end'] == '2026-12-31'
    assert config['calendar']['exchange'] == 'XNYS'
    assert config['risk_free']['publication_lag_us_business_days'] == 1
    assert not config['risk_free']['future_backfill']
    assert config['universe']['missing_trading_session_prices_tolerated'] == 0
    assert not config['universe']['price_forward_fill']
    assert config['optimization']['solver'] == 'CLARABEL'
    assert config['metrics']['annualization_sessions'] == 252
    assert config['metrics']['covariance_ddof'] == config['metrics']['volatility_ddof'] == 1
