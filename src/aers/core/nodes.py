# src/aers/core/nodes.py

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Iterable, Optional
from pathlib import Path

import numpy as np

from .events import AudioFrame


class BaseNode(ABC):
    """
    Base class for all processing nodes in the routing graph.

    Each node receives zero or more AudioFrame inputs and produces
    a single AudioFrame output with the same sample rate and channel count.
    """

    def __init__(
        self,
        name: str,
        sample_rate: int = 48_000,
        channels: int = 2,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.name = name
        self.sample_rate = int(sample_rate)
        self.channels = int(channels)
        self.config = config or {}

    @abstractmethod
    def process(
        self,
        num_frames: int,
        timestamp: float,
        inputs: Optional[Iterable[AudioFrame]] = None,
    ) -> AudioFrame:
        """
        Produce an AudioFrame of length `num_frames` at `timestamp`.

        Implementations MUST:
        - Always return exactly `num_frames` frames.
        - Always return exactly `self.channels` channels.
        - Be side-effect free except for internal node state (e.g. phase, delay buffers).
        """
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Source and utility nodes
# ---------------------------------------------------------------------------


class SineSourceNode(BaseNode):
    """
    Continuous sine-wave generator.

    Config keys:
      - frequency_hz: float (default 440.0)
      - amplitude: float in [0, 1] (default 0.2)
      - initial_phase: float, radians (default 0.0)
    """

    def __init__(
        self,
        name: str,
        sample_rate: int = 48_000,
        channels: int = 2,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(name, sample_rate, channels, config)
        cfg = self.config
        self.frequency_hz: float = float(cfg.get("frequency_hz", 440.0))
        self.amplitude: float = float(cfg.get("amplitude", 0.2))
        self._phase: float = float(cfg.get("initial_phase", 0.0))

    def process(
        self,
        num_frames: int,
        timestamp: float,
        inputs: Optional[Iterable[AudioFrame]] = None,
    ) -> AudioFrame:
        # Ignore inputs; this is a pure source.
        t = (np.arange(num_frames, dtype=np.float32) + self._phase) / float(self.sample_rate)
        phase_increment = 2.0 * np.pi * self.frequency_hz / float(self.sample_rate)

        # Compute phase per-sample to keep continuity
        phases = self._phase + phase_increment * np.arange(num_frames, dtype=np.float32)
        wave = self.amplitude * np.sin(phases, dtype=np.float32)

        # Update internal phase (wrap to avoid float blow-up)
        self._phase = float((self._phase + phase_increment * num_frames) % (2.0 * np.pi))

        # Broadcast to channels
        data = np.repeat(wave[:, None], self.channels, axis=1).astype(np.float32, copy=False)
        return AudioFrame(data=data, sample_rate=self.sample_rate, timestamp=timestamp)


class AudioFileSourceNode(BaseNode):
    """
    Load and play audio files (WAV, FLAC, etc.) using soundfile.

    Config keys:
      - file_path: str (required) - path to audio file
      - loop: bool (default False) - whether to loop the file
      - start_offset: float (default 0.0) - start position in seconds
    """

    def __init__(
        self,
        name: str,
        sample_rate: int = 48_000,
        channels: int = 2,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(name, sample_rate, channels, config)
        cfg = self.config
        
        file_path = cfg.get("file_path")
        if not file_path:
            raise ValueError("AudioFileSourceNode requires 'file_path' in config")
        
        self.file_path = Path(file_path)
        if not self.file_path.is_file():
            raise FileNotFoundError(f"Audio file not found: {self.file_path}")
        
        self.loop = bool(cfg.get("loop", False))
        self.start_offset = float(cfg.get("start_offset", 0.0))
        
        # Load audio file
        try:
            import soundfile as sf
            self._audio_data, self._file_sr = sf.read(str(self.file_path), dtype='float32')
            
            # Convert to mono if needed, then to target channels
            if self._audio_data.ndim == 1:
                self._audio_data = self._audio_data[:, None]
            
            # Resample if needed (simple linear interpolation for now)
            if self._file_sr != self.sample_rate:
                from scipy import signal
                num_samples = int(len(self._audio_data) * self.sample_rate / self._file_sr)
                self._audio_data = signal.resample(self._audio_data, num_samples, axis=0).astype(np.float32)
            
            # Match channel count
            if self._audio_data.shape[1] != self.channels:
                if self._audio_data.shape[1] == 1 and self.channels > 1:
                    self._audio_data = np.repeat(self._audio_data, self.channels, axis=1)
                else:
                    self._audio_data = self._audio_data[:, :self.channels]
            
            self._audio_data = self._audio_data.astype(np.float32)
            self._position = int(self.start_offset * self.sample_rate)
            
            # Compute overall file statistics
            self._file_duration = len(self._audio_data) / float(self.sample_rate)
            self._file_peak = float(np.max(np.abs(self._audio_data)))
            self._file_rms = float(np.sqrt(np.mean(self._audio_data.astype(np.float64) ** 2)))
            
            # Generate waveform data for visualization (downsampled to ~1000 points)
            self._waveform_points = self._generate_waveform(max_points=1000)
            
        except ImportError:
            raise ImportError("soundfile is required for AudioFileSourceNode. Install with: pip install soundfile")
        except Exception as e:
            raise RuntimeError(f"Failed to load audio file {self.file_path}: {e}") from e
    
    def _generate_waveform(self, max_points: int = 1000) -> list:
        """Generate downsampled waveform data for visualization."""
        total_samples = len(self._audio_data)
        if total_samples == 0:
            return []
        
        # Downsample to max_points for efficient rendering
        step = max(1, total_samples // max_points)
        num_points = total_samples // step
        
        # Compute min/max for each segment (creates a classic waveform look)
        waveform = []
        for i in range(num_points):
            start_idx = i * step
            end_idx = min((i + 1) * step, total_samples)
            segment = self._audio_data[start_idx:end_idx]
            
            # Get min and max for this segment (creates the waveform envelope)
            min_val = float(np.min(segment))
            max_val = float(np.max(segment))
            waveform.append({"min": min_val, "max": max_val, "time": start_idx / float(self.sample_rate)})
        
        return waveform
    
    def get_file_info(self) -> Dict[str, Any]:
        """Get metadata about the loaded audio file."""
        current_time = self._position / float(self.sample_rate)
        progress = (self._position / len(self._audio_data) * 100.0) if len(self._audio_data) > 0 else 0.0
        return {
            "file_path": str(self.file_path),
            "duration": self._file_duration,
            "current_time": current_time,
            "progress_percent": progress,
            "file_peak": self._file_peak,
            "file_rms": self._file_rms,
            "total_samples": len(self._audio_data),
            "loop": self.loop,
            "waveform": self._waveform_points,
        }

    def process(
        self,
        num_frames: int,
        timestamp: float,
        inputs: Optional[Iterable[AudioFrame]] = None,
    ) -> AudioFrame:
        if self._position >= len(self._audio_data):
            if self.loop:
                self._position = 0
            else:
                # End of file, return silence
                data = np.zeros((num_frames, self.channels), dtype=np.float32)
                return AudioFrame(data=data, sample_rate=self.sample_rate, timestamp=timestamp)
        
        end_pos = self._position + num_frames
        if end_pos > len(self._audio_data):
            if self.loop:
                # Wrap around
                chunk1 = self._audio_data[self._position:]
                remaining = num_frames - len(chunk1)
                chunk2 = self._audio_data[:remaining]
                data = np.vstack([chunk1, chunk2]).astype(np.float32)
                self._position = remaining
            else:
                # Pad with zeros
                chunk = self._audio_data[self._position:]
                pad = np.zeros((num_frames - len(chunk), self.channels), dtype=np.float32)
                data = np.vstack([chunk, pad]).astype(np.float32)
                self._position = len(self._audio_data)
        else:
            data = self._audio_data[self._position:end_pos].astype(np.float32, copy=False)
            self._position = end_pos
        
        return AudioFrame(data=data, sample_rate=self.sample_rate, timestamp=timestamp)


class PassthroughNode(BaseNode):
    """
    Sums all inputs (mixing) and passes them through unchanged otherwise.
    If no inputs are provided, outputs silence.
    """

    def process(
        self,
        num_frames: int,
        timestamp: float,
        inputs: Optional[Iterable[AudioFrame]] = None,
    ) -> AudioFrame:
        if not inputs:
            data = np.zeros((num_frames, self.channels), dtype=np.float32)
            return AudioFrame(data=data, sample_rate=self.sample_rate, timestamp=timestamp)

        inputs = list(inputs)
        # Ensure all inputs are the right length; truncate or pad with zeros if needed.
        mixed = np.zeros((num_frames, self.channels), dtype=np.float32)
        for frame in inputs:
            buf = frame.data
            # Up/down mix channels if necessary
            if frame.num_channels != self.channels:
                if frame.num_channels == 1 and self.channels > 1:
                    buf = np.repeat(buf, self.channels, axis=1)
                else:
                    buf = buf[:, : self.channels]
            # Match length
            if frame.num_frames < num_frames:
                pad = np.zeros((num_frames - frame.num_frames, self.channels), dtype=np.float32)
                buf = np.vstack([buf, pad])
            elif frame.num_frames > num_frames:
                buf = buf[:num_frames, :]
            mixed += buf.astype(np.float32, copy=False)

        return AudioFrame(data=mixed, sample_rate=self.sample_rate, timestamp=timestamp)


# ---------------------------------------------------------------------------
# DSP nodes: Gain, EQ, Delay
# ---------------------------------------------------------------------------


class GainNode(BaseNode):
    """
    Static gain in dB.

    Config keys:
      - gain_db: float, default 0.0 (negative attenuates, positive boosts)
    """

    def __init__(
        self,
        name: str,
        sample_rate: int = 48_000,
        channels: int = 2,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(name, sample_rate, channels, config)
        gain_db = float(self.config.get("gain_db", 0.0))
        self._gain_linear: float = float(10.0 ** (gain_db / 20.0))

    def process(
        self,
        num_frames: int,
        timestamp: float,
        inputs: Optional[Iterable[AudioFrame]] = None,
    ) -> AudioFrame:
        # Mix inputs (if any), then apply gain.
        passthrough = PassthroughNode(
            name=f"{self.name}_mix",
            sample_rate=self.sample_rate,
            channels=self.channels,
        )
        mixed = passthrough.process(num_frames=num_frames, timestamp=timestamp, inputs=inputs or [])
        data = mixed.data * self._gain_linear
        return AudioFrame(data=data.astype(np.float32, copy=False), sample_rate=self.sample_rate, timestamp=timestamp)


class EQNode(BaseNode):
    """
    Simple 3-band EQ implemented in the frequency domain.

    Config keys:
      - low_gain_db: float (default 0.0)
      - mid_gain_db: float (default 0.0)
      - high_gain_db: float (default 0.0)
      - low_cut_hz: float (default 200.0)
      - high_cut_hz: float (default 4000.0)

    This is not a studio-grade EQ but is deterministic and adequate for
    routing simulations and visual verification.
    """

    def __init__(
        self,
        name: str,
        sample_rate: int = 48_000,
        channels: int = 2,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(name, sample_rate, channels, config)
        cfg = self.config
        self.low_gain = float(10.0 ** (float(cfg.get("low_gain_db", 0.0)) / 20.0))
        self.mid_gain = float(10.0 ** (float(cfg.get("mid_gain_db", 0.0)) / 20.0))
        self.high_gain = float(10.0 ** (float(cfg.get("high_gain_db", 0.0)) / 20.0))

        self.low_cut_hz = float(cfg.get("low_cut_hz", 200.0))
        self.high_cut_hz = float(cfg.get("high_cut_hz", 4000.0))

    def process(
        self,
        num_frames: int,
        timestamp: float,
        inputs: Optional[Iterable[AudioFrame]] = None,
    ) -> AudioFrame:
        passthrough = PassthroughNode(
            name=f"{self.name}_mix",
            sample_rate=self.sample_rate,
            channels=self.channels,
        )
        mixed = passthrough.process(num_frames=num_frames, timestamp=timestamp, inputs=inputs or [])
        x = mixed.data  # (N, C)

        if x.size == 0:
            return AudioFrame(data=x, sample_rate=self.sample_rate, timestamp=timestamp)

        # FFT along time axis for each channel
        n = x.shape[0]
        freqs = np.fft.rfftfreq(n, d=1.0 / float(self.sample_rate))

        # Determine band masks
        low_mask = freqs < self.low_cut_hz
        high_mask = freqs > self.high_cut_hz
        mid_mask = ~(low_mask | high_mask)

        y = np.empty_like(x, dtype=np.float32)

        for ch in range(self.channels):
            spec = np.fft.rfft(x[:, ch])
            # Apply per-band gains
            spec[low_mask] *= self.low_gain
            spec[mid_mask] *= self.mid_gain
            spec[high_mask] *= self.high_gain
            # Back to time domain
            y_ch = np.fft.irfft(spec, n=n)
            y[:, ch] = y_ch.astype(np.float32, copy=False)

        return AudioFrame(data=y, sample_rate=self.sample_rate, timestamp=timestamp)


class DelayNode(BaseNode):
    """
    Simple delay with feedback and wet/dry mix.

    Config keys:
      - delay_ms: float, milliseconds of delay (default 250.0)
      - feedback: float in [0, 0.99] (default 0.3)
      - mix: float in [0, 1], 0 = dry, 1 = fully wet (default 0.5)
    """

    def __init__(
        self,
        name: str,
        sample_rate: int = 48_000,
        channels: int = 2,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(name, sample_rate, channels, config)
        cfg = self.config

        delay_ms = float(cfg.get("delay_ms", 250.0))
        self.delay_samples: int = max(1, int(round(self.sample_rate * delay_ms / 1000.0)))
        self.feedback: float = float(np.clip(cfg.get("feedback", 0.3), 0.0, 0.99))
        self.mix: float = float(np.clip(cfg.get("mix", 0.5), 0.0, 1.0))

        # Delay buffer: shape (delay_samples, channels)
        self._buffer = np.zeros((self.delay_samples, self.channels), dtype=np.float32)
        self._write_idx = 0

    def process(
        self,
        num_frames: int,
        timestamp: float,
        inputs: Optional[Iterable[AudioFrame]] = None,
    ) -> AudioFrame:
        passthrough = PassthroughNode(
            name=f"{self.name}_mix",
            sample_rate=self.sample_rate,
            channels=self.channels,
        )
        mixed = passthrough.process(num_frames=num_frames, timestamp=timestamp, inputs=inputs or [])
        dry = mixed.data

        if dry.size == 0:
            return AudioFrame(data=dry, sample_rate=self.sample_rate, timestamp=timestamp)

        wet = np.zeros_like(dry, dtype=np.float32)

        # Sample-by-sample processing with circular buffer
        # Read pointer is delay_samples behind write pointer
        for i in range(num_frames):
            # Calculate read position: delay_samples behind write position
            read_idx = (self._write_idx - self.delay_samples) % self.delay_samples
            
            # Read delayed signal from read pointer (copy to avoid view issues)
            delayed = self._buffer[read_idx].copy()  # (channels,)
            inp = dry[i].copy()

            # Write new value into buffer at write pointer (with feedback)
            self._buffer[self._write_idx] = inp + delayed * self.feedback

            # Output the delayed signal
            wet[i] = delayed

            # Advance write pointer
            self._write_idx += 1
            if self._write_idx >= self.delay_samples:
                self._write_idx = 0

        out = (1.0 - self.mix) * dry + self.mix * wet
        return AudioFrame(data=out.astype(np.float32, copy=False), sample_rate=self.sample_rate, timestamp=timestamp)


class AudioInputNode(BaseNode):
    """
    Capture audio from microphone/input device using sounddevice.
    
    Config keys:
      - device: int or str (optional) - audio device ID or name
      - channels: int (default 2) - number of input channels
    """
    
    def __init__(
        self,
        name: str,
        sample_rate: int = 48_000,
        channels: int = 2,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(name, sample_rate, channels, config)
        try:
            import sounddevice as sd
            self._sd = sd
        except ImportError:
            raise ImportError("sounddevice is required for AudioInputNode. Install with: pip install sounddevice")
        
        self._device = config.get("device") if config else None
        self._stream = None
        self._buffer = None
        self._buffer_lock = None
        
        try:
            import threading
            self._buffer_lock = threading.Lock()
        except ImportError:
            pass

    def _audio_callback(self, indata, frames, time_info, status):
        """Callback for sounddevice input stream."""
        if status:
            print(f"Audio input status: {status}")
        if self._buffer_lock:
            with self._buffer_lock:
                self._buffer = indata.copy()
        else:
            self._buffer = indata.copy()

    def process(
        self,
        num_frames: int,
        timestamp: float,
        inputs: Optional[Iterable[AudioFrame]] = None,
    ) -> AudioFrame:
        # Start stream if not running
        if self._stream is None or not self._stream.active:
            try:
                self._stream = self._sd.InputStream(
                    samplerate=self.sample_rate,
                    channels=self.channels,
                    dtype='float32',
                    device=self._device,
                    callback=self._audio_callback,
                    blocksize=num_frames,
                )
                self._stream.start()
            except Exception as e:
                print(f"Failed to start audio input: {e}")
                # Return silence on error
                data = np.zeros((num_frames, self.channels), dtype=np.float32)
                return AudioFrame(data=data, sample_rate=self.sample_rate, timestamp=timestamp)
        
        # Get latest buffer
        if self._buffer_lock:
            with self._buffer_lock:
                buffer = self._buffer.copy() if self._buffer is not None else None
        else:
            buffer = self._buffer.copy() if self._buffer is not None else None
        
        if buffer is None or len(buffer) == 0:
            # No data yet, return silence
            data = np.zeros((num_frames, self.channels), dtype=np.float32)
        else:
            # Ensure correct shape and length
            if buffer.shape[0] < num_frames:
                pad = np.zeros((num_frames - buffer.shape[0], self.channels), dtype=np.float32)
                data = np.vstack([buffer, pad]).astype(np.float32)
            elif buffer.shape[0] > num_frames:
                data = buffer[:num_frames].astype(np.float32, copy=False)
            else:
                data = buffer.astype(np.float32, copy=False)
        
        return AudioFrame(data=data, sample_rate=self.sample_rate, timestamp=timestamp)
    
    def __del__(self):
        """Clean up audio stream."""
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass


class AudioOutputNode(BaseNode):
    """
    Play audio to speakers/output device using sounddevice.
    
    This node consumes its input and plays it to the audio output.
    It returns silence (since audio is consumed by output).
    
    Config keys:
      - device: int or str (optional) - audio device ID or name
      - channels: int (default 2) - number of output channels
    """
    
    def __init__(
        self,
        name: str,
        sample_rate: int = 48_000,
        channels: int = 2,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(name, sample_rate, channels, config)
        try:
            import sounddevice as sd
            self._sd = sd
        except ImportError:
            raise ImportError("sounddevice is required for AudioOutputNode. Install with: pip install sounddevice")
        
        self._device = config.get("device") if config else None
        self._stream = None
        self._queue = []
        self._queue_lock = None
        
        try:
            import threading
            self._queue_lock = threading.Lock()
        except ImportError:
            pass

    def process(
        self,
        num_frames: int,
        timestamp: float,
        inputs: Optional[Iterable[AudioFrame]] = None,
    ) -> AudioFrame:
        # Mix inputs
        passthrough = PassthroughNode(
            name=f"{self.name}_mix",
            sample_rate=self.sample_rate,
            channels=self.channels,
        )
        mixed = passthrough.process(num_frames=num_frames, timestamp=timestamp, inputs=inputs or [])
        audio_data = mixed.data
        
        # Start stream if not running
        if self._stream is None or not self._stream.active:
            try:
                self._stream = self._sd.OutputStream(
                    samplerate=self.sample_rate,
                    channels=self.channels,
                    dtype='float32',
                    device=self._device,
                    blocksize=num_frames,
                )
                self._stream.start()
            except Exception as e:
                print(f"Failed to start audio output: {e}")
                # Return silence on error
                return AudioFrame(data=np.zeros((num_frames, self.channels), dtype=np.float32), 
                                sample_rate=self.sample_rate, timestamp=timestamp)
        
        # Play audio (non-blocking write)
        try:
            if self._stream.active:
                self._stream.write(audio_data)
        except Exception as e:
            print(f"Error writing to audio output: {e}")
        
        # Output node returns silence (audio is consumed)
        return AudioFrame(
            data=np.zeros((num_frames, self.channels), dtype=np.float32),
            sample_rate=self.sample_rate,
            timestamp=timestamp
        )
    
    def __del__(self):
        """Clean up audio stream."""
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
