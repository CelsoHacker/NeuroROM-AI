# -*- coding: utf-8 -*-
"""
================================================================================
REPORT GENERATOR - Human-Readable Extraction Report
================================================================================
Generates comprehensive extraction report with:
- COVERAGE metric (target: 1.0000)
- PerfectScore breakdown
- Decoded vs tokenized ratios
- Console-specific statistics
- Validation summary

Output: {CRC32}_report.txt
================================================================================
"""

import zlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ..unification.text_unifier import UnifiedTextItem


@dataclass
class PerfectScoreBreakdown:
    """Breakdown of PerfectScore components."""
    roundtrip: float = 0.0      # 30% weight - encoding round-trip
    language: float = 0.0       # 25% weight - language detection score
    consistency: float = 0.0    # 20% weight - cross-reference consistency
    structure: float = 0.0      # 15% weight - structural integrity
    constraints: float = 0.0    # 10% weight - constraint validation

    @property
    def weighted_total(self) -> float:
        """Calculate weighted total score."""
        return (
            self.roundtrip * 0.30 +
            self.language * 0.25 +
            self.consistency * 0.20 +
            self.structure * 0.15 +
            self.constraints * 0.10
        )


@dataclass
class ExtractionStats:
    """Statistics from extraction."""
    total_items: int = 0
    safe_items: int = 0
    unsafe_items: int = 0
    decoded_count: int = 0
    tokenized_count: int = 0
    static_only: int = 0
    runtime_only: int = 0
    hybrid_matched: int = 0
    avg_text_score: float = 0.0
    avg_length: float = 0.0
    encoding_distribution: Dict[str, int] = field(default_factory=dict)
    source_distribution: Dict[str, int] = field(default_factory=dict)
    reason_code_counts: Dict[str, int] = field(default_factory=dict)
    # UI/HUD Tilemap stats
    tilemap_detected: int = 0
    tilemap_translated: int = 0
    tilemap_blocked_no_map: int = 0
    tilemap_rejected_overflow: int = 0

    # Reinsertion stats (populated after reinsertion)
    reinsertion_in_place: int = 0
    reinsertion_relocated: int = 0
    reinsertion_fixed_shortened: int = 0
    reinsertion_blocked_no_pointer: int = 0
    reinsertion_blocked_no_glyph_map: int = 0
    reinsertion_blocked_allocation_failed: int = 0


@dataclass
class ExtractionReport:
    """Complete extraction report."""
    crc32: str
    rom_size: int
    console_type: str
    extraction_mode: str
    timestamp: str
    coverage: float
    perfect_score: PerfectScoreBreakdown
    stats: ExtractionStats
    validation_summary: Dict[str, Any]
    warnings: List[str]


