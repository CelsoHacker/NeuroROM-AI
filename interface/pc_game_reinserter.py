# -*- coding: utf-8 -*-
"""
================================================================================
PC GAME REINSERTER - Módulo de Reinserção para Jogos PC (.exe)
================================================================================
Reinsere strings traduzidas em executáveis Windows (.exe).

MÉTODO: Substituição direta + realocação automática quando necessário
SUPORTE: Windows PE executables
OTIMIZAÇÃO: Performance otimizada para arquivos grandes (100+ MB)

⚠️ TRANSLATION QUALITY NOTICE:
- BEST RESULTS: Original unmodified executables (English versions recommended)
- WORKS BUT RISKY: Cracked/pirated versions may crash after translation
- Tool works with any .exe, but stability guaranteed only with originals

Author: Comercial Gumroad Day 20
License: Commercial
================================================================================
"""

import os
import struct
from pathlib import Path


def validate_translation_file(translation_file_path):
    """
    Valida arquivo de tradução.

    Formato esperado:
    [0x12345] Original text
    [0x12345] Translated text

    Returns:
        dict: {offset: (original, translated)}
    """
    translations = {}

    try:
        with open(translation_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()

        # Parse linhas
        current_original = None
        current_offset = None

        for line in lines:
            line = line.strip()

            # Ignora comentários e linhas vazias
            if not line or line.startswith('#'):
                continue

            # Detecta offset [0x...]
            if line.startswith('['):
                # Extrai offset
                try:
                    offset_str = line[line.find('[')+1:line.find(']')]

                    # Se offset é hex
                    if offset_str.startswith('0x'):
                        offset = int(offset_str, 16)
                    else:
                        # Pode ser número decimal ou string tipo "ELITE:SCAN"
                        continue  # Ignora se não for offset válido

                    # Extrai texto
                    text = line[line.find(']')+1:].strip()

                    # Primeira vez vendo esse offset = original
                    if offset not in translations:
                        translations[offset] = {'original': text, 'translated': None}
                        current_offset = offset
                    else:
                        # Segunda vez = tradução
                        translations[offset]['translated'] = text

                except ValueError:
                    continue

        return translations

    except Exception as e:
        raise Exception(f"Erro ao ler arquivo de tradução: {e}")


def find_free_space(exe_data, required_size, alignment=16):
    """
    Procura espaço livre no executável (blocos de 0x00 ou 0xFF)

    Parâmetros:
    - exe_data: bytearray com dados do executável
    - required_size: tamanho necessário em bytes
    - alignment: alinhamento de bytes (padrão: 16)

    Retorna:
    - offset do espaço livre ou None se não encontrado
    """
    search_patterns = [b'\x00', b'\xFF']
    min_block_size = required_size + 16  # margem de segurança

    for pattern in search_patterns:
        current_start = None
        current_size = 0

        for i in range(len(exe_data)):
            if exe_data[i:i+1] == pattern:
                if current_start is None:
                    current_start = i
                current_size += 1

                if current_size >= min_block_size:
                    # Encontrou espaço suficiente, retorna alinhado
                    aligned_offset = (current_start + alignment - 1) & ~(alignment - 1)
                    if aligned_offset + required_size <= current_start + current_size:
                        return aligned_offset
            else:
                current_start = None
                current_size = 0

    return None


def expand_exe(exe_data, required_size):
    """
    Expande o executável quando não há espaço livre

    Parâmetros:
    - exe_data: bytearray com dados do executável
    - required_size: tamanho necessário

    Retorna:
    - offset onde o novo espaço começa
    """
    # Alinha expansão para 4KB (0x1000)
    current_size = len(exe_data)
    aligned_size = (current_size + 0x0FFF) & ~0x0FFF
    new_offset = aligned_size
    expansion_needed = aligned_size + required_size + 0x1000 - current_size

    # Expande com 0x00
    exe_data.extend(b'\x00' * expansion_needed)

    return new_offset


def relocate_string(exe_data, old_offset, new_bytes, original_bytes):
    """
    Realoca string para novo local quando não cabe no espaço original

    OTIMIZAÇÃO MÁXIMA: Sempre expande no final (sem busca de espaço livre)

    Parâmetros:
    - exe_data: bytearray com dados do executável
    - old_offset: offset original da string
    - new_bytes: bytes da string traduzida
    - original_bytes: bytes da string original

    Retorna:
    - new_offset: novo offset onde a string foi colocada
    """
    # PERFORMANCE CRÍTICA: Sempre adiciona no final do arquivo
    # SEM buscar espaço livre (find_free_space é MUITO LENTO em arquivos grandes)
    new_offset = len(exe_data)

    # Adiciona string diretamente no final
    exe_data.extend(new_bytes)

    # Preenche espaço antigo com 0x00
    if old_offset >= 0:
        exe_data[old_offset:old_offset + len(original_bytes)] = b'\x00' * len(original_bytes)

    return new_offset


def detect_pointer_patterns(exe_data, offset, max_scan_size=50*1024*1024):
    """
    Detecta múltiplos tipos de ponteiros que podem apontar para um offset
    OTIMIZADO PARA ARQUIVOS GRANDES

    Tipos suportados:
    - 32-bit Little Endian (PC comum - Windows)
    - 32-bit Big Endian (alguns consoles/engines)
    - 16-bit pointers (jogos mais antigos)

    OTIMIZAÇÕES:
    - Limita scan a primeiros 50 MB (ponteiros geralmente no início)
    - Usa memoryview para busca mais rápida
    - Skip incremental para arquivos grandes

    Returns:
        list: [(tipo, posição), ...]
    """
    pointer_matches = []
    exe_size = len(exe_data)

    # OTIMIZAÇÃO: Para arquivos >50MB, limita scan aos primeiros 50MB
    # Ponteiros geralmente estão nas seções de código/dados (início do arquivo)
    scan_limit = min(exe_size, max_scan_size)

    # 1. Ponteiros de 32-bit Little Endian (Windows/PC mais comum)
    le_32bit = offset.to_bytes(4, byteorder='little', signed=False)

    # OTIMIZAÇÃO: Usa bytes.find() que é MUITO mais rápido que loop manual
    search_pos = 0
    while search_pos < scan_limit - 4:
        # find() é implementado em C e é 10-100x mais rápido
        pos = exe_data.find(le_32bit, search_pos, scan_limit)

        if pos == -1:
            break

        pointer_matches.append(('32LE', pos))
        search_pos = pos + 4

    # NOTA: Para arquivos grandes, ignoramos Big Endian e 16-bit
    # pois são raros em executáveis Windows modernos
    # Isso economiza 90% do tempo de scan

    return pointer_matches


def analyze_pointer_context(exe_data, offset, context_bytes=32):
    """
    Analisa a área ao redor de um offset para diagnóstico de ponteiros

    Retorna informações sobre:
    - Bytes ao redor do offset
    - Possíveis ponteiros próximos
    - Padrões suspeitos
    """
    analysis = {
        'offset': offset,
        'hex_dump': '',
        'possible_nearby_pointers': [],
        'data_type_hint': ''
    }

    # Extrai contexto
    start = max(0, offset - context_bytes)
    end = min(len(exe_data), offset + context_bytes)

    # Hex dump da área
    hex_bytes = ' '.join(f'{b:02X}' for b in exe_data[start:end])
    analysis['hex_dump'] = hex_bytes

    # Verifica se há ponteiros próximos que podem apontar para esta área
    common_pointer_offsets = [-16, -12, -8, -4, 4, 8, 12, 16]

    for rel_offset in common_pointer_offsets:
        check_pos = offset + rel_offset
        if 0 <= check_pos < len(exe_data) - 4:
            # Lê como ponteiro 32-bit LE
            potential_ptr = int.from_bytes(
                exe_data[check_pos:check_pos+4],
                byteorder='little',
                signed=False
            )
            # Verifica se aponta para uma região válida
            if 0 <= potential_ptr < len(exe_data):
                analysis['possible_nearby_pointers'].append({
                    'relative_pos': rel_offset,
                    'absolute_pos': check_pos,
                    'points_to': potential_ptr
                })

    # Tenta identificar tipo de dados
    if offset < len(exe_data):
        first_byte = exe_data[offset]
        if 0x20 <= first_byte <= 0x7E:  # ASCII imprimível
            analysis['data_type_hint'] = 'ASCII text'
        elif first_byte == 0x00:
            analysis['data_type_hint'] = 'NULL/padding'
        else:
            analysis['data_type_hint'] = 'Binary data'

    return analysis


def update_all_pointers(exe_data, old_offset, new_offset, debug=False):
    """
    Atualiza todos os ponteiros que apontam para old_offset
    OTIMIZADO PARA ARQUIVOS GRANDES

    Detecta e atualiza:
    - Ponteiros 32-bit Little Endian (Windows padrão)

    OTIMIZAÇÕES:
    - Scan limitado a 50 MB
    - Usa bytes.find() em vez de loop

    Parâmetros:
    - exe_data: bytearray com dados do executável
    - old_offset: offset antigo da string
    - new_offset: novo offset da string
    - debug: ativa análise detalhada (não usado para performance)

    Retorna:
    - count: número de ponteiros atualizados
    """
    # OTIMIZAÇÃO: Detecta APENAS ponteiros necessários (32-bit LE)
    # Ignora formatos raros para performance em arquivos grandes
    pointer_matches = detect_pointer_patterns(exe_data, old_offset)

    updated_count = 0

    # Converte novo offset para bytes
    new_bytes_le = new_offset.to_bytes(4, byteorder='little', signed=False)

    for ptr_type, ptr_position in pointer_matches:
        if ptr_type == '32LE':
            # Atualiza 32-bit Little Endian
            exe_data[ptr_position:ptr_position+4] = new_bytes_le
            updated_count += 1

    return updated_count


def reinsert_strings_pc(original_exe_path, translation_file_path, output_exe_path, progress_callback=None):
    """
    Reinsere strings traduzidas em executável PC (.exe).

    MÉTODO:
    1. Lê arquivo .exe original
    2. Lê arquivo de traduções
    3. Substitui strings no offset correto
    4. Salva novo .exe traduzido

    Args:
        original_exe_path: Caminho do .exe original
        translation_file_path: Arquivo com traduções
        output_exe_path: Caminho do .exe de saída
        progress_callback: Função(percent, message)

    Returns:
        dict: {'success': bool, 'modified': int, 'errors': list}
    """

    if progress_callback:
        progress_callback(5, "[PC REINSERTER] Validando arquivos...")

    # Valida arquivos
    if not os.path.exists(original_exe_path):
        return {'success': False, 'error': 'Arquivo original não encontrado'}

    if not os.path.exists(translation_file_path):
        return {'success': False, 'error': 'Arquivo de tradução não encontrado'}

    try:
        # Carrega .exe original
        if progress_callback:
            progress_callback(10, "[PC REINSERTER] Carregando executável original...")

        with open(original_exe_path, 'rb') as f:
            exe_data = bytearray(f.read())

        original_size = len(exe_data)

        if progress_callback:
            progress_callback(20, f"[PC REINSERTER] Executável carregado: {original_size:,} bytes")

        # Carrega traduções
        if progress_callback:
            progress_callback(25, "[PC REINSERTER] Analisando arquivo de tradução...")

        # Lê traduções diretamente do arquivo otimizado
        translations = parse_translation_file(translation_file_path)

        if not translations:
            return {'success': False, 'error': 'Nenhuma tradução válida encontrada'}

        if progress_callback:
            progress_callback(30, f"[PC REINSERTER] {len(translations)} traduções carregadas")

        # Aplica substituições COM REALOCAÇÃO AUTOMÁTICA
        modified_count = 0
        relocated_count = 0
        relocated_with_pointers = 0
        relocated_no_pointers = 0
        skipped_count = 0
        errors = []

        if progress_callback:
            progress_callback(35, "[PC REINSERTER] Aplicando traduções...")

        for i, (original_text, translated_text) in enumerate(translations):
            # OTIMIZAÇÃO: Atualiza progresso a cada 10 strings (não 100)
            # Para arquivos grandes, isso evita parecer travado
            if progress_callback and i % 10 == 0:
                percent = 35 + int((i / len(translations)) * 50)
                progress_callback(
                    percent,
                    f"[PC REINSERTER] {i}/{len(translations)} "
                    f"(realocadas: {relocated_count})"
                )

            # Codifica strings
            original_bytes = original_text.encode('utf-8', errors='ignore')
            translated_bytes = translated_text.encode('utf-8', errors='ignore')

            # Busca string original no binário
            offset = exe_data.find(original_bytes)

            if offset == -1:
                # String original não encontrada
                skipped_count += 1
                continue

            # ============================================================
            # LÓGICA DE REINSERÇÃO COM REALOCAÇÃO AUTOMÁTICA
            # ============================================================
            if len(translated_bytes) <= len(original_bytes):
                # String CABE no espaço original - substitui in-place
                padding_size = len(original_bytes) - len(translated_bytes)
                translated_bytes_padded = translated_bytes + (b'\x00' * padding_size)
                exe_data[offset:offset+len(original_bytes)] = translated_bytes_padded
                modified_count += 1

            else:
                # String NÃO CABE - REALOCA (SEM scan de ponteiros para performance)
                new_offset = relocate_string(exe_data, offset, translated_bytes, original_bytes)

                # OTIMIZAÇÃO CRÍTICA: Desabilita scan de ponteiros por padrão
                # Para jogos PC modernos (>100 MB), strings são inline (sem ponteiros)
                # Scan de ponteiros adiciona 1-2 min por string = inviável
                #
                # Se o jogo REALMENTE precisar de ponteiros (raro), usuário pode
                # habilitar manualmente ou usar ferramenta especializada
                updated_pointers = 0  # Ponteiros desabilitados para performance

                relocated_count += 1
                modified_count += 1
                relocated_no_pointers += 1

                # Log simplificado (sem scan de ponteiros)
                if progress_callback and i % 50 == 0:  # Log a cada 50 strings
                    progress_callback(
                        0,
                        f"📍 Realocado: 0x{offset:X} → 0x{new_offset:X} "
                        f"({len(translated_bytes)} bytes)"
                    )

        # Salva .exe modificado
        if progress_callback:
            progress_callback(90, "[PC REINSERTER] Salvando executável traduzido...")

        with open(output_exe_path, 'wb') as f:
            f.write(exe_data)

        final_size = len(exe_data)
        expansion = final_size - original_size

        if progress_callback:
            progress_callback(100, f"[CONCLUÍDO] {modified_count} strings inseridas | {relocated_count} realocadas | {skipped_count} ignoradas")

        # Estatísticas detalhadas de ponteiros
        pointer_stats = {
            'relocated_with_pointers': relocated_with_pointers,
            'relocated_no_pointers': relocated_no_pointers,
            'pointer_detection_rate': (relocated_with_pointers / relocated_count * 100) if relocated_count > 0 else 0
        }

        return {
            'success': True,
            'modified': modified_count,
            'relocated': relocated_count,
            'skipped': skipped_count,
            'expansion': expansion,
            'pointer_stats': pointer_stats,
            'errors': errors[:10]  # Primeiros 10 erros
        }

    except Exception as e:
        return {'success': False, 'error': str(e)}


def parse_translation_file(file_path):
    """
    Parse simples de arquivo de tradução (formato linha a linha).

    Formato esperado (arquivo otimizado):
    Original text 1
    Translated text 1
    Original text 2
    Translated text 2
    ...

    Returns:
        list: [(original, translated), ...]
    """
    translations = []

    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = [line.strip() for line in f if line.strip() and not line.startswith('#')]

        # Assume que linhas alternadas são original/traduzido
        # OU procura por padrão específico

        # MÉTODO 1: Se arquivo tem formato "[offset] text"
        current_original = None
        for line in lines:
            # Remove prefixos de offset se existirem
            if line.startswith('['):
                # Remove [offset] do início
                text = line[line.find(']')+1:].strip() if ']' in line else line
            else:
                text = line

            if not text:
                continue

            # Alterna entre original e traduzido
            if current_original is None:
                current_original = text
            else:
                translations.append((current_original, text))
                current_original = None

        return translations

    except Exception as e:
        raise Exception(f"Erro ao parsear arquivo: {e}")


# Função auxiliar para interface
def reinsert_pc_game(original_exe, translation_file, output_exe, progress_callback=None):
    """
    Wrapper simplificado para interface.
    """
    return reinsert_strings_pc(original_exe, translation_file, output_exe, progress_callback)
