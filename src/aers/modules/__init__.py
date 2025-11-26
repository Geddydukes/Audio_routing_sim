"""
Module registry and plugin factory for AERS.

Responsibilities:
- Map node kinds to built-in node classes
- Optionally load plugin-defined node classes with security controls
- Expose get_node_class() and create_node_instance()
"""

from __future__ import annotations

import importlib
import inspect
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Type

from aers.core.nodes import (
    BaseNode,
    AudioFileSourceNode,
    AudioInputNode,
    AudioOutputNode,
    DelayNode,
    EQNode,
    GainNode,
    PassthroughNode,
    SineSourceNode,
)
from aers.security import load_manifest, verify_manifest_hash, PluginManifest


# ---------------------------------------------------------------------------
# Built-in registry
# ---------------------------------------------------------------------------

NODE_TYPE_REGISTRY: Mapping[str, Type[BaseNode]] = {
    "sine": SineSourceNode,
    "audio_file": AudioFileSourceNode,
    "audio_input": AudioInputNode,
    "audio_output": AudioOutputNode,
    "passthrough": PassthroughNode,
    "gain": GainNode,
    "eq": EQNode,
    "delay": DelayNode,
}


# ---------------------------------------------------------------------------
# Plugin security configuration
# ---------------------------------------------------------------------------

# Restrict which top-level package prefixes can be used for plugins.
# In a real deployment this would be something like "aers_plugins."
ALLOWED_PLUGIN_PACKAGE_PREFIXES = ("example_gain_plugin", "aers_plugins")

# Root directory where plugin packages are stored (adjust as needed).
DEFAULT_PLUGIN_ROOT = Path(os.getenv("AERS_PLUGIN_ROOT", "plugins")).resolve()


@dataclass
class NodeConfig:
    """Canonical node config passed into create_node_instance."""

    name: str
    kind: str
    params: Dict[str, Any]


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------


def get_node_class(
    kind: str,
    config: Optional[Dict[str, Any]] = None,
    manifest: Optional[PluginManifest] = None,
) -> Type[BaseNode]:
    """
    Resolve a node class for a given kind.

    Lookup order:
    1. Built-in registry
    2. Plugin via config["plugin"] (legacy)
    3. Plugin module declared in manifest (if provided)

    Raises KeyError if the kind is unknown.
    """
    kind = kind.lower()

    # 1) Built-in lookup
    cls = NODE_TYPE_REGISTRY.get(kind)
    if cls is not None:
        return cls

    # 2) Legacy plugin lookup via config
    if kind == "plugin":
        if not config or "plugin" not in config:
            raise ValueError("Plugin node requires 'plugin' configuration dict.")
        plugin_cfg = config["plugin"]
        module_path = plugin_cfg.get("module")
        class_name = plugin_cfg.get("class")
        if not module_path or not class_name:
            raise ValueError("Plugin config must include 'module' and 'class' keys.")
        return _load_plugin_node_class(module_path, class_name)

    # 3) Plugin lookup via manifest
    if manifest is not None:
        if kind not in manifest.allowed_node_kinds:
            raise KeyError(
                f"Kind '{kind}' not allowed by plugin manifest '{manifest.name}'"
            )
        module_path = manifest.module
        _ensure_allowed_prefix(module_path)
        module = importlib.import_module(module_path)

        # Convention: plugin exports a mapping PLUGIN_NODE_TYPES
        plugin_registry = getattr(module, "PLUGIN_NODE_TYPES", None)
        if not isinstance(plugin_registry, dict):
            raise KeyError(
                f"Plugin module '{module_path}' must define PLUGIN_NODE_TYPES dict"
            )

        cls = plugin_registry.get(kind)
        if cls is None:
            raise KeyError(
                f"Kind '{kind}' not found in plugin module '{module_path}'"
            )
        return cls

    available = ", ".join(sorted(NODE_TYPE_REGISTRY.keys()))
    raise KeyError(f"Unknown node kind '{kind}'. Available kinds: {available}")


def create_node_instance(
    kind: str,
    name: str,
    sample_rate: int,
    channels: int,
    config: Optional[Dict[str, Any]] = None,
    manifest_path: Optional[str] = None,
) -> BaseNode:
    """
    Factory entry-point used by the GraphEngine to construct nodes.

    Parameters
    ----------
    kind:
        The node kind string from the routing config, e.g. "sine", "gain", "eq", "delay", or "plugin".
    name:
        Node identifier / human-readable name.
    sample_rate:
        Audio sample rate for processing.
    channels:
        Number of channels this node should operate on.
    config:
        Optional configuration dict for the node, as loaded from YAML/JSON.
    manifest_path:
        Optional path to plugin manifest for secure plugin loading.
    """
    manifest: Optional[PluginManifest] = None
    if manifest_path:
        manifest = _load_and_verify_plugin_manifest(manifest_path)

    cls = get_node_class(kind, config=config, manifest=manifest)

    # Ensure the class has the expected signature
    sig = inspect.signature(cls.__init__)
    if "name" not in sig.parameters:
        raise TypeError(
            f"Node class '{cls.__name__}' must accept 'name' argument in __init__"
        )

    return cls(name=name, sample_rate=sample_rate, channels=channels, config=config or {})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ensure_allowed_prefix(module_path: str) -> None:
    """
    Ensure that a plugin module path uses an allowed prefix.

    This prevents arbitrary imports such as 'os', 'subprocess', etc.
    """
    if not any(
        module_path.startswith(prefix + ".") or module_path == prefix
        for prefix in ALLOWED_PLUGIN_PACKAGE_PREFIXES
    ):
        raise ImportError(
            f"Plugin module '{module_path}' not allowed; "
            f"must start with one of {ALLOWED_PLUGIN_PACKAGE_PREFIXES}"
        )


def _load_plugin_node_class(module_path: str, class_name: str) -> Type[BaseNode]:
    """
    Load a plugin node class from a Python module in a restricted namespace.

    Only modules whose dotted path begins with one of the ALLOWED_PLUGIN_PACKAGE_PREFIXES
    are accepted. This prevents arbitrary code execution from untrusted configs.
    """
    _ensure_allowed_prefix(module_path)

    module = importlib.import_module(module_path)
    try:
        cls = getattr(module, class_name)
    except AttributeError as exc:
        raise ImportError(f"Module '{module_path}' has no attribute '{class_name}'") from exc

    if not isinstance(cls, type) or not issubclass(cls, BaseNode):
        raise TypeError(
            f"Plugin class '{module_path}:{class_name}' must be a subclass of BaseNode."
        )

    return cls


def _load_and_verify_plugin_manifest(manifest_path: str) -> PluginManifest:
    """
    Load and verify a plugin manifest.

    - Ensures the manifest is structurally valid
    - Verifies that the hash matches the plugin directory contents
    """
    manifest = load_manifest(manifest_path)

    # Infer plugin root directory based on manifest and DEFAULT_PLUGIN_ROOT
    plugin_root = DEFAULT_PLUGIN_ROOT / manifest.name
    if not verify_manifest_hash(manifest, plugin_root):
        raise ValueError(
            f"Plugin hash mismatch for '{manifest.name}'; "
            f"plugin directory may have been modified."
        )

    return manifest


__all__ = [
    "BaseNode",
    "SineSourceNode",
    "AudioFileSourceNode",
    "AudioInputNode",
    "AudioOutputNode",
    "PassthroughNode",
    "GainNode",
    "EQNode",
    "DelayNode",
    "NODE_TYPE_REGISTRY",
    "NodeConfig",
    "get_node_class",
    "create_node_instance",
]
