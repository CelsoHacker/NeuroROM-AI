# -*- coding: utf-8 -*-
"""
================================================================================
ORCHESTRATOR MODULE - Main Pipeline Controller
================================================================================
Controls the complete text extraction pipeline:
1. Console detection → plugin selection
2. Static extraction
3. Runtime capture (for N64/PS1: AUTO_DEEP)
4. Unification
5. Policy enforcement
6. Neutral export

Components:
- plugin_orchestrator: Main entry point
- policy_enforcer: NoEmptyOutputPolicy and validation rules
================================================================================
"""

from .plugin_orchestrator import PluginOrchestrator, run_extraction
from .policy_enforcer import PolicyEnforcer, NoEmptyOutputPolicy

__all__ = [
    'PluginOrchestrator',
    'run_extraction',
    'PolicyEnforcer',
    'NoEmptyOutputPolicy',
]
