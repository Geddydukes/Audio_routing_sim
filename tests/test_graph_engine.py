from __future__ import annotations

import numpy as np

from aers.core.graph_engine import GraphEngine, Connection


def _make_simple_engine() -> GraphEngine:
    node_specs = [
        {
            "id": "source1",
            "kind": "sine",
            "params": {"frequency_hz": 440.0, "amplitude": 0.2, "channels": 2},
        },
        {
            "id": "bus_main",
            "kind": "gain",
            "params": {"gain_db": -3.0, "channels": 2},
        },
    ]
    connections = [Connection(src="source1", dst="bus_main")]

    engine = GraphEngine(
        sample_rate=48000,
        frame_size=1024,
        node_specs=node_specs,
        connections=connections,
        default_channels=2,
    )
    return engine


def test_execution_order():
    engine = _make_simple_engine()
    assert engine.execution_order[0] == "source1"
    assert engine.execution_order[1] == "bus_main"


def test_process_frame_shapes_and_peaks():
    engine = _make_simple_engine()
    frames = engine.process_frame(frame_index=0)

    assert "source1" in frames
    assert "bus_main" in frames

    src = frames["source1"]
    bus = frames["bus_main"]

    assert src.data.shape == (1024, 2)
    assert bus.data.shape == (1024, 2)

    assert np.isfinite(src.peak)
    assert np.isfinite(bus.peak)

    # bus_main should have a lower peak than source1 due to negative gain
    assert bus.peak < src.peak

