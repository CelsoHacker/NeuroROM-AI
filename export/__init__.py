# -*- coding: utf-8 -*-
"""
================================================================================
EXPORT MODULE - Neutral Export System
================================================================================
Generates CRC32-based output files without game names or marketing text.

Components:
- neutral_exporter: Main export coordinator
- proof_generator: SHA256 proof.json generation
- report_generator: Coverage and PerfectScore reports

V1 Output Files (all CRC32-based):
- {CRC32}_pure_text.jsonl
- {CRC32}_reinsertion_mapping.json
- {CRC32}_report.txt
- {CRC32}_proof.json
================================================================================
"""

import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .neutral_exporter import NeutralExporter, export_unified_items, ExportResult
from .proof_generator import ProofGenerator, generate_proof
from .report_generator import ReportGenerator, generate_report


@dataclass
class V1ExportResult:
    """Result of V1 export with all 4 mandatory files."""
    crc32: str
    pure_text_path: Path
    reinsertion_mapping_path: Path
    report_path: Path
    proof_path: Path
    total_items: int
    safe_items: int
    coverage: float

    def get_all_paths(self) -> List[Path]:
        """Returns list of all 4 generated file paths."""
        return [
            self.pure_text_path,
            self.reinsertion_mapping_path,
            self.report_path,
            self.proof_path
        ]

    def to_dict(self) -> dict:
        return {
            'crc32': self.crc32,
            'files': {
                'pure_text': str(self.pure_text_path),
                'reinsertion_mapping': str(self.reinsertion_mapping_path),
                'report': str(self.report_path),
                'proof': str(self.proof_path)
            },
            'statistics': {
                'total_items': self.total_items,
                'safe_items': self.safe_items,
                'coverage': self.coverage
            }
        }


def export_all_v1(
    rom_data: bytes,
    items: list,
    output_dir: Union[str, Path],
    console_type: str = "unknown",
    extraction_mode: str = "hybrid",
    config: Optional[Dict[str, Any]] = None,
    include_unsafe: bool = True
) -> V1ExportResult:
    """
    Export all 4 mandatory V1 files with CRC32 naming.

    This is the main entry point for V1 pipeline exports.
    Generates:
    - {CRC32}_pure_text.jsonl
    - {CRC32}_reinsertion_mapping.json
    - {CRC32}_report.txt
    - {CRC32}_proof.json

    Args:
        rom_data: ROM data for CRC32 calculation
        items: List of UnifiedTextItem
        output_dir: Output directory
        console_type: Console type (SNES, NES, SMS, MD, etc.)
        extraction_mode: Extraction mode (static, runtime, hybrid)
        config: Pipeline configuration (for proof)
        include_unsafe: Include unsafe items in pure_text

    Returns:
        V1ExportResult with paths to all 4 files
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    crc32 = f"{zlib.crc32(rom_data) & 0xFFFFFFFF:08X}"

    # 1. Export pure_text.jsonl and reinsertion_mapping.json
    exporter = NeutralExporter(rom_data, output_dir)
    export_result = exporter.export(items, include_unsafe=include_unsafe)

    # 2. Generate report.txt
    report_gen = ReportGenerator(rom_data, console_type)
    report_path = report_gen.generate(
        items=items,
        output_dir=output_dir,
        extraction_mode=extraction_mode
    )

    # 3. Generate proof.json
    generated_files = [
        export_result.pure_text_path,
        export_result.reinsertion_path,
        report_path
    ]

    proof_gen = ProofGenerator(rom_data, console_type)
    proof_path = proof_gen.generate(
        items=items,
        output_dir=output_dir,
        extraction_mode=extraction_mode,
        config=config,
        generated_files=generated_files
    )

    # Calculate coverage
    safe_items = export_result.safe_items
    total_items = export_result.total_items
    coverage = safe_items / total_items if total_items > 0 else 0.0

    return V1ExportResult(
        crc32=crc32,
        pure_text_path=export_result.pure_text_path,
        reinsertion_mapping_path=export_result.reinsertion_path,
        report_path=report_path,
        proof_path=proof_path,
        total_items=total_items,
        safe_items=safe_items,
        coverage=coverage
    )


__all__ = [
    'NeutralExporter',
    'export_unified_items',
    'ExportResult',
    'ProofGenerator',
    'generate_proof',
    'ReportGenerator',
    'generate_report',
    'export_all_v1',
    'V1ExportResult',
]
