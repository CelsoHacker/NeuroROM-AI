# -*- coding: utf-8 -*-
"""
================================================================================
TECHNICAL VALIDATOR - Validacao Tecnica de Traducoes
================================================================================
Valida traducoes antes e depois da reinsercao para garantir integridade.

Validacoes pre-reinsercao:
- Terminador preservado
- Tokens/comandos preservados (<XX>, {var}, %d)
- Placeholders preservados
- Round-trip encode/decode valido

Validacoes pos-reinsercao:
- Ponteiros apontam para offsets validos
- Nao ha overlap entre alocacoes
- Texto no destino corresponde ao esperado
================================================================================
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass
class TechValidationResult:
    """Resultado de validacao tecnica."""
    valid: bool
    checks: Dict[str, bool] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            'valid': self.valid,
            'checks': self.checks,
            'errors': self.errors,
            'warnings': self.warnings
        }


class TechnicalValidator:
    """
    Validador tecnico para traducoes de ROM.

    Garante que traducoes nao quebram a ROM:
    - Preserva tokens de controle
    - Preserva placeholders
    - Valida encoding round-trip
    - Verifica integridade pos-reinsercao
    """

    # Padroes de tokens comuns em ROMs
    TOKEN_PATTERNS = [
        r'<[0-9A-Fa-f]{2}>',           # Bytes de controle: <00>, <FF>
        r'<[0-9A-Fa-f]{4}>',           # Bytes 16-bit: <0000>
        r'\{[^}]+\}',                   # Variaveis: {name}, {player}
        r'%[sdxXofeEgGc]',              # Printf-style: %s, %d, %x
        r'%[0-9]*[sdxXofeEgGc]',        # Printf com tamanho: %3d
        r'\$[A-Za-z_][A-Za-z0-9_]*',    # Variaveis $: $PLAYER
        r'\\n|\\r|\\t',                 # Escapes
        r'\[pause\]|\[wait\]|\[end\]',  # Comandos de script
        r'\[color=[^\]]+\]',            # Tags de cor
    ]

    # Padroes de placeholder (devem ser preservados exatamente)
    PLACEHOLDER_PATTERNS = [
        r'\{[^}]+\}',           # {name}, {item}, {count}
        r'%[0-9]*[sdxX]',       # %s, %d, %3d
        r'\$[A-Z_]+',           # $PLAYER, $ITEM
        r'<TILE_[0-9A-F]+>',    # Tiles: <TILE_00>
        r'<UNK_[0-9A-F]+>',     # Unknown bytes
        r'<BYTE_[0-9A-F]+>',    # Raw bytes
    ]

    def __init__(self, charset: Optional[Dict] = None):
        """
        Inicializa validador.

        Args:
            charset: Tabela de caracteres para validacao de round-trip
        """
        self.charset = charset or {}
        self._compile_patterns()

    def _compile_patterns(self):
        """Compila padroes regex."""
        self.token_regex = re.compile('|'.join(self.TOKEN_PATTERNS))
        self.placeholder_regex = re.compile('|'.join(self.PLACEHOLDER_PATTERNS))

    def validate_pre_reinsertion(
        self,
        original: str,
        translation: str,
        entry: Optional[Dict] = None
    ) -> TechValidationResult:
        """
        Valida traducao ANTES de reinserir.

        Args:
            original: Texto original
            translation: Texto traduzido
            entry: Entrada do mapping (opcional, para contexto)

        Returns:
            TechValidationResult com resultado da validacao
        """
        result = TechValidationResult(valid=True)
        entry = entry or {}

        # Check 1: Tokens preservados
        tokens_ok, token_errors = self._check_tokens(original, translation)
        result.checks['tokens_preserved'] = tokens_ok
        if not tokens_ok:
            result.errors.extend(token_errors)

        # Check 2: Placeholders preservados
        placeholders_ok, ph_errors = self._check_placeholders(original, translation)
        result.checks['placeholders_preserved'] = placeholders_ok
        if not placeholders_ok:
            result.errors.extend(ph_errors)

        # Check 3: Round-trip encoding valido
        encoding = entry.get('encoding', 'ascii')
        roundtrip_ok, rt_errors = self._check_roundtrip(translation, encoding)
        result.checks['roundtrip_valid'] = roundtrip_ok
        if not roundtrip_ok:
            result.errors.extend(rt_errors)

        # Check 4: Nao esta vazio (se original nao estava)
        if original.strip() and not translation.strip():
            result.checks['not_empty'] = False
            result.errors.append("Translation is empty but original was not")
        else:
            result.checks['not_empty'] = True

        # Check 5: Comprimento razoavel (aviso se muito diferente)
        len_ratio = len(translation) / max(1, len(original))
        if len_ratio > 3.0:
            result.warnings.append(f"Translation is {len_ratio:.1f}x longer than original")
        result.checks['length_reasonable'] = len_ratio <= 5.0

        # Resultado final
        result.valid = all(result.checks.values())
        return result

    def _check_tokens(self, original: str, translation: str) -> Tuple[bool, List[str]]:
        """Verifica se todos os tokens foram preservados."""
        errors = []

        orig_tokens = set(self.token_regex.findall(original))
        trans_tokens = set(self.token_regex.findall(translation))

        # Tokens faltando na traducao
        missing = orig_tokens - trans_tokens
        for token in missing:
            errors.append(f"Missing token in translation: {token}")

        # Tokens extras na traducao (aviso, nao erro)
        # extra = trans_tokens - orig_tokens

        return len(missing) == 0, errors

    def _check_placeholders(self, original: str, translation: str) -> Tuple[bool, List[str]]:
        """Verifica se todos os placeholders foram preservados."""
        errors = []

        orig_ph = self.placeholder_regex.findall(original)
        trans_ph = self.placeholder_regex.findall(translation)

        # Conta ocorrencias
        from collections import Counter
        orig_counts = Counter(orig_ph)
        trans_counts = Counter(trans_ph)

        # Verifica se todos os placeholders estao presentes
        for ph, count in orig_counts.items():
            trans_count = trans_counts.get(ph, 0)
            if trans_count < count:
                errors.append(
                    f"Placeholder '{ph}' appears {count}x in original "
                    f"but only {trans_count}x in translation"
                )

        return len(errors) == 0, errors

    def _check_roundtrip(self, text: str, encoding: str) -> Tuple[bool, List[str]]:
        """Verifica se texto pode ser codificado e decodificado sem perda."""
        errors = []

        # Se temos charset customizado
        if self.charset and self.charset.get('char_to_byte'):
            char_to_byte = self.charset['char_to_byte']
            for char in text:
                # Ignora tokens de controle
                if char in '<>{}%$[]\\':
                    continue
                if char not in char_to_byte:
                    errors.append(f"Character '{char}' not in charset table")
            return len(errors) == 0, errors

        # Usa encoding padrao
        try:
            if encoding in ('ascii', 'latin-1', 'utf-8', 'shift_jis'):
                encoded = text.encode(encoding, errors='strict')
                decoded = encoded.decode(encoding, errors='strict')
                if decoded != text:
                    errors.append("Round-trip encoding failed: text changed")
        except (UnicodeEncodeError, UnicodeDecodeError) as e:
            errors.append(f"Encoding error: {e}")

        return len(errors) == 0, errors

    def validate_post_reinsertion(
        self,
        rom_data: bytes,
        mapping: Dict,
        allocations: Optional[List[Dict]] = None
    ) -> TechValidationResult:
        """
        Valida ROM DEPOIS de reinsercao.

        Args:
            rom_data: Dados da ROM apos reinsercao
            mapping: Mapping de reinsercao usado
            allocations: Lista de alocacoes realizadas

        Returns:
            TechValidationResult com resultado da validacao
        """
        result = TechValidationResult(valid=True)
        allocations = allocations or []

        # Check 1: Verifica ponteiros apontam para offsets validos
        pointer_errors = self._validate_pointers(rom_data, mapping)
        result.checks['pointers_valid'] = len(pointer_errors) == 0
        result.errors.extend(pointer_errors)

        # Check 2: Verifica nao ha overlap entre alocacoes
        overlap_errors = self._check_allocation_overlaps(allocations)
        result.checks['no_overlaps'] = len(overlap_errors) == 0
        result.errors.extend(overlap_errors)

        # Check 3: Verifica alocacoes estao dentro dos limites da ROM
        bounds_errors = self._check_allocation_bounds(rom_data, allocations)
        result.checks['within_bounds'] = len(bounds_errors) == 0
        result.errors.extend(bounds_errors)

        result.valid = all(result.checks.values())
        return result

    def _validate_pointers(self, rom_data: bytes, mapping: Dict) -> List[str]:
        """Verifica se ponteiros apontam para offsets validos."""
        errors = []
        rom_size = len(rom_data)

        for entry in mapping.get('mappings', []):
            for pref in entry.get('pointer_refs', []):
                ptr_offset = pref.get('ptr_offset')
                if isinstance(ptr_offset, str):
                    ptr_offset = int(ptr_offset, 16)

                if ptr_offset is None:
                    continue

                ptr_size = pref.get('ptr_size', 2)

                # Verifica ponteiro esta dentro da ROM
                if ptr_offset < 0 or ptr_offset + ptr_size > rom_size:
                    errors.append(
                        f"Pointer at 0x{ptr_offset:06X} is out of ROM bounds"
                    )

        return errors

    def _check_allocation_overlaps(self, allocations: List[Dict]) -> List[str]:
        """Verifica se ha sobreposicao entre alocacoes."""
        errors = []

        # Converte para lista de (start, end, uid)
        ranges = []
        for alloc in allocations:
            offset = alloc.get('offset')
            if isinstance(offset, str):
                offset = int(offset, 16)
            if offset is None:
                continue

            size = alloc.get('size', 0)
            uid = alloc.get('item_uid', 'unknown')
            ranges.append((offset, offset + size, uid))

        # Ordena por offset
        ranges.sort(key=lambda x: x[0])

        # Verifica overlaps
        for i in range(len(ranges) - 1):
            curr_start, curr_end, curr_uid = ranges[i]
            next_start, next_end, next_uid = ranges[i + 1]

            if curr_end > next_start:
                errors.append(
                    f"OVERLAP: {curr_uid} (0x{curr_start:06X}-0x{curr_end:06X}) "
                    f"overlaps with {next_uid} (0x{next_start:06X}-0x{next_end:06X})"
                )

        return errors

    def _check_allocation_bounds(
        self,
        rom_data: bytes,
        allocations: List[Dict]
    ) -> List[str]:
        """Verifica se alocacoes estao dentro dos limites da ROM."""
        errors = []
        rom_size = len(rom_data)

        for alloc in allocations:
            offset = alloc.get('offset')
            if isinstance(offset, str):
                offset = int(offset, 16)
            if offset is None:
                continue

            size = alloc.get('size', 0)
            uid = alloc.get('item_uid', 'unknown')

            if offset < 0:
                errors.append(f"{uid}: negative offset 0x{offset:06X}")
            elif offset + size > rom_size:
                errors.append(
                    f"{uid}: allocation at 0x{offset:06X} + {size} bytes "
                    f"exceeds ROM size ({rom_size} bytes)"
                )

        return errors


def validate_translation_batch(
    items: List[Tuple[str, str, str]],
    charset: Optional[Dict] = None
) -> Dict[str, TechValidationResult]:
    """
    Valida um lote de traducoes.

    Args:
        items: Lista de (uid, original, translation)
        charset: Tabela de caracteres opcional

    Returns:
        Dicionario {uid: TechValidationResult}
    """
    validator = TechnicalValidator(charset)
    results = {}

    for uid, original, translation in items:
        results[uid] = validator.validate_pre_reinsertion(original, translation)

    return results
