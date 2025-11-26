# src/aers/modules/gain.py

from __future__ import annotations

import math
from typing import Mapping, Any, Optional

import numpy as np

from aers.core.nodes import Node, AudioBuffer, NodeContext, NodeError
from . import register_node_type


class Gain(Node):
    """
    Simple gain node.

    Parameters (in params mapping):
    - gain_db: float (default 0.0)
      Gain in decibels to apply to the incoming buffer.
    """

    def __init__(
        self,
        node_id: str,
        params: Optional[Mapping[str, Any]] = None,
        context: Optional[NodeContext] = None,
    ) -> None:
        super().__init__(node_id=node_id, params=params, context=context)
        raw_gain = self.params.get("gain_db", 0.0)
        try:
            self._gain_db = float(raw_gain)
        except (TypeError, ValueError) as exc:
            raise NodeError(f"{self.id}: invalid gain_db value {raw_gain!r}") from exc

    def process(self, buffer: AudioBuffer, timestamp: float) -> AudioBuffer:
        if not isinstance(buffer, np.ndarray):
            raise NodeError(f"{self.id}: buffer must be numpy.ndarray")
        factor = self._db_to_linear(self._gain_db)
        # Multiply in float32 space
        return (buffer.astype(np.float32, copy=False) * factor).astype(np.float32, copy=False)

    @staticmethod
    def _db_to_linear(db_value: float) -> float:
        return math.pow(10.0, db_value / 20.0)


# Register under a simple logical type name
register_node_type("gain", Gain)
