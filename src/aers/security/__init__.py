"""
Security utilities for AERS.

This package focuses on:
- Plugin manifest validation
- Hash verification for plugin code
- Basic path and import restrictions
"""

from .manifest import (
    PluginManifest,
    load_manifest,
    verify_manifest_hash,
    validate_manifest,
)

__all__ = [
    "PluginManifest",
    "load_manifest",
    "verify_manifest_hash",
    "validate_manifest",
]

