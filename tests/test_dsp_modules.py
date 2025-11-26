# tests/test_dsp_modules.py

import numpy as np

from aers.core.nodes import AudioFrame, GainNode, EQNode, DelayNode


def _make_constant_frame(
    value: float,
    num_frames: int = 1024,
    channels: int = 2,
    sample_rate: int = 48_000,
):
    data = np.full((num_frames, channels), value, dtype=np.float32)
    return AudioFrame(data=data, sample_rate=sample_rate, timestamp=0.0)


def test_gain_node_attenuates_signal():
    frame = _make_constant_frame(0.5)
    node = GainNode(name="gain_test", sample_rate=frame.sample_rate, channels=frame.num_channels,
                    config={"gain_db": -6.0})

    out = node.process(num_frames=frame.num_frames, timestamp=0.0, inputs=[frame])

    # -6 dB ≈ 0.5012 linear attenuation, so output should be about half the input peak.
    assert out.data.shape == frame.data.shape
    assert out.peak < frame.peak
    ratio = out.peak / frame.peak
    assert 0.45 < ratio < 0.6  # loose bounds


def test_eq_node_boosts_highs():
    # White-ish noise → EQ high band boost should increase RMS.
    rng = np.random.default_rng(0)
    data = rng.normal(0.0, 0.2, size=(2048, 1)).astype(np.float32)
    frame = AudioFrame(data=data, sample_rate=48_000, timestamp=0.0)

    eq = EQNode(
        name="eq_test",
        sample_rate=frame.sample_rate,
        channels=frame.num_channels,
        config={
            "low_gain_db": 0.0,
            "mid_gain_db": 0.0,
            "high_gain_db": 6.0,  # boost highs
            "low_cut_hz": 500.0,
            "high_cut_hz": 4000.0,
        },
    )

    out = eq.process(num_frames=frame.num_frames, timestamp=0.0, inputs=[frame])

    def rms(x: np.ndarray) -> float:
        return float(np.sqrt(np.mean(np.square(x), dtype=np.float64)))

    in_rms = rms(frame.data)
    out_rms = rms(out.data)

    assert out.data.shape == frame.data.shape
    # High boost should increase overall RMS a bit.
    assert out_rms > in_rms


def test_delay_node_inserts_delayed_impulse():
    sample_rate = 48_000
    num_frames = 480  # 10 ms frame
    delay_ms = 5.0   # 5 ms => 240 samples

    # Single-sample impulse at t=0
    data = np.zeros((num_frames, 1), dtype=np.float32)
    data[0, 0] = 1.0
    frame = AudioFrame(data=data, sample_rate=sample_rate, timestamp=0.0)

    delay = DelayNode(
        name="delay_test",
        sample_rate=sample_rate,
        channels=frame.num_channels,
        config={
            "delay_ms": delay_ms,
            "feedback": 0.0,
            "mix": 1.0,  # fully wet to make detection easier
        },
    )

    out = delay.process(num_frames=frame.num_frames, timestamp=0.0, inputs=[frame])

    # Expect a delayed impulse at approximately delay_samples.
    delay_samples = int(round(sample_rate * delay_ms / 1000.0))

    # Bounds check
    assert delay_samples < num_frames

    # With mix=1.0 (fully wet), the output should be only the delayed signal
    # At sample 0, the buffer is empty so output should be near zero
    assert abs(out.data[0, 0]) < 1e-4

    # The delayed impulse should be present at delay_samples position
    # (the input at sample 0 appears in the output at sample delay_samples)
    assert out.data[delay_samples, 0] > 0.5

