# -*- coding: utf-8 -*-
import sys
import struct
import shutil
import os
import heapq
import json
import base64
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QScrollArea, QGridLayout,
    QFrame, QMessageBox, QDialog, QLineEdit, QSpinBox
)
from PyQt6.QtGui import QImage, QPixmap, QColor, QPainter, QPen
from PyQt6.QtCore import Qt, pyqtSignal

# OCR & AI Translation imports
try:
    import pytesseract
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    print("⚠️ pytesseract ou Pillow não instalado. OCR desabilitado.")

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("⚠️ google-generativeai não instalado. Tradução AI desabilitada.")

# Modern Texture Support (Unity/Unreal)
try:
    from PIL import ImageFile
    ImageFile.LOAD_TRUNCATED_IMAGES = True
    MODERN_TEXTURES_AVAILABLE = True
except ImportError:
    MODERN_TEXTURES_AVAILABLE = False
    print("⚠️ Suporte a texturas modernas limitado.")

def lz2_decompress(rom_data: bytes, offset: int) -> tuple[bytes, int]:
    output = bytearray()
    idx = offset
    start_idx = offset
    if idx >= len(rom_data): return b"", 0

    try:
        while True:
            if idx >= len(rom_data): break
            cmd = rom_data[idx]; idx += 1
            if cmd == 0xFF: break

            ctype = (cmd >> 5) & 0x07
            length = (cmd & 0x1F) + 1
            if length == 32:
                while True:
                    if idx >= len(rom_data): break
                    ext = rom_data[idx]; idx += 1
                    length += ext
                    if ext != 0xFF: break

            if ctype == 0:
                for _ in range(length):
                    if idx < len(rom_data): output.append(rom_data[idx]); idx += 1
            elif ctype == 1:
                if idx < len(rom_data):
                    val = rom_data[idx]; idx += 1
                    for _ in range(length): output.append(val)
            elif ctype == 2:
                if idx + 1 < len(rom_data):
                    b1, b2 = rom_data[idx], rom_data[idx+1]; idx += 2
                    for _ in range(length): output.extend([b1, b2])
            elif ctype == 3:
                if idx < len(rom_data):
                    val = rom_data[idx]; idx += 1
                    for i in range(length): output.append((val + i) & 0xFF)
            elif ctype == 4:
                if idx + 1 < len(rom_data):
                    rel = (rom_data[idx] << 8) | rom_data[idx+1]; idx += 2
                    src = len(output) - rel
                    for _ in range(length):
                        if 0 <= src < len(output): output.append(output[src])
                        else: output.append(0)
                        src += 1
            if len(output) > 64 * 1024: break
        return bytes(output), (idx - start_idx)
    except: return b"", 0

def lz2_compress_optimal(raw_data: bytes) -> bytes:
    length = len(raw_data)
    if length == 0: return b'\xFF'

    dist = [float('inf')] * (length + 1)
    dist[0] = 0
    parent = [None] * (length + 1)
    heap = [(0, 0)]

    while heap:
        d, pos = heapq.heappop(heap)
        if d > dist[pos]: continue
        if pos == length: break

        max_direct = min(32, length - pos)
        for L in range(1, max_direct + 1):
            cost = 1 + L
            if dist[pos] + cost < dist[pos + L]:
                dist[pos + L] = dist[pos] + cost
                parent[pos + L] = (pos, 0, L, None)
                heapq.heappush(heap, (dist[pos + L], pos + L))

        if pos < length:
            b = raw_data[pos]
            rle_len = 1
            while pos + rle_len < length and raw_data[pos + rle_len] == b and rle_len < 32: rle_len += 1
            if rle_len >= 2:
                for L in range(2, rle_len + 1):
                    cost = 2
                    if dist[pos] + cost < dist[pos + L]:
                        dist[pos + L] = dist[pos] + cost
                        parent[pos + L] = (pos, 1, L, b)
                        heapq.heappush(heap, (dist[pos + L], pos + L))

        best_lz = 0; best_off = 0
        search_start = max(0, pos - 1024)
        if pos + 3 < length:
            sub = raw_data[pos:pos+32]
            window = raw_data[search_start:pos]
            for i in range(len(window)):
                match = 0
                while match < len(sub) and (i+match) < len(window) and window[i+match] == sub[match]:
                    match += 1
                if match > best_lz:
                    best_lz = match
                    best_off = len(window) - i

        if best_lz >= 3:
            for L in range(3, min(best_lz + 1, 33)):
                cost = 3
                if dist[pos] + cost < dist[pos + L]:
                    dist[pos + L] = dist[pos] + cost
                    parent[pos + L] = (pos, 4, L, best_off)
                    heapq.heappush(heap, (dist[pos + L], pos + L))

    output = bytearray()
    curr = length
    cmds = []
    while curr > 0:
        prev, type, l, arg = parent[curr]
        cmds.append((type, l, arg, prev))
        curr = prev
    cmds.reverse()

    for type, l, arg, start in cmds:
        header = (type << 5) | (l - 1)
        if type == 0: output.append(header); output.extend(raw_data[start:start+l])
        elif type == 1: output.append(header); output.append(arg)
        elif type == 4: output.append(header); output.append((arg >> 8) & 0xFF); output.append(arg & 0xFF)

    output.append(0xFF)
    return bytes(output)

def decode_tile_4bpp(tile_bytes):
    pixels = [0]*64
    if len(tile_bytes) < 32: return pixels
    for y in range(8):
        p0, p1 = tile_bytes[y*2], tile_bytes[y*2+1]
        p2, p3 = tile_bytes[16+y*2], tile_bytes[16+y*2+1]
        for x in range(8):
            bit = 7-x
            val = ((p3>>bit&1)<<3) | ((p2>>bit&1)<<2) | ((p1>>bit&1)<<1) | (p0>>bit&1)
            pixels[y*8+x] = val
    return pixels

