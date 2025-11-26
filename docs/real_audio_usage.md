# Real Audio Routing - Usage Guide

## Overview

AERS now supports real audio I/O:
- **Audio File Playback**: Load and play WAV, FLAC, and other audio files
- **Microphone Input**: Capture audio from your microphone
- **Speaker Output**: Play processed audio to your speakers

## Quick Start

### 1. Install Audio Dependencies

```bash
source .venv/bin/activate
pip install sounddevice scipy
```

### 2. Audio File Playback

Create a config file (e.g., `configs/my_audio.yaml`):

```yaml
sample_rate: 48000
frame_size: 1024

nodes:
  - id: file_source
    kind: audio_file
    params:
      file_path: "path/to/your/audio.wav"
      loop: true
      channels: 2

  - id: bus_main
    kind: gain
    params:
      gain_db: -3.0

  - id: output
    kind: audio_output
    params:
      channels: 2

connections:
  - from: file_source
    to: bus_main
  - from: bus_main
    to: output
```

Run with:
```bash
PYTHONPATH=src python scripts/run_server.py --reload
```

### 3. Microphone to Speaker (Live Monitoring)

Use `configs/mic_to_speaker.yaml`:

```yaml
sample_rate: 48000
frame_size: 512  # Smaller for lower latency

nodes:
  - id: mic_input
    kind: audio_input
    params:
      channels: 2

  - id: gain_control
    kind: gain
    params:
      gain_db: 0.0

  - id: speaker_output
    kind: audio_output
    params:
      channels: 2

connections:
  - from: mic_input
    to: gain_control
  - from: gain_control
    to: speaker_output
```

## Node Types

### AudioFileSourceNode
- **kind**: `audio_file`
- **params**:
  - `file_path` (required): Path to audio file
  - `loop` (default: false): Whether to loop the file
  - `start_offset` (default: 0.0): Start position in seconds

### AudioInputNode
- **kind**: `audio_input`
- **params**:
  - `device` (optional): Audio device ID or name
  - `channels` (default: 2): Number of input channels

### AudioOutputNode
- **kind**: `audio_output`
- **params**:
  - `device` (optional): Audio device ID or name
  - `channels` (default: 2): Number of output channels

## Finding Audio Devices

To list available audio devices:

```python
import sounddevice as sd
print(sd.query_devices())
```

Then use the device ID or name in your config.

## Example Configurations

### File → EQ → Output
```yaml
nodes:
  - id: file_source
    kind: audio_file
    params:
      file_path: "music.wav"
      loop: true

  - id: eq_processor
    kind: eq
    params:
      low_gain_db: 0.0
      mid_gain_db: 2.0
      high_gain_db: 0.0

  - id: output
    kind: audio_output

connections:
  - from: file_source
    to: eq_processor
  - from: eq_processor
    to: output
```

### Mic → Delay → Output (Echo Effect)
```yaml
nodes:
  - id: mic
    kind: audio_input

  - id: delay_fx
    kind: delay
    params:
      delay_ms: 250.0
      feedback: 0.3
      mix: 0.5

  - id: output
    kind: audio_output

connections:
  - from: mic
    to: delay_fx
  - from: delay_fx
    to: output
```

## Notes

- **Latency**: Use smaller `frame_size` (e.g., 512) for lower latency
- **Sample Rate**: Match your audio file's sample rate or use 48kHz
- **Channels**: Ensure all nodes use the same channel count
- **Real-time**: The server processes audio in real-time when using `audio_input` and `audio_output`

## Troubleshooting

- **No audio**: Check audio device permissions and device selection
- **Latency**: Reduce `frame_size` in config
- **Clicks/pops**: Increase `frame_size` or check sample rate matching
- **Import errors**: Install `sounddevice` and `scipy`

