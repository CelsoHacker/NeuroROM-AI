# -*- coding: utf-8 -*-
"""
================================================================================
PLUGINS - Multi-Console ROM Translation Plugin System
================================================================================
Plugin-based architecture for NES, SMS, MD, SNES, GBA, N64, PS1 support.
Each console has specialized extraction logic while sharing universal tools.
================================================================================
"""

from .base_plugin import (
    ConsoleType,
    ConsoleSpec,
    BaseConsolePlugin,
    PluginCapability,
)
from .plugin_registry import PluginRegistry, get_plugin_for_rom

__all__ = [
    'ConsoleType',
    'ConsoleSpec',
    'BaseConsolePlugin',
    'PluginCapability',
    'PluginRegistry',
    'get_plugin_for_rom',
]
