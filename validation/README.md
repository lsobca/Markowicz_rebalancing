# Validation and completed primary run

Execution was separately authorized by the user after all eight source phases.
The primary run completed with fee_rate=0.001 and rf_mode=fred_dgs3mo.
Exact UTC run timestamps and output hashes are in results/run_manifest.json.

- Python 3.11 on macOS ARM64; installed packages in requirements-validated.txt.
- 29 offline tests passed (pytest.txt), including bounded Yahoo retries, four
  PNG export paths, and lossless deterministic weight-history compression.
- pip check: no broken requirements. Python compileall completed successfully.
- Notebook schema valid; every code cell executed without a cell error against
  the saved results, with downloads disabled. The sandbox prevented ipykernel's
  child-process enumeration during shutdown; this emitted a cleanup warning
  after successful execution, not an analysis-cell failure.
- All generated artifact SHA-256 hashes verified. The gzip copy decompresses
  exactly to the original weight_history.csv hash.
- All four actual graphs visually inspected for labels, legends and clipping.
- 503 roster entries; 383 with complete history; 120 excluded for coverage;
  one duplicate eligible issuer/share class removed; 100 selected.
- No zero-fee or zero-RF sensitivity run was executed.

Runtime adjustments: used installed Python 3.11 instead of system Python 3.9;
repeated unresolved Yahoo requests in bounded small batches while retaining
individual coverage checks and retry limits; directed future yfinance internal
cache into the ignored project cache; added progress logging and interrupted
manifest status. No financial methodology or selection criteria were changed.
The first DNS failure and interrupted pre-batching attempt remain documented.

The backtest completed successfully; this does not validate historical corporate
actions independently or remove the explicitly disclosed survivors-only bias.
Raw source cache is local and ignored; manifests/universe records/results are
versioned. The large uncompressed weight CSV is local; its identical gzip copy
is versioned and supported by the notebook checksum verification.
