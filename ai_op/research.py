"""Offline research on validated finalized-bar JSONL; no network or pickle loads."""
import argparse
import hashlib
import json
import math
from decimal import Decimal
from pathlib import Path
from statistics import fmean, pstdev

from ai_op.features import FEATURES, VERSION, TIMEFRAME, WARMUP, FeatureStream
from schemas.data_types import canonical_json, validate_finalized_bar


def validate_dataset(events):
    bars = [validate_finalized_bar(event) for event in events]
    if len(bars) < WARMUP + 40:
        raise ValueError('at least 100 bars required')
    feature_stream = FeatureStream()
    for bar in bars:
        feature_stream.add(bar)
    return bars


def samples(events):
    bars = validate_dataset(events)
    stream = FeatureStream()
    rows = []
    for index, bar in enumerate(bars):
        vector = stream.add(bar)
        if vector is not None and index + 1 < len(bars):
            future = bars[index + 1]
            rows.append(dict(x=vector, y=int(Decimal(future['close']) > Decimal(bar['close'])),
                             open=bar['open_time_ms'], end=bar['end_time_ms'],
                             label_end=future['end_time_ms']))
    return bars, rows


def walk_forward(rows, folds=3):
    """Expanding folds; purge one next-bar label at each boundary."""
    width = len(rows) // (folds + 1)
    if width < 4:
        raise ValueError('insufficient fold history')
    result = []
    for fold in range(1, folds + 1):
        start = fold * width
        end = len(rows) if fold == folds else (fold + 1)*width
        train, test = rows[:start-1], rows[start:end]
        if train[-1]['label_end'] > test[0]['open']:
            raise ValueError('label interval overlaps prediction boundary')
        result.append((train, test))
    return result


def _sigmoid(value):
    return 1/(1+math.exp(-max(-40, min(40, value))))


def fit(rows, *, kind='logistic'):
    """Train-only standardization; fixed configuration, no test-set tuning."""
    means = [fmean(row['x'][j] for row in rows) for j in range(len(FEATURES))]
    scales = [pstdev(row['x'][j] for row in rows) or 1 for j in range(len(FEATURES))]
    x = [[(v-means[j])/scales[j] for j, v in enumerate(row['x'])] for row in rows]
    if kind == 'xgboost':
        from xgboost import XGBClassifier
        model = XGBClassifier(n_estimators=100, max_depth=3, learning_rate=0.05,
                              random_state=42, n_jobs=1, eval_metric='logloss')
        import numpy as np
        model.fit(np.array(x), np.array([row['y'] for row in rows]))
        payload = dict(kind=kind, booster=model.get_booster().save_raw(raw_format='json').decode())
    elif kind == 'logistic':
        weights = [0.0] * (len(FEATURES)+1)
        for _ in range(120):
            gradient = [0.0] * len(weights)
            for vector, row in zip(x, rows):
                error = _sigmoid(weights[-1] + sum(w*v for w, v in zip(weights, vector))) - row['y']
                for j, value in enumerate(vector + [1]):
                    gradient[j] += error*value
            weights = [w - 0.05*g/len(rows) for w, g in zip(weights, gradient)]
        payload = dict(kind=kind, weights=weights)
    else:
        raise ValueError('unsupported model kind')
    return dict(means=means, scales=scales, **payload)


def probability(model, vector):
    scaled = [(value-model['means'][j])/model['scales'][j] for j, value in enumerate(vector)]
    if model['kind'] == 'logistic':
        return _sigmoid(model['weights'][-1] + sum(w*v for w, v in zip(model['weights'], scaled)))
    if model['kind'] == 'xgboost':
        from xgboost import XGBClassifier
        import numpy as np
        classifier = XGBClassifier()
        classifier.load_model(bytearray(model['booster'], 'utf-8'))
        return float(classifier.predict_proba(np.array([scaled]))[0][1])
    raise ValueError('unsupported model kind')


def metrics(actual, predicted):
    counts = {label: sum(y == label for y in actual) for label in (0, 1)}
    tp = sum(y == p == 1 for y, p in zip(actual, predicted))
    fp = sum(y == 0 and p == 1 for y, p in zip(actual, predicted))
    fn = sum(y == 1 and p == 0 for y, p in zip(actual, predicted))
    tn = sum(y == p == 0 for y, p in zip(actual, predicted))
    return dict(n=len(actual), accuracy=sum(y == p for y, p in zip(actual, predicted))/len(actual),
                positive_precision=tp/(tp+fp) if tp+fp else 0,
                positive_recall=tp/(tp+fn) if tp+fn else 0,
                negative_recall=tn/(tn+fp) if tn+fp else 0,
                balanced_accuracy=((tp/(tp+fn) if tp+fn else 0)
                                   + (tn/(tn+fp) if tn+fp else 0))/2,
                class_counts=counts)


