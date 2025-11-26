from dataclasses import dataclass
import numpy as np

@dataclass(slots=True)
class AudioBuffer:
    "Interleaved float32 PCM buffer with timestamp in samples"
    samples: np.ndarray
    sample_rate: int
    t0: int

    @property
    def num_frames(self) -> int:
        return int(self.samples.shape[0])

    @ property
    def num_channels(self) -> int:
        return int(self.samples.shape[0])
    
    def copy(self) -> "AudioBuffer":
        return AudioBuffer(
            samples=self.samples.copy(),
            sample_rate=self.sample_rate,
            t0=self.t0
        )
    
    @staticmethod
    def silence(num_frames: int, num_channels: int, sample_rate: int, t0: int) -> "AudioBuffer":
        return AudioBuffer(
            samples=np.zeros((num_frames, num_channels), dtype=np.float32),
            sample_rate=sample_rate,
            t0=t0
        )
