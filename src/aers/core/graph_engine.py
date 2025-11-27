# src/aers/core/graph_engine.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple, Iterable, Optional, Set

import numpy as np

from .events import AudioFrame
from .nodes import BaseNode
from aers.modules import create_node_instance


@dataclass(frozen=True)
class Connection:
    src: str
    dst: str


class GraphEngine:
    """
    Core audio routing engine.

    Responsibilities:
      - Build a directed acyclic graph (DAG) of nodes.
      - For each processing block, execute nodes in topological order.
      - Sum all inputs for a node before passing to its processor.
    """

    def __init__(
        self,
        sample_rate: int,
        frame_size: int,
        node_specs: List[dict],
        connections: List[Connection],
        default_channels: int = 2,
        node_positions: Optional[Dict[str, Tuple[float, float]]] = None,
    ) -> None:
        self.sample_rate = int(sample_rate)
        self.frame_size = int(frame_size)
        self.default_channels = int(default_channels)

        self._nodes: Dict[str, BaseNode] = {}
        self._connections: List[Connection] = connections
        self._node_positions: Dict[str, Tuple[float, float]] = node_positions or {}
        self._layout_version: int = 0

        self._build_nodes(node_specs)
        self._validate()
        self._execution_order: List[str] = self._topological_sort()

    # --------------------------------------------------------------------- #
    # Graph building
    # --------------------------------------------------------------------- #
    def _build_nodes(self, node_specs: List[dict]) -> None:
        for spec in node_specs:
            node_id = spec["id"]
            kind = spec.get("kind", "passthrough")
            config = dict(spec.get("params", {}))
            channels = int(config.pop("channels", self.default_channels))

            if node_id in self._nodes:
                raise ValueError(f"Duplicate node id '{node_id}' found in config")

            node = create_node_instance(
                kind=kind,
                name=node_id,
                sample_rate=self.sample_rate,
                channels=channels,
                config=config,
            )
            self._nodes[node_id] = node

    def _validate(self) -> None:
        # Ensure all connection endpoints exist
        ids: Set[str] = set(self._nodes.keys())
        for c in self._connections:
            if c.src not in ids:
                raise ValueError(f"Connection references unknown src node '{c.src}'")
            if c.dst not in ids:
                raise ValueError(f"Connection references unknown dst node '{c.dst}'")

    def _topological_sort(self) -> List[str]:
        """
        Kahn's algorithm for topological sort.
        Raises if a cycle is detected.
        """
        incoming_count: Dict[str, int] = {nid: 0 for nid in self._nodes.keys()}
        for c in self._connections:
            incoming_count[c.dst] += 1

        # Start with nodes that have no incoming edges
        queue: List[str] = [nid for nid, cnt in incoming_count.items() if cnt == 0]
        order: List[str] = []

        outgoing: Dict[str, List[str]] = {nid: [] for nid in self._nodes.keys()}
        for c in self._connections:
            outgoing[c.src].append(c.dst)

        while queue:
            nid = queue.pop(0)
            order.append(nid)
            for dst in outgoing[nid]:
                incoming_count[dst] -= 1
                if incoming_count[dst] == 0:
                    queue.append(dst)

        if len(order) != len(self._nodes):
            raise ValueError("Graph contains a cycle; topological sort failed")

        return order

    # --------------------------------------------------------------------- #
    # Processing
    # --------------------------------------------------------------------- #
    def _build_input_map(self) -> Dict[str, List[str]]:
        inputs: Dict[str, List[str]] = {nid: [] for nid in self._nodes.keys()}
        for c in self._connections:
            inputs[c.dst].append(c.src)
        return inputs

    def process_frame(self, frame_index: int) -> Dict[str, AudioFrame]:
        """
        Process a single block of audio and return frames for all nodes.

        Returns:
            Dict mapping node_id -> AudioFrame for this block.
        """
        inputs_map = self._build_input_map()
        outputs: Dict[str, AudioFrame] = {}

        # Calculate timestamp for this frame
        timestamp = float(frame_index * self.frame_size) / float(self.sample_rate)

        for node_id in self._execution_order:
            node = self._nodes[node_id]
            input_ids = inputs_map[node_id]
            input_frames: Optional[Iterable[AudioFrame]] = None

            if input_ids:
                # Collect all input frames
                input_frames = [outputs[i] for i in input_ids]

            frame = node.process(
                num_frames=self.frame_size,
                timestamp=timestamp,
                inputs=input_frames,
            )
            outputs[node_id] = frame

        return outputs

    def run(
        self,
        num_frames: int,
        track_nodes: Optional[Iterable[str]] = None,
    ) -> Dict[str, AudioFrame]:
        """
        Run the graph for 'num_frames' (blocks, not samples) and return
        the final frame for the specified nodes (or all nodes if None).
        """
        tracked = set(track_nodes) if track_nodes is not None else None
        last_frames: Dict[str, AudioFrame] = {}

        for frame_idx in range(num_frames):
            frames = self.process_frame(frame_idx)
            for nid, frame in frames.items():
                if tracked is None or nid in tracked:
                    last_frames[nid] = frame

        return last_frames

    # --------------------------------------------------------------------- #
    # Introspection helpers
    # --------------------------------------------------------------------- #
    @property
    def nodes(self) -> Dict[str, BaseNode]:
        return dict(self._nodes)

    @property
    def connections(self) -> List[Connection]:
        return list(self._connections)

    @property
    def execution_order(self) -> List[str]:
        return list(self._execution_order)
    
    def set_node_position(self, node_id: str, x: float, y: float) -> None:
        """Update node position in layout."""
        if node_id not in self._nodes:
            raise ValueError(f"Node '{node_id}' not found")
        self._node_positions[node_id] = (float(x), float(y))
        self._layout_version += 1
    
    def get_node_position(self, node_id: str) -> Tuple[float, float]:
        """Get node position, defaulting to (0, 0) if not set."""
        return self._node_positions.get(node_id, (0.0, 0.0))
    
    def get_graph_state(self) -> Dict[str, any]:
        """Get complete graph state including layout for visualization."""
        from aers.modules import NODE_TYPE_REGISTRY
        
        # Map node classes to kind names
        kind_map = {}
        for k, v in NODE_TYPE_REGISTRY.items():
            kind_map[v] = k
        
        nodes = []
        for node_id, node in self._nodes.items():
            node_type = type(node)
            kind = "unknown"
            
            # Check if node type is in registry
            if node_type in kind_map:
                kind = kind_map[node_type]
            else:
                # Try to match by class name
                for cls, k in kind_map.items():
                    if node_type == cls:
                        kind = k
                        break
            
            pos = self.get_node_position(node_id)
            nodes.append({
                "id": node_id,
                "name": node.name,
                "kind": kind,
                "position": {"x": pos[0], "y": pos[1]},
            })
        
        connections = [
            {"from": conn.src, "to": conn.dst}
            for conn in self._connections
        ]
        
        return {
            "nodes": nodes,
            "connections": connections,
            "layout_version": self._layout_version,
        }
