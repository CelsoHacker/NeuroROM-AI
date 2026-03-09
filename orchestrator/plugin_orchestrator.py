# -*- coding: utf-8 -*-
"""
================================================================================
PLUGIN ORCHESTRATOR - Main Pipeline Controller
================================================================================
Orchestrates the complete text extraction pipeline:
1. Console detection → plugin selection
2. Static text extraction
3. Runtime text capture (AUTO_DEEP for N64/PS1)
4. Text unification
5. Policy enforcement
6. Neutral export

Entry point: PluginOrchestrator.run(rom_path) or run_extraction(rom_path)
================================================================================
"""

import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ..plugins.plugin_registry import PluginRegistry, get_plugin_for_rom
from ..plugins.base_plugin import BaseConsolePlugin, ConsoleType, TextBank
from ..universal_kit.endian_pointer_hunter import EndianPointerHunter, PointerTableResult
from ..universal_kit.multi_decompress import MultiDecompressor
from ..universal_kit.tile_text_engine import TileTextEngine
from ..universal_kit.auto_char_table_solver import AutoCharTableSolver
from ..universal_kit.container_extractor import ContainerExtractor
from ..unification.text_unifier import TextUnifier, UnifiedTextItem, StaticTextItem, RuntimeTextItem
from ..unification.reinsertion_validator import ReinsertionValidator
from ..export.neutral_exporter import NeutralExporter, ExportResult
from ..export.proof_generator import ProofGenerator
from ..export.report_generator import ReportGenerator
from .policy_enforcer import PolicyEnforcer


@dataclass
class ExtractionConfig:
    """Configuration for extraction pipeline."""
    output_dir: Path
    use_runtime: bool = True
    auto_deep: bool = True  # AUTO_DEEP for N64/PS1
    runtime_core_path: Optional[str] = None
    runtime_max_frames: int = 18000
    runtime_max_screens: int = 100
    include_unsafe: bool = True
    validate_reinsertion: bool = True
    enforce_policies: bool = True
    deterministic_seed: Optional[int] = None  # CRC32 if None


@dataclass
class ExtractionResult:
    """Complete extraction result."""
    success: bool
    crc32: str
    console_type: str
    extraction_mode: str
    unified_items: List[UnifiedTextItem]
    export_result: Optional[ExportResult]
    report_path: Optional[Path]
    proof_path: Optional[Path]
    statistics: Dict[str, Any]
    errors: List[str]
    warnings: List[str]