def evaluate(train, test, kind):
    model = fit(train, kind=kind)
    majority = int(sum(r['y'] for r in train) > len(train)/2)
    actual = [r['y'] for r in test]
    return model, dict(model=metrics(actual, [int(probability(model, r['x']) >= .5) for r in test]),
                       majority=metrics(actual, [majority]*len(test)),
                       train_label_end=train[-1]['label_end'], test_open=test[0]['open'])


def train(events, *, provenance, kind='logistic'):
    if not isinstance(provenance, str) or not provenance.strip():
        raise ValueError('explicit data provenance required')
    bars, rows = samples(events)
    split = int(len(rows)*.8)
    development, holdout = rows[:split-1], rows[split:]
    validation = [evaluate(a, b, kind)[1] for a, b in walk_forward(development)]
    if development[-1]['label_end'] > holdout[0]['open']:
        raise ValueError('holdout boundary leakage')
    model, result = evaluate(development, holdout, kind)
    digest = hashlib.sha256('\n'.join(canonical_json(b) for b in bars).encode()).hexdigest()
    artifact = dict(artifact_version=1, feature_version=VERSION, feature_order=list(FEATURES),
                    preprocessing_version='train-standardize-v1', warmup_bars=WARMUP,
                    stream={k: bars[0][k] for k in ('exchange', 'market', 'symbol', 'timeframe')},
                    provenance=provenance, dataset_sha256=digest,
                    coverage=dict(start=bars[0]['open_time_ms'], end=bars[-1]['end_time_ms'], bars=len(bars)),
                    fit_label_end_ms=development[-1]['label_end'],
                    configuration=dict(seed=42, kind=kind, validation='expanding-3-gap-1', final_holdout=.2),
                    model=model)
    return artifact, dict(validation=validation, holdout=result,
                          warning='Classification research only; no trading-profitability evidence')


def validate_artifact(artifact, event):
    bar = validate_finalized_bar(event)
    try:
        valid = (artifact['artifact_version'] == 1 and artifact['feature_version'] == VERSION
                 and artifact['feature_order'] == list(FEATURES)
                 and artifact['preprocessing_version'] == 'train-standardize-v1'
                 and artifact['warmup_bars'] == WARMUP
                 and artifact['stream'] == {k: bar[k] for k in ('exchange', 'market', 'symbol', 'timeframe')}
                 and bar['timeframe'] == TIMEFRAME and bool(artifact['provenance'])
                 and len(artifact['dataset_sha256']) == 64
                 and type(artifact['fit_label_end_ms']) is int
                 and bar['open_time_ms'] >= artifact['fit_label_end_ms'])
    except (KeyError, TypeError):
        valid = False
    if not valid:
        raise ValueError('model metadata missing or incompatible')
    model = artifact['model']
    if (len(model['means']) != len(FEATURES) or len(model['scales']) != len(FEATURES)
            or not all(math.isfinite(v) for v in model['means'] + model['scales'])
            or not all(v > 0 for v in model['scales'])):
        raise ValueError('invalid preprocessing metadata')
    if model['kind'] == 'logistic':
        if len(model['weights']) != len(FEATURES)+1 or not all(math.isfinite(w) for w in model['weights']):
            raise ValueError('invalid model weights')
    elif model['kind'] != 'xgboost' or not isinstance(model.get('booster'), str):
        raise ValueError('unsupported model payload')


def infer(artifact, vector, event, *, now_ms, replay=True, healthy=False, max_age_ms=120_000):
    validate_artifact(artifact, event)
    if (type(now_ms) is not int or type(replay) is not bool or type(healthy) is not bool
            or type(max_age_ms) is not int or max_age_ms <= 0):
        raise ValueError('invalid inference context')
    if (replay or not healthy or now_ms < event['published_at_ms'] or
            now_ms-event['end_time_ms'] > max_age_ms):
        raise ValueError('inference blocked: replay/stale/incomplete stream')
    if len(vector) != len(FEATURES) or not all(math.isfinite(v) for v in vector):
        raise ValueError('invalid feature vector')
    return probability(artifact['model'], vector)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset', type=Path, help='completed validated MARKET_BAR_V1 JSONL')
    parser.add_argument('--provenance', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--kind', choices=['logistic', 'xgboost'], default='logistic')
    args = parser.parse_args()
    events = [json.loads(line) for line in args.dataset.read_text().splitlines() if line.strip()]
    artifact, report = train(events, provenance=args.provenance, kind=args.kind)
    args.output.mkdir(parents=True, exist_ok=True)
    for name, value in [('model.json', artifact), ('evaluation.json', report)]:
        path = args.output / name
        with path.open('x') as output:
            json.dump(value, output, indent=2, allow_nan=False)


if __name__ == '__main__':
    main()
