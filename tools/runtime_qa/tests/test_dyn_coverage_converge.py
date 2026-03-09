# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List


REPO_ROOT = Path(__file__).resolve().parents[3]


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, meta: Dict[str, Any], rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write(json.dumps(meta, ensure_ascii=False) + "\n")
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_unique(path: Path, lines: List[str]) -> None:
    out_lines = []
    for idx, text in enumerate(lines):
        out_lines.append(
            f"{text}\tframe={100 + idx}\tscene_hash=SC{idx:02d}\thits=1\tunmapped_ratio_max=0.5000"
        )
    content = "\n".join(out_lines)
    if content and not content.endswith("\n"):
        content += "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _make_dyn_row(frame: int, line_idx: int, line: str, glyph_hashes: List[str], patterns: List[str]) -> Dict[str, Any]:
    unknown_samples = []
    for idx, glyph_hash in enumerate(glyph_hashes):
        pattern_hex = patterns[idx] if idx < len(patterns) else patterns[-1]
        unknown_samples.append(
            {"glyph_hash": glyph_hash, "pattern_hex": pattern_hex, "tile_id": idx}
        )
    return {
        "type": "dyn_text",
        "frame": frame,
        "scene_hash": f"SCENE{frame:04X}",
        "line_idx": line_idx,
        "line": line,
        "glyph_hashes": glyph_hashes,
        "unknown_glyph_samples": unknown_samples,
        "unmapped_ratio": 0.5,
    }


def _create_run(
    run_dir: Path,
    *,
    crc: str,
    rom_size: int,
    unique_lines: List[str],
    dyn_rows: List[Dict[str, Any]],
    bootstrap_rows: List[Dict[str, Any]],
) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)

    dyn_log = run_dir / f"{crc}_dyn_text_log.jsonl"
    dyn_unique = run_dir / f"{crc}_dyn_text_unique.txt"
    bootstrap = run_dir / f"{crc}_dyn_fontmap_bootstrap.json"

    meta = {
        "type": "meta",
        "schema": "runtime_dyn_text_log.v2",
        "rom_crc32": crc,
        "rom_size": int(rom_size),
        "rows_total": len(dyn_rows),
    }
    _write_jsonl(dyn_log, meta, dyn_rows)
    _write_unique(dyn_unique, unique_lines)

    payload = {
        "schema": "runtime_dyn_fontmap_bootstrap.v2",
        "rom_crc32": crc,
        "rom_size": int(rom_size),
        "unknown_glyphs_total": len(bootstrap_rows),
        "rows": bootstrap_rows,
    }
    _write_json(bootstrap, payload)


