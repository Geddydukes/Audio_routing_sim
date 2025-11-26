# scripts/run_simulation.py

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from aers.utils.config_loader import load_routing_config
from aers.core.graph_engine import GraphEngine


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Audio Event Routing Simulator (AERS) on a routing config."
    )
    parser.add_argument(
        "--config",
        "-c",
        required=True,
        help="Path to YAML routing configuration file.",
    )
    parser.add_argument(
        "--frames",
        "-f",
        type=int,
        default=1,
        help="Number of processing blocks to run.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
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

    # Track all nodes by default
    last_frames = engine.run(num_frames=args.frames)

    for node_id, frame in last_frames.items():
        print(
            f"Node {node_id}: buffer shape={frame.data.shape}, "
            f"peak={frame.peak:.4f}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

