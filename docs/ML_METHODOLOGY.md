# ML methodology and current evidence

## Data and modeling contract

Recommended models use one contiguous finalized `binance/spot/<symbol>/1m` stream. No implicit resampling, gap filling, duplicate dropping, or mixed-timeframe model reuse occurs. Validated JSONL is the input; floats remain confined to the explicit modeling boundary. Duplicate, reversed, mixed-stream and missing intervals fail. Exact market decimal strings remain in storage. Next-close labels use Decimal comparison and remove the endpoint with no future observation.

`bounded-indicators-v1` recomputes from exactly 60 trailing bars in both offline and streaming paths. Feature order: RSI_14, MACD_hist, BB_high, BB_low, Dist_to_EMA50, ATR_14, close, volume. EMA uses an SMA seed and alpha=2/(period+1); MACD is EMA12-EMA26 with EMA9 signal; RSI and ATR use a 14-observation mean seed and Wilder updates. Bollinger bands use population standard deviation on 20 closes. Flat RSI is 50; no-loss rising RSI is 100. This bounded policy intentionally differs from unbounded ta recursion. It is a new model version, with no compatibility claim for old pickles. Nonfinite float features fail.

## Validation

Samples require a known next completed close. An 80/20 chronological development/holdout split purges one row at the boundary. Development evaluation uses three expanding folds, each purging one next-bar label. Assertions require every training label end <= first test bar open. Predictions are defined after the feature bar closes. Preprocessing means/scales fit training rows only; no held-out statistics or tuning. Model configuration is fixed, not optimized on the final holdout.

The mandatory logistic baseline is dependency-free batch gradient descent (120 epochs, learning rate .05); each fold also reports a training-only majority baseline. Optional XGBoost uses fixed 100 trees, depth 3, learning rate .05, seed 42 and one worker. Artifact configuration records the seed and implementation kind; exact fixed hyperparameters are in research.py. Reports include accuracy, positive precision/recall, negative recall, balanced accuracy and class counts. A missing class makes the corresponding recall zero; interpret class counts before comparing balanced accuracy. These are classification metrics, not execution returns.

JSON artifacts contain stream/timeframe, feature/preprocessing versions, feature order, warmup, source description, dataset SHA-256, coverage, the final training-label availability cutoff, configuration and model parameters. Inference rejects bars predating that cutoff. XGBoost uses native JSON booster bytes, not pickle. Treat all model files as untrusted input and review provenance/dependency security; metadata validates compatibility, not authenticity. Artifacts and reports are created in a new owner-selected output directory and are not checked in automatically.

## Observed evidence and limits

The only available dataset is deterministic synthetic fixtures generated from tools.fixtures. Tests prove parity, causality under future perturbations, warmup, purged label boundaries, deterministic logistic training and inference metadata/freshness gates. The demo discards synthetic evaluation metrics and makes no profitability claim. There is no reviewed market dataset, valid legacy model artifact or real-market predictive evaluation. XGBoost/numpy/sklearn are unavailable, so its optional backend test is skipped. Real-data performance validation is BLOCKED.

## Real-data workflow (owner-supplied offline data)

1. Acquire authoritative finalized 1m bars separately with permission, preserving request-start time evidence, source, coverage and corrections.
2. Export canonical MARKET_BAR_V1 JSONL, one stream in strict contiguous order. Resolve gaps/conflicts before training; never silently interpolate.
3. Review provenance, licensing, time coverage, class balance and holdout period.
4. Run `python3 -B -m ai_op.research DATASET.jsonl --provenance 'reviewed source and acquisition details' --output artifacts/experiment-001`.
5. For XGBoost, separately install reviewed optional dependencies and add `--kind xgboost`; rerun optional backend tests. Installation was not performed in this task.
6. Inspect evaluation.json, model.json, baselines and coverage; independently evaluate distribution shifts and economic execution costs. Synthetic results cannot satisfy this step.

Inference requires compatible metadata, finite features, explicit non-replay invocation, current time evidence and healthy durable continuity. It returns a probability, never an order. Paper simulation is opt-in and separately gated.