class PluginOrchestrator:
    """
    Main orchestrator for plugin-based text extraction.

    Coordinates all extraction phases:
    - Plugin detection and selection
    - Static extraction (pointers, compression, tiles)
    - Runtime capture (emulator-based)
    - Unification and deduplication
    - Policy enforcement
    - Export generation
    """

    def __init__(self, config: Optional[ExtractionConfig] = None):
        """
        Initialize orchestrator.

        Args:
            config: Extraction configuration
        """
        self.config = config or ExtractionConfig(output_dir=Path("./output"))
        self.registry = PluginRegistry()
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def run(self, rom_path: Union[str, Path]) -> ExtractionResult:
        """
        Run complete extraction pipeline.

        Args:
            rom_path: Path to ROM file

        Returns:
            ExtractionResult with all extracted items and files
        """
        rom_path = Path(rom_path)
        self.errors = []
        self.warnings = []

        # Load ROM data
        try:
            rom_data = rom_path.read_bytes()
        except Exception as e:
            return self._error_result(f"Failed to load ROM: {e}")

        # Calculate CRC32 (used for deterministic seed and file naming)
        crc32 = f"{zlib.crc32(rom_data) & 0xFFFFFFFF:08X}"

        # Set deterministic seed
        if self.config.deterministic_seed is None:
            self.config.deterministic_seed = zlib.crc32(rom_data) & 0xFFFFFFFF

        # Detect console and get plugin
        plugin = get_plugin_for_rom(rom_data)
        if plugin is None:
            return self._error_result("Could not detect console type")

        console_type = plugin.console_spec.console_type.value

        # Determine extraction mode
        should_use_runtime = self._should_use_runtime(plugin)
        extraction_mode = "hybrid" if should_use_runtime else "static"

        # Phase 1: Static extraction
        static_items = self._extract_static(rom_data, plugin)

        # Phase 2: Runtime extraction (if enabled)
        runtime_items: List[RuntimeTextItem] = []
        if should_use_runtime and self.config.runtime_core_path:
            runtime_items = self._extract_runtime(rom_path, plugin)

        # Phase 3: Unification
        unified_items = self._unify_items(rom_data, static_items, runtime_items, plugin)

        # Phase 4: Reinsertion validation
        if self.config.validate_reinsertion:
            self._validate_reinsertion(rom_data, unified_items, plugin)

        # Phase 5: Policy enforcement
        if self.config.enforce_policies:
            unified_items = self._enforce_policies(unified_items)

        # Phase 6: Export
        export_result, report_path, proof_path = self._export(
            rom_data, unified_items, console_type, extraction_mode
        )

        # Calculate statistics
        statistics = self._calculate_statistics(unified_items, static_items, runtime_items)

        return ExtractionResult(
            success=True,
            crc32=crc32,
            console_type=console_type,
            extraction_mode=extraction_mode,
            unified_items=unified_items,
            export_result=export_result,
            report_path=report_path,
            proof_path=proof_path,
            statistics=statistics,
            errors=self.errors,
            warnings=self.warnings,
        )

    def _should_use_runtime(self, plugin: BaseConsolePlugin) -> bool:
        """Determine if runtime mode should be used."""
        if not self.config.use_runtime:
            return False

        # Check if plugin recommends runtime
        if plugin.should_use_runtime_mode():
            return True

        # AUTO_DEEP for N64 and PS1
        console_type = plugin.console_spec.console_type
        if self.config.auto_deep and console_type in (ConsoleType.N64, ConsoleType.PS1):
            return True

        return False

    def _extract_static(self, rom_data: bytes,
                        plugin: BaseConsolePlugin) -> List[StaticTextItem]:
        """
        Phase 1: Static text extraction.

        Combines:
        - Pointer table hunting
        - Compression detection and decompression
        - Tile text extraction
        - Direct text scanning
        """
        items: List[StaticTextItem] = []
        char_table: Dict[int, str] = {}

        # Get text-likely regions
        text_banks = plugin.get_text_banks(rom_data)

        # Try pointer hunting
        pointer_items = self._hunt_pointers(rom_data, plugin, text_banks)
        items.extend(pointer_items)

        # Try decompression
        decompress_items = self._extract_compressed(rom_data, plugin)
        items.extend(decompress_items)

        # Try tile text extraction
        if plugin.console_spec.tile_bpp:
            tile_items, char_table = self._extract_tiles(rom_data, plugin)
            items.extend(tile_items)

        # Direct text scanning in text-likely regions
        scan_items = self._scan_text_regions(rom_data, plugin, text_banks, char_table)
        items.extend(scan_items)

        # Container extraction for PS1
        if plugin.console_spec.console_type == ConsoleType.PS1:
            container_items = self._extract_containers(rom_data, plugin)
            items.extend(container_items)

        return items

    def _hunt_pointers(self, rom_data: bytes, plugin: BaseConsolePlugin,
                       text_banks: List[TextBank]) -> List[StaticTextItem]:
        """Hunt for pointer tables and extract text."""
        items = []

        hunter = EndianPointerHunter(rom_data, plugin)

        # Convert text banks to regions format
        text_regions = [
            {'offset': b.start, 'length': b.end - b.start}
            for b in text_banks
        ]

        tables = hunter.hunt(text_regions=text_regions)

        for table in tables:
            if table.confidence < 0.5:
                continue

            # Extract text from table
            extracted = hunter.extract_text_from_table(table)
            encodings = plugin.get_encoding_priority()

            for ptr, raw_bytes in extracted:
                text, encoding = self._decode_bytes(raw_bytes, encodings)
                if text:
                    items.append(StaticTextItem(
                        offset=ptr.target_offset,
                        raw_bytes=raw_bytes,
                        text=text,
                        encoding=encoding,
                        text_score=ptr.text_score,
                        source_method="pointer_table",
                        pointer_offset=ptr.offset,
                    ))

        return items

    def _extract_compressed(self, rom_data: bytes,
                            plugin: BaseConsolePlugin) -> List[StaticTextItem]:
        """Extract text from compressed blocks."""
        items = []

        config = plugin.get_compression_config()
        if not config.get('algorithms'):
            return items

        decompressor = MultiDecompressor(rom_data)
        encodings = plugin.get_encoding_priority()

        for algo in config['algorithms']:
            results = decompressor.find_and_decompress(algo.lower())

            for result in results:
                if not result.success:
                    continue

                # Scan decompressed data for text
                text_items = self._scan_data_for_text(
                    result.data, encodings, plugin
                )

                for text, offset, encoding in text_items:
                    items.append(StaticTextItem(
                        offset=result.offset,  # Compressed block offset
                        raw_bytes=result.data[offset:offset + len(text.encode(encoding, errors='ignore'))],
                        text=text,
                        encoding=encoding,
                        text_score=0.7,
                        source_method=f"compressed_{algo.lower()}",
                        extra={'decompressed_offset': offset},
                    ))

        return items

    def _extract_tiles(self, rom_data: bytes,
                       plugin: BaseConsolePlugin) -> tuple:
        """Extract text from tile graphics."""
        items = []
        char_table: Dict[int, str] = {}

        bpp_options = plugin.console_spec.tile_bpp
        if not bpp_options:
            return items, char_table

        engine = TileTextEngine(rom_data)

        for bpp in bpp_options:
            # Find font patterns
            fonts = engine.find_font_patterns(bpp=bpp)

            if fonts:
                # Try to solve character table
                solver = AutoCharTableSolver()
                # This would need sample text for proper solving
                # For now, just use the engine's built-in detection
                pass

        return items, char_table

    def _scan_text_regions(self, rom_data: bytes, plugin: BaseConsolePlugin,
                           text_banks: List[TextBank],
                           char_table: Dict[int, str]) -> List[StaticTextItem]:
        """Scan text-likely regions for strings."""
        items = []
        encodings = plugin.get_encoding_priority()
        min_len = plugin.console_spec.min_text_len

        for bank in text_banks:
            if bank.score < 0.3:
                continue

            region_data = rom_data[bank.start:bank.end]
            text_items = self._scan_data_for_text(region_data, encodings, plugin, bank.start)

            for text, offset, encoding in text_items:
                if len(text) < min_len:
                    continue

                raw_start = offset - bank.start if offset >= bank.start else 0
                raw_end = raw_start + len(text.encode(encoding, errors='ignore'))
                raw_bytes = region_data[raw_start:raw_end] if raw_end <= len(region_data) else b''

                items.append(StaticTextItem(
                    offset=offset,
                    raw_bytes=raw_bytes,
                    text=text,
                    encoding=encoding,
                    text_score=bank.score,
                    source_method="region_scan",
                ))

        return items

    def _scan_data_for_text(self, data: bytes, encodings: List[str],
                            plugin: BaseConsolePlugin,
                            base_offset: int = 0) -> List[tuple]:
        """Scan binary data for text strings."""
        results = []
        min_len = plugin.console_spec.min_text_len
        threshold = plugin.console_spec.language_score_threshold

        for encoding in encodings:
            try:
                # Find null-terminated strings
                offset = 0
                while offset < len(data):
                    # Find start of potential string
                    start = offset
                    while start < len(data) and data[start] == 0:
                        start += 1

                    if start >= len(data):
                        break

                    # Find end (null terminator)
                    end = start
                    while end < len(data) and data[end] != 0:
                        end += 1

                    if end - start >= min_len:
                        raw = data[start:end]
                        try:
                            text = raw.decode(encoding, errors='strict')
                            score = plugin.calculate_text_score(raw)
                            if score >= threshold:
                                results.append((text, base_offset + start, encoding))
                        except (UnicodeDecodeError, LookupError):
                            pass

                    offset = end + 1

            except Exception:
                continue

        return results

    def _extract_containers(self, rom_data: bytes,
                            plugin: BaseConsolePlugin) -> List[StaticTextItem]:
        """Extract text from container files (ISO, segments)."""
        items = []

        try:
            extractor = ContainerExtractor(rom_data)
            info = extractor.extract()

            encodings = plugin.get_encoding_priority()

            for file in info.files:
                if file.file_type in ('data', 'unknown', 'ps1_exe'):
                    # Scan file for text
                    text_items = self._scan_data_for_text(
                        file.data, encodings, plugin, file.offset
                    )

                    for text, offset, encoding in text_items:
                        items.append(StaticTextItem(
                            offset=offset,
                            raw_bytes=file.data[offset - file.offset:offset - file.offset + 256],
                            text=text,
                            encoding=encoding,
                            text_score=0.6,
                            source_method=f"container_{file.path}",
                            extra={'container_path': file.path},
                        ))

        except Exception as e:
            self.warnings.append(f"Container extraction failed: {e}")

        return items

    def _decode_bytes(self, raw: bytes, encodings: List[str]) -> tuple:
        """Try to decode bytes with multiple encodings."""
        for encoding in encodings:
            try:
                text = raw.decode(encoding, errors='strict')
                # Basic validation
                if text and any(c.isalpha() for c in text):
                    return text, encoding
            except (UnicodeDecodeError, LookupError):
                continue
        return None, None

    def _extract_runtime(self, rom_path: Path,
                         plugin: BaseConsolePlugin) -> List[RuntimeTextItem]:
        """
        Phase 2: Runtime text extraction.

        Uses emulator to capture text displayed during gameplay.
        """
        items = []

        if not self.config.runtime_core_path:
            self.warnings.append("Runtime core path not configured")
            return items

        try:
            from ..runtime.emulator_runtime_host import EmulatorRuntimeHost
            from ..runtime.runtime_text_harvester import RuntimeTextHarvester
            from ..runtime.auto_explorer import AutoExplorer

            # Initialize runtime host
            host = EmulatorRuntimeHost(
                self.config.runtime_core_path,
                str(rom_path)
            )

            # Initialize harvester
            harvester = RuntimeTextHarvester(host, plugin)

            # Initialize explorer
            explorer = AutoExplorer(
                host, harvester,
                seed=self.config.deterministic_seed
            )

            # Run exploration
            harvest_result = explorer.explore(
                max_screens=self.config.runtime_max_screens,
                max_frames=self.config.runtime_max_frames
            )

            items = harvest_result.items

        except Exception as e:
            self.warnings.append(f"Runtime extraction failed: {e}")

        return items

    def _unify_items(self, rom_data: bytes,
                     static_items: List[StaticTextItem],
                     runtime_items: List[RuntimeTextItem],
                     plugin: BaseConsolePlugin) -> List[UnifiedTextItem]:
        """
        Phase 3: Unify static and runtime items.
        """
        char_table = {}  # Would be populated from tile extraction
        unifier = TextUnifier(rom_data, char_table)

        unified = unifier.unify(static_items, runtime_items)
        return unified

    def _validate_reinsertion(self, rom_data: bytes,
                               unified_items: List[UnifiedTextItem],
                               plugin: BaseConsolePlugin) -> None:
        """
        Phase 4: Validate reinsertion safety.
        """
        char_table = {}  # Would be populated from tile extraction
        validator = ReinsertionValidator(rom_data, char_table)
        validator.validate_all(unified_items)

    def _enforce_policies(self, items: List[UnifiedTextItem]) -> List[UnifiedTextItem]:
        """
        Phase 5: Enforce extraction policies.
        """
        enforcer = PolicyEnforcer()
        return enforcer.enforce_all(items)

    def _export(self, rom_data: bytes, items: List[UnifiedTextItem],
                console_type: str, extraction_mode: str) -> tuple:
        """
        Phase 6: Export to neutral format.
        """
        self.config.output_dir.mkdir(parents=True, exist_ok=True)

        # Export
        exporter = NeutralExporter(rom_data, self.config.output_dir)
        export_result = exporter.export(
            items,
            include_unsafe=self.config.include_unsafe
        )

        # Generate report
        reporter = ReportGenerator(rom_data, console_type)
        report_path = reporter.generate(
            items,
            self.config.output_dir,
            extraction_mode=extraction_mode
        )

        # Generate proof
        proofer = ProofGenerator(rom_data, console_type)
        generated_files = [
            export_result.pure_text_path,
            export_result.reinsertion_path,
            report_path,
        ]
        proof_path = proofer.generate(
            items,
            self.config.output_dir,
            extraction_mode=extraction_mode,
            generated_files=generated_files
        )

        return export_result, report_path, proof_path

    def _calculate_statistics(self, unified: List[UnifiedTextItem],
                               static: List[StaticTextItem],
                               runtime: List[RuntimeTextItem]) -> Dict[str, Any]:
        """Calculate extraction statistics."""
        safe_count = sum(1 for i in unified if i.reinsertion_safe)
        tokenized = sum(1 for i in unified if '<TILE_' in i.text_src or '<UNK_' in i.text_src)

        return {
            'total_unified': len(unified),
            'total_static': len(static),
            'total_runtime': len(runtime),
            'safe_items': safe_count,
            'unsafe_items': len(unified) - safe_count,
            'coverage': safe_count / len(unified) if unified else 0.0,
            'decoded_count': len(unified) - tokenized,
            'tokenized_count': tokenized,
            'decoded_ratio': (len(unified) - tokenized) / len(unified) if unified else 0.0,
            'tokenized_ratio': tokenized / len(unified) if unified else 0.0,
        }

    def _error_result(self, message: str) -> ExtractionResult:
        """Create error result."""
        return ExtractionResult(
            success=False,
            crc32="00000000",
            console_type="unknown",
            extraction_mode="none",
            unified_items=[],
            export_result=None,
            report_path=None,
            proof_path=None,
            statistics={},
            errors=[message],
            warnings=[],
        )


def run_extraction(rom_path: Union[str, Path],
                   output_dir: Union[str, Path] = "./output",
                   use_runtime: bool = False,
                   runtime_core: Optional[str] = None
                   ) -> ExtractionResult:
    """
    Convenience function to run extraction pipeline.

    Args:
        rom_path: Path to ROM file
        output_dir: Output directory
        use_runtime: Enable runtime extraction
        runtime_core: Path to Libretro core

    Returns:
        ExtractionResult
    """
    config = ExtractionConfig(
        output_dir=Path(output_dir),
        use_runtime=use_runtime,
        runtime_core_path=runtime_core,
    )
    orchestrator = PluginOrchestrator(config)
    return orchestrator.run(rom_path)
