# -*- coding: utf-8 -*-
import os
import json
import shutil
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QTextEdit, QFileDialog,
    QMessageBox, QProgressBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

CONSOLE_PROFILES = {
    'SNES_SMC': {'header_offset': 0x200, 'pointer_bytes': 3, 'endian': 'little'},
    'SNES_SFC': {'header_offset': 0x000, 'pointer_bytes': 3, 'endian': 'little'},
    'NES': {'header_offset': 0x010, 'pointer_bytes': 2, 'endian': 'little'},
    'GENESIS': {'header_offset': 0x000, 'pointer_bytes': 4, 'endian': 'big'},
    'GB': {'header_offset': 0x000, 'pointer_bytes': 2, 'endian': 'little'},
    'GBA': {'header_offset': 0x000, 'pointer_bytes': 4, 'endian': 'little'},
}

def rom_offset_to_pointer_bytes(rom_offset, pointer_format='SNES_LOROM', endian='little'):
    """
    Converte ROM offset para bytes de ponteiro com inversão de endianness.

    Exemplos:
    - SNES LoROM: 0x012345 -> [45 A3 80] (3 bytes little-endian com bank mapping)
    - NES: 0x1234 -> [34 12] (2 bytes little-endian)
    - Genesis: 0x12345678 -> [12 34 56 78] (4 bytes big-endian)
    """
    if pointer_format == 'SNES_LOROM':
        bank = (rom_offset >> 15) & 0x7F
        addr_in_bank = (rom_offset & 0x7FFF) | 0x8000
        snes_addr = (bank << 16) | addr_in_bank

        byte0 = snes_addr & 0xFF
        byte1 = (snes_addr >> 8) & 0xFF
        byte2 = (snes_addr >> 16) & 0xFF
        return bytes([byte0, byte1, byte2])

    elif pointer_format == 'NES':
        if endian == 'little':
            return bytes([rom_offset & 0xFF, (rom_offset >> 8) & 0xFF])
        else:
            return bytes([(rom_offset >> 8) & 0xFF, rom_offset & 0xFF])

    elif pointer_format == 'GENESIS':
        if endian == 'big':
            return bytes([
                (rom_offset >> 24) & 0xFF,
                (rom_offset >> 16) & 0xFF,
                (rom_offset >> 8) & 0xFF,
                rom_offset & 0xFF
            ])

    return bytes([rom_offset & 0xFF, (rom_offset >> 8) & 0xFF])

def pointer_bytes_to_rom_offset(byte_data, pointer_format='SNES_LOROM'):
    """Converte bytes de ponteiro para ROM offset (com tratamento de endianness)."""
    if pointer_format == 'SNES_LOROM':
        if len(byte_data) < 3:
            return None
        snes_addr = byte_data[0] | (byte_data[1] << 8) | (byte_data[2] << 16)
        bank = (snes_addr >> 16) & 0x7F
        addr_in_bank = snes_addr & 0xFFFF

        if 0x8000 <= addr_in_bank <= 0xFFFF:
            return (bank << 15) | (addr_in_bank & 0x7FFF)
        return None

    elif pointer_format == 'NES':
        if len(byte_data) < 2:
            return None
        return byte_data[0] | (byte_data[1] << 8)

    elif pointer_format == 'GENESIS':
        if len(byte_data) < 4:
            return None
        return (byte_data[0] << 24) | (byte_data[1] << 16) | (byte_data[2] << 8) | byte_data[3]

    return None

