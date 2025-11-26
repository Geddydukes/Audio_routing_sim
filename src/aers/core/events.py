from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class AudioFrame:
    """
    A block of audio samples with an associated start timestamp.

    data: np.ndarray of shape (num_frames, num_channels), dtype=float32
    sample_rate: samples per second (e.g. 48000)
    timestamp: start time of this frame in seconds
    """
    data: np.ndarray
    sample_rate: int
    timestamp: float

    def __post_init__(self) -> None:
        if self.data.ndim != 2:
            raise ValueError(f"AudioFrame.data must be 2D (frames, channels), got {self.data.shape}")
        if self.data.dtype != np.float32:
            self.data = self.data.astype(np.float32, copy=False)

    @property
    def num_frames(self) -> int:
        return int(self.data.shape[0])

    @property
    def num_channels(self) -> int:
        return int(self.data.shape[1])

    @property
    def peak(self) -> float:
        if self.data.size == 0:
            return 0.0
        return float(np.max(np.abs(self.data)))


@dataclass(frozen=True)
class ScheduledEvent:
    """
    High-level event scheduled for a given frame.

    For now we only support 'start' and 'stop' style events,
    but this can be extended for more complex behaviors.
    """

    target_node_id: str
    frame_index: int
    kind: str  # e.g. "start", "stop"
    payload: Optional[dict] = None

