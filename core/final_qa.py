# -*- coding: utf-8 -*-
"""
QA Final de Reinsercao
======================
Gera avaliacao final por console/jogo e destaca casos que podem depender de
codec/script proprietario.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _int(value: Any, default: int = 0) -> int:
    if value is None:
        return int(default)
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        raw = value.strip().lower()
        if not raw:
            return int(default)
        try:
            if raw.startswith("0x"):
                return int(raw, 16)
            return int(raw)
        except ValueError:
            return int(default)
    return int(default)


def _status_from_optional_bool(value: Optional[bool]) -> str:
    if value is None:
        return "unknown"
    return "pass" if bool(value) else "fail"


def _add_gate(
    gates: List[Dict[str, Any]],
    name: str,
    status: str,
    required: bool,
    detail: str,
) -> None:
    gates.append(
        {
            "name": str(name),
            "status": str(status),
            "required": bool(required),
            "detail": str(detail),
        }
    )


def detect_proprietary_codec_risk(
    compression_policy: Optional[Dict[str, Any]] = None,
    limitations: Optional[List[str]] = None,
    stats: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Detecta sinais de que o jogo exige engenharia/codec especifico."""
    policy = compression_policy if isinstance(compression_policy, dict) else {}
    limits = limitations if isinstance(limitations, list) else []
    st = stats if isinstance(stats, dict) else {}

    reasons: List[str] = []
    hints: List[str] = []
    mode = str(policy.get("mode", "")).strip().lower()
    notes = str(policy.get("notes", "")).strip()
    requires_codec = str(policy.get("requires_codec", "")).strip()

    if mode in ("mixed", "proprietary", "external", "compressed"):
        hints.append(f"compression_mode={mode}")
    if requires_codec:
        reasons.append(f"requires_codec={requires_codec}")
    notes_l = notes.lower()
    if notes and any(k in notes_l for k in ("codec", "propriet", "compress", "comprim", "script")):
        hints.append(f"compression_notes={notes}")

    unsupported = max(
        _int(st.get("unsupported_algorithm_blocks", 0)),
        _int(st.get("roundtrip_fail_blocks", 0)),
        _int(st.get("bank_table_skipped_high_fanout", 0)),
    )
    if unsupported > 0:
        reasons.append(f"runtime_compression_flags={unsupported}")

    # blocked_items por si só pode ser truncamento/placeholder/budget, não codec.
    # Só vira risco de codec quando já existe indício explícito de compressão/script.
    blocked_items = _int(st.get("blocked_items", 0))
    if blocked_items > 0 and (
        mode in ("mixed", "proprietary", "external", "compressed")
        or bool(requires_codec)
        or any(k in notes_l for k in ("codec", "propriet", "compress", "comprim", "script"))
    ):
        reasons.append(f"blocked_under_compression_context={blocked_items}")

    non_text = _int(st.get("non_text_meta_skipped", 0))
    if non_text > 0:
        hints.append(f"non_text_meta_skipped={non_text}")

    for item in limits:
        txt = str(item).strip()
        low = txt.lower()
        if any(k in low for k in ("codec", "propriet", "comprim", "compressed", "script")):
            hints.append(f"limitation={txt}")

    # remove duplicados mantendo ordem
    uniq: List[str] = []
    seen = set()
    for r in reasons:
        if r in seen:
            continue
        seen.add(r)
        uniq.append(r)
    hint_uniq: List[str] = []
    for h in hints:
        if h in seen:
            continue
        if h in hint_uniq:
            continue
        hint_uniq.append(h)

    return {
        "requires_special_engineering": bool(uniq),
        "reasons": uniq,
        "hints": hint_uniq,
    }