class ReinsertionWorker(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict)

    def __init__(self, rom_path, translation_data, pointer_offset, parent=None):
        super().__init__(parent)
        self.rom_path = rom_path
        self.translation_data = translation_data
        self.pointer_offset = pointer_offset

    def find_free_space(self, rom_data, required_size, alignment=16):
        """
        Procura espaço livre na ROM (blocos de 0x00 ou 0xFF)

        Parâmetros:
        - rom_data: bytearray com dados da ROM
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

            for i in range(len(rom_data)):
                if rom_data[i:i+1] == pattern:
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

    def relocate_string(self, rom_data, old_offset, new_bytes, original_bytes):
        """
        Realoca string para novo local quando não cabe no espaço original

        Parâmetros:
        - rom_data: bytearray com dados da ROM
        - old_offset: offset original da string
        - new_bytes: bytes da string traduzida
        - original_bytes: bytes da string original

        Retorna:
        - new_offset: novo offset onde a string foi colocada
        """
        required_size = len(new_bytes)

        # Tenta encontrar espaço livre existente
        new_offset = self.find_free_space(rom_data, required_size)

        if new_offset is None:
            # Não encontrou espaço livre, expande arquivo
            new_offset = self.expand_rom_advanced(rom_data, required_size)
            self.progress.emit(0, f"⚠️ ROM expandida: +{required_size} bytes")

        # Copia string para novo local
        rom_data[new_offset:new_offset + len(new_bytes)] = new_bytes

        # Preenche espaço antigo com 0x00
        rom_data[old_offset:old_offset + len(original_bytes)] = b'\x00' * len(original_bytes)

        return new_offset

    def expand_rom_advanced(self, rom_data, required_size):
        """
        Expande a ROM quando não há espaço livre (versão para PC games)

        Parâmetros:
        - rom_data: bytearray com dados da ROM
        - required_size: tamanho necessário

        Retorna:
        - offset onde o novo espaço começa
        """
        # Alinha expansão para 4KB (0x1000)
        current_size = len(rom_data)
        aligned_size = (current_size + 0x0FFF) & ~0x0FFF
        new_offset = aligned_size
        expansion_needed = aligned_size + required_size + 0x1000 - current_size

        # Expande com 0x00
        rom_data.extend(b'\x00' * expansion_needed)

        return new_offset

    def update_all_pointers(self, rom_data, old_offset, new_offset):
        """
        Atualiza todos os ponteiros que apontam para old_offset

        Parâmetros:
        - rom_data: bytearray com dados da ROM
        - old_offset: offset antigo da string
        - new_offset: novo offset da string

        Retorna:
        - count: número de ponteiros atualizados
        """
        updated_count = 0

        # PC executables: ponteiros de 32-bit little-endian
        pointer_size = 4
        old_pointer_bytes = old_offset.to_bytes(pointer_size, byteorder='little')
        new_pointer_bytes = new_offset.to_bytes(pointer_size, byteorder='little')

        # Busca e substitui todos os ponteiros
        search_offset = 0
        while search_offset < len(rom_data) - pointer_size:
            if rom_data[search_offset:search_offset + pointer_size] == old_pointer_bytes:
                rom_data[search_offset:search_offset + pointer_size] = new_pointer_bytes
                updated_count += 1
                search_offset += pointer_size
            else:
                search_offset += 1

        return updated_count

    def run(self):
        """
        Processo de Reinserção - ENGINE RETRO-A v2.0 com Realocação Automática
        Baseado no Manual de ROM Hacking (Capítulos II e IV)

        FLUXO COMPLETO:
        ================
        1. BACKUP: Copia ROM original
        2. CARREGA: Lê ROM em memória (bytearray mutável)
        3. ITERA: Processa cada entrada traduzida
        4. DECIDE:
           a) Tradução cabe no espaço original?
              -> SIM: Substitui in-place + padding 0x00
              -> NÃO: REALOCAÇÃO AUTOMÁTICA + ATUALIZAÇÃO DE PONTEIROS
        5. REALOCAÇÃO (quando necessário):
           - Busca espaço livre na ROM (blocos 0x00 ou 0xFF)
           - Se não encontrar, expande ROM em blocos de 0x1000 (4KB)
           - Grava texto no novo offset
           - Atualiza TODOS os ponteiros que apontam para o offset antigo
           - Limpa offset antigo com 0x00
        6. SALVA: Grava ROM traduzida (*_TRANSLATED.smc)
        """
        try:
            backup_path = self.rom_path.replace('.smc', '_BACKUP.smc')
            if not os.path.exists(backup_path):
                shutil.copy(self.rom_path, backup_path)
                self.progress.emit(5, f"✅ Backup: {os.path.basename(backup_path)}")

            with open(self.rom_path, 'rb') as f:
                rom_data = bytearray(f.read())

            original_size = len(rom_data)
            self.progress.emit(10, f"ROM: {original_size:,} bytes")

            char_table = self.build_char_table_inverse()

            repointed_count = 0
            relocated_count = 0
            modified_count = 0
            skipped_count = 0
            total = len(self.translation_data)

            for i, entry in enumerate(self.translation_data):
                if i % 10 == 0:
                    percent = 10 + int(i / total * 80)
                    self.progress.emit(percent, f"Processando {i+1}/{total} (realocados: {relocated_count})...")

                translated = entry.get('translated', '').strip()
                if not translated:
                    skipped_count += 1
                    continue

                new_bytes = self.encode_string(translated, char_table)
                original_offset = entry['rom_offset']

                original_text = entry['original']
                original_bytes = self.encode_string(original_text, char_table)

                # ============================================================
                # LÓGICA DE REINSERÇÃO COM REALOCAÇÃO AUTOMÁTICA
                # ============================================================
                if len(new_bytes) <= len(original_bytes):
                    # String cabe no espaço original - substitui in-place
                    rom_data[original_offset:original_offset + len(new_bytes)] = new_bytes
                    padding = len(original_bytes) - len(new_bytes)
                    if padding > 0:
                        rom_data[original_offset + len(new_bytes):original_offset + len(original_bytes)] = b'\x00' * padding

                    modified_count += 1

                else:
                    # String NÃO cabe - REALOCA + ATUALIZA PONTEIROS
                    new_offset = self.relocate_string(rom_data, original_offset, new_bytes, original_bytes)
                    updated_pointers = self.update_all_pointers(rom_data, original_offset, new_offset)

                    relocated_count += 1
                    modified_count += 1

                    # Log de realocação
                    self.progress.emit(
                        0,
                        f"📍 Realocado: 0x{original_offset:X} → 0x{new_offset:X} "
                        f"({len(new_bytes)} bytes, {updated_pointers} ponteiros atualizados)"
                    )

                    # FALLBACK: Se tiver pointer_index, atualiza também pela tabela
                    if 'pointer_index' in entry and self.pointer_offset is not None:
                        self.update_pointer(rom_data, self.pointer_offset + (entry['pointer_index'] * 3), new_offset)
                        repointed_count += 1

            # ============================================================
            # ✅ KERNEL V 9.5: CHECKSUM FIXER (LACRE DE COMPATIBILIDADE)
            # ============================================================
            # CRÍTICO: Hardware SNES real exige checksum válido
            # Sem isso, flashcarts e consoles reais podem travar
            self.progress.emit(95, "🔐 Recalculando checksum SNES...")
            self.fix_snes_checksum(rom_data)

            output_path = self.rom_path.replace('.smc', '_TRANSLATED.smc')
            with open(output_path, 'wb') as f:
                f.write(rom_data)

            final_size = len(rom_data)
            expansion = final_size - original_size

            self.progress.emit(100, "✅ Concluído!")

            self.finished.emit({
                'success': True,
                'output_path': output_path,
                'original_size': original_size,
                'final_size': final_size,
                'expansion': expansion,
                'repointed': repointed_count,
                'relocated': relocated_count,
                'modified': modified_count,
                'skipped': skipped_count,
                'total': total
            })

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            self.progress.emit(0, f"❌ ERRO: {str(e)}\n{error_details}")
            self.finished.emit({'success': False, 'error': str(e), 'details': error_details})

    def expand_rom(self, rom_data, new_bytes):
        """
        Expande ROM para acomodar texto traduzido (REPOINTING AUTOMÁTICO).

        Algoritmo baseado no Capítulo IV do Manual de ROM Hacking:
        1. Calcula tamanho alinhado em blocos de 0x8000 (32KB)
        2. Preenche até o alinhamento com 0xFF
        3. Grava novo texto no final da ROM expandida
        4. Retorna novo offset para atualização do ponteiro

        Exemplo:
        - ROM atual: 0x1F234 bytes
        - Alinhado: 0x20000 (próximo múltiplo de 0x8000)
        - Padding: 0xDCC bytes (0xFF)
        - Novo offset: 0x20000 (local do texto traduzido)
        """
        current_size = len(rom_data)

        block_size = 0x8000
        aligned_size = ((current_size + block_size - 1) // block_size) * block_size

        if aligned_size > current_size:
            rom_data.extend(b'\xFF' * (aligned_size - current_size))

        new_offset = len(rom_data)
        rom_data.extend(new_bytes)

        return new_offset

    def update_pointer(self, rom_data, table_offset, new_rom_offset):
        """
        Atualiza ponteiro na tabela com o novo offset.
        Usa função de conversão com endianness automático.

        Processo:
        1. Converte ROM offset -> bytes de ponteiro (com inversão endian)
        2. Grava bytes na Pointer Table
        3. Exemplo SNES: offset 0x012345 -> [45 A3 80] na tabela
        """
        pointer_bytes = rom_offset_to_pointer_bytes(new_rom_offset, 'SNES_LOROM')

        for i, byte_val in enumerate(pointer_bytes):
            rom_data[table_offset + i] = byte_val

    def build_char_table_inverse(self):
        """
        Tabela de conversão texto -> bytes.
        Control codes padrão da Engine Retro-A.
        """
        table = {}
        for i in range(32, 127):
            table[chr(i)] = i
        table['[END]'] = 0x00
        table['[LINE]'] = 0x01
        table['[WAIT]'] = 0x02
        table['[TERM]'] = 0xFF
        return table

    def fix_snes_checksum(self, rom_data):
        """
        ✅ KERNEL V 9.5: CHECKSUM FIXER (LACRE DE COMPATIBILIDADE)

        Recalcula e corrige o checksum SNES no header interno.
        CRÍTICO para funcionamento em hardware real (SNES/Everdrive/flashcarts).

        Processo (Baseado no SNES ROM Header Specification):
        ========================================================
        1. Detecta offset do header interno:
           - LoROM: 0x7FDC-0x7FDF (ou +0x200 se tem header SMC)
           - HiROM: 0xFFDC-0xFFDF (ou +0x200 se tem header SMC)

        2. Calcula checksum:
           - Soma TODOS os bytes da ROM (16-bit, com wraparound)
           - Ignora apenas os 4 bytes do checksum durante soma

        3. Calcula complemento:
           - Complemento = 0xFFFF - Checksum

        4. Grava no header interno:
           - Offset +0: Complemento Low Byte
           - Offset +1: Complemento High Byte
           - Offset +2: Checksum Low Byte
           - Offset +3: Checksum High Byte

        Args:
            rom_data: bytearray mutável com dados da ROM

        Returns:
            None (modifica rom_data in-place)

        Exemplo de valores:
        - ROM soma: 0x12A4F8BC
        - Checksum (16-bit): 0xF8BC
        - Complemento: 0xFFFF - 0xF8BC = 0x0743
        - Gravação: [43 07 BC F8] em $7FDC-$7FDF
        """
        rom_size = len(rom_data)

        # Detecta se tem header SMC (512 bytes)
        has_header = (rom_size % 1024 == 512)
        header_offset = 0x200 if has_header else 0x000

        # Detecta tipo de mapeamento (LoROM vs HiROM)
        # Lê byte em $FFD5 para determinar
        map_mode_offset = 0x7FD5 + header_offset
        if map_mode_offset < rom_size:
            map_mode = rom_data[map_mode_offset]
            is_hirom = (map_mode in [0x21, 0x31])  # HiROM ou HiROM+FastROM
        else:
            is_hirom = False  # Fallback LoROM

        # Define offset do checksum baseado no mapeamento
        if is_hirom:
            checksum_offset = 0xFFDC + header_offset
        else:
            checksum_offset = 0x7FDC + header_offset

        # Valida se offset existe na ROM
        if checksum_offset + 4 > rom_size:
            self.progress.emit(0, f"⚠️ ROM muito pequena para conter header SNES válido ({rom_size} bytes)")
            return

        # ============================================================
        # CÁLCULO DO CHECKSUM (16-bit sum com wraparound)
        # ============================================================
        checksum = 0

        for i in range(rom_size):
            # Pula os 4 bytes do checksum durante a soma
            if checksum_offset <= i < checksum_offset + 4:
                continue

            checksum += rom_data[i]

        # Reduz para 16-bit (wraparound automático)
        checksum = checksum & 0xFFFF

        # Calcula complemento
        complement = (0xFFFF - checksum) & 0xFFFF

        # ============================================================
        # GRAVAÇÃO NO HEADER INTERNO
        # ============================================================
        # Formato: [Complement_Lo, Complement_Hi, Checksum_Lo, Checksum_Hi]
        rom_data[checksum_offset + 0] = complement & 0xFF        # Complemento Low
        rom_data[checksum_offset + 1] = (complement >> 8) & 0xFF # Complemento High
        rom_data[checksum_offset + 2] = checksum & 0xFF          # Checksum Low
        rom_data[checksum_offset + 3] = (checksum >> 8) & 0xFF   # Checksum High

        # Log de confirmação
        map_type = "HiROM" if is_hirom else "LoROM"
        self.progress.emit(
            0,
            f"🔐 Checksum SNES corrigido: 0x{checksum:04X} / Complemento: 0x{complement:04X} "
            f"({map_type}, offset 0x{checksum_offset:X})"
        )

    def encode_string(self, text, char_table):
        """
        Codifica string para bytes da ROM.

        Endstring padrão: 0x00 (compatível com 0xFF como alternativa)
        Suporta control codes entre colchetes: [END], [LINE], [WAIT], [TERM]

        Processo:
        1. Converte cada caractere usando char_table
        2. Reconhece tags de controle [TAG]
        3. Adiciona terminador 0x00 ao final
        """
        result = bytearray()
        i = 0
        while i < len(text):
            if text[i] == '[':
                end = text.find(']', i)
                if end != -1:
                    tag = text[i:end+1]
                    if tag in char_table:
                        result.append(char_table[tag])
                        i = end + 1
                        continue

            char = text[i]
            byte_val = char_table.get(char, ord('?'))
            result.append(byte_val)
            i += 1

        result.append(0x00)
        return bytes(result)


class ReinsertionTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.rom_path = None
        self.translation_data = []
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        self.setStyleSheet("""
            QWidget {
                background-color: #2b2b2b;
                color: #ffffff;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 10pt;
            }
            QPushButton {
                background-color: #2ecc71;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #27ae60;
            }
            QPushButton:pressed {
                background-color: #229954;
            }
            QPushButton#btn_load {
                background-color: #0078d7;
            }
            QPushButton#btn_load:hover {
                background-color: #1e88e5;
            }
            QLineEdit {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 2px solid #3f3f3f;
                border-radius: 4px;
                padding: 8px;
            }
            QTextEdit {
                background-color: #1e1e1e;
                color: #00ff00;
                border: 2px solid #3f3f3f;
                border-radius: 4px;
                font-family: 'Consolas', monospace;
            }
            QProgressBar {
                background-color: #1e1e1e;
                border: 2px solid #3f3f3f;
                border-radius: 4px;
                text-align: center;
                color: #ffffff;
            }
            QProgressBar::chunk {
                background-color: #2ecc71;
            }
            QLabel {
                color: #ffffff;
            }
        """)

        title = QLabel("💉 REINSERÇÃO - ENGINE RETRO-A")
        title.setStyleSheet("font-size: 14pt; font-weight: bold; color: #2ecc71;")
        layout.addWidget(title)

        rom_layout = QHBoxLayout()
        rom_layout.addWidget(QLabel("ROM:"))
        self.rom_input = QLineEdit()
        self.rom_input.setPlaceholderText("Selecione o arquivo ROM...")
        rom_layout.addWidget(self.rom_input)

        btn_browse = QPushButton("📁 SELECIONAR ROM")
        btn_browse.setObjectName("btn_load")
        btn_browse.clicked.connect(self.select_rom)
        rom_layout.addWidget(btn_browse)
        layout.addLayout(rom_layout)

        trans_layout = QHBoxLayout()
        trans_layout.addWidget(QLabel("JSON:"))
        self.trans_input = QLineEdit()
        self.trans_input.setPlaceholderText("Selecione o arquivo JSON...")
        trans_layout.addWidget(self.trans_input)

        btn_browse_trans = QPushButton("📄 CARREGAR JSON")
        btn_browse_trans.setObjectName("btn_load")
        btn_browse_trans.clicked.connect(self.load_translation)
        trans_layout.addWidget(btn_browse_trans)
        layout.addLayout(trans_layout)

        offset_layout = QHBoxLayout()
        offset_layout.addWidget(QLabel("Offset Pointer Table:"))
        self.offset_input = QLineEdit("0x012F4")
        self.offset_input.setMaximumWidth(120)
        offset_layout.addWidget(self.offset_input)
        offset_layout.addStretch()
        layout.addLayout(offset_layout)

        btn_reinsert = QPushButton("💉 APLICAR TRADUÇÕES")
        btn_reinsert.setStyleSheet("padding: 12px; font-size: 11pt;")
        btn_reinsert.clicked.connect(self.start_reinsertion)
        layout.addWidget(btn_reinsert)

        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)

        layout.addWidget(QLabel("📋 LOG:"))
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        layout.addWidget(self.log_output)

    def select_rom(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Selecionar ROM", "",
            "ROM Files (*.smc *.sfc *.bin);;All Files (*.*)"
        )
        if file_path:
            self.rom_path = file_path
            self.rom_input.setText(file_path)
            self.log(f"✅ ROM: {os.path.basename(file_path)}")

    def load_translation(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Carregar Tradução", "", "JSON Files (*.json)")
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    self.translation_data = json.load(f)

                self.trans_input.setText(file_path)
                self.log(f"✅ Carregadas {len(self.translation_data)} strings")

            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Erro ao carregar JSON:\n{str(e)}")

    def start_reinsertion(self):
        if not self.rom_path:
            QMessageBox.warning(self, "Aviso", "Selecione um arquivo ROM!")
            return

        if not self.translation_data:
            QMessageBox.warning(self, "Aviso", "Carregue um arquivo JSON!")
            return

        try:
            offset = int(self.offset_input.text(), 16)
        except:
            QMessageBox.warning(self, "Aviso", "Offset inválido!")
            return

        reply = QMessageBox.question(
            self, "Confirmar",
            f"⚠️ ATENÇÃO ⚠️\n\n"
            f"• Backup automático\n"
            f"• Aplicar {len(self.translation_data)} traduções\n"
            f"• Repointing automático se necessário\n\n"
            f"Continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        self.log("🚀 Iniciando reinserção...")
        self.progress_bar.setValue(0)

        self.worker = ReinsertionWorker(self.rom_path, self.translation_data, offset)
        self.worker.progress.connect(self.on_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def on_progress(self, value, message):
        self.progress_bar.setValue(value)
        self.log(message)

    def on_finished(self, result):
        if not result.get('success'):
            error_msg = result.get('error', 'Erro desconhecido')
            details = result.get('details', '')
            QMessageBox.critical(self, "Erro", f"Falha:\n{error_msg}\n\nDetalhes:\n{details}")
            return

        output = result['output_path']
        expansion = result['expansion']
        repointed = result.get('repointed', 0)
        relocated = result.get('relocated', 0)
        modified = result.get('modified', 0)
        skipped = result.get('skipped', 0)
        total = result['total']

        self.log(f"\n{'='*60}")
        self.log(f"✅ REINSERÇÃO CONCLUÍDA!")
        self.log(f"{'='*60}")
        self.log(f"📦 Arquivo: {os.path.basename(output)}")
        self.log(f"📊 ROM original: {result['original_size']:,} bytes")
        self.log(f"📊 ROM final: {result['final_size']:,} bytes")
        self.log(f"📈 Expansão: +{expansion:,} bytes")
        self.log(f"")
        self.log(f"📝 Estatísticas de Processamento:")
        self.log(f"   • Total de strings: {total}")
        self.log(f"   • Strings modificadas: {modified}")
        self.log(f"   • Strings realocadas: {relocated}")
        self.log(f"   • Repointing (tabela): {repointed}")
        self.log(f"   • Strings ignoradas: {skipped}")
        self.log(f"{'='*60}\n")

        QMessageBox.information(self, "Sucesso",
            f"✅ Reinserção Concluída!\n\n"
            f"Arquivo:\n{output}\n\n"
            f"📊 Estatísticas:\n"
            f"• Total: {total} strings\n"
            f"• Modificadas: {modified}\n"
            f"• Realocadas: {relocated}\n"
            f"• Repointing: {repointed}\n"
            f"• Expansão: +{expansion:,} bytes")

    def log(self, message):
        self.log_output.append(message)

    def set_rom_path(self, path):
        if path:
            self.rom_path = path
            self.rom_input.setText(path)

    def retranslate(self):
        pass
