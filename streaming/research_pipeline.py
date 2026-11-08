"""Durable acceptance -> one feature row. Inference is a separate explicit call."""
from ai_op.features import FeatureStream
from ai_op.research import infer


class ResearchPipeline:
    def __init__(self, pipeline):
        self.pipeline = pipeline
        self.features = {}
        self.latest = {}
        self.fenced = False

    def register_stream(self, **kwargs):
        stream = self.pipeline.register_stream(**kwargs)
        self.features[stream] = FeatureStream()
        return stream

    def deliver(self, event, *, now_ms):
        if self.fenced:
            raise RuntimeError('feature pipeline fenced; rebuild/replay required')
        result = self.pipeline.deliver(event, now_ms=now_ms)
        if result.fenced:
            self.fenced = True
        if result.storage_confirmed and result.processing.outcome == 'accepted':
            stream = result.processing.stream
            try:
                vector = self.features[stream].add(event)
                self.latest[stream] = (dict(event), vector)
            except BaseException:
                self.fenced = True
                raise
        return result

    def predict(self, stream, artifact, *, now_ms, replay=True):
        if self.fenced or self.pipeline.fenced or stream not in self.latest:
            raise ValueError('inference blocked by storage/feature state')
        snapshot = self.pipeline.snapshot(stream)
        state = snapshot['processor']
        bar, vector = self.latest[stream]
        healthy = (state['conflict'] is None and state['recovery_end_ms'] is None
                   and snapshot['confirmed_next_cursor_ms'] == bar['end_time_ms']
                   and vector is not None)
        if not healthy:
            raise ValueError('inference blocked by incomplete features/continuity')
        return infer(artifact, vector, bar, now_ms=now_ms, replay=replay, healthy=healthy)
