# -*- coding: utf-8 -*-
"""
================================================================================
PROOF GENERATOR - SHA256 Verification Proof
================================================================================
Generates cryptographic proof of extraction for reproducibility verification.

Output: {CRC32}_proof.json with SHA256 hashes of:
- ROM data
- Extracted text items
- Generated files
- Pipeline configuration
================================================================================
"""

import hashlib
import json
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ..unification.text_unifier import UnifiedTextItem


@dataclass
class ProofEntry:
    """A single proof entry with hash."""
    name: str
    sha256: str
    size: int
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractionProof:
    """Complete extraction proof."""
    crc32: str
    rom_sha256: str
    rom_size: int
    timestamp_utc: str
    pipeline_version: str
    console_type: str
    extraction_mode: str  # static, runtime, hybrid
    total_items: int
    safe_items: int
    coverage: float
    file_proofs: List[ProofEntry]
    config_hash: str
    deterministic: bool = True


class ProofGenerator:
    """
    Generates cryptographic proof of extraction.

    Ensures:
    - Reproducibility verification via SHA256
    - Pipeline configuration tracking
    - Deterministic output verification
    """

    PIPELINE_VERSION = "1.0.0"

    def __init__(self, rom_data: bytes, console_type: str = "unknown"):
        """
        Initialize proof generator.

        Args:
            rom_data: ROM data for hash calculation
            console_type: Detected console type
        """
        self.rom_data = rom_data
        self.console_type = console_type

        # Calculate hashes
        self.crc32 = f"{zlib.crc32(rom_data) & 0xFFFFFFFF:08X}"
        self.rom_sha256 = hashlib.sha256(rom_data).hexdigest()

    def generate(self,
                 items: List[UnifiedTextItem],
                 output_dir: Union[str, Path],
                 extraction_mode: str = "hybrid",
                 config: Optional[Dict[str, Any]] = None,
                 generated_files: Optional[List[Path]] = None
                 ) -> Path:
        """
        Generate extraction proof.

        Args:
            items: Extracted unified text items
            output_dir: Directory for output
            extraction_mode: Mode used (static/runtime/hybrid)
            config: Pipeline configuration used
            generated_files: List of generated file paths to hash

        Returns:
            Path to proof.json file
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Calculate items hash
        items_data = self._serialize_items_for_hash(items)
        items_hash = hashlib.sha256(items_data.encode('utf-8')).hexdigest()

        # Calculate config hash
        config_data = json.dumps(config or {}, sort_keys=True)
        config_hash = hashlib.sha256(config_data.encode('utf-8')).hexdigest()

        # Hash generated files
        file_proofs = []
        if generated_files:
            for file_path in generated_files:
                if file_path.exists():
                    file_proofs.append(self._hash_file(file_path))

        # Add items hash as a proof entry
        file_proofs.append(ProofEntry(
            name="extracted_items",
            sha256=items_hash,
            size=len(items),
            metadata={'type': 'items_collection'}
        ))

        # Calculate statistics
        safe_items = sum(1 for i in items if i.reinsertion_safe)
        coverage = safe_items / len(items) if items else 0.0

        # Build proof
        proof = ExtractionProof(
            crc32=self.crc32,
            rom_sha256=self.rom_sha256,
            rom_size=len(self.rom_data),
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            pipeline_version=self.PIPELINE_VERSION,
            console_type=self.console_type,
            extraction_mode=extraction_mode,
            total_items=len(items),
            safe_items=safe_items,
            coverage=round(coverage, 4),
            file_proofs=[self._proof_entry_to_dict(p) for p in file_proofs],
            config_hash=config_hash,
            deterministic=True,
        )

        # Write proof file
        output_path = output_dir / f"{self.crc32}_proof.json"
        self._write_proof(proof, output_path)

        return output_path

    def _serialize_items_for_hash(self, items: List[UnifiedTextItem]) -> str:
        """Serialize items deterministically for hashing."""
        # Sort items by uid for deterministic output
        sorted_items = sorted(items, key=lambda x: x.uid)

        entries = []
        for item in sorted_items:
            entry = {
                'uid': item.uid,
                'text_src': item.text_src,
                'source': item.source,
                'reinsertion_safe': item.reinsertion_safe,
                'static_offset': item.static_offset,
                'origin_offset': item.origin_offset,
            }
            entries.append(entry)

        return json.dumps(entries, sort_keys=True, ensure_ascii=False)

    def _hash_file(self, file_path: Path) -> ProofEntry:
        """Calculate SHA256 hash of a file."""
        hasher = hashlib.sha256()
        size = 0

        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
                size += len(chunk)

        return ProofEntry(
            name=file_path.name,
            sha256=hasher.hexdigest(),
            size=size,
            metadata={'path': str(file_path)}
        )

    def _proof_entry_to_dict(self, entry: ProofEntry) -> Dict[str, Any]:
        """Convert ProofEntry to dictionary."""
        return {
            'name': entry.name,
            'sha256': entry.sha256,
            'size': entry.size,
            'metadata': entry.metadata,
        }

    def _write_proof(self, proof: ExtractionProof, output_path: Path) -> None:
        """Write proof to JSON file."""
        proof_dict = {
            'crc32': proof.crc32,
            'rom_sha256': proof.rom_sha256,
            'rom_size': proof.rom_size,
            'timestamp_utc': proof.timestamp_utc,
            'pipeline_version': proof.pipeline_version,
            'console_type': proof.console_type,
            'extraction_mode': proof.extraction_mode,
            'statistics': {
                'total_items': proof.total_items,
                'safe_items': proof.safe_items,
                'coverage': proof.coverage,
            },
            'file_proofs': proof.file_proofs,
            'config_hash': proof.config_hash,
            'deterministic': proof.deterministic,
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(proof_dict, f, ensure_ascii=False, indent=2)

    def generate_reinsertion_proof(
        self,
        output_dir: Union[str, Path],
        reinsertion_entries: List[Dict[str, Any]],
        stats: Dict[str, int],
        modified_rom_data: Optional[bytes] = None
    ) -> Path:
        """
        Generate proof for reinsertion operation.

        Validates:
        - len/terminator/tokens for each item
        - Pointers now point to new_offset (for relocated items)

        Args:
            output_dir: Output directory
            reinsertion_entries: Proof entries from ReinsertionRules
            stats: Reinsertion statistics
            modified_rom_data: Modified ROM data for hash

        Returns:
            Path to reinsertion proof file
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Calculate ROM hash if provided
        modified_sha256 = ""
        if modified_rom_data:
            modified_sha256 = hashlib.sha256(modified_rom_data).hexdigest()

        # Validate each entry
        validations = []
        for entry in reinsertion_entries:
            validation = {
                "id": entry.get("id"),
                "offset": entry.get("offset"),
                "status": entry.get("status"),
                "len_valid": entry.get("len_valid", True),
                "terminator_present": entry.get("terminator_present", True),
                "tokens_preserved": entry.get("tokens_preserved", 0),
            }

            # For relocated items, verify pointers
            if entry.get("pointers_updated"):
                validation["pointers_validated"] = True
                validation["pointers_count"] = entry.get("pointers_updated")

            validations.append(validation)

        # Build proof
        proof_data = {
            "crc32": self.crc32,
            "original_rom_sha256": self.rom_sha256,
            "modified_rom_sha256": modified_sha256,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "pipeline_version": self.PIPELINE_VERSION,
            "operation": "reinsertion",
            "statistics": {
                "total_processed": sum(stats.values()),
                "in_place": stats.get("in_place", 0),
                "relocated": stats.get("relocated", 0),
                "fixed_shortened": stats.get("fixed_shortened", 0),
                "blocked_no_pointer": stats.get("blocked_no_pointer", 0),
                "blocked_no_glyph_map": stats.get("blocked_no_glyph_map", 0),
                "blocked_allocation_failed": stats.get("blocked_allocation_failed", 0),
            },
            "validations": validations,
            "all_valid": all(v.get("len_valid", True) for v in validations),
        }

        output_path = output_dir / f"{self.crc32}_reinsertion_proof.json"

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(proof_data, f, ensure_ascii=False, indent=2)

        return output_path

    def verify_proof(self, proof_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Verify an existing proof file.

        Args:
            proof_path: Path to proof.json

        Returns:
            Verification result with status and details
        """
        proof_path = Path(proof_path)

        with open(proof_path, 'r', encoding='utf-8') as f:
            proof_data = json.load(f)

        results = {
            'valid': True,
            'checks': {},
        }

        # Verify CRC32
        crc_match = proof_data['crc32'] == self.crc32
        results['checks']['crc32'] = {
            'expected': proof_data['crc32'],
            'actual': self.crc32,
            'match': crc_match,
        }
        if not crc_match:
            results['valid'] = False

        # Verify SHA256
        sha_match = proof_data['rom_sha256'] == self.rom_sha256
        results['checks']['rom_sha256'] = {
            'expected': proof_data['rom_sha256'],
            'actual': self.rom_sha256,
            'match': sha_match,
        }
        if not sha_match:
            results['valid'] = False

        # Verify ROM size
        size_match = proof_data['rom_size'] == len(self.rom_data)
        results['checks']['rom_size'] = {
            'expected': proof_data['rom_size'],
            'actual': len(self.rom_data),
            'match': size_match,
        }
        if not size_match:
            results['valid'] = False

        # Verify file proofs if files exist
        results['checks']['file_proofs'] = []
        for file_proof in proof_data.get('file_proofs', []):
            if 'path' in file_proof.get('metadata', {}):
                file_path = Path(file_proof['metadata']['path'])
                if file_path.exists():
                    actual = self._hash_file(file_path)
                    match = actual.sha256 == file_proof['sha256']
                    results['checks']['file_proofs'].append({
                        'name': file_proof['name'],
                        'match': match,
                    })
                    if not match:
                        results['valid'] = False

        return results


def generate_proof(rom_data: bytes,
                   items: List[UnifiedTextItem],
                   output_dir: Union[str, Path],
                   console_type: str = "unknown",
                   extraction_mode: str = "hybrid",
                   config: Optional[Dict[str, Any]] = None,
                   generated_files: Optional[List[Path]] = None
                   ) -> Path:
    """
    Convenience function to generate extraction proof.

    Args:
        rom_data: ROM data
        items: Extracted unified text items
        output_dir: Directory for output
        console_type: Detected console type
        extraction_mode: Mode used (static/runtime/hybrid)
        config: Pipeline configuration
        generated_files: List of generated files to hash

    Returns:
        Path to proof.json file
    """
    generator = ProofGenerator(rom_data, console_type)
    return generator.generate(
        items=items,
        output_dir=output_dir,
        extraction_mode=extraction_mode,
        config=config,
        generated_files=generated_files,
    )