def decode_tile_2bpp(tile_bytes):
    pixels = [0]*64
    if len(tile_bytes) < 16: return pixels
    for y in range(8):
        p0, p1 = tile_bytes[y*2], tile_bytes[y*2+1]
        for x in range(8):
            bit = 7-x
            val = ((p1>>bit&1)<<1) | (p0>>bit&1)
            pixels[y*8+x] = val
    return pixels

def encode_tile_4bpp(pixels):
    tile_bytes = bytearray(32)
    for y in range(8):
        p0=p1=p2=p3=0
        for x in range(8):
            c = pixels[y*8+x]; bit = 7-x
            p0 |= ((c>>0)&1)<<bit; p1 |= ((c>>1)&1)<<bit
            p2 |= ((c>>2)&1)<<bit; p3 |= ((c>>3)&1)<<bit
        tile_bytes[y*2]=p0; tile_bytes[y*2+1]=p1
        tile_bytes[16+y*2]=p2; tile_bytes[16+y*2+1]=p3
    return tile_bytes

class PixelEditor(QDialog):
    def __init__(self, pixels, palette, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Editor de Tile - Engine Retro-A")
        self.pixels = list(pixels)
        self.palette = palette
        self.selected_color = 15
        self.zoom = 40
        self.init_ui()

    def init_ui(self):
        self.setFixedSize(500, 500)
        self.setStyleSheet("background-color: #2b2b2b; color: white;")
        layout = QVBoxLayout(self)

        canvas_container = QWidget()
        canvas_container.setStyleSheet("background-color: #1e1e1e;")
        clayout = QVBoxLayout(canvas_container)
        clayout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lbl = QLabel()
        self.lbl.setFixedSize(8 * self.zoom, 8 * self.zoom)
        self.lbl.setStyleSheet("border: 2px solid #0078d7; background-color: black;")
        self.lbl.setCursor(Qt.CursorShape.CrossCursor)
        self.lbl.mousePressEvent = self.paint
        self.lbl.mouseMoveEvent = self.paint

        clayout.addWidget(self.lbl)
        layout.addWidget(canvas_container)
        self.update_canvas()

        tools = QHBoxLayout()
        be = QPushButton("🧽 BORRACHA (Cor 0)")
        be.setStyleSheet("background:#e74c3c; padding:10px; font-weight:bold; border-radius:5px;")
        be.setCursor(Qt.CursorShape.PointingHandCursor)  # Cursor de mãozinha
        be.clicked.connect(self.use_eraser)

        bp = QPushButton("✏️ PINCEL (Cor 15)")
        bp.setStyleSheet("background:#3498db; padding:10px; font-weight:bold; border-radius:5px;")
        bp.setCursor(Qt.CursorShape.PointingHandCursor)  # Cursor de mãozinha
        bp.clicked.connect(self.use_pencil)

        tools.addWidget(be); tools.addWidget(bp)
        layout.addLayout(tools)

        pal = QHBoxLayout(); pal.setSpacing(1)
        for i, c in enumerate(self.palette):
            b = QPushButton()
            b.setFixedSize(24,24)
            b.setStyleSheet(f"background:{QColor(c).name()}; border:1px solid #555;")
            b.setCursor(Qt.CursorShape.PointingHandCursor)  # Cursor de mãozinha
            b.clicked.connect(lambda _,x=i: self.set_c(x))
            pal.addWidget(b)
        layout.addLayout(pal)

        btn = QPushButton("💾 SALVAR E GRAVAR")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)  # Cursor de mãozinha
        btn.clicked.connect(self.accept)
        btn.setStyleSheet("background:#2ecc71; padding:10px; font-weight:bold; color:black;")
        layout.addWidget(btn)

    def use_eraser(self):
        self.selected_color = 0
        self.lbl.setCursor(Qt.CursorShape.ForbiddenCursor)

    def use_pencil(self):
        self.selected_color = 15
        self.lbl.setCursor(Qt.CursorShape.CrossCursor)

    def set_c(self, i):
        self.selected_color = i
        self.lbl.setCursor(Qt.CursorShape.CrossCursor)

    def paint(self, e):
        x = int(e.position().x()) // self.zoom
        y = int(e.position().y()) // self.zoom
        if 0<=x<8 and 0<=y<8:
            self.pixels[y*8+x] = self.selected_color
            self.update_canvas()

    def update_canvas(self):
        img = QImage(8,8,QImage.Format.Format_Indexed8)
        img.setColorTable(self.palette)
        for y in range(8):
            for x in range(8):
                img.setPixel(x, y, self.pixels[y*8+x])
        self.lbl.setPixmap(QPixmap.fromImage(img).scaled(
            self.lbl.size(),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.FastTransformation
        ))

    def get_pixels(self):
        return self.pixels

class TileWidget(QLabel):
    clicked = pyqtSignal(int)
    def __init__(self, idx, img):
        super().__init__()
        self.idx = idx
        self.setPixmap(QPixmap.fromImage(img).scaled(32,32))
        self.setFixedSize(34,34)
        self.setFrameStyle(QFrame.Shape.Box)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
    def mousePressEvent(self, e):
        self.clicked.emit(self.idx)

class GraphicLabTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.rom_data = None
        self.rom_name = None
        self.tiles_info = []
        self.current_bpp = 4
        self.palette = [QColor(i*17,i*17,i*17).rgb() for i in range(16)]
        self.selected_tile_idx = None
        self.gemini_api_key = None
        self.target_language = "Portuguese (Brazil)"

        # Modern Textures Support (Unity/Unreal/Godot)
        self.modern_texture = None
        self.modern_texture_path = None
        self.modern_texture_format = None

        self.init_ui()

    def init_ui(self):
        l = QVBoxLayout(self)
        top = QHBoxLayout()

        self.combo = QComboBox()
        self.combo.setCursor(Qt.CursorShape.PointingHandCursor)  # Cursor de mãozinha
        self.combo.addItems(["Engine Retro-A (LZ2)", "SNES 4bpp", "SNES 2bpp"])

        self.btn = QPushButton("🔍 SCAN")
        self.btn.setCursor(Qt.CursorShape.PointingHandCursor)  # Cursor de mãozinha
        self.btn.clicked.connect(self.scan)
        self.btn.setStyleSheet("background:#0078D7; color:white; padding:8px;")

        btn_font = QPushButton("📝 IR PARA FONTE DE TEXTO")
        btn_font.setCursor(Qt.CursorShape.PointingHandCursor)  # Cursor de mãozinha
        btn_font.clicked.connect(self.go_to_font)
        btn_font.setStyleSheet("background:#9b59b6; color:white; padding:8px;")

        # NOVO: Botão OCR + AI Translation (Smart Router)
        btn_ocr = QPushButton("🤖 OCR + TRADUÇÃO AI")
        btn_ocr.setCursor(Qt.CursorShape.PointingHandCursor)  # Cursor de mãozinha
        btn_ocr.clicked.connect(self.intelligent_ocr_translation)
        btn_ocr.setStyleSheet("background:#e67e22; color:white; padding:8px; font-weight:bold;")
        btn_ocr.setToolTip("Detecta texto (tiles 8x8 ou texturas modernas) e traduz automaticamente")

        # NOVO: Botão para Texturas Modernas
        btn_modern = QPushButton("🎨 CARREGAR TEXTURA")
        btn_modern.setCursor(Qt.CursorShape.PointingHandCursor)  # Cursor de mãozinha
        btn_modern.clicked.connect(self.load_modern_texture)
        btn_modern.setStyleSheet("background:#16a085; color:white; padding:8px; font-weight:bold;")
        btn_modern.setToolTip("Carrega texturas modernas (DDS, PNG, TGA, BMP)")

        top.addWidget(QLabel("PERFIL:"))
        top.addWidget(self.combo)
        top.addWidget(self.btn)
        top.addWidget(btn_font)
        top.addWidget(btn_ocr)
        top.addWidget(btn_modern)
        l.addLayout(top)

        self.scroll = QScrollArea()
        self.gridw = QWidget()
        self.grid = QGridLayout(self.gridw)
        self.grid.setSpacing(2)
        self.scroll.setWidget(self.gridw)
        self.scroll.setWidgetResizable(True)
        l.addWidget(self.scroll)

        self.status = QLabel("Pronto.")
        l.addWidget(self.status)

    def set_rom_path(self, path):
        if path:
            with open(path, "rb") as f:
                self.rom_data = bytearray(f.read())
                self.rom_name = path

    def go_to_font(self):
        if not self.rom_data:
            QMessageBox.warning(self, "Aviso", "Carregue uma ROM primeiro!")
            return

        self.current_bpp = 2
        self.palette = [QColor(i*85,i*85,i*85).rgb() for i in range(4)]
        self.combo.setCurrentIndex(2)

        for i in reversed(range(self.grid.count())):
            self.grid.itemAt(i).widget().setParent(None)
        self.tiles_info = []

        offset = 0x008000
        raw_data = self.rom_data[offset:offset+4096]

        row, col, total = 0, 0, 0
        num_tiles = len(raw_data) // 16

        for i in range(min(num_tiles, 256)):
            px = decode_tile_2bpp(raw_data[i*16:(i+1)*16])
            img = QImage(8,8,QImage.Format.Format_Indexed8)
            img.setColorTable(self.palette)
            for k in range(64):
                img.setPixel(k%8, k//8, px[k])

            w = TileWidget(total, img)
            w.clicked.connect(lambda idx: None)
            self.grid.addWidget(w, row, col)
            col += 1
            if col > 15:
                col = 0
                row += 1
            total += 1

        self.status.setText(f"Fonte de texto: {total} tiles (2bpp) no offset 0x8000")

    def scan(self):
        if not self.rom_data: return

        for i in reversed(range(self.grid.count())):
            self.grid.itemAt(i).widget().setParent(None)
        self.tiles_info = []

        offsets = [0x008000, 0x008200, 0x010000, 0x018000, 0x020000, 0x040000, 0x042000]
        row, col, total = 0, 0, 0

        for off in offsets:
            raw, size = lz2_decompress(self.rom_data, off)
            if len(raw) > 512:
                limit = min(len(raw)//32, 128)
                raw_copy = bytearray(raw)
                for i in range(limit):
                    px = decode_tile_4bpp(raw[i*32:(i+1)*32])
                    img = QImage(8,8,QImage.Format.Format_Indexed8)
                    img.setColorTable(self.palette)
                    for k in range(64):
                        img.setPixel(k%8, k//8, px[k])
                    w = TileWidget(total, img)
                    w.clicked.connect(self.edit)
                    self.grid.addWidget(w, row, col)
                    self.tiles_info.append({
                        "pixels": px,
                        "block_offset": off,
                        "tile_idx": i,
                        "raw_block": raw_copy,
                        "orig_size": size
                    })
                    col += 1
                    if col > 15:
                        col = 0
                        row += 1
                    total += 1

        self.status.setText(f"Encontrados {total} tiles.")

    def edit(self, idx):
        # Salva tile selecionado para OCR
        self.selected_tile_idx = idx

        info = self.tiles_info[idx]
        editor = PixelEditor(info['pixels'], self.palette, self)

        if editor.exec():
            info['pixels'] = editor.get_pixels()
            try:
                new_tile_bytes = encode_tile_4bpp(info['pixels'])
                start = info['tile_idx'] * 32
                info['raw_block'][start:start+32] = new_tile_bytes

                new_compressed = lz2_compress_optimal(info['raw_block'])

                orig_size = info["orig_size"]
                new_size = len(new_compressed)

                if new_size > orig_size:
                    msg = QMessageBox(self)
                    msg.setIcon(QMessageBox.Icon.Warning)
                    msg.setWindowTitle("⚠️ Arquivo Maior")
                    msg.setText(f"Original: {orig_size} | Novo: {new_size}\nDeseja EXPANDIR a ROM?")
                    msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                    if msg.exec() == QMessageBox.StandardButton.Yes:
                        with open(self.rom_name, 'rb') as f:
                            full_rom = bytearray(f.read())
                        new_offset = len(full_rom)
                        full_rom.extend(new_compressed)

                        expanded_fn = self.rom_name.replace(".smc", "_EXPANDED.smc")
                        with open(expanded_fn, 'wb') as f:
                            f.write(full_rom)

                        QMessageBox.information(self, "ROM Expandida",
                            f"Offset: {hex(new_offset)}\nArquivo: {os.path.basename(expanded_fn)}")
                    return

                new_fn = self.rom_name.replace(".smc", "_MOD.smc")
                if not os.path.exists(new_fn):
                    shutil.copy(self.rom_name, new_fn)

                with open(new_fn, "r+b") as f:
                    f.seek(info['block_offset'])
                    f.write(new_compressed)
                    pad = orig_size - new_size
                    if pad > 0:
                        f.write(b'\xFF' * pad)

                img = QImage(8,8,QImage.Format.Format_Indexed8)
                img.setColorTable(self.palette)
                for k in range(64):
                    img.setPixel(k%8, k//8, info['pixels'][k])
                self.grid.itemAt(idx).widget().setPixmap(QPixmap.fromImage(img).scaled(32,32))

                QMessageBox.information(self, "SUCESSO", "Salvo com Compressão Ótima!")
            except Exception as e:
                QMessageBox.warning(self, "Erro", str(e))

    # ========================================================================
    # PIPELINE OCR + AI TRANSLATION
    # ========================================================================

    def intelligent_ocr_translation(self):
        """
        Smart Router para OCR + AI Translation.

        Detecta automaticamente:
        - Se há textura moderna carregada → process_modern_texture_ocr_translation()
        - Se há tile selecionado → process_tile_ocr_translation()
        - Caso contrário → aviso ao usuário
        """
        # Prioridade 1: Textura moderna (se carregada)
        if self.modern_texture is not None:
            self.log_area.append(
                "<span style='color:#3498db;'>[MODO DETECTADO]</span> Textura Moderna - "
                "Usando pipeline OCR para texturas completas"
            )
            self.process_modern_texture_ocr_translation()
            return

        # Prioridade 2: Tile selecionado (modo retro)
        if self.selected_tile_idx is not None and self.tiles_info:
            self.log_area.append(
                "<span style='color:#3498db;'>[MODO DETECTADO]</span> Tile 8x8 - "
                "Usando pipeline OCR para tiles retro"
            )
            self.process_tile_ocr_translation()
            return

        # Nenhum modo disponível
        QMessageBox.information(
            self,
            "Selecione Conteúdo",
            "Para usar OCR + AI Translation:\n\n"
            "OPÇÃO 1 - Jogos Modernos:\n"
            "• Clique em '🎨 CARREGAR TEXTURA'\n"
            "• Carregue PNG/TGA/DDS de jogos indie\n\n"
            "OPÇÃO 2 - Jogos Retro:\n"
            "• Carregue ROM e faça scan\n"
            "• Clique em um tile 8x8 na grid\n\n"
            "Depois use este botão para traduzir automaticamente!"
        )

    def process_tile_ocr_translation(self):
        """
        Pipeline completo de OCR + AI Translation para tiles gráficos.

        Fluxo:
        1. Image Reconstruction (4bpp/8bpp → PIL.Image)
        2. Pre-processing (upscaling + binarização)
        3. OCR (pytesseract)
        4. AI Translation (Gemini)
        5. Text Rendering (PIL ImageDraw)
        6. Quantização (PIL.Image → 4bpp bytes)
        7. In-place Reinsertion (ROM binária)
        """
        # Validações iniciais
        if not TESSERACT_AVAILABLE:
            QMessageBox.critical(self, "Erro",
                "❌ pytesseract não instalado!\n\n"
                "Instale com: pip install pytesseract pillow\n"
                "E configure o caminho do Tesseract-OCR.")
            return

        if not GEMINI_AVAILABLE:
            QMessageBox.warning(self, "Aviso",
                "⚠️ google-generativeai não instalado!\n\n"
                "Tradução AI desabilitada. Apenas OCR será executado.\n"
                "Instale com: pip install google-generativeai")

        if not self.tiles_info:
            QMessageBox.warning(self, "Aviso", "Execute o SCAN primeiro!")
            return

        # Solicita configurações ao usuário
        config_dialog = QDialog(self)
        config_dialog.setWindowTitle("🤖 Configuração OCR + AI")
        config_dialog.setFixedSize(500, 300)
        config_dialog.setStyleSheet("background:#2b2b2b; color:white;")

        layout = QVBoxLayout(config_dialog)

        layout.addWidget(QLabel("📍 Tile Index (clique em um tile primeiro):"))
        tile_spin = QSpinBox()
        tile_spin.setMinimum(0)
        tile_spin.setMaximum(len(self.tiles_info) - 1)
        tile_spin.setValue(self.selected_tile_idx or 0)
        layout.addWidget(tile_spin)

        layout.addWidget(QLabel("🔑 Gemini API Key:"))
        api_input = QLineEdit()
        api_input.setPlaceholderText("Cole sua API key do Google AI Studio")
        api_input.setText(self.gemini_api_key or "")
        layout.addWidget(api_input)

        layout.addWidget(QLabel("🌍 Idioma Destino:"))
        lang_combo = QComboBox()
        lang_combo.addItems([
            "Portuguese (Brazil)",
            "Spanish",
            "French",
            "German",
            "Italian",
            "Japanese",
            "Korean"
        ])
        layout.addWidget(lang_combo)

        btn_process = QPushButton("🚀 PROCESSAR OCR + TRADUÇÃO")
        btn_process.setCursor(Qt.CursorShape.PointingHandCursor)  # Cursor de mãozinha
        btn_process.setStyleSheet("background:#e67e22; padding:10px; font-weight:bold;")
        btn_process.clicked.connect(config_dialog.accept)
        layout.addWidget(btn_process)

        if config_dialog.exec() != QDialog.DialogCode.Accepted:
            return

        # Captura configurações
        tile_idx = tile_spin.value()
        self.gemini_api_key = api_input.text().strip()
        self.target_language = lang_combo.currentText()

        if not self.gemini_api_key and GEMINI_AVAILABLE:
            QMessageBox.warning(self, "Aviso",
                "API Key não fornecida. Apenas OCR será executado.")

        # Executa pipeline
        try:
            self._execute_ocr_pipeline(tile_idx)
        except Exception as e:
            QMessageBox.critical(self, "Erro no Pipeline",
                f"Falha ao processar tile:\n\n{str(e)}\n\n"
                f"Detalhes: {type(e).__name__}")

    def _execute_ocr_pipeline(self, tile_idx):
        """Executa o pipeline OCR completo."""
        info = self.tiles_info[tile_idx]

        # ETAPA 1: Image Reconstruction
        pil_image = self._reconstruct_tile_image(info['pixels'])

        # ETAPA 2: Pre-processing
        processed_image = self._preprocess_for_ocr(pil_image)

        # ETAPA 3: OCR
        detected_text = self._perform_ocr(processed_image)

        if not detected_text.strip():
            QMessageBox.warning(self, "OCR Vazio",
                "Nenhum texto detectado no tile.\n"
                "O tile pode não conter texto legível ou está muito pequeno.")
            return

        # ETAPA 4: AI Translation
        translated_text = detected_text  # Default: sem tradução

        if GEMINI_AVAILABLE and self.gemini_api_key:
            translated_text = self._translate_with_gemini(
                detected_text,
                self.target_language
            )

        # ETAPA 5: Text Rendering
        rendered_image = self._render_text_on_tile(translated_text, pil_image.size)

        # ETAPA 6: Quantização
        new_pixels = self._quantize_image_to_4bpp(rendered_image)

        # ETAPA 7: In-place Reinsertion
        self._reinsert_tile_in_rom(info, new_pixels)

        # Atualiza preview na UI
        self._update_tile_preview(tile_idx, new_pixels)

        # Mostra resultado
        QMessageBox.information(self, "✅ Pipeline Concluído",
            f"🔍 OCR Detectado: '{detected_text}'\n"
            f"🌍 Traduzido para: '{translated_text}'\n"
            f"💾 Tile reinserido na ROM com sucesso!")

    def _reconstruct_tile_image(self, pixels):
        """Converte pixels 4bpp para PIL.Image."""
        from PIL import Image

        # Cria imagem 8x8 indexed color
        img = Image.new('P', (8, 8))

        # Define paleta (converte QColor.rgb() para RGB tuples)
        palette_flat = []
        for qcolor_rgb in self.palette:
            r = (qcolor_rgb >> 16) & 0xFF
            g = (qcolor_rgb >> 8) & 0xFF
            b = qcolor_rgb & 0xFF
            palette_flat.extend([r, g, b])

        # Preenche até 768 bytes (256 cores * 3)
        while len(palette_flat) < 768:
            palette_flat.append(0)

        img.putpalette(palette_flat)

        # Define pixels
        img.putdata(pixels)

        return img

    def _preprocess_for_ocr(self, pil_image):
        """Upscaling + Binarização para melhorar OCR."""
        from PIL import Image, ImageFilter

        # Upscale para 256x256 (32x maior)
        upscaled = pil_image.resize((256, 256), Image.Resampling.NEAREST)

        # Converte para RGB
        rgb_image = upscaled.convert('RGB')

        # Binarização (threshold adaptativo)
        grayscale = rgb_image.convert('L')
        threshold = 128
        binary = grayscale.point(lambda x: 255 if x > threshold else 0, mode='1')

        # Converte de volta para RGB para pytesseract
        final = binary.convert('RGB')

        return final

    def _perform_ocr(self, image):
        """Executa OCR com pytesseract."""
        import pytesseract

        # Configuração do Tesseract
        custom_config = r'--oem 3 --psm 7'  # PSM 7: linha única de texto

        text = pytesseract.image_to_string(
            image,
            config=custom_config,
            lang='eng'  # Idioma do texto original
        )

        return text.strip()

    def _translate_with_gemini(self, text, target_language):
        """Traduz texto usando Gemini API."""
        import google.generativeai as genai

        try:
            genai.configure(api_key=self.gemini_api_key)
            model = genai.GenerativeModel('gemini-1.5-flash')

            prompt = (
                f"Translate the following text to {target_language}. "
                f"Provide ONLY the translation, no explanations:\n\n{text}"
            )

            response = model.generate_content(prompt)
            return response.text.strip()

        except Exception as e:
            QMessageBox.warning(self, "Erro na Tradução",
                f"Falha ao traduzir com Gemini:\n{str(e)}\n\n"
                "Usando texto original.")
            return text

    def _render_text_on_tile(self, text, size=(8, 8)):
        """Renderiza texto traduzido em nova imagem."""
        from PIL import Image, ImageDraw, ImageFont

        # Cria imagem em escala maior para renderização
        scale = 32
        img = Image.new('RGB', (size[0] * scale, size[1] * scale), color=(0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Tenta carregar fonte apropriada
        try:
            # Tenta fontes comuns do Windows
            font = ImageFont.truetype("arial.ttf", 48)
        except:
            try:
                font = ImageFont.truetype("C:\\Windows\\Fonts\\arial.ttf", 48)
            except:
                # Fallback para fonte padrão
                font = ImageFont.load_default()

        # Centraliza texto
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        x = (img.width - text_width) // 2
        y = (img.height - text_height) // 2

        # Desenha texto em branco
        draw.text((x, y), text, fill=(255, 255, 255), font=font)

        # Redimensiona de volta para 8x8
        small = img.resize(size, Image.Resampling.LANCZOS)

        return small

    def _quantize_image_to_4bpp(self, pil_image):
        """Quantiza imagem RGB de volta para 4bpp usando paleta."""
        from PIL import Image

        # Converte para modo indexed usando paleta
        palette_img = Image.new('P', (1, 1))

        # Define paleta
        palette_flat = []
        for qcolor_rgb in self.palette:
            r = (qcolor_rgb >> 16) & 0xFF
            g = (qcolor_rgb >> 8) & 0xFF
            b = qcolor_rgb & 0xFF
            palette_flat.extend([r, g, b])

        while len(palette_flat) < 768:
            palette_flat.append(0)

        palette_img.putpalette(palette_flat)

        # Quantiza imagem para usar a paleta
        quantized = pil_image.quantize(palette=palette_img, dither=0)

        # Extrai pixels
        pixels = list(quantized.getdata())

        # Limita a 4bpp (0-15)
        pixels = [min(p, 15) for p in pixels]

        return pixels

    def _reinsert_tile_in_rom(self, info, new_pixels):
        """Reinsere tile na ROM binária (in-place)."""
        # Encode pixels para 4bpp bytes
        new_tile_bytes = encode_tile_4bpp(new_pixels)

        # Atualiza bloco descomprimido
        start = info['tile_idx'] * 32
        info['raw_block'][start:start+32] = new_tile_bytes

        # Recomprime bloco
        new_compressed = lz2_compress_optimal(info['raw_block'])

        # Escreve no arquivo ROM
        new_fn = self.rom_name.replace(".smc", "_OCR_TRANSLATED.smc")

        # Cria cópia se não existe
        if not os.path.exists(new_fn):
            shutil.copy(self.rom_name, new_fn)

        # Escreve dados comprimidos no offset original
        with open(new_fn, "r+b") as f:
            f.seek(info['block_offset'])
            f.write(new_compressed)

            # Padding se necessário
            orig_size = info["orig_size"]
            new_size = len(new_compressed)

            if new_size < orig_size:
                f.write(b'\xFF' * (orig_size - new_size))

    def _update_tile_preview(self, idx, pixels):
        """Atualiza preview visual do tile na UI."""
        img = QImage(8, 8, QImage.Format.Format_Indexed8)
        img.setColorTable(self.palette)

        for k in range(64):
            img.setPixel(k % 8, k // 8, pixels[k])

        self.grid.itemAt(idx).widget().setPixmap(
            QPixmap.fromImage(img).scaled(32, 32)
        )

        # Atualiza dados internos
        self.tiles_info[idx]['pixels'] = pixels

    # ========================================================================
    # MODERN TEXTURE SUPPORT (.DDS, .PNG, .TGA for Unity/Unreal Games)
    # ========================================================================

    def load_modern_texture(self):
        """
        Carrega texturas modernas de jogos indie (.DDS, .PNG, .TGA, .BMP).

        Fluxo:
        1. Abre arquivo com QFileDialog
        2. Carrega com PIL.Image
        3. Exibe preview na grid
        4. Habilita botão de OCR + Tradução
        """
        if not MODERN_TEXTURES_AVAILABLE:
            QMessageBox.warning(
                self,
                "Recurso Indisponível",
                "Pillow não está instalado.\n\nInstale com: pip install Pillow"
            )
            return

        from PyQt6.QtWidgets import QFileDialog

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Carregar Textura Moderna",
            "",
            "Textures (*.png *.tga *.bmp *.dds);;PNG Files (*.png);;TGA Files (*.tga);;DDS Files (*.dds);;All Files (*.*)"
        )

        if not file_path:
            return

        try:
            # Carrega textura com PIL
            from PIL import Image

            # DDS requer plugin específico ou conversão
            if file_path.lower().endswith('.dds'):
                try:
                    # Tenta carregar DDS diretamente
                    self.modern_texture = Image.open(file_path)
                except Exception:
                    QMessageBox.warning(
                        self,
                        "Formato DDS",
                        "DDS não suportado diretamente pelo Pillow.\n\n"
                        "Converta para PNG/TGA usando ferramentas como:\n"
                        "- GIMP\n"
                        "- ImageMagick\n"
                        "- Paint.NET"
                    )
                    return
            else:
                self.modern_texture = Image.open(file_path)

            # Converte para RGB se necessário (para compatibilidade)
            if self.modern_texture.mode not in ('RGB', 'RGBA'):
                self.modern_texture = self.modern_texture.convert('RGB')

            self.modern_texture_path = file_path
            self.modern_texture_format = os.path.splitext(file_path)[1].lower()

            # Exibe preview
            self._display_modern_texture_preview()

            # Log de sucesso
            width, height = self.modern_texture.size
            self.log_area.append(
                f"<span style='color:#2ecc71;'>[TEXTURA CARREGADA]</span> "
                f"{os.path.basename(file_path)} ({width}x{height}) {self.modern_texture.mode}"
            )

            QMessageBox.information(
                self,
                "Textura Carregada",
                f"Textura carregada com sucesso!\n\n"
                f"Arquivo: {os.path.basename(file_path)}\n"
                f"Resolução: {width}x{height}\n"
                f"Modo: {self.modern_texture.mode}\n\n"
                f"Use o botão '🤖 OCR + TRADUÇÃO AI' para processar."
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Erro ao Carregar Textura",
                f"Falha ao carregar textura:\n\n{str(e)}"
            )
            self.log_area.append(f"<span style='color:#e74c3c;'>[ERRO]</span> {str(e)}")

    def _display_modern_texture_preview(self):
        """
        Exibe preview da textura moderna na grid de tiles.
        Redimensiona para caber na área de visualização.
        """
        if not self.modern_texture:
            return

        from PyQt6.QtGui import QPixmap, QImage
        from PIL.ImageQt import ImageQt

        # Limpa grid existente
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Converte PIL.Image para QPixmap
        qim = ImageQt(self.modern_texture)
        pixmap = QPixmap.fromImage(QImage(qim))

        # Redimensiona para caber na grid (max 512x512)
        max_size = 512
        pixmap = pixmap.scaled(
            max_size, max_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        # Cria label para exibir
        from PyQt6.QtWidgets import QLabel
        preview_label = QLabel()
        preview_label.setPixmap(pixmap)
        preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_label.setStyleSheet("border: 2px solid #16a085; background: #1e1e1e;")

        self.grid.addWidget(preview_label, 0, 0)

    def process_modern_texture_ocr_translation(self):
        """
        Pipeline completo de OCR + AI Translation para texturas modernas.

        Fluxo:
        1. Valida textura carregada
        2. Pre-processamento (otimiza para OCR)
        3. OCR com pytesseract (modo multilinha)
        4. AI Translation com Gemini
        5. Renderiza texto traduzido na textura
        6. Salva textura modificada
        """
        if not self.modern_texture:
            QMessageBox.warning(
                self,
                "Nenhuma Textura Carregada",
                "Carregue uma textura moderna primeiro usando o botão '🎨 CARREGAR TEXTURA'."
            )
            return

        if not TESSERACT_AVAILABLE:
            QMessageBox.warning(
                self,
                "OCR Indisponível",
                "pytesseract não está instalado.\n\nInstale com: pip install pytesseract"
            )
            return

        if not GEMINI_AVAILABLE:
            QMessageBox.warning(
                self,
                "IA Indisponível",
                "google-generativeai não está instalado.\n\nInstale com: pip install google-generativeai"
            )
            return

        if not self.gemini_api_key:
            from PyQt6.QtWidgets import QInputDialog
            api_key, ok = QInputDialog.getText(
                self,
                "Gemini API Key",
                "Insira sua Gemini API Key:",
                echo=QInputDialog.EchoMode.Password
            )
            if ok and api_key:
                self.gemini_api_key = api_key
            else:
                return

        try:
            self.log_area.append("<span style='color:#3498db;'>[PIPELINE INICIADO]</span> Processando textura moderna...")

            # Etapa 1: Pre-processamento
            self.log_area.append("[1/5] Pre-processamento para OCR...")
            processed_image = self._preprocess_modern_texture_for_ocr(self.modern_texture)

            # Etapa 2: OCR
            self.log_area.append("[2/5] Executando OCR (pytesseract)...")
            extracted_text = self._perform_modern_texture_ocr(processed_image)

            if not extracted_text:
                QMessageBox.warning(
                    self,
                    "OCR Falhou",
                    "Nenhum texto foi detectado na textura.\n\n"
                    "Dicas:\n"
                    "- Verifique se a textura contém texto legível\n"
                    "- Textura pode estar em baixa resolução\n"
                    "- Tente aumentar o contraste da imagem"
                )
                return

            self.log_area.append(f"<span style='color:#2ecc71;'>[OCR SUCESSO]</span> Texto: \"{extracted_text[:50]}...\"")

            # Etapa 3: AI Translation
            self.log_area.append("[3/5] Traduzindo com Gemini AI...")
            translated_text = self._translate_with_gemini(extracted_text, self.target_language)
            self.log_area.append(f"<span style='color:#2ecc71;'>[TRADUÇÃO]</span> \"{translated_text[:50]}...\"")

            # Etapa 4: Renderização
            self.log_area.append("[4/5] Renderizando texto traduzido na textura...")
            modified_texture = self._render_text_on_modern_texture(
                self.modern_texture.copy(),
                extracted_text,
                translated_text
            )

            # Etapa 5: Salvamento
            self.log_area.append("[5/5] Salvando textura modificada...")
            output_path = self._save_modern_texture(modified_texture)

            self.log_area.append(f"<span style='color:#2ecc71;'>[CONCLUÍDO]</span> Textura salva: {output_path}")

            QMessageBox.information(
                self,
                "Tradução Concluída",
                f"Textura traduzida com sucesso!\n\n"
                f"Texto Original: {extracted_text[:100]}\n\n"
                f"Tradução: {translated_text[:100]}\n\n"
                f"Arquivo salvo em:\n{output_path}\n\n"
                f"Substitua o arquivo original no jogo para aplicar a tradução."
            )

            # Atualiza preview
            self.modern_texture = modified_texture
            self._display_modern_texture_preview()

        except Exception as e:
            self.log_area.append(f"<span style='color:#e74c3c;'>[ERRO]</span> {str(e)}")
            QMessageBox.critical(
                self,
                "Erro no Pipeline",
                f"Falha ao processar textura:\n\n{str(e)}"
            )

    def _preprocess_modern_texture_for_ocr(self, pil_image):
        """
        Otimiza textura moderna para OCR.

        Técnicas:
        - Conversão para escala de cinza
        - Aumento de contraste
        - Binarização adaptativa
        - Upscaling se resolução < 512px
        """
        from PIL import Image, ImageEnhance, ImageFilter

        # Converte para RGB se necessário
        if pil_image.mode != 'RGB':
            pil_image = pil_image.convert('RGB')

        # Upscaling se muito pequena
        width, height = pil_image.size
        if width < 512 or height < 512:
            scale_factor = max(512 / width, 512 / height)
            new_size = (int(width * scale_factor), int(height * scale_factor))
            pil_image = pil_image.resize(new_size, Image.Resampling.LANCZOS)

        # Conversão para escala de cinza
        grayscale = pil_image.convert('L')

        # Aumento de contraste
        enhancer = ImageEnhance.Contrast(grayscale)
        enhanced = enhancer.enhance(2.0)

        # Nitidez
        sharpened = enhanced.filter(ImageFilter.SHARPEN)

        # Binarização (threshold adaptativo)
        binary = sharpened.point(lambda x: 255 if x > 128 else 0, mode='L')

        return binary.convert('RGB')

    def _perform_modern_texture_ocr(self, pil_image):
        """
        Executa OCR em textura moderna (modo multilinha).

        Configuração:
        - PSM 3: Automatic page segmentation (multilinha)
        - OEM 3: Default (LSTM neural net)
        - Lang: eng (pode ser expandido)
        """
        import pytesseract

        # Configuração otimizada para texturas de jogos
        custom_config = r'--oem 3 --psm 3'

        text = pytesseract.image_to_string(
            pil_image,
            config=custom_config,
            lang='eng'
        )

        return text.strip()

    def _render_text_on_modern_texture(self, pil_image, original_text, translated_text):
        """
        Renderiza texto traduzido sobre a textura original.

        Estratégia:
        1. Detecta região do texto original (bounding box)
        2. Apaga região original (preenche com cor de fundo)
        3. Desenha texto traduzido centralizado
        4. Ajusta fonte dinamicamente para caber
        """
        from PIL import Image, ImageDraw, ImageFont
        import pytesseract

        # Detecta bounding boxes do texto
        data = pytesseract.image_to_data(pil_image, output_type=pytesseract.Output.DICT)

        # Encontra região total do texto
        x_coords = []
        y_coords = []
        widths = []
        heights = []

        for i, word in enumerate(data['text']):
            if word.strip():
                x_coords.append(data['left'][i])
                y_coords.append(data['top'][i])
                widths.append(data['width'][i])
                heights.append(data['height'][i])

        if not x_coords:
            # Se não detectou região, usa imagem inteira
            text_region = (0, 0, pil_image.width, pil_image.height)
        else:
            # Calcula bounding box total
            x_min = min(x_coords)
            y_min = min(y_coords)
            x_max = max(x_coords[i] + widths[i] for i in range(len(x_coords)))
            y_max = max(y_coords[i] + heights[i] for i in range(len(y_coords)))
            text_region = (x_min, y_min, x_max, y_max)

        # Cria cópia da imagem
        modified = pil_image.copy()
        draw = ImageDraw.Draw(modified)

        # Apaga região do texto original (preenche com cor predominante de fundo)
        # Para simplicidade, usa preto ou detecta cor média
        background_color = self._detect_background_color(pil_image, text_region)
        draw.rectangle(text_region, fill=background_color)

        # Calcula tamanho de fonte dinâmico
        region_width = text_region[2] - text_region[0]
        region_height = text_region[3] - text_region[1]
        font_size = max(12, min(region_height - 4, region_width // len(translated_text)))

        # Carrega fonte
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except:
            font = ImageFont.load_default()

        # Desenha texto traduzido centralizado
        bbox = draw.textbbox((0, 0), translated_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        x_centered = text_region[0] + (region_width - text_width) // 2
        y_centered = text_region[1] + (region_height - text_height) // 2

        # Cor do texto (branco se fundo escuro, preto se fundo claro)
        text_color = (255, 255, 255) if sum(background_color[:3]) < 384 else (0, 0, 0)

        draw.text((x_centered, y_centered), translated_text, fill=text_color, font=font)

        return modified

    def _detect_background_color(self, pil_image, text_region):
        """
        Detecta cor predominante de fundo na região do texto.

        Estratégia:
        - Amostra pixels ao redor da região de texto
        - Retorna média RGB
        """
        from PIL import Image

        # Amostra área ao redor (margem de 10px)
        x1, y1, x2, y2 = text_region
        margin = 10
        sample_region = (
            max(0, x1 - margin),
            max(0, y1 - margin),
            min(pil_image.width, x2 + margin),
            min(pil_image.height, y2 + margin)
        )

        cropped = pil_image.crop(sample_region)
        pixels = list(cropped.getdata())

        # Calcula média RGB
        if not pixels:
            return (0, 0, 0)

        avg_r = sum(p[0] for p in pixels) // len(pixels)
        avg_g = sum(p[1] for p in pixels) // len(pixels)
        avg_b = sum(p[2] for p in pixels) // len(pixels)

        return (avg_r, avg_g, avg_b)

    def _save_modern_texture(self, pil_image):
        """
        Salva textura moderna modificada.

        Formato:
        - Mantém formato original (.png, .tga, .bmp)
        - DDS é salvo como PNG (conversão manual necessária)
        - Adiciona sufixo '_TRANSLATED'
        """
        if not self.modern_texture_path:
            raise ValueError("Caminho da textura original não definido")

        # Gera nome do arquivo de saída
        base_name = os.path.splitext(self.modern_texture_path)[0]
        extension = self.modern_texture_format

        # DDS não suportado para escrita, converte para PNG
        if extension == '.dds':
            extension = '.png'

        output_path = f"{base_name}_TRANSLATED{extension}"

        # Salva imagem
        pil_image.save(output_path, quality=95)

        return output_path

    def retranslate(self):
        pass
