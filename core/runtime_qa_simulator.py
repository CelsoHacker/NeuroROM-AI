# -*- coding: utf-8 -*-
"""
Simulador de QA runtime (pre-check de reinsercao).

Suposicoes minimas:
1) Recebe `string_entry` em formato parecido com mapping/extraction atual.
2) `layout_result` vem do TextLayoutEngine.
3) O resumo agregado fica no proprio objeto (`summary`) e tambem no retorno.
"""

from __future__ import annotations

from typing import Any, Mapping

try:
    from .console_memory_model import ConsoleMemoryModel
    from .encoding_adapter import EncodingAdapter
except Exception:  # pragma: no cover
    from console_memory_model import ConsoleMemoryModel
    from encoding_adapter import EncodingAdapter


def _to_int(value: Any, default: int | None = None) -> int | None:
    if value is None:
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return default
        try:
            if raw.lower().startswith("0x"):
                return int(raw, 16)
            return int(raw)
        except ValueError:
            return default
    return default


class RuntimeQASimulator:
    def __init__(self, console_model: ConsoleMemoryModel, encoding_adapter: EncodingAdapter | None = None):
        self.console_model = console_model
        self.encoding_adapter = encoding_adapter
        self._score_total = 0
        self._runs = 0
        self._summary = {"ok": 0, "warn": 0, "error": 0, "score": 100}

    def simulate(self, string_entry: Mapping[str, Any], layout_result: Mapping[str, Any]) -> dict[str, Any]:
        """
        Verifica:
        - Overflow visual
        - Overflow de bytes
        - Bank crossing (SNES)
        - Segment overflow (N64)
        - Pointer safety
        - Encoding compatibility

        Retorna:
        {
            "visual_overflow": bool,
            "byte_overflow": bool,
            "bank_violation": bool,
            "pointer_safe": bool,
            "final_score": int
        }
        """
        layout = dict(layout_result) if isinstance(layout_result, Mapping) else {}
        entry = dict(string_entry) if isinstance(string_entry, Mapping) else {}

        visual_overflow = bool(layout.get("visual_overflow", False))

        encoded_bytes = entry.get("encoded_bytes")
        encoding_compatible = True
        if not isinstance(encoded_bytes, (bytes, bytearray)):
            text = str(entry.get("text", ""))
            if self.encoding_adapter is not None:
                try:
                    encoded_bytes = self.encoding_adapter.encode(text)
                except Exception:
                    encoding_compatible = False
                    encoded_bytes = b""
            else:
                encoded_bytes = text.encode("ascii", errors="replace")
        encoded_len = len(encoded_bytes)

        max_bytes = _to_int(
            entry.get("max_bytes")
            or entry.get("max_len_bytes")
            or entry.get("max_len")
            or entry.get("length"),
            default=0,
        ) or 0
        byte_overflow = bool(max_bytes > 0 and encoded_len > max_bytes)

        offset = _to_int(entry.get("offset") or entry.get("target_offset") or entry.get("offset_dec"))
        memory_ok = True
        if offset is not None and encoded_len > 0:
            memory_ok = self.console_model.validate_write(offset, encoded_len)

        bank_violation = not memory_ok
        pointer_safe = self._pointer_safe(entry.get("pointer_refs", []))

        final_score = 100
        if visual_overflow:
            final_score -= 25
        if byte_overflow:
            final_score -= 35
        if bank_violation:
            final_score -= 20
        if not pointer_safe:
            final_score -= 10
        if not encoding_compatible:
            final_score -= 10
        final_score = max(0, min(100, int(final_score)))

        severity = "ok"
        if byte_overflow or bank_violation or not pointer_safe or not encoding_compatible:
            severity = "error"
        elif visual_overflow:
            severity = "warn"

        self._runs += 1
        self._score_total += final_score
        self._summary[severity] += 1
        self._summary["score"] = int(round(self._score_total / max(1, self._runs)))

        return {
            "visual_overflow": visual_overflow,
            "byte_overflow": byte_overflow,
            "bank_violation": bank_violation,
            "pointer_safe": pointer_safe,
            "final_score": final_score,
            "encoding_compatible": encoding_compatible,
            "summary": self.get_summary(),
        }

    def get_summary(self) -> dict[str, Any]:
        return {
            "ok": int(self._summary["ok"]),
            "warn": int(self._summary["warn"]),
            "error": int(self._summary["error"]),
            "score": int(self._summary["score"]),
        }

    def _pointer_safe(self, pointer_refs: Any) -> bool:
        if not pointer_refs:
            return True
        if not isinstance(pointer_refs, list):
            return False
        for ref in pointer_refs:
            if not isinstance(ref, Mapping):
                return False
            ptr_offset = _to_int(ref.get("ptr_offset") or ref.get("pointer_offset"))
            ptr_size = _to_int(ref.get("ptr_size"), default=2) or 2
            if ptr_offset is None or ptr_offset < 0:
                return False
            if ptr_size not in (2, 3, 4):
                return False
        return True

