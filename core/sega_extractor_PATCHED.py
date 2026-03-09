
# -*- coding: utf-8 -*-
"""
Sega Extractor - Master System & Mega Drive/Genesis
====================================================
Extrator especializado para plataformas Sega com ASCII puro.

V6 PRO Upgrade (SMS):
- Extração por ponteiros (pointer-based) para reduzir ruído
- Filtro de confiança antes de exibir strings ao usuário
- Log: "Extração PRO baseada em ponteiros ativada"

Plataformas Suportadas:
- Sega Master System (.sms)
- Sega Mega Drive/Genesis (.gen, .md, .smd, .bin)

Author: NeuroROM AI
License: MIT
"""

import os
import struct
from pathlib import Path
from typing import List, Dict, Tuple, Optional


class SegaExtractor:
    """Extrator especializado para plataformas Sega"""

    # Configurações por plataforma
    PLATFORM_CONFIG = {
        'MASTER_SYSTEM': {
            'name': 'Sega Master System',
            'extensions': ['.sms'],
            'header_offset': 0x7FF0,
            'header_size': 16,
            'ram_start': 0xC000,
            'ram_size': 8192,
            'endian': 'little',
            'bank_size': 0x4000,  # 16KB (paging típico no SMS)
        },
        'GENESIS': {
            'name': 'Sega Genesis / Mega Drive',
            'extensions': ['.gen', '.md', '.bin'],
            'header_offset': 0x100,
            'header_size': 256,
            'ram_start': 0xFF0000,
            'ram_size': 65536,
            'endian': 'big'
        },
        'SMD': {
            'name': 'Sega Mega Drive (Interleaved)',
            'extensions': ['.smd'],
            'header_offset': 0x200,  # SMD tem header de 512 bytes
            'header_size': 256,
            'ram_start': 0xFF0000,
            'ram_size': 65536,
            'endian': 'big',
            'interleaved': True
        }
    }

    # ASCII “visível” + controles úteis
    _PRINTABLE = set(range(0x20, 0x7F))
    _ALLOWED_EXTRA = {0x0A, 0x0D, 0x09}  # \n \r \t

    def __init__(self, rom_path: str):
        """
        Inicializa extrator Sega

        Args:
            rom_path: Caminho da ROM
        """
        self.rom_path = Path(rom_path)
        self.rom_data = None
        self.platform = None
        self.config = None

        if not self.rom_path.exists():
            raise FileNotFoundError(f"ROM não encontrada: {rom_path}")

        # Carrega ROM
        with open(self.rom_path, 'rb') as f:
            self.rom_data = bytearray(f.read())

        # Detecta plataforma
        self._detect_platform()

        # Decodifica SMD se necessário
        if self.config.get('interleaved'):
            self._decode_smd()

    def _detect_platform(self):
        """Detecta plataforma Sega automaticamente"""
        ext = self.rom_path.suffix.lower()

        # Por extensão
        for platform, config in self.PLATFORM_CONFIG.items():
            if ext in config['extensions']:
                self.platform = platform
                self.config = config
                return

        # Fallback: tenta detectar por tamanho
        size = len(self.rom_data)

        if size <= 512 * 1024:  # <= 512KB
            self.platform = 'MASTER_SYSTEM'
        else:
            self.platform = 'GENESIS'

        self.config = self.PLATFORM_CONFIG[self.platform]

    def _decode_smd(self):
        """
        Decodifica formato SMD interleaved para binário linear

        SMD Format:
        - Header de 512 bytes
        - Dados em blocos de 16KB interleaved (odd/even bytes)
        """
        if len(self.rom_data) < 512:
            return

        # Remove header SMD (512 bytes)
        smd_data = self.rom_data[512:]
        decoded = bytearray()

        # Decodifica blocos de 16KB
        block_size = 16384
        for offset in range(0, len(smd_data), block_size):
            block = smd_data[offset:offset + block_size]

            if len(block) < block_size:
                # Último bloco incompleto
                decoded.extend(block)
                break

            # Separa odd/even
            half = block_size // 2
            odd_bytes = block[:half]
            even_bytes = block[half:]

            # Intercala: even, odd, even, odd...
            for i in range(half):
                decoded.append(even_bytes[i])
                decoded.append(odd_bytes[i])

        self.rom_data = decoded

    # =====================================================================
    # V6 PRO (SMS): Ponteiros + Confiança
    # =====================================================================

    @staticmethod
    def _u16_le(buf: bytes, off: int) -> int:
        return buf[off] | (buf[off + 1] << 8)

    @staticmethod
    def _read_c_string(buf: bytes, start: int, terminators=(0x00, 0xFF), max_len=180) -> Optional[bytes]:
        if start < 0 or start >= len(buf):
            return None
        out = bytearray()
        for i in range(max_len):
            p = start + i
            if p >= len(buf):
                break
            b = buf[p]
            if b in terminators:
                break
            out.append(b)
        if len(out) < 3:
            return None
        return bytes(out)

    def _text_confidence(self, bs: bytes) -> float:
        """Retorna confiança [0..1] de que os bytes são texto (não tiles/dados)."""
        if not bs:
            return 0.0

        good = 0
        bad = 0
        for b in bs:
            if b in self._PRINTABLE or b in self._ALLOWED_EXTRA:
                good += 1
            else:
                bad += 1

        total = good + bad
        if total == 0:
            return 0.0

        score = good / total

        # Penaliza strings com pouquíssimos chars únicos (AAAAAA, /////)
        uniq = len(set(bs))
        if len(bs) >= 6 and uniq <= 2:
            score -= 0.20

        # Penaliza excesso de símbolos
        symbols = set(b"!@#$%^&*()_+-=[]{}|;:'\",.<>?/\\`~")
        sym_count = sum(1 for b in bs if b in symbols)
        if len(bs) > 0 and (sym_count / len(bs)) > 0.45:
            score -= 0.15

        if score < 0.0:
            score = 0.0
        if score > 1.0:
            score = 1.0
        return score

    def _looks_like_real_text(self, bs: bytes, min_conf: float = 0.86) -> bool:
        """Filtro final: barra KOYQ/jtkem e outras strings fake."""
        conf = self._text_confidence(bs)
        if conf < min_conf:
            return False

        try:
            s = bs.decode("ascii", errors="ignore").strip()
        except Exception:
            return False

        if len(s) < 3:
            return False

        # Strings curtinhas: exige mais letras
        if len(s) <= 6:
            letters = sum(1 for c in s if c.isalpha())
            if letters < len(s) * 0.75:
                return False

        return True

    def extract_sms_by_pointers(self, min_length: int = 3) -> List[Dict]:
        """
        V6 PRO: Extração por ponteiros (SMS), reduzindo ruído.
        Estratégia:
        1) acha amostras de texto real para inferir a base (0x8000/0x4000/0x0000)
        2) varre u16 LE na ROM e tenta resolver para offsets dentro do bank 16KB
        3) valida string por terminador + confiança
        """
        rom = bytes(self.rom_data)
        bank_size = int(self.config.get('bank_size', 0x4000))

        # Import seguro (projeto pode rodar como pacote ou script)
        try:
            from core.retro8_bank_tools import detect_sms_pointer_base
        except Exception:
            try:
                from retro8_bank_tools import detect_sms_pointer_base
            except Exception:
                detect_sms_pointer_base = None

        # 1) detectar candidatos reais (pra inferir base)
        candidates = []
        scan_limit = min(len(rom), 0x200000)
        for off in range(0, scan_limit - 16):
            bs = self._read_c_string(rom, off)
            if not bs or len(bs) < min_length:
                continue
            if self._looks_like_real_text(bs):
                candidates.append(off)
                if len(candidates) >= 200:
                    break

        if not candidates:
            return []

        base = detect_sms_pointer_base(rom, candidates, bank_size=bank_size) if detect_sms_pointer_base else 0x8000

        # 2) varrer ponteiros e validar alvo
        out: List[Dict] = []
        seen_offsets = set()

        for ptr_off in range(0, len(rom) - 2):
            addr = self._u16_le(rom, ptr_off)
            within = (addr - base) & 0xFFFF

            # PRO: exige que caiba no bank
            if within >= bank_size:
                continue

            # Heurística conservadora: string no mesmo bank do ponteiro
            bank_start = (ptr_off // bank_size) * bank_size
            str_off = bank_start + within

            if str_off < 0 or str_off >= len(rom) - 4:
                continue

            bs = self._read_c_string(rom, str_off)
            if not bs or len(bs) < min_length:
                continue

            if not self._looks_like_real_text(bs):
                continue

            if str_off in seen_offsets:
                continue
            seen_offsets.add(str_off)

            txt = bs.decode("ascii", errors="ignore")
            conf = self._text_confidence(bs)

            # Passa também pelo seu filtro final de “texto de jogo”
            if not self._is_valid_game_text(txt):
                # Se confiança for MUITO alta, ainda deixa passar (créditos às vezes fogem do padrão)
                if conf < 0.93:
                    continue
            # ✅ PRO: corta ruído típico (PTVX/RTVX/@BDFH/bdf) antes do anti-overlap
            t = txt.strip()

            # 1) muito curto = quase sempre lixo
            if len(t) <= 4:
                continue

            # 2) se começa com @, geralmente é tabela de fonte / lixo
            if t.startswith('@'):
                continue

            # 3) se for só letras sem vogais (PTVX, RTVX, BDFH)
            vowels = set('aeiouAEIOU')
            letters_only = ''.join(c for c in t if c.isalpha())
            if len(letters_only) >= 3 and not any(c in vowels for c in letters_only):
                continue

            # 4) se for “quase tudo maiúsculo” e curto, geralmente lixo
            if len(t) <= 6:
                upp = sum(1 for c in t if c.isupper())
                if upp / len(t) >= 0.85:
                    continue

            # Anti-overlap PRO: evita strings "deslizantes" (eveloped/veloped/eloped...)
            # Se a string nova começa dentro de uma string já aceita, ignora.
            overlap = False
            for it in out:
                prev_start = it["offset"]
                prev_end = prev_start + max(1, it.get("length", 0))
                if prev_start <= str_off < prev_end:
                    overlap = True
                    break
            if overlap:
                continue

            out.append({
                "offset": str_off,
                "offset_hex": hex(str_off),
                "text": txt,
                "length": len(txt),
                "confidence": round(conf, 3),
            })

        out.sort(key=lambda x: x["offset"])
        return out

    # =====================================================================
    # Extração principal (mantém sua lógica, adiciona o PRO SMS)
    # =====================================================================

    def extract_texts(self, min_length: int = 4) -> List[Dict]:
        """
        Extrai textos ASCII da ROM com 4 filtros restritivos

        Args:
            min_length: Tamanho mínimo da string

        Returns:
            Lista de dicts com offset e texto
        """
        # -------------------------
        # V6 PRO: SMS por ponteiros
        # -------------------------
        if self.platform == 'MASTER_SYSTEM':
            print("🧠 Extração PRO baseada em ponteiros ativada")
            pro_texts = self.extract_sms_by_pointers(min_length=max(3, min_length))

            if len(pro_texts) > 0:
                # Remove duplicatas exatas
                unique_texts = []
                seen = set()
                for item in pro_texts:
                    if item['text'] not in seen:
                        seen.add(item['text'])
                        unique_texts.append(item)

                avg_conf = sum(t.get("confidence", 0.0) for t in unique_texts) / max(1, len(unique_texts))

                print(f"✅ SMS PRO: {len(unique_texts)} strings válidas por ponteiros | Confiança média: {avg_conf:.3f}\n")
                return unique_texts

            print("⚠️ SMS PRO: ponteiros não detectados com segurança. Fallback para varredura ASCII com filtro de confiança.\n")

        # -------------------------
        # V5: varredura ASCII (Genesis/SMD e fallback SMS)
        # -------------------------
        texts = []
        current_text = bytearray()
        text_start = None

        # Stats detalhados
        total_extracted = 0
        filtered_sequence = 0    # Filtro 1: Sequências alfabéticas
        filtered_symbols = 0     # Filtro 2: Repetição de símbolos
        filtered_vowels = 0      # Filtro 3: Sem vogais
        filtered_caps = 0        # Filtro 4: Capitalização estranha
        filtered_other = 0       # Outros filtros
        filtered_confidence = 0  # PRO: confiança baixa

        for offset in range(len(self.rom_data)):
            byte = self.rom_data[offset]

            # ASCII printable (0x20-0x7E)
            if 0x20 <= byte <= 0x7E:
                if text_start is None:
                    text_start = offset
                current_text.append(byte)
            else:
                # Fim da string
                if len(current_text) >= min_length:
                    try:
                        decoded = current_text.decode('ascii')
                        total_extracted += 1

                        # PRO filtro: confiança antes de tudo
                        if not self._looks_like_real_text(current_text, min_conf=0.88):
                            filtered_confidence += 1

                        # Aplica os 4 filtros restritivos em ordem
                        elif self._is_alphabet_sequence(decoded):
                            filtered_sequence += 1
                        elif self._has_symbol_repetition(decoded):
                            filtered_symbols += 1
                        elif self._lacks_vowels(decoded):
                            filtered_vowels += 1
                        elif self._has_weird_capitalization(decoded):
                            filtered_caps += 1
                        elif not self._is_valid_game_text(decoded):
                            filtered_other += 1
                        else:
                            # Texto válido - passou em todos os filtros!
                            texts.append({
                                'offset': text_start,
                                'offset_hex': hex(text_start),
                                'text': decoded,
                                'length': len(decoded),
                                'confidence': round(self._text_confidence(current_text), 3),
                            })
                    except UnicodeDecodeError:
                        pass

                # Reset
                current_text = bytearray()
                text_start = None

        # Remove duplicatas exatas
        unique_texts = []
        seen = set()
        for item in texts:
            if item['text'] not in seen:
                seen.add(item['text'])
                unique_texts.append(item)

        # Stats
        total_garbage = filtered_sequence + filtered_symbols + filtered_vowels + filtered_caps + filtered_other + filtered_confidence

        print(f"\n{'='*70}")
        print(f"🎮 {self.config['name']}")
        print(f"{'='*70}")
        print(f"📊 Strings brutas encontradas: {total_extracted:,}")
        print(f"🗑️  Lixo binário removido: {total_garbage:,}")
        print(f"   • Confiança baixa (PRO): {filtered_confidence:,}")
        print(f"   • Sequências alfabéticas (fontes): {filtered_sequence:,}")
        print(f"   • Repetição de símbolos (tiles): {filtered_symbols:,}")
        print(f"   • Sem vogais (consoantes): {filtered_vowels:,}")
        print(f"   • Capitalização estranha: {filtered_caps:,}")
        print(f"   • Outros filtros: {filtered_other:,}")
        print(f"✅ Textos de jogo válidos: {len(unique_texts):,}")
        print(f"📈 Taxa de limpeza: {(total_garbage/total_extracted*100) if total_extracted > 0 else 0:.1f}%")
        print(f"{'='*70}\n")

        return unique_texts

    # =====================================================================
    # Seus filtros originais (mantidos)
    # =====================================================================

    def _is_alphabet_sequence(self, text: str) -> bool:
        """
        FILTRO 1: Sequências alfabéticas/numéricas (definições de fonte)
        Remove: 'abcdefg', 'ABCDEFGH', '0123456', 'ghijklmn', etc.
        """
        text_lower = text.lower()

        alphabet = 'abcdefghijklmnopqrstuvwxyz'
        for i in range(len(alphabet) - 3):
            seq = alphabet[i:i+4]
            if seq in text_lower:
                return True

        numbers = '0123456789'
        for i in range(len(numbers) - 3):
            seq = numbers[i:i+4]
            if seq in text:
                return True

        return False

    def _has_symbol_repetition(self, text: str) -> bool:
        """
        FILTRO 2: Entropia simbólica (gradientes de tiles)
        Remove: '((<<<PPPP', '!!!!', '@@@', etc.
        """
        symbols = set('!@#$%^&*()_+-=[]{}|;:\'",.<>?/\\`~')
        symbol_count = sum(1 for c in text if c in symbols)

        if len(text) > 0 and symbol_count / len(text) > 0.4:
            return True

        prev_char = ''
        repeat_count = 0
        for char in text:
            if char == prev_char:
                repeat_count += 1
                if repeat_count >= 3:
                    return True
            else:
                repeat_count = 1
                prev_char = char

        return False

    def _lacks_vowels(self, text: str) -> bool:
        """
        FILTRO 3: Legibilidade humana (precisa de vogais)
        Remove: 'ptvx', 'RTVX', 'bdf', 'DPDb4C7' etc.
        Mantém: palavras com pelo menos 1 vogal
        """
        vowels = set('aeiouAEIOU')
        letters_only = ''.join(c for c in text if c.isalpha())

        if len(letters_only) >= 3:
            vowel_count = sum(1 for c in letters_only if c in vowels)
            if vowel_count == 0:
                return True

            vowel_ratio = vowel_count / len(letters_only)
            if vowel_ratio < 0.10:
                return True

        return False

    def _has_weird_capitalization(self, text: str) -> bool:
        """
        FILTRO 4: Capitalização estranha (mistura símbolos+letras sem sentido)
        Remove: '@BDFH', 'V98?:', '5b@7FD', 'FbDDQ', etc.
        """
        if '@' in text:
            letters_after_at = sum(
                1 for i, c in enumerate(text)
                if c == '@' and i+1 < len(text) and text[i+1].isupper()
            )
            if letters_after_at > 0:
                return True

        hex_chars = set('0123456789ABCDEFabcdef')
        if len(text) >= 4:
            hex_count = sum(1 for c in text if c in hex_chars)
            if hex_count == len(text):
                vowels = set('aeiouAEIOU')
                if not any(c in vowels for c in text):
                    return True

        weird_pattern = 0
        for i in range(len(text) - 2):
            if text[i].isupper() and text[i+1].islower() and text[i+2].isupper():
                weird_pattern += 1
        if weird_pattern >= 2:
            return True

        return False

    def _is_valid_game_text(self, text: str) -> bool:
        """
        Validação final RESTRITIVA: texto que um jogador veria na tela
        (Créditos, Menus, Nome das Zonas, Diálogos)
        """
        text = text.strip()

        if len(text) < 3:
            return False

        if len(text) <= 5:
            letters = sum(1 for c in text if c.isalpha())
            if letters < len(text) * 0.8:
                return False

        if text[0].isdigit() or text[0] in '!@#$%^&*()_+-=[]{}|;:\'",.<>?/\\`~':
            if not text.replace('-', '').replace(' ', '').isdigit():
                return False

        letters = sum(1 for c in text if c.isalpha())
        if len(text) > 0 and letters / len(text) < 0.6:
            return False

        import re
        if re.search(r'\d[A-Za-z]|[A-Za-z]\d', text):
            valid_patterns = ['zone', 'act', 'level', 'stage', 'world', 'up', 'player']
            text_lower = text.lower()
            if not any(p in text_lower for p in valid_patterns):
                if not re.match(r'^(19|20)\d{2}$', text) and not text.replace(',', '').isdigit():
                    return False

        vowels = set('aeiouAEIOU')
        vowel_count = sum(1 for c in text if c in vowels)
        if len(text) >= 6 and vowel_count < 2:
            return False

        if text.startswith(('?', '!', ',', '.', ';', ':')) and len(text) < 10:
            return False

        return True

    def save_texts(self, texts: List[Dict], output_path: Optional[str] = None) -> str:
        """
        Salva textos extraídos em arquivo
        """
        if output_path is None:
            output_path = self.rom_path.parent / f"{self.rom_path.stem}_extracted_sega.txt"
        else:
            output_path = Path(output_path)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("# NeuroROM AI - Sega Text Extraction\n")
            f.write("# " + "="*68 + "\n")
            f.write(f"# Platform: {self.config['name']}\n")
            f.write(f"# ROM: {self.rom_path.name}\n")
            f.write(f"# Total strings: {len(texts)}\n")
            f.write(f"# Encoding: ASCII (0x20-0x7E)\n")
            f.write(f"# Endian: {self.config['endian']}\n")
            f.write("#\n")
            f.write("# Format: [offset_hex] text\n")
            f.write("# " + "="*68 + "\n\n")

            for item in texts:
                f.write(f"[{item['offset_hex']}] {item['text']}\n")

        print(f"💾 Arquivo salvo: {output_path}\n")
        return str(output_path)

    def extract_and_save(self, output_path: Optional[str] = None, min_length: int = 4) -> Tuple[List[Dict], str]:
        """
        Extrai e salva textos em uma única operação
        """
        texts = self.extract_texts(min_length=min_length)
        saved_path = self.save_texts(texts, output_path)
        return texts, saved_path


def main():
    """CLI Interface"""
    import sys

    print("="*70)
    print("  NeuroROM AI - Sega Text Extractor")
    print("  Master System + Mega Drive/Genesis")
    print("="*70)
    print()

    if len(sys.argv) < 2:
        print("Uso:")
        print(f"  python {Path(__file__).name} <rom_file> [output.txt]")
        print()
        print("Exemplos:")
        print(f"  python {Path(__file__).name} sonic.gen")
        print(f"  python {Path(__file__).name} alex_kidd.sms custom_output.txt")
        print()
        sys.exit(1)

    rom_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None

    try:
        extractor = SegaExtractor(rom_path)
        texts, saved_path = extractor.extract_and_save(output_path)

        print(f"✅ Extração concluída!")
        print(f"📊 {len(texts)} strings extraídas")
        print(f"💾 Arquivo: {saved_path}")

    except Exception as e:
        print(f"❌ ERRO: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