def evaluate_reinsertion_qa(
    console: str,
    rom_crc32: Optional[str],
    rom_size: Optional[int],
    stats: Optional[Dict[str, Any]] = None,
    evidence: Optional[Dict[str, Any]] = None,
    checks: Optional[Dict[str, Optional[bool]]] = None,
    limitations: Optional[List[str]] = None,
    compression_policy: Optional[Dict[str, Any]] = None,
    translation_input: Optional[Dict[str, Any]] = None,
    require_manual_emulator: bool = False,
) -> Dict[str, Any]:
    """Monta QA final padronizado para report/proof por console/jogo."""
    st = stats if isinstance(stats, dict) else {}
    ev = evidence if isinstance(evidence, dict) else {}
    ck = checks if isinstance(checks, dict) else {}
    limits = limitations if isinstance(limitations, list) else []
    t_input = translation_input if isinstance(translation_input, dict) else {}

    trunc_count = max(
        _int(st.get("TRUNC", 0)),
        _int(st.get("truncated", 0)),
        _int(st.get("TRUNC_OVERFLOW", 0)),
        _int(st.get("truncated_items", 0)),
        _int(ev.get("truncated_count", 0)),
    )
    blocked_count = max(
        _int(st.get("BLOCKED", 0)),
        _int(st.get("blocked", 0)),
        _int(st.get("BLOCKED_UNSAFE", 0)),
        _int(st.get("BLOCKED_NO_POINTER", 0)),
        _int(st.get("blocked_items", 0)),
    )
    same_as_source_phrase_count = max(
        _int(ev.get("same_as_source_phrase_count", 0)),
        _int(ev.get("not_translated_count", 0)),
        _int(ev.get("runtime_displayed_same_as_source_phrase_count", 0)),
    )
    english_likely_count = _int(ev.get("english_likely_count", 0))
    displayed_trace_skip_displayed_count = max(
        _int(ev.get("displayed_trace_skip_displayed_count", 0)),
        _int(ev.get("runtime_displayed_skip_displayed_count", 0)),
    )
    displayed_trace_english_residual_count = max(
        _int(ev.get("displayed_trace_english_residual_count", 0)),
        _int(ev.get("runtime_displayed_english_residual_count", 0)),
    )
    runtime_missing_displayed_text_count = max(
        _int(ev.get("runtime_missing_displayed_text_count", 0)),
        _int(ev.get("missing_displayed_text_count", 0)),
    )
    critical_count = sum(
        [
            _int(ev.get("rom_vs_translated_mismatch_count", 0)),
            _int(ev.get("placeholder_fail_count", 0)),
            _int(ev.get("terminator_missing_count", 0)),
            _int(ev.get("suspicious_non_pt_count", 0)),
            _int(ev.get("unchanged_equal_src_count", 0)),
            int(same_as_source_phrase_count),
            int(english_likely_count),
            int(displayed_trace_skip_displayed_count),
            int(displayed_trace_english_residual_count),
            int(runtime_missing_displayed_text_count),
        ]
    )

    prop = detect_proprietary_codec_risk(
        compression_policy=compression_policy,
        limitations=limits,
        stats=st,
    )

    input_match = ck.get("input_match")
    ordering_ok = ck.get("ordering")
    emulator_smoke = ck.get("emulator_smoke")

    gates: List[Dict[str, Any]] = []
    _add_gate(
        gates,
        "no_truncation",
        _status_from_optional_bool(trunc_count == 0),
        True,
        f"truncated_total={trunc_count}",
    )
    _add_gate(
        gates,
        "no_blocked_items",
        _status_from_optional_bool(blocked_count == 0),
        True,
        f"blocked_total={blocked_count}",
    )
    _add_gate(
        gates,
        "critical_issues_zero",
        _status_from_optional_bool(critical_count == 0),
        True,
        f"critical_total={critical_count}",
    )
    _add_gate(
        gates,
        "english_likely_zero",
        _status_from_optional_bool(int(english_likely_count) == 0),
        True,
        f"english_likely_count={int(english_likely_count)}",
    )
    _add_gate(
        gates,
        "same_as_source_phrase_zero",
        _status_from_optional_bool(int(same_as_source_phrase_count) == 0),
        True,
        f"same_as_source_phrase_count={int(same_as_source_phrase_count)}",
    )
    _add_gate(
        gates,
        "displayed_trace_skip_displayed_zero",
        _status_from_optional_bool(int(displayed_trace_skip_displayed_count) == 0),
        True,
        f"displayed_trace_skip_displayed_count={int(displayed_trace_skip_displayed_count)}",
    )
    _add_gate(
        gates,
        "displayed_trace_english_residual_zero",
        _status_from_optional_bool(int(displayed_trace_english_residual_count) == 0),
        True,
        f"displayed_trace_english_residual_count={int(displayed_trace_english_residual_count)}",
    )
    _add_gate(
        gates,
        "runtime_missing_displayed_zero",
        _status_from_optional_bool(int(runtime_missing_displayed_text_count) == 0),
        True,
        f"runtime_missing_displayed_text_count={int(runtime_missing_displayed_text_count)}",
    )
    _add_gate(
        gates,
        "input_match",
        _status_from_optional_bool(input_match),
        True,
        "CRC/size de entrada e ROM selecionada",
    )
    _add_gate(
        gates,
        "ordering_consistent",
        _status_from_optional_bool(ordering_ok),
        True,
        "ordem deterministica por seq/offset",
    )
    _add_gate(
        gates,
        "proprietary_codec_case",
        "fail" if prop.get("requires_special_engineering") else "pass",
        True,
        (
            "; ".join(prop.get("reasons", []))
            if prop.get("reasons")
            else (
                "; ".join(prop.get("hints", []))
                if prop.get("hints")
                else "sem indicios"
            )
        ),
    )
    _add_gate(
        gates,
        "emulator_smoke_test",
        _status_from_optional_bool(emulator_smoke),
        bool(require_manual_emulator),
        "inicio/menu/dialogo validado no emulador",
    )

    required_failed = [g["name"] for g in gates if g["required"] and g["status"] == "fail"]
    required_unknown = [g["name"] for g in gates if g["required"] and g["status"] == "unknown"]

    known_required = [g for g in gates if g["required"] and g["status"] in ("pass", "fail")]
    if known_required:
        pass_known = sum(1 for g in known_required if g["status"] == "pass")
        score = round((pass_known / len(known_required)) * 100.0, 2)
    else:
        score = 0.0

    overall_pass = len(required_failed) == 0 and len(required_unknown) == 0
    if not require_manual_emulator:
        # gate manual vira informativo por padrao
        required_unknown = [g for g in required_unknown if g != "emulator_smoke_test"]
        overall_pass = len(required_failed) == 0 and len(required_unknown) == 0

    next_actions: List[str] = []
    if "proprietary_codec_case" in required_failed:
        next_actions.append(
            "Implementar/selecionar codec especifico do jogo e recompressao binaria equivalente."
        )
    if "input_match" in required_failed:
        next_actions.append(
            "Conferir ROM original selecionada e JSONL correspondente (CRC32/rom_size)."
        )
    if "ordering_consistent" in required_failed:
        next_actions.append(
            "Regerar JSONL com seq deterministico e reinserir em ordem."
        )
    if "critical_issues_zero" in required_failed:
        next_actions.append(
            "Corrigir placeholders/terminadores/mismatch e repetir reinsercao."
        )
    if "english_likely_zero" in required_failed:
        next_actions.append(
            "Reprocessar linhas com ingles residual (stopwords EN) ate zerar english_likely_count."
        )
    if "same_as_source_phrase_zero" in required_failed:
        next_actions.append(
            "Reprocessar frases que permaneceram iguais ao source ate zerar same_as_source_phrase_count."
        )
    if "displayed_trace_skip_displayed_zero" in required_failed:
        next_actions.append(
            "Cobrir e aplicar itens exibiveis que ainda ficaram SKIP/BLOCKED/NOT_APPLIED no tracer."
        )
    if "displayed_trace_english_residual_zero" in required_failed:
        next_actions.append(
            "Reprocessar textos exibiveis com ingles residual ate zerar displayed_trace_english_residual_count."
        )
    if "runtime_missing_displayed_zero" in required_failed:
        next_actions.append(
            "Executar RuntimeQA e fechar itens faltantes ate zerar runtime_missing_displayed_text_count."
        )
    if "no_truncation" in required_failed:
        next_actions.append(
            "Aplicar abreviacao/reformulacao com limite estrito de bytes."
        )
    if "emulator_smoke_test" in required_unknown and require_manual_emulator:
        next_actions.append(
            "Executar smoke test no emulador (inicio/menu/dialogo) e registrar resultado."
        )

    return {
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "console": str(console),
        "rom_crc32": str(rom_crc32 or "").upper() or None,
        "rom_size": _int(rom_size, default=0) if rom_size is not None else None,
        "translation_input": t_input,
        "gates": gates,
        "required_failed": required_failed,
        "required_unknown": required_unknown,
        "overall_pass": bool(overall_pass),
        "quality_score_percent": float(score),
        "proprietary_codec_risk": prop,
        "limitations": limits,
        "next_actions": next_actions,
    }


