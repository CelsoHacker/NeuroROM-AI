# -*- coding: utf-8 -*-
"""
Adaptador de encoding multi-console.

Suposicoes minimas:
1) Reusa `tbl_path` existente em game_profiles_db/perfis.
2) Se houver mapa custom `char_to_byte`, usa ASCII custom.
3) Sem profile explicito, aplica defaults por console (ASCII/SJIS/UTF-8).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping

try:
    from .tbl_loader import TBLLoader
except Exception:  # pragma: no cover
    from tbl_loader import TBLLoader


_HEX_TOKEN_RE = re.compile(r"^[0-9A-Fa-f]{2}$")


def _to_console_alias(console_type: str) -> str:
    raw = str(console_type or "").strip().upper()
    aliases = {
        "GENESIS": "MD",
        "MEGADRIVE": "MD",
        "MASTER_SYSTEM": "SMS",
        "PC_WINDOWS": "PC",
    }
    return aliases.get(raw, raw)


def _parse_int(value: Any, default: int | None = None) -> int | None:
    if value is None:
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return int(value)
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return default
        try:
            if raw.lower().startswith("0x"):
                return int(raw, 16)
            # Se parece hex sem prefixo, prioriza base16.
            if any(c in raw.lower() for c in "abcdef"):
                return int(raw, 16)
            return int(raw)
        except ValueError:
            return default
    return default


class EncodingAdapter:
    def __init__(
        self,
        console_type: str,
        profile: Mapping[str, Any] | None = None,
        table_path: str | Path | None = None,
        custom_ascii_map: Mapping[str, Any] | None = None,
    ):
        self.console_type = _to_console_alias(console_type)
        self.profile = dict(profile) if isinstance(profile, Mapping) else {}

        raw_tbl = table_path if table_path is not None else self.profile.get("tbl_path")
        self.table_path = self._resolve_tbl_path(raw_tbl)
        self.custom_ascii_map = self._normalize_ascii_map(
            custom_ascii_map if custom_ascii_map is not None else self.profile.get("char_to_byte")
        )
        self.mode = self._resolve_mode()
        self._tbl: TBLLoader | None = None

        if self.mode == "tbl" and self.table_path:
            self._tbl = TBLLoader(str(self.table_path))

    def encode(self, text: str) -> bytes:
        """
        Suporte:
        - ASCII custom
        - Table files
        - Shift-JIS
        - UTF-8 (PC)
        """
        if self.mode == "tbl":
            if not self._tbl:
                return text.encode("ascii", errors="strict")
            encoded = self._tbl.encode_text(text)
            if encoded is None:
                raise UnicodeEncodeError("tbl", text, 0, max(1, len(text)), "caractere fora da tabela")
            return encoded

        if self.mode == "custom_ascii":
            return self._encode_custom_ascii(text)

        if self.mode == "shift_jis":
            return text.encode("shift_jis", errors="strict")

        if self.mode == "utf-8":
            return text.encode("utf-8", errors="strict")

        return text.encode("ascii", errors="strict")

    def decode(self, byte_data: bytes) -> str:
        """
        Decodifica baseado no console.
        """
        if self.mode == "tbl":
            if not self._tbl:
                return byte_data.decode("ascii", errors="replace")
            return self._tbl.decode_bytes(byte_data, max_length=max(1, len(byte_data)))

        if self.mode == "custom_ascii":
            reverse: dict[int, str] = {}
            for ch, b in self.custom_ascii_map.items():
                if b not in reverse:
                    reverse[b] = ch
            out: list[str] = []
            for b in byte_data:
                out.append(reverse.get(int(b), f"<{int(b):02X}>"))
            return "".join(out)

        if self.mode == "shift_jis":
            return byte_data.decode("shift_jis", errors="replace")

        if self.mode == "utf-8":
            return byte_data.decode("utf-8", errors="replace")

        return byte_data.decode("ascii", errors="replace")

    def _resolve_mode(self) -> str:
        explicit = str(self.profile.get("encoding", "")).strip().lower()
        if explicit in {"tilemap", "tbl"} and self.table_path:
            return "tbl"
        if explicit in {"sjis", "shift-jis", "shift_jis"}:
            return "shift_jis"
        if explicit in {"utf-8", "utf8"}:
            return "utf-8"
        if explicit in {"ascii_custom", "custom_ascii"}:
            return "custom_ascii" if self.custom_ascii_map else "ascii"

        if self.table_path:
            return "tbl"
        if self.custom_ascii_map:
            return "custom_ascii"

        default_by_console = {
            "PS1": "shift_jis",
            "N64": "shift_jis",
            "PC": "utf-8",
        }
        return default_by_console.get(self.console_type, "ascii")

    def _resolve_tbl_path(self, raw_path: Any) -> Path | None:
        if not raw_path:
            return None
        p = Path(str(raw_path))
        if p.exists():
            return p

        project_root = Path(__file__).resolve().parent.parent
        candidate = project_root / str(raw_path)
        if candidate.exists():
            return candidate

        raw = str(raw_path).replace("\\", "/")
        if raw.startswith("core/"):
            candidate = project_root / raw[5:]
            if candidate.exists():
                return candidate

        local_candidate = Path(__file__).resolve().parent / str(raw_path)
        if local_candidate.exists():
            return local_candidate
        return None

    def _normalize_ascii_map(self, raw_map: Any) -> dict[str, int]:
        if not isinstance(raw_map, Mapping):
            return {}
        out: dict[str, int] = {}
        for key, value in raw_map.items():
            if not isinstance(key, str) or len(key) != 1:
                continue
            parsed = _parse_int(value)
            if parsed is None:
                continue
            out[key] = int(parsed) & 0xFF
        return out

    def _encode_custom_ascii(self, text: str) -> bytes:
        out = bytearray()
        i = 0
        while i < len(text):
            if text[i] == "<" and i + 3 < len(text) and text[i + 3] == ">":
                token = text[i + 1 : i + 3]
                if _HEX_TOKEN_RE.match(token):
                    out.append(int(token, 16))
                    i += 4
                    continue

            ch = text[i]
            value = self.custom_ascii_map.get(ch)
            if value is None:
                raise UnicodeEncodeError("custom_ascii", text, i, i + 1, f"char '{ch}' sem mapeamento")
            out.append(int(value) & 0xFF)
            i += 1
        return bytes(out)

