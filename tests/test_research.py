import copy
import unittest

from ai_op.features import FEATURES, WARMUP, FeatureStream, feature_vector
from ai_op.research import fit, infer, samples, train, validate_artifact, walk_forward
from tools.fixtures import bars


class ResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bars = bars(160)
        cls.artifact, cls.report = train(cls.bars, provenance='synthetic-test-not-market-data')

    def test_stream_offline_parity_and_warmup(self):
        stream = FeatureStream()
        for index, bar in enumerate(self.bars):
            vector = stream.add(bar)
            if index < WARMUP-1:
                self.assertIsNone(vector)
            else:
                self.assertEqual(vector, feature_vector(self.bars[:index+1]))
                self.assertEqual(len(vector), len(FEATURES))

    def test_future_values_cannot_change_past_features(self):
        original = feature_vector(self.bars[:80])
        altered = copy.deepcopy(self.bars)
        for bar in altered[80:]:
            bar['close'] = '80'
        self.assertEqual(feature_vector(altered[:80]), original)

    def test_flat_price_indicators_match_hand_calculation(self):
        events = [dict(bar, open='100', close='100', high='110', low='90', volume='10')
                  for bar in self.bars]
        vector = feature_vector(events)
        self.assertEqual(vector, (50, 0, 100, 100, 0, 20, 100, 10))

    def test_gap_duplicate_timeframe_and_order_rejected(self):
        for data in (self.bars[::2], self.bars[::-1], [self.bars[0]]*120):
            with self.assertRaises(ValueError):
                samples(data)
        stream = FeatureStream()
        stream.add(self.bars[0])
        with self.assertRaises(ValueError):
            stream.add(self.bars[0])

    def test_endpoint_has_no_fabricated_label(self):
        _, rows = samples(self.bars)
        self.assertEqual(len(rows), len(self.bars)-WARMUP)
        self.assertEqual(rows[-1]['label_end'], self.bars[-1]['end_time_ms'])
        self.assertEqual(rows[-1]['open'], self.bars[-2]['open_time_ms'])

    def test_every_fold_purges_label_boundary(self):
        _, rows = samples(self.bars)
        for train_rows, test in walk_forward(rows):
            self.assertLessEqual(max(r['label_end'] for r in train_rows), test[0]['open'])
        holdout = self.report['holdout']
        self.assertLessEqual(holdout['train_label_end'], holdout['test_open'])

    def test_scaling_fits_training_only(self):
        _, rows = samples(self.bars)
        training = rows[:30]
        model = fit(training)
        self.assertAlmostEqual(model['means'][-1], sum(r['x'][-1] for r in training)/30)
        before = copy.deepcopy(model)
        rows[-1]['x'] = tuple([1e10]*len(FEATURES))
        self.assertEqual(model, before)

    def test_reproducible_training_and_provenance(self):
        artifact, report = train(self.bars, provenance='synthetic-test-not-market-data')
        self.assertEqual(artifact, self.artifact)
        self.assertEqual(report, self.report)
        self.assertEqual(artifact['coverage']['bars'], 160)

    def test_missing_metadata_and_incompatible_models_fail_closed(self):
        for key, value in [('feature_version', 'other'), ('feature_order', []),
                           ('warmup_bars', 1), ('provenance', ''), ('stream', {})]:
            artifact = copy.deepcopy(self.artifact)
            artifact[key] = value
            with self.assertRaises(ValueError):
                validate_artifact(artifact, self.bars[-1])
        with self.assertRaises(ValueError):
            validate_artifact({}, self.bars[-1])
        with self.assertRaises(ValueError):
            validate_artifact(self.artifact, self.bars[0])

    def test_replay_stale_incomplete_and_live_inference(self):
        bar = self.bars[-1]
        vector = feature_vector(self.bars)
        for options in ({}, {'replay': False}, {'replay': False, 'healthy': True,
                                               'now_ms': bar['end_time_ms']+200_000}):
            args = dict(now_ms=bar['published_at_ms'])
            args.update(options)
            with self.assertRaises(ValueError):
                infer(self.artifact, vector, bar, **args)
        value = infer(self.artifact, vector, bar, now_ms=bar['published_at_ms'],
                      replay=False, healthy=True)
        self.assertTrue(0 <= value <= 1)
