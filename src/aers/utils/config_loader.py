from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Any, Dict, Tuple

import yaml

from aers.core.graph_engine import Connection


@dataclass(frozen=True)
class RoutingConfig:
    sample_rate: int
    frame_size: int
    node_specs: List[Dict[str, Any]]
    connections: List[Connection]
    node_positions: Dict[str, Tuple[float, float]] = field(default_factory=dict)


def load_routing_config(path: str) -> RoutingConfig:
    """
    Load routing configuration from a YAML file.

    Expected structure:
        sample_rate: 48000
        frame_size: 2048
        nodes:
          - id: source1
            kind: sine_source
            params:
              frequency: 440.0
              amplitude: 0.2
              channels: 2
          - id: bus_main
            kind: gain
            params:
              gain_db: -3.0
        connections:
          - from: source1
            to: bus_main
    """
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        raise ValueError(f"Config at {path} must be a mapping")

    sample_rate = int(raw.get("sample_rate", 48000))
    frame_size = int(raw.get("frame_size", 1024))

    node_specs = raw.get("nodes", [])
    if not isinstance(node_specs, list):
        raise ValueError("Config 'nodes' must be a list")

    raw_conns = raw.get("connections", [])
    if not isinstance(raw_conns, list):
        raise ValueError("Config 'connections' must be a list")

    connections: List[Connection] = []
    for c in raw_conns:
        try:
            src = c["from"]
            dst = c["to"]
        except KeyError as e:
            raise ValueError(f"Connection entry missing key: {e}") from e
        connections.append(Connection(src=src, dst=dst))
    
    # Load node positions if present
    node_positions: Dict[str, Tuple[float, float]] = {}
    for node_spec in node_specs:
        node_id = node_spec.get("id")
        if node_id and "position" in node_spec:
            pos = node_spec["position"]
            if isinstance(pos, dict):
                node_positions[node_id] = (float(pos.get("x", 0)), float(pos.get("y", 0)))
            elif isinstance(pos, (list, tuple)) and len(pos) >= 2:
                node_positions[node_id] = (float(pos[0]), float(pos[1]))

    return RoutingConfig(
        sample_rate=sample_rate,
        frame_size=frame_size,
        node_specs=node_specs,
        connections=connections,
        node_positions=node_positions,
    )

