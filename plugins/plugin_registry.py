# -*- coding: utf-8 -*-
"""
================================================================================
PLUGIN REGISTRY - Auto-Discovery and Management of Console Plugins
================================================================================
Provides automatic plugin registration and ROM-to-plugin matching.
================================================================================
"""

from typing import Dict, List, Optional, Type
import importlib
import pkgutil
from pathlib import Path

from .base_plugin import BaseConsolePlugin, ConsoleType


class PluginRegistry:
    """
    Registry for console plugins.
    Handles auto-discovery, registration, and ROM matching.
    """

    _instance: Optional['PluginRegistry'] = None
    _plugins: Dict[ConsoleType, Type[BaseConsolePlugin]] = {}
    _plugin_instances: Dict[ConsoleType, BaseConsolePlugin] = {}

    def __new__(cls) -> 'PluginRegistry':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._discover_plugins()
        return cls._instance

    def _discover_plugins(self) -> None:
        """Auto-discover and register all available plugins."""
        # Get the plugins package directory
        plugins_dir = Path(__file__).parent

        # Import all plugin modules
        for module_info in pkgutil.iter_modules([str(plugins_dir)]):
            if module_info.name.endswith('_plugin'):
                try:
                    module = importlib.import_module(f'.{module_info.name}', 'plugins')

                    # Find plugin classes in module
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (isinstance(attr, type) and
                            issubclass(attr, BaseConsolePlugin) and
                            attr is not BaseConsolePlugin):

                            # Instantiate to get console type
                            try:
                                instance = attr()
                                console_type = instance.console_spec.console_type
                                self._plugins[console_type] = attr
                                self._plugin_instances[console_type] = instance
                            except Exception:
                                pass  # Skip plugins that fail to instantiate

                except Exception as e:
                    print(f"Warning: Failed to load plugin module {module_info.name}: {e}")

    def register(self, plugin_class: Type[BaseConsolePlugin]) -> None:
        """
        Manually register a plugin class.

        Args:
            plugin_class: Plugin class to register
        """
        instance = plugin_class()
        console_type = instance.console_spec.console_type
        self._plugins[console_type] = plugin_class
        self._plugin_instances[console_type] = instance

    def get_plugin(self, console_type: ConsoleType) -> Optional[BaseConsolePlugin]:
        """
        Get plugin instance by console type.

        Args:
            console_type: Target console type

        Returns:
            Plugin instance or None if not found
        """
        return self._plugin_instances.get(console_type)

    def get_plugin_for_rom(self, rom_data: bytes) -> Optional[BaseConsolePlugin]:
        """
        Detect console and return appropriate plugin.

        Args:
            rom_data: Raw ROM bytes

        Returns:
            Plugin instance that can handle this ROM, or None
        """
        # Priority order for detection (most specific first)
        priority_order = [
            ConsoleType.NES,    # Has clear magic number
            ConsoleType.SNES,   # Has header with checksum
            ConsoleType.N64,    # Has clear magic number
            ConsoleType.GBA,    # Has fixed value at 0xB2
            ConsoleType.PS1,    # Has PS-X EXE header
            ConsoleType.MD,     # Has SEGA string
            ConsoleType.SMS,    # Least specific detection
        ]

        for console_type in priority_order:
            plugin = self._plugin_instances.get(console_type)
            if plugin and plugin.detect_rom(rom_data):
                # Create fresh instance for this ROM
                fresh_instance = self._plugins[console_type]()
                fresh_instance.set_rom_data(rom_data)
                return fresh_instance

        return None

    def get_all_plugins(self) -> List[BaseConsolePlugin]:
        """
        Get all registered plugin instances.

        Returns:
            List of all plugin instances
        """
        return list(self._plugin_instances.values())

    def get_supported_consoles(self) -> List[ConsoleType]:
        """
        Get list of supported console types.

        Returns:
            List of ConsoleType values
        """
        return list(self._plugins.keys())

    def is_supported(self, console_type: ConsoleType) -> bool:
        """
        Check if a console type is supported.

        Args:
            console_type: Console type to check

        Returns:
            True if plugin exists for this console
        """
        return console_type in self._plugins

    def __repr__(self) -> str:
        supported = [ct.value for ct in self._plugins.keys()]
        return f"<PluginRegistry plugins={supported}>"


# Convenience function for quick access
def get_plugin_for_rom(rom_data: bytes) -> Optional[BaseConsolePlugin]:
    """
    Get the appropriate plugin for a ROM.

    Args:
        rom_data: Raw ROM bytes

    Returns:
        Plugin instance or None if no matching plugin
    """
    registry = PluginRegistry()
    return registry.get_plugin_for_rom(rom_data)


def get_registry() -> PluginRegistry:
    """Get the plugin registry singleton."""
    return PluginRegistry()
