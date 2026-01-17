#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Security Manager - License Validation & Anti-Piracy
====================================================

Handles EULA acceptance and Gumroad license key validation.

Author: Celso - Programador Solo
Version: 1.0.0
Copyright: © 2025 All Rights Reserved
"""

import os
import hashlib
import time
from pathlib import Path
from typing import Tuple


class SecurityManager:
    """Manages license validation and EULA acceptance."""

    LICENSE_FILE = Path(__file__).parent.parent / "license.key"
    EULA_ACCEPTED_FILE = Path(__file__).parent.parent / ".eula_accepted"

    # EULA/Disclaimer Text
    EULA_TEXT = """
NeuroROM AI - EULA & DISCLAIMER

NeuroROM AI is a localization and accessibility tool designed for video game translation.

IMPORTANT LEGAL NOTICE:

1. ANTI-PIRACY STATEMENT:
   The author does NOT condone piracy in any form. Users MUST legally own
   all ROMs they translate. Distributing copyrighted ROMs is ILLEGAL.

2. ACCEPTABLE USE:
   ✓ Translating ROMs you personally own
   ✓ Creating accessibility patches (.ips format)
   ✓ Educational and research purposes
   ✓ Authorized commercial translation projects

3. PROHIBITED USE:
   ✗ Distributing copyrighted ROMs
   ✗ Selling translated ROMs without permission
   ✗ Circumventing DRM or copy protection
   ✗ Any form of software piracy

4. PATCH DISTRIBUTION:
   To share translations legally, use .IPS patch files.
   Users apply patches to their own legally-owned ROMs.

5. WARRANTY DISCLAIMER:
   This software is provided "AS-IS" without any warranty.
   The author is NOT responsible for any damage or legal issues
   arising from misuse of this tool.

By clicking "Accept", you agree to these terms and confirm you will
use NeuroROM AI responsibly and legally.

© 2025 Celso - Programador Solo. All Rights Reserved.
"""

    @staticmethod
    def is_eula_accepted() -> bool:
        """Check if user has accepted EULA."""
        return SecurityManager.EULA_ACCEPTED_FILE.exists()

    @staticmethod
    def accept_eula() -> None:
        """Mark EULA as accepted."""
        with open(SecurityManager.EULA_ACCEPTED_FILE, 'w') as f:
            f.write("EULA_ACCEPTED=true\n")
            f.write(f"TIMESTAMP={time.time()}\n")

    @staticmethod
    def is_licensed() -> bool:
        """Check if valid license exists."""
        return SecurityManager.LICENSE_FILE.exists()

    @staticmethod
    def validate_license(license_key: str) -> Tuple[bool, str]:
        """
        Validate Gumroad license key.

        Args:
            license_key: License key from Gumroad

        Returns:
            Tuple (is_valid, message)
        """
        if not license_key or len(license_key) < 10:
            return False, "Invalid license key format"

        # PLACEHOLDER: Real validation would check against Gumroad API
        # For now, accept any key with specific pattern

        # Simple validation: key must contain "NEUROROM" and be 20+ chars
        if "NEUROROM" in license_key.upper() and len(license_key) >= 20:
            SecurityManager._save_license(license_key)
            return True, "License activated successfully!"

        # For development: Accept "DEV-LICENSE" as valid
        if license_key == "DEV-LICENSE":
            SecurityManager._save_license(license_key)
            return True, "Development license activated"

        return False, "Invalid license key. Please check your Gumroad purchase."

    @staticmethod
    def _save_license(license_key: str) -> None:
        """Save validated license key."""
        # Hash the key before saving (security)
        key_hash = hashlib.sha256(license_key.encode()).hexdigest()

        with open(SecurityManager.LICENSE_FILE, 'w') as f:
            f.write(f"LICENSE_HASH={key_hash}\n")
            f.write(f"PRODUCT=NeuroROM_AI\n")
            f.write(f"VERSION=5.3\n")

    @staticmethod
    def get_license_info() -> dict:
        """Get current license information."""
        if not SecurityManager.is_licensed():
            return {"status": "unlicensed", "type": "none"}

        try:
            with open(SecurityManager.LICENSE_FILE, 'r') as f:
                content = f.read()
                return {
                    "status": "licensed",
                    "type": "commercial",
                    "product": "NeuroROM AI",
                    "version": "5.3"
                }
        except:
            return {"status": "error", "type": "unknown"}


def main():
    """CLI test for security manager."""
    print("=" * 60)
    print("SECURITY MANAGER - TEST")
    print("=" * 60)

    print(f"\nEULA Accepted: {SecurityManager.is_eula_accepted()}")
    print(f"Licensed: {SecurityManager.is_licensed()}")

    if not SecurityManager.is_licensed():
        print("\nTest License Validation:")
        test_keys = [
            "NEUROROM-GUMROAD-12345678",
            "DEV-LICENSE",
            "INVALID-KEY"
        ]

        for key in test_keys:
            valid, msg = SecurityManager.validate_license(key)
            print(f"  {key}: {valid} - {msg}")

    print(f"\nLicense Info: {SecurityManager.get_license_info()}")
    print("=" * 60)


if __name__ == '__main__':
    main()