def write_qa_artifacts(
    output_dir: Path,
    base_tag: str,
    qa_data: Dict[str, Any],
) -> Tuple[Path, Path]:
    """Escreve QA final em JSON e TXT."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = str(base_tag)

    qa_json_path = out_dir / f"{tag}_qa_final.json"
    qa_txt_path = out_dir / f"{tag}_qa_final.txt"

    qa_json_path.write_text(
        json.dumps(qa_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines: List[str] = [
        f"QA_FINAL {tag}",
        f"created_at={qa_data.get('created_at')}",
        f"console={qa_data.get('console')}",
        f"rom_crc32={qa_data.get('rom_crc32')}",
        f"rom_size={qa_data.get('rom_size')}",
        f"overall_pass={str(bool(qa_data.get('overall_pass', False))).lower()}",
        f"quality_score_percent={qa_data.get('quality_score_percent')}",
        "",
        "GATES:",
    ]
    for gate in qa_data.get("gates", []) or []:
        lines.append(
            "  - "
            + f"{gate.get('name')}: status={gate.get('status')} "
            + f"required={str(bool(gate.get('required', False))).lower()} "
            + f"detail={gate.get('detail')}"
        )

    prop = qa_data.get("proprietary_codec_risk", {}) or {}
    lines.extend(
        [
            "",
            "PROPRIETARY_CODEC_RISK:",
            f"  requires_special_engineering={str(bool(prop.get('requires_special_engineering', False))).lower()}",
            f"  reasons={json.dumps(prop.get('reasons', []), ensure_ascii=False)}",
        ]
    )

    nxt = qa_data.get("next_actions", []) or []
    if nxt:
        lines.append("")
        lines.append("NEXT_ACTIONS:")
        for item in nxt:
            lines.append(f"  - {item}")

    qa_txt_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return qa_json_path, qa_txt_path
