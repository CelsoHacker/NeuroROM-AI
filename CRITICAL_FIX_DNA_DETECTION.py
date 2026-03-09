# ================================================================
# CORREÇÃO CRÍTICA 1: PRIORIDADE ABSOLUTA PARA .EXE
# Adicionar NO INÍCIO do método run() do EngineDetectionWorker
# ANTES da linha 1492 (antes de "DETECÇÃO LAYER 1")
# ================================================================

# ADICIONAR ESTE BLOCO LOGO APÓS A LEITURA DOS HEADERS (após linha 1490):

# ================================================================
# DETECÇÃO LAYER 0: PRIORIDADE ABSOLUTA - EXTENSÃO .EXE
# ================================================================
# REGRA: .exe SEMPRE é Windows, não importa o conteúdo interno
if file_ext in ['.exe', '.dll', '.scr']:
    # Analisa tamanho para categorizar
    if file_size_mb > 100:
        category = "High Capacity"
    elif file_size_mb > 10:
        category = "Medium Size"
    else:
        category = "Small"

    # Valida assinatura PE se possível
    pe_info = "Windows Executable"
    engine_name = f'Windows Executable ({category})'
    notes = f'{pe_info} | {file_size_mb:.1f} MB'

    if header[0:2] == b'MZ':
        try:
            if len(header) > 0x3C + 4:
                pe_offset = int.from_bytes(header[0:3C:0x3C+4], 'little')
                if pe_offset < len(header) - 4:
                    if header[pe_offset:pe_offset+4] == b'PE\x00\x00':
                        pe_info = "Win32 PE Confirmed"
                        notes = f'{pe_info} | {file_size_mb:.1f} MB'
        except:
            pass

    # Detecta DarkStone especificamente
    if b'DarkStone' in header or b'DARKSTONE' in header or b'jeRaff' in header:
        engine_name = 'DarkStone Original (Delphine Software)'
        notes = f'Action RPG ({file_size_mb:.1f} MB) | Desenvolvido em 1999'

    self.detection_complete.emit({
        'type': 'PC_GAME',
        'platform': 'PC (Windows)',
        'engine': engine_name,
        'notes': notes,
        'platform_code': 'PC'
    })
    return


# ================================================================
# CORREÇÃO CRÍTICA 2: ADICIONAR LIMITES DE TAMANHO
# ================================================================

# LINHA 1497: SUBSTITUIR
# DE:
if file_ext in ['.smc', '.sfc'] or (len(snes_header_zone) >= 64):

# PARA:
# TRAVA DE SANIDADE: SNES real nunca ultrapassa 12MB
if (file_ext in ['.smc', '.sfc'] and file_size_mb <= 12) and file_size_mb <= 12:


# LINHA 1535: SUBSTITUIR
# DE:
if file_ext in ['.md', '.gen', '.smd'] or b'SEGA' in genesis_header_zone[:16]:

# PARA:
# TRAVA DE SANIDADE: Genesis real nunca ultrapassa 8MB
if (file_ext in ['.md', '.gen', '.smd'] and file_size_mb <= 8) or (b'SEGA' in genesis_header_zone[:16] and file_size_mb <= 8):


# LINHA 1579: SUBSTITUIR
# DE:
if header[0:4] == b'NES\x1a' or file_ext == '.nes':

# PARA:
# TRAVA DE SANIDADE: NES real nunca ultrapassa 2MB
if ((header[0:4] == b'NES\x1a' or file_ext == '.nes') and file_size_mb <= 2):


# LINHA 1623-1633: DELETAR COMPLETAMENTE
# (Detecção de DarkStone movida para LAYER 0 - prioridade .exe)


# ================================================================
# CORREÇÃO CRÍTICA 3: REMOVER BLOQUEIO DITATORIAL
# Localização: Método select_rom() - Linhas 3929-3951
# ================================================================

# SUBSTITUIR AS LINHAS 3929-3951:
# DE:
                if not is_valid:
                    # BLOQUEAR arquivo incompatível
                    self.log(f"❌ Arquivo bloqueado: {error_message[:50]}...")

                    # Mostrar mensagem de erro ao usuário
                    msg_box = QMessageBox(self)
                    msg_box.setIcon(QMessageBox.Icon.Warning)
                    msg_box.setWindowTitle("Arquivo Incompatível")
                    msg_box.setTextFormat(Qt.TextFormat.RichText)
                    msg_box.setText(error_message)
                    msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
                    msg_box.exec()

                    # Limpar seleção
                    self.original_rom_path = None
                    self.rom_path_label.setText("⚠️ Arquivo incompatível - Selecione novamente")
                    self.rom_path_label.setStyleSheet("color:#FF5722;font-weight:bold;")
                    self.reinsert_rom_label.setText(self.tr("no_rom"))
                    self.reinsert_rom_label.setStyleSheet("")
                    self.engine_detection_label.setVisible(False)

                    self.log("❌ Seleção de arquivo cancelada por incompatibilidade")
                    return  # Parar aqui - não permitir uso do arquivo

# PARA:
                if not is_valid:
                    # AVISO (não bloqueia - usuário tem palavra final)
                    self.log(f"⚠️ AVISO: Possível incompatibilidade detectada")
                    self.log(f"   Plataforma selecionada: {selected_platform}")
                    self.log(f"   Arquivo detectado: {self.detected_engine.get('platform', 'Unknown')}")
                    self.log(f"   ℹ️  Você pode prosseguir se souber o que está fazendo")

                    # Não bloqueia - apenas informa
                    # O usuário pode clicar em "Extrair" normalmente
