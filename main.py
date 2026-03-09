#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ROM Translation Framework - Main Entry Point
================================================================================
Universal ROM Translation Framework

Usage:
    python main.py          - Launch GUI application
    python main.py --cli    - Run in CLI mode (future)
    python main.py --help   - Show help message

Author: Celso
License: Proprietary
================================================================================
"""

import sys
import os
import re

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)


def _sanitize_error(msg) -> str:
    """Remove possíveis API keys / tokens de mensagens de erro."""
    s = str(msg)
    s = re.sub(r'AIza[0-9A-Za-z\-_]{10,}', '[REDACTED]', s)
    s = re.sub(r'([?&]key=)[^&\s]+', r'\1[REDACTED]', s)
    s = re.sub(r'(Bearer\s+)[A-Za-z0-9\-_\.]{10,}', r'\1[REDACTED]', s)
    s = re.sub(r'sk-[A-Za-z0-9]{10,}', 'sk-[REDACTED]', s)
    return s


def check_dependencies():
    """Check if required dependencies are installed."""
    missing = []

    try:
        import PyQt6
    except ImportError:
        missing.append("PyQt6")

    try:
        import numpy
    except ImportError:
        missing.append("numpy")

    try:
        import requests
    except ImportError:
        missing.append("requests")

    if missing:
        print("=" * 60)
        print("MISSING DEPENDENCIES")
        print("=" * 60)
        print(f"\nThe following packages are required but not installed:")
        for pkg in missing:
            print(f"  - {pkg}")
        print(f"\nInstall them with:")
        print(f"  pip install -r requirements.txt")
        print("=" * 60)
        return False

    return True


def launch_gui():
    """Launch the GUI application."""
    try:
        from PyQt6.QtWidgets import QApplication
        from interface.interface_tradutor_final import MainWindow, _ContextMenuPTBR

        app = QApplication(sys.argv)
        app.setApplicationName("ROM Translation Framework")
        app.setApplicationVersion("1.0.0")

        # Instala filtro PT-BR para menus de contexto em todos os widgets
        _ctx_filter = _ContextMenuPTBR(app)
        app.installEventFilter(_ctx_filter)

        window = MainWindow()
        window.show()

        return app.exec()

    except ImportError as e:
        print(f"Error importing GUI modules: {_sanitize_error(e)}")
        print("\nMake sure all dependencies are installed:")
        print("  pip install -r requirements.txt")
        return 1
    except Exception as e:
        print(f"Error launching application: {_sanitize_error(e)}")
        return 1


def show_help():
    """Display help message."""
    print(__doc__)
    print("\nAvailable commands:")
    print("  --gui     Launch graphical interface (default)")
    print("  --cli     Run in command-line mode")
    print("  --help    Show this help message")
    print("  --version Show version information")


def show_version():
    """Display version information."""
    print("ROM Translation Framework")
    print("Version: 1.0.0")
    print("Author: Celso")


def main():
    """Main entry point."""
    args = sys.argv[1:]

    if "--help" in args or "-h" in args:
        show_help()
        return 0

    if "--version" in args or "-v" in args:
        show_version()
        return 0

    # Check dependencies before launching
    if not check_dependencies():
        return 1

    if "--cli" in args:
        print("CLI mode not yet implemented.")
        print("Use --gui or no arguments to launch the graphical interface.")
        return 0

    # Default: launch GUI
    return launch_gui()


if __name__ == "__main__":
    sys.exit(main())
