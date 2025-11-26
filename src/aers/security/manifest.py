import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any

import yaml


@dataclass
class PluginManifest:
    """
    Declarative description of a plugin package.

    The plugin manifest is YAML like:
    ---
    name: "example_gain_plugin"
    version: "1.0.0"
    module: "example_gain_plugin.gain"
    hash:
      algorithm: "sha256"
      value: "<hex-digest-of-plugin-dir>"
    allowed_node_kinds:
      - "gain"
    """

    name: str
    version: str
    module: str
    hash_algorithm: str
    hash_value: str
    allowed_node_kinds: list[str]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PluginManifest":
        try:
            hash_info = data["hash"]
        except KeyError as exc:
            raise ValueError("Manifest missing required 'hash' field") from exc

        return cls(
            name=str(data["name"]),
            version=str(data["version"]),
            module=str(data["module"]),
            hash_algorithm=str(hash_info["algorithm"]).lower(),
            hash_value=str(hash_info["value"]),
            allowed_node_kinds=list(data.get("allowed_node_kinds", [])),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "module": self.module,
            "hash": {
                "algorithm": self.hash_algorithm,
                "value": self.hash_value,
            },
            "allowed_node_kinds": self.allowed_node_kinds,
        }


def load_manifest(path: str | os.PathLike[str]) -> PluginManifest:
    """
    Load a plugin manifest from YAML.

    Raises ValueError if validation fails.
    """
    path_obj = Path(path)
    if not path_obj.is_file():
        raise FileNotFoundError(f"Plugin manifest not found: {path_obj}")

    with path_obj.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Invalid manifest structure in {path_obj}")

    manifest = PluginManifest.from_dict(data)
    validate_manifest(manifest)
    return manifest


def validate_manifest(manifest: PluginManifest) -> None:
    """
    Basic structural validation. This is intentionally strict but simple.
    """
    if not manifest.name:
        raise ValueError("Manifest 'name' cannot be empty")
    if not manifest.version:
        raise ValueError("Manifest 'version' cannot be empty")
    if "." not in manifest.module:
        raise ValueError("Manifest 'module' must be a fully qualified module path")
    if manifest.hash_algorithm not in ("sha256",):
        raise ValueError(f"Unsupported hash algorithm: {manifest.hash_algorithm}")
    if not manifest.hash_value or len(manifest.hash_value) < 32:
        raise ValueError("Manifest 'hash.value' appears invalid (too short)")
    if not manifest.allowed_node_kinds:
        raise ValueError("Manifest must declare at least one allowed_node_kinds")


def _hash_directory_sha256(root: Path) -> str:
    """
    Compute a deterministic SHA256 hash of all files under the directory.

    - Walks the directory in sorted order
    - Ignores __pycache__ and hidden directories
    - Includes relative path + file bytes in digest
    """
    digest = hashlib.sha256()

    for path in sorted(root.rglob("*")):
        if path.is_dir():
            # Ignore hidden and __pycache__ directories
            parts = path.parts
            if any(p.startswith(".") for p in parts):
                continue
            if "__pycache__" in parts:
                continue
            continue

        if path.name.startswith("."):
            continue

        rel_path = path.relative_to(root)
        digest.update(str(rel_path).encode("utf-8"))

        with path.open("rb") as f:
            while chunk := f.read(8192):
                digest.update(chunk)

    return digest.hexdigest()


def verify_manifest_hash(manifest: PluginManifest, plugin_root: str | os.PathLike[str]) -> bool:
    """
    Verify that the hash in the manifest matches the plugin directory contents.

    This is a coarse-grained guarantee that plugin code has not been tampered with.
    """
    root = Path(plugin_root).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Plugin directory not found: {root}")

    if manifest.hash_algorithm != "sha256":
        raise ValueError(f"Unsupported hash algorithm: {manifest.hash_algorithm}")

    computed = _hash_directory_sha256(root)
    return computed == manifest.hash_value


def manifest_to_json(manifest: PluginManifest) -> str:
    """
    Useful for debugging and logging.
    """
    return json.dumps(manifest.to_dict(), sort_keys=True, indent=2)

