# -*- coding: utf-8 -*-
"""
Layout engine universal (pixel + mono).

Suposicoes minimas:
1) `box_profile` contem ao menos: mode, max_width e opcionalmente max_lines.
2) Quebras manuais (`\\n`) sao preservadas.
3) Tokens de controle no formato <...> nao contam na metricao visual.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Mapping, Protocol


class _GlyphMetricsLike(Protocol):
    def measure(self, text: str) -> int:
        ...


_TOKEN_RE = re.compile(r"<[^>]+>")
_WORD_RE = re.compile(r"\S+")


def _strip_tokens(text: str) -> str:
    return _TOKEN_RE.sub("", text or "")


class TextLayoutEngine:
    def __init__(self, glyph_metrics: _GlyphMetricsLike | None, box_profile: Mapping[str, Any]):
        self.glyph_metrics = glyph_metrics
        self.box_profile = dict(box_profile)

    def layout(self, text: str) -> dict[str, Any]:
        """
        Processa:
        - Word wrap inteligente
        - Respeita quebras manuais
        - Evita linhas orfas
        - Mede por pixel ou mono
        - Detecta overflow visual

        Retorna:
        {
            "lines": [...],
            "visual_overflow": bool,
            "pixel_widths": [...],
            "line_count": int,
            "score": int
        }
        """
        mode = str(self.box_profile.get("mode", "mono")).strip().lower()
        max_width = int(self.box_profile.get("max_width", 32))
        max_lines = int(self.box_profile.get("max_lines", 0))
        measure = self._build_measure_fn(mode)

        normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n")
        lines: list[str] = []

        for paragraph in normalized.split("\n"):
            wrapped = self._wrap_paragraph(paragraph, max_width, measure)
            lines.extend(wrapped)

        lines = self._balance_last_line(lines, max_width, measure)
        widths = [measure(line) for line in lines]

        overflow_by_width = any(w > max_width for w in widths)
        overflow_by_lines = max_lines > 0 and len(lines) > max_lines
        visual_overflow = bool(overflow_by_width or overflow_by_lines)
        score = self._score_layout(lines, widths, max_width, max_lines)

        return {
            "lines": lines,
            "visual_overflow": visual_overflow,
            "pixel_widths": widths,
            "line_count": len(lines),
            "score": score,
        }

    def _build_measure_fn(self, mode: str) -> Callable[[str], int]:
        if mode == "pixel" and self.glyph_metrics is not None:
            return lambda s: int(self.glyph_metrics.measure(s))
        return lambda s: len(_strip_tokens(s))

    def _wrap_paragraph(self, paragraph: str, max_width: int, measure: Callable[[str], int]) -> list[str]:
        words = _WORD_RE.findall(paragraph)
        if not words:
            return [""]

        out: list[str] = []
        current = ""

        for word in words:
            candidate = word if not current else f"{current} {word}"
            if measure(candidate) <= max_width:
                current = candidate
                continue

            if current:
                out.append(current)
                if measure(word) <= max_width:
                    current = word
                else:
                    # Nunca quebra palavra no meio. Palavra longa vira linha overflow.
                    out.append(word)
                    current = ""
                continue

            out.append(word)

        if current:
            out.append(current)
        return out

    def _balance_last_line(
        self, lines: list[str], max_width: int, measure: Callable[[str], int]
    ) -> list[str]:
        if len(lines) < 2:
            return lines

        result = list(lines)
        short_threshold = max(1, int(max_width * 0.35))

        while len(result) >= 2:
            last = result[-1]
            prev = result[-2]
            if measure(last) >= short_threshold:
                break

            prev_words = prev.split()
            if len(prev_words) <= 1:
                break

            moved = prev_words[-1]
            new_prev = " ".join(prev_words[:-1])
            new_last = moved if not last else f"{moved} {last}"

            if measure(new_last) > max_width:
                break
            if not new_prev.strip():
                break

            result[-2] = new_prev
            result[-1] = new_last

        return result

    def _score_layout(
        self,
        lines: list[str],
        widths: list[int],
        max_width: int,
        max_lines: int,
    ) -> int:
        score = 100
        width_overflows = sum(1 for w in widths if w > max_width)
        score -= width_overflows * 20

        if max_lines > 0 and len(lines) > max_lines:
            score -= (len(lines) - max_lines) * 10

        if len(lines) >= 2:
            last_w = widths[-1] if widths else 0
            if last_w > 0 and last_w < int(max_width * 0.25):
                score -= 5

        return max(0, min(100, int(score)))