class DynCoverageConvergeTests(unittest.TestCase):
    def test_converged_false_then_true_with_thresholds(self) -> None:
        crc = "A1B2C3D4"
        rom_size = 262144
        pattern_a = "AA" * 32
        pattern_b = "BB" * 32
        pattern_c = "CC" * 32
        pattern_d = "DD" * 32
        pattern_e = "EE" * 32

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            crc_dir = base / crc
            runtime_dir = crc_dir / "runtime"
            run2 = runtime_dir / "2_runtime_dyn"
            run3 = runtime_dir / "3_runtime_dyn"

            _create_run(
                run2,
                crc=crc,
                rom_size=rom_size,
                unique_lines=["AB??", "HELLO"],
                dyn_rows=[
                    _make_dyn_row(100, 0, "AB??", ["AAA00001", "BBB00002", "CCC00003", "DDD00004"], [pattern_a, pattern_b, pattern_c, pattern_d]),
                    _make_dyn_row(101, 1, "HELLO", ["AAA00001", "BBB00002", "CCC00003", "DDD00004", "AAA00001"], [pattern_a, pattern_b, pattern_c, pattern_d, pattern_a]),
                ],
                bootstrap_rows=[
                    {"glyph_hash": "AAA00001", "hits": 80, "pattern_hex": pattern_a},
                    {"glyph_hash": "BBB00002", "hits": 10, "pattern_hex": pattern_b},
                    {"glyph_hash": "CCC00003", "hits": 5, "pattern_hex": pattern_c},
                    {"glyph_hash": "DDD00004", "hits": 5, "pattern_hex": pattern_d},
                ],
            )
            _create_run(
                run3,
                crc=crc,
                rom_size=rom_size,
                unique_lines=["AB??", "HELLO", "WORLD"],
                dyn_rows=[
                    _make_dyn_row(200, 0, "AB??", ["AAA00001", "BBB00002", "CCC00003", "DDD00004"], [pattern_a, pattern_b, pattern_c, pattern_d]),
                    _make_dyn_row(201, 1, "HELLO", ["AAA00001", "BBB00002", "CCC00003", "DDD00004", "AAA00001"], [pattern_a, pattern_b, pattern_c, pattern_d, pattern_a]),
                    _make_dyn_row(202, 2, "WORLD", ["EEE00005", "AAA00001", "BBB00002", "CCC00003", "DDD00004"], [pattern_e, pattern_a, pattern_b, pattern_c, pattern_d]),
                ],
                bootstrap_rows=[
                    {"glyph_hash": "AAA00001", "hits": 80, "pattern_hex": pattern_a},
                    {"glyph_hash": "BBB00002", "hits": 10, "pattern_hex": pattern_b},
                    {"glyph_hash": "CCC00003", "hits": 5, "pattern_hex": pattern_c},
                    {"glyph_hash": "DDD00004", "hits": 5, "pattern_hex": pattern_d},
                    {"glyph_hash": "EEE00005", "hits": 5, "pattern_hex": pattern_e},
                ],
            )

            mapping_path = base / "mapping.json"
            _write_json(
                mapping_path,
                {
                    "mappings": {
                        "AAA00001": "A",
                        "BBB00002": "B",
                        "CCC00003": "C",
                        "DDD00004": "D",
                        "EEE00005": "E",
                    }
                },
            )

            cmd_false = [
                sys.executable,
                "-m",
                "tools.runtime_qa.dyn_coverage_converge",
                "--runs-dir",
                str(runtime_dir),
                "--mapping-json",
                str(mapping_path),
                "--k",
                "2",
                "--delta-unique-pct",
                "10.0",
                "--delta-glyph-pct",
                "10.0",
                "--max-unknown-pct",
                "1.0",
                "--min-coverage-hits",
                "95.0",
            ]
            proc_false = subprocess.run(
                cmd_false,
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc_false.returncode, 0, msg=proc_false.stderr)
            report_path = crc_dir / f"{crc}_dyn_convergence_report.json"
            self.assertTrue(report_path.exists())
            report_false = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertFalse(bool(report_false.get("converged")))

            cmd_true = [
                sys.executable,
                "-m",
                "tools.runtime_qa.dyn_coverage_converge",
                "--runs-dir",
                str(runtime_dir),
                "--mapping-json",
                str(mapping_path),
                "--k",
                "2",
                "--delta-unique-pct",
                "60.0",
                "--delta-glyph-pct",
                "30.0",
                "--max-unknown-pct",
                "1.0",
                "--min-coverage-hits",
                "95.0",
            ]
            proc_true = subprocess.run(
                cmd_true,
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc_true.returncode, 0, msg=proc_true.stderr)
            report_true = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertTrue(bool(report_true.get("converged")))
            self.assertTrue((crc_dir / f"{crc}_dyn_convergence_report.txt").exists())
            self.assertTrue((crc_dir / f"{crc}_dyn_convergence_proof.json").exists())

    def test_strict_fails_on_crc_or_size_mismatch(self) -> None:
        crc = "FEEDBEEF"
        pattern = "11" * 32
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            crc_dir = base / crc
            runtime_dir = crc_dir / "runtime"
            run2 = runtime_dir / "2_runtime_dyn"
            run3 = runtime_dir / "3_runtime_dyn"

            _create_run(
                run2,
                crc=crc,
                rom_size=131072,
                unique_lines=["AAAA"],
                dyn_rows=[_make_dyn_row(1, 0, "AAAA", ["ABC00001"] * 4, [pattern] * 4)],
                bootstrap_rows=[{"glyph_hash": "ABC00001", "hits": 10, "pattern_hex": pattern}],
            )
            _create_run(
                run3,
                crc=crc,
                rom_size=999999,
                unique_lines=["AAAA"],
                dyn_rows=[_make_dyn_row(2, 0, "AAAA", ["ABC00001"] * 4, [pattern] * 4)],
                bootstrap_rows=[{"glyph_hash": "ABC00001", "hits": 10, "pattern_hex": pattern}],
            )

            cmd = [
                sys.executable,
                "-m",
                "tools.runtime_qa.dyn_coverage_converge",
                "--runs-dir",
                str(runtime_dir),
                "--strict",
            ]
            proc = subprocess.run(
                cmd,
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(proc.returncode, 0)


if __name__ == "__main__":
    unittest.main()

