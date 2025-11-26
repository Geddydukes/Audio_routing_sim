#!/usr/bin/env python
"""Run AERS with real audio I/O (file input, mic input, or speaker output)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from aers.utils.config_loader import load_routing_config
from aers.core.graph_engine import GraphEngine


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run AERS audio routing with real audio I/O."
    )
    parser.add_argument(
        "--config",
        "-c",
        required=True,
        help="Path to YAML routing configuration file.",
    )
    parser.add_argument(
        "--duration",
        "-d",
        type=float,
        default=10.0,
        help="Duration to run in seconds (default: 10.0). Use 0 for infinite.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_path = Path(args.config)

    if not config_path.is_file():
        print(f"[ERROR] Config file not found: {config_path}", file=sys.stderr)
        return 1

    routing = load_routing_config(str(config_path))

    engine = GraphEngine(
        sample_rate=routing.sample_rate,
        frame_size=routing.frame_size,
        node_specs=routing.node_specs,
        connections=routing.connections,
        default_channels=2,
    )

    print(f"Starting audio routing...")
    print(f"  Sample rate: {routing.sample_rate} Hz")
    print(f"  Frame size: {routing.frame_size} samples")
    print(f"  Duration: {args.duration}s" if args.duration > 0 else "  Duration: infinite")
    print(f"  Nodes: {', '.join(engine.nodes.keys())}")
    print()
    print("Press Ctrl+C to stop...")
    print()

    try:
        import time
        frame_duration = routing.frame_size / float(routing.sample_rate)
        num_frames_total = int(args.duration / frame_duration) if args.duration > 0 else None
        
        frame_index = 0
        start_time = time.time()
        
        while True:
            if num_frames_total and frame_index >= num_frames_total:
                break
            
            # Process one frame
            outputs = engine.process_frame(frame_index)
            
            # Print progress every second
            if frame_index % int(1.0 / frame_duration) == 0:
                elapsed = time.time() - start_time
                print(f"Running... {elapsed:.1f}s", end='\r')
            
            frame_index += 1
            
            # Small sleep to prevent CPU spinning
            time.sleep(frame_duration * 0.1)
            
    except KeyboardInterrupt:
        print("\n\nStopped by user.")
    except Exception as e:
        print(f"\n[ERROR] {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

