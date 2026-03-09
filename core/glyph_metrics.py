# -*- coding: utf-8 -*-
"""
Metrica de glyph para layout pixel.

Suposicoes minimas:
1) Se o arquivo de tabela nao existir, o modulo continua funcional com fallback.
2) Tokens de controle no formato <...> nao contam para largura visual.
3) O JSON pode vir como mapa direto {"A": 7} ou {"widths": {...}, "default_width": 8}.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

_TOKEN_RE = re.compile(r"<[^>]+>")


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


class GlyphMetrics:
    def __init__(self, glyph_table_path: str | Path, default_width: int = 8):
        self.glyph_table_path = Path(glyph_table_path)
        raw = _load_json(self.glyph_table_path)
        payload: Mapping[str, Any]
        if isinstance(raw, Mapping):
            maybe_widths = raw.get("widths")
            payload = maybe_widths if isinstance(maybe_widths, Mapping) else raw
        else:
            payload = {}

        self.default_width = int(raw.get("default_width", default_width)) if isinstance(raw, Mapping) else int(default_width)
        self.widths: dict[str, int] = {}
        for key, value in payload.items():
            if not isinstance(key, str) or len(key) != 1:
                continue
            try:
                self.widths[key] = int(value)
            except Exception:
                continue

    def measure(self, text: str) -> int:
        """
        Retorna largura total em pixels.
        """
        visible = _TOKEN_RE.sub("", text or "")
        total = 0
        for ch in visible:
            total += self.widths.get(ch, self.default_width)
        return int(total)

