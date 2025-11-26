from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import math

from aers.core.events import AudioFrame


@dataclass(frozen=True)
class NodeMetric:
    """Single-node metric snapshot suitable for serialization to JSON."""

    name: str
    peak: float
    rms: float
    num_frames: int
    num_channels: int
    # Optional file metadata (for AudioFileSourceNode)
    file_info: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "name": self.name,
            "peak": self.peak,
            "rms": self.rms,
            "num_frames": self.num_frames,
            "num_channels": self.num_channels,
        }
        if self.file_info:
            result["file_info"] = self.file_info
        return result


@dataclass(frozen=True)
class MetricsSnapshot:
    """Aggregate metrics for all nodes at a given wall-clock timestamp."""

    timestamp: float  # seconds since epoch
    nodes: List[NodeMetric]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "nodes": [n.to_dict() for n in self.nodes],
        }


def frame_to_metrics(name: str, frame: AudioFrame) -> NodeMetric:
    """
    Compute metrics for a single AudioFrame.

    Peak is taken from frame.peak (already max abs sample).
    RMS is computed per-frame across all samples.
    """
    samples = frame.data
    if samples.size == 0:
        rms_value = 0.0
    else:
        # RMS over all channels and frames
        sq = (samples.astype("float64") ** 2).mean()
        rms_value = math.sqrt(float(sq))

    return NodeMetric(
        name=name,
        peak=float(frame.peak),
        rms=float(rms_value),
        num_frames=frame.num_frames,
        num_channels=frame.num_channels,
    )

