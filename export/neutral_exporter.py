# -*- coding: utf-8 -*-
"""
================================================================================
NEUTRAL EXPORTER - CRC32-Based Export System
================================================================================
Exports unified text items with neutral naming (CRC32 only).
No game names, no marketing text, no metadata that could identify the ROM.

Output files:
- {CRC32}_pure_text.jsonl      : All extracted text items
- {CRC32}_reinsertion_mapping.json : Reinsertion-safe items with offsets
================================================================================
"""

import json
import zlib
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ..unification.text_unifier import UnifiedTextItem


@dataclass
class ExportConfig:
    """Configuration for export."""
    output_dir: Path
    crc32: str
    include_unsafe: bool = True  # Include non-reinsertion-safe items
    pretty_print: bool = False
    include_metadata: bool = True


@dataclass
class ExportResult:
    """Result of export operation."""
    crc32: str
    pure_text_path: Path
    reinsertion_path: Path
    total_items: int
    safe_items: int
    unsafe_items: int
    decoded_count: int
    tokenized_count: int
    export_metadata: Dict[str, Any] = field(default_factory=dict)


class NeutralExporter:
    """
    Exports unified text items with neutral CRC32-based naming.

    Strict rules:
    - NO game names in output
    - NO marketing text
    - Only CRC32 for file naming
    - Deterministic output (sorted, consistent format)
    """

    def __init__(self, rom_data: bytes, output_dir: Union[str, Path]):
        """
        Initialize exporter.

        Args:
            rom_data: ROM data for CRC32 calculation
            output_dir: Directory for output files
        """
        self.rom_data = rom_data
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Calculate CRC32
        self.crc32 = f"{zlib.crc32(rom_data) & 0xFFFFFFFF:08X}"

    def export(self,
               items: List[UnifiedTextItem],
               include_unsafe: bool = True,
               pretty_print: bool = False
               ) -> ExportResult:
        """
        Export unified text items to neutral format.

        Args:
            items: List of unified text items
            include_unsafe: Include items not safe for reinsertion
            pretty_print: Pretty print JSON output

        Returns:
            ExportResult with file paths and statistics
        """
        # Sort items by offset for deterministic output
        sorted_items = sorted(items, key=lambda x: (
            x.static_offset if x.static_offset is not None else 0xFFFFFFFF,
            x.origin_offset if x.origin_offset is not None else 0xFFFFFFFF,
            x.uid
        ))

        # Separate safe and unsafe items
        safe_items = [i for i in sorted_items if i.reinsertion_safe]
        unsafe_items = [i for i in sorted_items if not i.reinsertion_safe]

        # Count decoded vs tokenized
        decoded_count = sum(1 for i in sorted_items if not self._is_tokenized(i.text_src))
        tokenized_count = len(sorted_items) - decoded_count

        # Export pure text (all items or safe only)
        items_to_export = sorted_items if include_unsafe else safe_items
        pure_text_path = self._export_pure_text(items_to_export, pretty_print)

        # Export reinsertion mapping (safe items only)
        reinsertion_path = self._export_reinsertion_mapping(safe_items, pretty_print)

        return ExportResult(
            crc32=self.crc32,
            pure_text_path=pure_text_path,
            reinsertion_path=reinsertion_path,
            total_items=len(sorted_items),
            safe_items=len(safe_items),
            unsafe_items=len(unsafe_items),
            decoded_count=decoded_count,
            tokenized_count=tokenized_count,
            export_metadata={
                'include_unsafe': include_unsafe,
                'rom_size': len(self.rom_data),
            }
        )

    def _is_tokenized(self, text: str) -> bool:
        """Check if text contains tokenized placeholders."""
        return '<TILE_' in text or '<UNK_' in text or '<BYTE_' in text

    def _export_pure_text(self, items: List[UnifiedTextItem], pretty: bool) -> Path:
        """Export pure text to JSONL format."""
        output_path = self.output_dir / f"{self.crc32}_pure_text.jsonl"

        with open(output_path, 'w', encoding='utf-8') as f:
            for item in items:
                entry = self._item_to_pure_text_entry(item)
                if pretty:
                    f.write(json.dumps(entry, ensure_ascii=False, indent=2))
                else:
                    f.write(json.dumps(entry, ensure_ascii=False))
                f.write('\n')

        return output_path

    def _item_to_pure_text_entry(self, item: UnifiedTextItem) -> Dict[str, Any]:
        """Convert UnifiedTextItem to pure text export entry."""
        entry = {
            'uid': item.uid,
            'text_src': item.text_src,
            'source': item.source,
            'reinsertion_safe': item.reinsertion_safe,
        }

        # Add optional fields if present
        if item.static_offset is not None:
            entry['static_offset'] = f"0x{item.static_offset:06X}"

        if item.origin_offset is not None:
            entry['origin_offset'] = f"0x{item.origin_offset:06X}"

        if item.encoding:
            entry['encoding'] = item.encoding

        if item.text_like_score > 0:
            entry['text_score'] = round(item.text_like_score, 4)

        if item.reason_codes:
            entry['reason_codes'] = item.reason_codes

        # UI/HUD Tilemap support
        if hasattr(item, 'kind') and item.kind and item.kind != "text":
            entry['kind'] = item.kind
        if hasattr(item, 'raw_tokens') and item.raw_tokens:
            entry['raw_tokens'] = item.raw_tokens
        if hasattr(item, 'constraints') and item.constraints:
            entry['constraints'] = item.constraints

        return entry

    def _export_reinsertion_mapping(self, items: List[UnifiedTextItem], pretty: bool) -> Path:
        """Export reinsertion mapping for safe items."""
        output_path = self.output_dir / f"{self.crc32}_reinsertion_mapping.json"

        mappings = []
        for item in items:
            if not item.reinsertion_safe:
                continue

            mapping = self._item_to_reinsertion_entry(item)
            if mapping:
                mappings.append(mapping)

        # Sort by target offset
        mappings.sort(key=lambda x: int(x.get('target_offset', '0x0'), 16))

        output_data = {
            'crc32': self.crc32,
            'count': len(mappings),
            'mappings': mappings,
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            if pretty:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
            else:
                json.dump(output_data, f, ensure_ascii=False)

        return output_path

    def _item_to_reinsertion_entry(self, item: UnifiedTextItem) -> Optional[Dict[str, Any]]:
        """Convert UnifiedTextItem to reinsertion mapping entry."""
        # Must have a target offset for reinsertion
        target_offset = item.origin_offset or item.static_offset
        if target_offset is None:
            return None

        entry = {
            'uid': item.uid,
            'target_offset': f"0x{target_offset:06X}",
            'text_src': item.text_src,
        }

        # Add encoding info
        if item.encoding:
            entry['encoding'] = item.encoding

        # Add size constraint if available
        if item.static_item and hasattr(item.static_item, 'raw_bytes'):
            entry['max_bytes'] = len(item.static_item.raw_bytes)

        # Add terminator info if available
        if item.static_item and hasattr(item.static_item, 'terminator'):
            entry['terminator'] = getattr(item.static_item, 'terminator', 0x00)

        # Add pointer_refs array for reallocation support
        entry['pointer_refs'] = []
        if item.static_item and hasattr(item.static_item, 'pointer_refs'):
            ptr_refs = getattr(item.static_item, 'pointer_refs', [])
            for pref in ptr_refs:
                # Handle both PointerRef objects and dicts
                if hasattr(pref, 'to_dict'):
                    entry['pointer_refs'].append(pref.to_dict())
                elif hasattr(pref, 'ptr_offset'):
                    entry['pointer_refs'].append({
                        'ptr_offset': f"0x{pref.ptr_offset:06X}",
                        'ptr_size': getattr(pref, 'ptr_size', 2),
                        'endianness': getattr(pref, 'endianness', 'little'),
                        'addressing_mode': getattr(pref, 'mode', 'ABSOLUTE'),
                        'base': f"0x{getattr(pref, 'base', 0):04X}",
                        'bank': getattr(pref, 'bank', None),
                        'addend': getattr(pref, 'addend', 0),
                        'table_start': (f"0x{pref.table_start:06X}"
                                       if getattr(pref, 'table_start', None) else None),
                        'index': getattr(pref, 'index', None),
                        'bank_table_offset': (f"0x{pref.bank_table_offset:06X}"
                                             if getattr(pref, 'bank_table_offset', None) else None)
                    })
                elif isinstance(pref, dict):
                    entry['pointer_refs'].append(pref)

        # Legacy: Add single pointer_offset for backwards compatibility
        if item.static_item and hasattr(item.static_item, 'pointer_offset'):
            ptr_offset = getattr(item.static_item, 'pointer_offset', None)
            if ptr_offset is not None:
                entry['pointer_offset'] = f"0x{ptr_offset:06X}"

        # Determine if reallocatable (has pointer refs)
        entry['reallocatable'] = len(entry['pointer_refs']) > 0
        if not entry['reallocatable']:
            entry['reason_if_not'] = "no_pointer_refs_inline_text"
        else:
            entry['reason_if_not'] = None

        # UI/HUD Tilemap support
        if hasattr(item, 'kind') and item.kind and item.kind != "text":
            entry['kind'] = item.kind
            entry['reallocatable'] = False  # Tilemaps are fixed position
            entry['reason_if_not'] = "tilemap_fixed_position"
        if hasattr(item, 'raw_tokens') and item.raw_tokens:
            entry['raw_tokens'] = item.raw_tokens
        if hasattr(item, 'constraints') and item.constraints:
            entry['constraints'] = item.constraints
            if 'max_bytes' in item.constraints:
                entry['max_bytes'] = item.constraints['max_bytes']

        return entry

    def export_translation_template(self, items: List[UnifiedTextItem]) -> Path:
        """
        Export a translation template file.

        Format: JSON with text_src and empty text_dst fields.
        """
        output_path = self.output_dir / f"{self.crc32}_translation_template.json"

        # Only safe items with decoded text
        template_items = [
            i for i in items
            if i.reinsertion_safe and not self._is_tokenized(i.text_src)
        ]

        # Sort for deterministic output
        template_items.sort(key=lambda x: (
            x.static_offset if x.static_offset is not None else 0xFFFFFFFF,
            x.uid
        ))

        entries = []
        for item in template_items:
            entries.append({
                'uid': item.uid,
                'text_src': item.text_src,
                'text_dst': '',  # Empty for translator to fill
                'context': item.source,
            })

        output_data = {
            'crc32': self.crc32,
            'source_language': 'auto',
            'target_language': '',
            'count': len(entries),
            'entries': entries,
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)

        return output_path


def export_unified_items(rom_data: bytes,
                         items: List[UnifiedTextItem],
                         output_dir: Union[str, Path],
                         include_unsafe: bool = True
                         ) -> ExportResult:
    """
    Convenience function to export unified items.

    Args:
        rom_data: ROM data for CRC32 calculation
        items: List of unified text items
        output_dir: Directory for output files
        include_unsafe: Include non-reinsertion-safe items

    Returns:
        ExportResult with file paths and statistics
    """
    exporter = NeutralExporter(rom_data, output_dir)
    return exporter.export(items, include_unsafe=include_unsafe)