class ReportGenerator:
    """
    Generates human-readable extraction reports.

    Reports include:
    - COVERAGE metric (safe_items / total_items)
    - PerfectScore breakdown by component
    - Detailed statistics
    - Validation warnings
    """

    def __init__(self, rom_data: bytes, console_type: str = "unknown"):
        """
        Initialize report generator.

        Args:
            rom_data: ROM data for CRC32
            console_type: Detected console type
        """
        self.rom_data = rom_data
        self.console_type = console_type
        self.crc32 = f"{zlib.crc32(rom_data) & 0xFFFFFFFF:08X}"

    def generate(self,
                 items: List[UnifiedTextItem],
                 output_dir: Union[str, Path],
                 extraction_mode: str = "hybrid",
                 validation_results: Optional[Dict[str, Any]] = None
                 ) -> Path:
        """
        Generate extraction report.

        Args:
            items: Extracted unified text items
            output_dir: Directory for output
            extraction_mode: Mode used (static/runtime/hybrid)
            validation_results: Optional validation results

        Returns:
            Path to report.txt file
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Calculate statistics
        stats = self._calculate_stats(items)

        # Calculate PerfectScore
        perfect_score = self._calculate_perfect_score(items, stats)

        # Calculate coverage
        coverage = stats.safe_items / stats.total_items if stats.total_items > 0 else 0.0

        # Collect warnings
        warnings = self._collect_warnings(items, stats, coverage)

        # Build report
        report = ExtractionReport(
            crc32=self.crc32,
            rom_size=len(self.rom_data),
            console_type=self.console_type,
            extraction_mode=extraction_mode,
            timestamp=datetime.now(timezone.utc).isoformat(),
            coverage=coverage,
            perfect_score=perfect_score,
            stats=stats,
            validation_summary=validation_results or {},
            warnings=warnings,
        )

        # Write report
        output_path = output_dir / f"{self.crc32}_report.txt"
        self._write_report(report, output_path)

        return output_path

    def _calculate_stats(self, items: List[UnifiedTextItem]) -> ExtractionStats:
        """Calculate extraction statistics."""
        stats = ExtractionStats()

        if not items:
            return stats

        stats.total_items = len(items)
        stats.safe_items = sum(1 for i in items if i.reinsertion_safe)
        stats.unsafe_items = stats.total_items - stats.safe_items

        # Count decoded vs tokenized
        for item in items:
            if self._is_tokenized(item.text_src):
                stats.tokenized_count += 1
            else:
                stats.decoded_count += 1

        # Count by source
        for item in items:
            source = item.source
            stats.source_distribution[source] = stats.source_distribution.get(source, 0) + 1

            if source == "static":
                stats.static_only += 1
            elif source == "runtime":
                stats.runtime_only += 1
            elif source == "hybrid":
                stats.hybrid_matched += 1

        # Count by encoding
        for item in items:
            enc = item.encoding or "unknown"
            stats.encoding_distribution[enc] = stats.encoding_distribution.get(enc, 0) + 1

        # Count reason codes
        for item in items:
            for code in item.reason_codes:
                stats.reason_code_counts[code] = stats.reason_code_counts.get(code, 0) + 1

        # Count UI/HUD tilemap items
        for item in items:
            kind = getattr(item, 'kind', 'text')
            if kind == "UI_TILEMAP_LABEL":
                stats.tilemap_detected += 1
                if item.reinsertion_safe:
                    stats.tilemap_translated += 1
                elif "NO_GLYPH_MAP" in item.reason_codes:
                    stats.tilemap_blocked_no_map += 1
                elif any("OVERFLOW" in c for c in item.reason_codes):
                    stats.tilemap_rejected_overflow += 1

        # Calculate averages
        scores = [i.text_like_score for i in items if i.text_like_score > 0]
        stats.avg_text_score = sum(scores) / len(scores) if scores else 0.0

        lengths = [len(i.text_src) for i in items]
        stats.avg_length = sum(lengths) / len(lengths) if lengths else 0.0

        return stats

    def _is_tokenized(self, text: str) -> bool:
        """Check if text contains tokenized placeholders."""
        return '<TILE_' in text or '<TILE:' in text or '<UNK_' in text or '<BYTE_' in text

    def _calculate_perfect_score(self, items: List[UnifiedTextItem],
                                  stats: ExtractionStats) -> PerfectScoreBreakdown:
        """Calculate PerfectScore breakdown."""
        score = PerfectScoreBreakdown()

        if not items:
            return score

        # Roundtrip score (30%): Items that survive encoding round-trip
        roundtrip_ok = sum(1 for i in items if i.reinsertion_safe)
        score.roundtrip = roundtrip_ok / len(items)

        # Language score (25%): Average text-like score
        lang_scores = [i.text_like_score for i in items if i.text_like_score > 0]
        score.language = sum(lang_scores) / len(lang_scores) if lang_scores else 0.0

        # Consistency score (20%): Items matched between static and runtime
        if stats.hybrid_matched > 0:
            total_possible = stats.static_only + stats.runtime_only + stats.hybrid_matched
            score.consistency = stats.hybrid_matched / total_possible if total_possible > 0 else 0.0
        else:
            # No runtime mode, base on source consistency
            score.consistency = 0.9 if stats.total_items > 0 else 0.0

        # Structure score (15%): Items with valid offsets
        with_offsets = sum(1 for i in items if i.static_offset is not None or i.origin_offset is not None)
        score.structure = with_offsets / len(items)

        # Constraints score (10%): Items without constraint violations
        no_violations = sum(1 for i in items if 'CONSTRAINT:' not in ' '.join(i.reason_codes))
        score.constraints = no_violations / len(items)

        return score

    def _collect_warnings(self, items: List[UnifiedTextItem],
                          stats: ExtractionStats, coverage: float) -> List[str]:
        """Collect warnings about extraction quality."""
        warnings = []

        # Coverage warning
        if coverage < 1.0:
            warnings.append(f"COVERAGE below 1.0: {coverage:.4f}")

        # High tokenization warning
        if stats.total_items > 0:
            tokenized_ratio = stats.tokenized_count / stats.total_items
            if tokenized_ratio > 0.20:
                warnings.append(f"High tokenization ratio: {tokenized_ratio:.2%}")

        # No items warning
        if stats.total_items == 0:
            warnings.append("No text items extracted")

        # Low text score warning
        if stats.avg_text_score < 0.5:
            warnings.append(f"Low average text score: {stats.avg_text_score:.4f}")

        # Runtime mismatch warning
        if stats.runtime_only > stats.hybrid_matched and stats.static_only > 0:
            warnings.append(f"Many runtime items not matched to static: {stats.runtime_only} vs {stats.hybrid_matched}")

        # Encoding diversity warning
        if len(stats.encoding_distribution) > 3:
            warnings.append(f"Multiple encodings detected: {list(stats.encoding_distribution.keys())}")

        return warnings

    def _write_report(self, report: ExtractionReport, output_path: Path) -> None:
        """Write report to text file."""
        lines = []

        # Header
        lines.append("=" * 80)
        lines.append("EXTRACTION REPORT")
        lines.append("=" * 80)
        lines.append("")

        # Basic info
        lines.append(f"CRC32:           {report.crc32}")
        lines.append(f"ROM Size:        {report.rom_size:,} bytes")
        lines.append(f"Console:         {report.console_type}")
        lines.append(f"Mode:            {report.extraction_mode}")
        lines.append(f"Timestamp:       {report.timestamp}")
        lines.append("")

        # Coverage (the key metric)
        lines.append("-" * 80)
        lines.append("COVERAGE METRIC")
        lines.append("-" * 80)
        lines.append(f"COVERAGE: {report.coverage:.4f}")
        lines.append("")

        # PerfectScore breakdown
        lines.append("-" * 80)
        lines.append("PERFECTSCORE BREAKDOWN")
        lines.append("-" * 80)
        ps = report.perfect_score
        lines.append(f"  Roundtrip:     {ps.roundtrip:.4f} (30%)")
        lines.append(f"  Language:      {ps.language:.4f} (25%)")
        lines.append(f"  Consistency:   {ps.consistency:.4f} (20%)")
        lines.append(f"  Structure:     {ps.structure:.4f} (15%)")
        lines.append(f"  Constraints:   {ps.constraints:.4f} (10%)")
        lines.append(f"  ─────────────────────────")
        lines.append(f"  WEIGHTED TOTAL: {ps.weighted_total:.4f}")
        lines.append("")

        # Statistics
        lines.append("-" * 80)
        lines.append("EXTRACTION STATISTICS")
        lines.append("-" * 80)
        s = report.stats
        lines.append(f"  Total Items:      {s.total_items}")
        lines.append(f"  Safe Items:       {s.safe_items}")
        lines.append(f"  Unsafe Items:     {s.unsafe_items}")
        lines.append("")
        lines.append(f"  Decoded Count:    {s.decoded_count}")
        lines.append(f"  Tokenized Count:  {s.tokenized_count}")

        if s.total_items > 0:
            decoded_ratio = s.decoded_count / s.total_items
            tokenized_ratio = s.tokenized_count / s.total_items
            lines.append(f"  decoded_ratio:    {decoded_ratio:.4f}")
            lines.append(f"  tokenized_ratio:  {tokenized_ratio:.4f}")

        lines.append("")
        lines.append(f"  Avg Text Score:   {s.avg_text_score:.4f}")
        lines.append(f"  Avg Length:       {s.avg_length:.1f} chars")
        lines.append("")

        # Source distribution
        lines.append("  Source Distribution:")
        for source, count in sorted(s.source_distribution.items()):
            lines.append(f"    {source}: {count}")
        lines.append("")

        # Encoding distribution
        lines.append("  Encoding Distribution:")
        for enc, count in sorted(s.encoding_distribution.items()):
            lines.append(f"    {enc}: {count}")
        lines.append("")

        # Reason codes
        if s.reason_code_counts:
            lines.append("  Reason Codes:")
            for code, count in sorted(s.reason_code_counts.items(), key=lambda x: -x[1]):
                lines.append(f"    {code}: {count}")
            lines.append("")

        # UI/HUD Tilemap stats
        if s.tilemap_detected > 0:
            lines.append("  UI/HUD Tilemap Labels:")
            lines.append(f"    Detected:          {s.tilemap_detected}")
            lines.append(f"    Translated:        {s.tilemap_translated}")
            lines.append(f"    Blocked (no map):  {s.tilemap_blocked_no_map}")
            lines.append(f"    Rejected (overflow): {s.tilemap_rejected_overflow}")
            lines.append("")

        # Reinsertion stats (if available)
        reinsertion_total = (
            s.reinsertion_in_place +
            s.reinsertion_relocated +
            s.reinsertion_fixed_shortened +
            s.reinsertion_blocked_no_pointer +
            s.reinsertion_blocked_no_glyph_map +
            s.reinsertion_blocked_allocation_failed
        )
        if reinsertion_total > 0:
            lines.append("  Reinsertion Status:")
            lines.append(f"    In-place:             {s.reinsertion_in_place}")
            lines.append(f"    Relocated:            {s.reinsertion_relocated}")
            lines.append(f"    Fixed/Shortened:      {s.reinsertion_fixed_shortened}")
            lines.append(f"    Blocked (no pointer): {s.reinsertion_blocked_no_pointer}")
            lines.append(f"    Blocked (no glyph):   {s.reinsertion_blocked_no_glyph_map}")
            lines.append(f"    Blocked (no space):   {s.reinsertion_blocked_allocation_failed}")
            lines.append("")

        # Warnings
        if report.warnings:
            lines.append("-" * 80)
            lines.append("WARNINGS")
            lines.append("-" * 80)
            for warning in report.warnings:
                lines.append(f"  ! {warning}")
            lines.append("")

        # Footer
        lines.append("=" * 80)
        lines.append("END OF REPORT")
        lines.append("=" * 80)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

    def update_reinsertion_stats(
        self,
        stats: ExtractionStats,
        reinsertion_stats: Dict[str, int]
    ) -> ExtractionStats:
        """
        Update ExtractionStats with reinsertion statistics.

        Args:
            stats: Current extraction stats
            reinsertion_stats: Stats from ReinsertionRules.get_stats()

        Returns:
            Updated ExtractionStats
        """
        stats.reinsertion_in_place = reinsertion_stats.get("in_place", 0)
        stats.reinsertion_relocated = reinsertion_stats.get("relocated", 0)
        stats.reinsertion_fixed_shortened = reinsertion_stats.get("fixed_shortened", 0)
        stats.reinsertion_blocked_no_pointer = reinsertion_stats.get("blocked_no_pointer", 0)
        stats.reinsertion_blocked_no_glyph_map = reinsertion_stats.get("blocked_no_glyph_map", 0)
        stats.reinsertion_blocked_allocation_failed = reinsertion_stats.get("blocked_allocation_failed", 0)
        return stats


def generate_report(rom_data: bytes,
                    items: List[UnifiedTextItem],
                    output_dir: Union[str, Path],
                    console_type: str = "unknown",
                    extraction_mode: str = "hybrid",
                    validation_results: Optional[Dict[str, Any]] = None
                    ) -> Path:
    """
    Convenience function to generate extraction report.

    Args:
        rom_data: ROM data
        items: Extracted unified text items
        output_dir: Directory for output
        console_type: Detected console type
        extraction_mode: Mode used
        validation_results: Optional validation results

    Returns:
        Path to report.txt file
    """
    generator = ReportGenerator(rom_data, console_type)
    return generator.generate(
        items=items,
        output_dir=output_dir,
        extraction_mode=extraction_mode,
        validation_results=validation_results,
    )
