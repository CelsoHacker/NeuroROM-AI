import json
from pathlib import Path

from core.MASTER_SYSTEM_UNIVERSAL_EXTRACTOR_FIXED_NEUTRAL import (
    ExtractorConfig,
    PointerTable,
    UniversalMasterSystemExtractor,
)


def _make_extractor(tmp_path: Path) -> UniversalMasterSystemExtractor:
    rom_path = tmp_path / "test.sms"
    rom_path.write_bytes(b"\x00" * 0x8000)
    config = ExtractorConfig(
        min_pointers_for_table=4,
        pointer_validation_threshold=0.6,
        pointer_partial_mode_enabled=True,
        pointer_partial_min_entries=2,
        pointer_partial_min_ratio=0.2,
        pointer_partial_min_plausibility_score=0.55,
    )
    return UniversalMasterSystemExtractor(str(rom_path), config=config)


def _mk_item(
    *,
    item_id: int,
    offset: int,
    text: str,
    has_pointer: bool,
    source: str = "POINTER",
    confidence: float = 0.9,
    requires_recompression: bool = False,
) -> dict:
    raw = text.encode("ascii", errors="ignore")
    return {
        "id": int(item_id),
        "offset": int(offset),
        "decoded": text,
        "clean": text,
        "max_len": int(max(1, len(raw))),
        "raw_len": int(len(raw)),
        "raw_bytes_hex": raw.hex().upper(),
        "terminator": 0x00,
        "source": source,
        "region": source,
        "category": source,
        "encoding": "ascii",
        "confidence": float(confidence),
        "pointer_table_offset": 0x20 if has_pointer else None,
        "pointer_entry_offset": 0x22 if has_pointer else None,
        "pointer_value": 0x1234 if has_pointer else None,
        "resolved_rom_offset": int(offset),
        "has_pointer": bool(has_pointer),
        "requires_recompression": bool(requires_recompression),
    }


def test_pointer_table_partial_salvage_keeps_good_entries(tmp_path: Path):
    extractor = _make_extractor(tmp_path)
    valid_entries = [
        {
            "entry_idx": 0,
            "ptr": 0x4000,
            "resolved": 0x1000,
            "decoded": "HELLO",
            "score": 0.95,
            "plausible": True,
            "terminator": 0x00,
        },
        {
            "entry_idx": 1,
            "ptr": 0x4010,
            "resolved": 0x1008,
            "decoded": "ZXQJ",
            "score": 0.20,
            "plausible": False,
            "terminator": 0x7F,
        },
        {
            "entry_idx": 2,
            "ptr": 0x4020,
            "resolved": 0x1010,
            "decoded": "WORLD",
            "score": 0.91,
            "plausible": True,
            "terminator": 0x00,
        },
    ]
    partial = extractor._try_build_partial_pointer_table(
        table_offset=0x80,
        valid_entries=valid_entries,
        confidence=0.40,
        total_checked=6,
        plausibility_ratio=0.66,
        trigger_reason="LOW_PLAUSIBILITY",
    )
    assert partial is not None
    assert partial.mode == "PARTIAL"
    assert partial.pointer_entry_indexes == [0, 2]
    assert partial.entry_count == 2
    assert extractor.pointer_table_partial_kept_count == 2

    injected_partial = PointerTable(
        table_offset=0,
        entry_count=2,
        entry_size=2,
        valid_pointers=[0x4000, 0x4010],
        pointer_entry_indexes=[0, 1],
        confidence=0.40,
        mode="PARTIAL",
        checked_entries=4,
    )
    seen = {"done": False}

    def _fake_detect(offset: int):
        if offset == 0 and not seen["done"]:
            seen["done"] = True
            return injected_partial
        return None

    extractor._try_detect_pointer_table_at = _fake_detect  # type: ignore[method-assign]
    discovered = extractor._find_potential_pointer_tables()
    assert len(discovered) == 1
    assert discovered[0].mode == "PARTIAL"


def test_overlap_cluster_resolution_writes_evidence(tmp_path: Path):
    extractor = _make_extractor(tmp_path)
    extractor.results = [
        _mk_item(item_id=1, offset=0x0100, text="In another world", has_pointer=True),
        _mk_item(item_id=2, offset=0x0106, text="other w", has_pointer=True),
        _mk_item(item_id=3, offset=0x0200, text="Options:", has_pointer=True),
    ]

    out_dir = tmp_path / "out_overlap"
    extractor.save_results(out_dir)
    crc = extractor.crc32_full

    jsonl_path = out_dir / f"{crc}_pure_text.jsonl"
    rows = [
        json.loads(line)
        for line in jsonl_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert rows[0].get("build_id") == extractor.build_id
    body = [r for r in rows if str(r.get("type", "")).lower() != "meta"]
    overlap_rows = [r for r in body if "OVERLAP_DISCARDED" in (r.get("review_flags") or [])]
    assert len(overlap_rows) == 1
    assert overlap_rows[0]["text_src"] == "other w"

    evidence_path = out_dir / f"{crc}_overlap_resolution_evidence.jsonl"
    assert evidence_path.exists()
    evidence_rows = [
        json.loads(line)
        for line in evidence_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert evidence_rows[0]["build_id"] == extractor.build_id
    clusters = [r for r in evidence_rows[1:] if r.get("type") == "overlap_cluster"]
    assert len(clusters) >= 1
    assert int(clusters[0].get("discarded_count", 0)) >= 1


def test_catalogs_split_and_recompress_tag(tmp_path: Path):
    extractor = _make_extractor(tmp_path)
    extractor.results = [
        _mk_item(item_id=1, offset=0x0300, text="Art thou Male or Female", has_pointer=True),
        _mk_item(
            item_id=2,
            offset=0x0400,
            text="Compressed preview line",
            has_pointer=False,
            source="DECOMPRESSED_PREVIEW_AUTO",
            requires_recompression=True,
        ),
    ]

    out_dir = tmp_path / "out_catalogs"
    extractor.save_results(out_dir)
    crc = extractor.crc32_full

    trans_path = out_dir / f"{crc}_catalog_texts_for_translation.txt"
    rein_path = out_dir / f"{crc}_catalog_texts_reinsertable.txt"
    partial_path = out_dir / f"{crc}_partial_pointer_tables.txt"

    assert trans_path.exists()
    assert rein_path.exists()
    assert partial_path.exists()

    trans_txt = trans_path.read_text(encoding="utf-8")
    rein_txt = rein_path.read_text(encoding="utf-8")
    partial_txt = partial_path.read_text(encoding="utf-8")
    assert f"# BUILD_ID: {extractor.build_id}" in trans_txt
    assert "[RECOMPRESS_NEEDED]" in trans_txt
    assert "Compressed preview line" in trans_txt
    assert "Compressed preview line" not in rein_txt
    assert "Art thou Male or Female" in rein_txt
    assert f"BUILD_ID: {extractor.build_id}" in partial_txt

    report_path = out_dir / f"{crc}_report.txt"
    report_txt = report_path.read_text(encoding="utf-8")
    for key in (
        "pointer_table_partial_kept_count",
        "overlap_discarded_count",
        "translatable_total_count",
        "reinsertable_total_count",
        "recompress_pending_count",
    ):
        assert key in report_txt

    proof_path = out_dir / f"{crc}_proof.json"
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    assert proof.get("build_id") == extractor.build_id
    stats = proof.get("statistics", {})
    assert int(stats.get("translatable_total_count", 0)) >= 2
    assert int(stats.get("reinsertable_total_count", 0)) >= 1
    assert int(stats.get("recompress_pending_count", 0)) >= 1
