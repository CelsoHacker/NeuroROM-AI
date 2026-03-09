# -*- coding: utf-8 -*-
import sys
import struct
import shutil
import os
import heapq
import json
import base64
import zlib
import hashlib
import datetime
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


def detect_text_tiles(rom_data, charset_offset, tile_width=8, tile_height=8):
    """
    Detecta tiles com alta chance de conter texto legível.
    Heurística leve (densidade + transições + bounding box) para 8x8.
    """
    if not isinstance(rom_data, (bytes, bytearray)):
        return []
    if tile_width != 8 or tile_height != 8:
        return []

    start = max(0, int(charset_offset or 0))
    if start >= len(rom_data):
        return []

    # Assume 4bpp por padrão (32 bytes/tile), com fallback 2bpp.
    tile_size = 32
    max_tiles = min((len(rom_data) - start) // tile_size, 2048)
    out = []

    for tile_idx in range(max_tiles):
        off = start + (tile_idx * tile_size)
        raw = bytes(rom_data[off : off + tile_size])
        if len(raw) < tile_size:
            continue
        px = decode_tile_4bpp(raw)
        if not px or len(px) != 64:
            continue

        # Fallback 2bpp para tiles quase vazios em 4bpp.
        fg_4bpp = sum(1 for p in px if int(p) != 0)
        if fg_4bpp < 3:
            px = decode_tile_2bpp(raw[:16])
            if not px or len(px) != 64:
                continue

        ink = [1 if int(p) != 0 else 0 for p in px]
        fg = sum(ink)
        density = fg / 64.0
        if density < 0.06 or density > 0.72:
            continue

        # Transições horizontais/verticais (texto tende a ter várias bordas).
        trans = 0
        for y in range(8):
            row = ink[y * 8 : (y + 1) * 8]
            for x in range(7):
                if row[x] != row[x + 1]:
                    trans += 1
        for x in range(8):
            for y in range(7):
                if ink[(y * 8) + x] != ink[((y + 1) * 8) + x]:
                    trans += 1
        if trans < 10 or trans > 96:
            continue

        # Bounding box do "traço".
        coords = [(i % 8, i // 8) for i, val in enumerate(ink) if val]
        if not coords:
            continue
        xs = [c[0] for c in coords]
        ys = [c[1] for c in coords]
        bw = (max(xs) - min(xs) + 1)
        bh = (max(ys) - min(ys) + 1)
        if bw < 2 or bh < 3:
            continue

        # Score simples para ordenar.
        density_score = max(0.0, 1.0 - abs(density - 0.28) / 0.28)
        trans_score = min(1.0, trans / 48.0)
        bbox_score = min(1.0, (bw * bh) / 40.0)
        score = (density_score * 45.0) + (trans_score * 35.0) + (bbox_score * 20.0)
        if score < 28.0:
            continue

        out.append(
            {
                "tile_idx": int(tile_idx),
                "offset": int(off),
                "score": float(round(score, 2)),
                "density": float(round(density, 3)),
                "transitions": int(trans),
                "bbox": [int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))],
            }
        )

    out.sort(key=lambda row: (-float(row.get("score", 0.0)), int(row.get("tile_idx", 0))))
    return out


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
        self.rom_crc32 = None
        self.rom_size = None
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
        self._auto_scan_done_for = None
        self._auto_ocr_done_for = None
        self._auto_running = False

        # Lab results (OCR text collected, NOT for direct ROM reinsertion)
        self._lab_results = []
        self._lab_failures = []
        self._glyphmap = {}
        self._gfx_regions = []
        self._gfx_stats = {}
        self._needs_review_gfx = 0
        self._last_debug_pack = None
        self._gfx_auto_refine_enabled = True
        self._gfx_auto_refine_max_attempts = 8
        self._gfx_auto_refine_min_score = 72.0

        # Config toggles (defaults OFF per regras)
        self._auto_scan_on_open = False
        self._auto_ocr_on_open = False
        self._load_config_toggles()

        self.init_ui()

    def _load_config_toggles(self):
        """Carrega toggles do translator_config.json."""
        try:
            cfg_path = os.path.join(os.path.dirname(__file__), "..", "translator_config.json")
            if os.path.isfile(cfg_path):
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                self._auto_scan_on_open = bool(cfg.get("auto_scan_on_open", False))
                self._auto_ocr_on_open = bool(cfg.get("auto_ocr_on_open", False))
                self._gfx_auto_refine_enabled = bool(cfg.get("gfx_auto_refine_enabled", True))
                self._gfx_auto_refine_max_attempts = max(
                    1,
                    int(cfg.get("gfx_auto_refine_max_attempts", 8) or 8),
                )
                self._gfx_auto_refine_min_score = float(
                    cfg.get("gfx_auto_refine_min_score", 72.0) or 72.0
                )
        except Exception:
            pass

    def _log(self, msg: str):
        """Log seguro: usa status bar local + parent.log() se disponível."""
        plain = msg.replace("<span style='color:#3498db;'>", "").replace(
            "<span style='color:#2ecc71;'>", "").replace(
            "<span style='color:#e74c3c;'>", "").replace("</span>", "")
        self.status.setText(plain[:200])
        parent = self.parent()
        if parent and hasattr(parent, "log"):
            try:
                parent.log(plain)
            except Exception:
                pass

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

        btn_font_editor = QPushButton("FONT EDITOR (PT-BR)")
        btn_font_editor.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_font_editor.clicked.connect(self.open_font_editor)
        btn_font_editor.setStyleSheet("background:#8e44ad; color:white; padding:8px; font-weight:bold;")
        btn_font_editor.setToolTip("Editar/criar tiles de caracteres acentuados PT-BR na ROM")

        top.addWidget(QLabel("PERFIL:"))
        top.addWidget(self.combo)
        top.addWidget(self.btn)
        top.addWidget(btn_font)
        top.addWidget(btn_font_editor)
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

        scan_st = "ON" if self._auto_scan_on_open else "OFF"
        ocr_st = "ON" if self._auto_ocr_on_open else "OFF"
        self.status = QLabel(f"Pronto. | auto_scan={scan_st} | auto_ocr={ocr_st}")
        l.addWidget(self.status)

    def set_rom_path(self, path):
        if path:
            with open(path, "rb") as f:
                raw = f.read()
                self.rom_data = bytearray(raw)
                self.rom_name = path
                self.rom_crc32 = format(zlib.crc32(raw) & 0xFFFFFFFF, "08X")
                self.rom_size = len(raw)
                # Reseta flags para nova ROM
                self._auto_scan_done_for = None
                self._auto_ocr_done_for = None
                self._lab_results = []
                self._lab_failures = []
                self._glyphmap = {}
                self.status.setText(
                    f"ROM carregada | CRC32={self.rom_crc32} | ROM_SIZE={self.rom_size}"
                )

    def auto_scan_and_ocr(self):
        """Executa auto-scan e auto-OCR respeitando config toggles."""
        if self._auto_running:
            return
        if not self.rom_data or not self.rom_name:
            self.status.setText("Carregue uma ROM para iniciar o scan.")
            return

        # Respeita config toggles (padrão OFF)
        if not self._auto_scan_on_open and not self._auto_ocr_on_open:
            self.status.setText(
                f"CRC32={self.rom_crc32 or 'N/A'} | auto_scan=OFF | auto_ocr=OFF"
            )
            return

        self._auto_running = True
        try:
            if self._auto_scan_on_open and self._auto_scan_done_for != self.rom_name:
                self.status.setText("Auto-scan em andamento...")
                self.scan()
                self._auto_scan_done_for = self.rom_name

            if self._auto_ocr_on_open and self._auto_ocr_done_for != self.rom_name:
                if self.modern_texture is not None or self.tiles_info:
                    if not TESSERACT_AVAILABLE:
                        self.status.setText("OCR indisponivel (instale pytesseract/pillow).")
                        return
                    self.status.setText("Auto-OCR em andamento...")
                    self.intelligent_ocr_translation()
                    self._auto_ocr_done_for = self.rom_name

            scan_st = "ON" if self._auto_scan_on_open else "OFF"
            ocr_st = "ON" if self._auto_ocr_on_open else "OFF"
            self.status.setText(
                f"CRC32={self.rom_crc32 or 'N/A'} | auto_scan={scan_st} | auto_ocr={ocr_st}"
            )
        finally:
            self._auto_running = False

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

        crc_tag = self.rom_crc32 or "N/A"
        self.status.setText(f"CRC32={crc_tag} | Fonte: {total} tiles (2bpp) offset 0x8000")

    def open_font_editor(self):
        """Abre o Font Editor PT-BR para a ROM carregada."""
        if not self.rom_data or not self.rom_name:
            QMessageBox.warning(self, "Aviso", "Carregue uma ROM primeiro!")
            return
        try:
            from interface.gui_tabs.font_editor import FontEditorDialog
            font_offset = 0x008000
            bpp = 1
            dialog = FontEditorDialog(
                rom_path=self.rom_name,
                font_offset=font_offset,
                bpp=bpp,
                num_tiles=256,
                rom_crc32=self.rom_crc32 or "",
                parent=self,
            )
            dialog.exec()
        except Exception as e:
            QMessageBox.warning(self, "Erro", f"Font Editor: {e}")

    def _load_profile_ranges(self):
        """Tenta carregar ranges do profile para o CRC32 atual."""
        if not self.rom_crc32:
            return None
        profiles_dir = os.path.join(os.path.dirname(__file__), "..", "..", "profiles", "sms")
        profile_path = os.path.join(profiles_dir, f"{self.rom_crc32}.json")
        if os.path.isfile(profile_path):
            try:
                with open(profile_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return None

    def scan(self):
        if not self.rom_data:
            self.status.setText("Sem ROM carregada. Carregue antes de scanear.")
            return

        for i in reversed(range(self.grid.count())):
            self.grid.itemAt(i).widget().setParent(None)
        self.tiles_info = []

        # Tenta obter ranges do profile (controlado)
        profile = self._load_profile_ranges()
        scan_source = "profile"
        if profile and profile.get("tile_offsets"):
            offsets = [int(o, 16) if isinstance(o, str) else int(o)
                       for o in profile["tile_offsets"]]
        else:
            # Heuristica interna LZ2 (ranges controladas, nao scan cego)
            offsets = [0x008000, 0x008200, 0x010000, 0x018000, 0x020000, 0x040000, 0x042000]
            scan_source = "heuristic_lz2"

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

        crc_tag = self.rom_crc32 or "N/A"
        self.status.setText(
            f"CRC32={crc_tag} | {total} tiles | source={scan_source}"
        )

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
                    msg.setWindowTitle("Arquivo Maior")
                    msg.setText(f"Original: {orig_size} | Novo: {new_size}\nDeseja EXPANDIR a ROM?")
                    msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                    if msg.exec() == QMessageBox.StandardButton.Yes:
                        with open(self.rom_name, 'rb') as f:
                            full_rom = bytearray(f.read())
                        new_offset = len(full_rom)
                        full_rom.extend(new_compressed)

                        rom_dir = os.path.dirname(self.rom_name)
                        rom_ext = os.path.splitext(self.rom_name)[1]
                        crc_tag = self.rom_crc32 or "UNKNOWN"
                        expanded_fn = os.path.join(rom_dir, f"{crc_tag}_EXPANDED{rom_ext}")
                        with open(expanded_fn, 'wb') as f:
                            f.write(full_rom)

                        QMessageBox.information(self, "ROM Expandida",
                            f"Offset: {hex(new_offset)}\nCRC32: {crc_tag}")
                    return

                rom_dir = os.path.dirname(self.rom_name)
                rom_ext = os.path.splitext(self.rom_name)[1]
                crc_tag = self.rom_crc32 or "UNKNOWN"
                new_fn = os.path.join(rom_dir, f"{crc_tag}_MOD{rom_ext}")
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
            self._log(
                "<span style='color:#3498db;'>[MODO DETECTADO]</span> Textura Moderna - "
                "Usando pipeline OCR para texturas completas"
            )
            self.process_modern_texture_ocr_translation()
            return

        # Prioridade 2: Tile selecionado (modo retro)
        if self.selected_tile_idx is not None and self.tiles_info:
            self._log(
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
        """Executa o pipeline OCR: extrai texto e coleta para export (sem reinserção direta)."""
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
                "O tile pode nao conter texto legivel ou esta muito pequeno.")
            return

        # ETAPA 4: AI Translation (opcional)
        translated_text = detected_text
        if GEMINI_AVAILABLE and self.gemini_api_key:
            translated_text = self._translate_with_gemini(
                detected_text,
                self.target_language
            )

        # Registra glyphmap entry (tile_idx -> detected char)
        if len(detected_text.strip()) == 1:
            tile_key = f"0x{info['block_offset']:06X}:{info['tile_idx']}"
            self._glyphmap[tile_key] = detected_text.strip()

        # OCR sem offset ROM preciso -> entra em pure_text com no_offset=true
        # NAO entra em reinsertion_mapping (regra obrigatoria)
        lab_entry = {
            "original": detected_text,
            "translated": translated_text,
            "source": "lab_ocr",
            "no_offset": True,
            "block_offset": f"0x{info['block_offset']:06X}",
            "tile_idx": info["tile_idx"],
        }
        self._lab_results.append(lab_entry)

        # Mostra resultado (sem reinserção)
        QMessageBox.information(self, "OCR Concluido",
            f"OCR: '{detected_text}'\n"
            f"Traduzido: '{translated_text}'\n\n"
            f"Resultado salvo em lab_results (source=lab_ocr, no_offset=true).\n"
            f"Use 'Exportar' para gerar os 4 arquivos obrigatorios.")

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
        """Reinsere tile na ROM binaria (in-place). Usa CRC32 no nome de saida."""
        new_tile_bytes = encode_tile_4bpp(new_pixels)

        start = info['tile_idx'] * 32
        info['raw_block'][start:start+32] = new_tile_bytes

        new_compressed = lz2_compress_optimal(info['raw_block'])

        rom_dir = os.path.dirname(self.rom_name)
        rom_ext = os.path.splitext(self.rom_name)[1]
        crc_tag = self.rom_crc32 or "UNKNOWN"
        new_fn = os.path.join(rom_dir, f"{crc_tag}_OCR_TRANSLATED{rom_ext}")

        if not os.path.exists(new_fn):
            shutil.copy(self.rom_name, new_fn)

        with open(new_fn, "r+b") as f:
            f.seek(info['block_offset'])
            f.write(new_compressed)

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
            self._log(
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
            self._log(f"<span style='color:#e74c3c;'>[ERRO]</span> {str(e)}")

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
            self._log("<span style='color:#3498db;'>[PIPELINE INICIADO]</span> Processando textura moderna...")

            # Etapa 1: Pre-processamento
            self._log("[1/5] Pre-processamento para OCR...")
            processed_image = self._preprocess_modern_texture_for_ocr(self.modern_texture)

            # Etapa 2: OCR
            self._log("[2/5] Executando OCR (pytesseract)...")
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

            self._log(f"<span style='color:#2ecc71;'>[OCR SUCESSO]</span> Texto: \"{extracted_text[:50]}...\"")

            # Etapa 3: AI Translation
            self._log("[3/5] Traduzindo com Gemini AI...")
            translated_text = self._translate_with_gemini(extracted_text, self.target_language)
            self._log(f"<span style='color:#2ecc71;'>[TRADUÇÃO]</span> \"{translated_text[:50]}...\"")

            # Etapa 4: Renderização
            self._log("[4/5] Renderizando texto traduzido na textura...")
            refine = self._auto_refine_modern_texture_translation(
                self.modern_texture,
                extracted_text,
                translated_text,
                max_attempts=self._gfx_auto_refine_max_attempts,
            )
            modified_texture = refine.get("image")
            best_score = float(refine.get("score", 0.0) or 0.0)
            best_text = str(refine.get("text", "") or translated_text)
            if modified_texture is None:
                modified_texture = self._render_text_on_modern_texture(
                    self.modern_texture.copy(),
                    extracted_text,
                    translated_text
                )
            self._log(
                f"[AUTO-REFINE] score={best_score:.1f} | tentativas={int(refine.get('attempts', 0) or 0)}"
            )

            # Etapa 5: Salvamento
            self._log("[5/5] Salvando textura modificada...")
            output_path = self._save_modern_texture(modified_texture)

            self._log(f"<span style='color:#2ecc71;'>[CONCLUÍDO]</span> Textura salva: {output_path}")

            QMessageBox.information(
                self,
                "Tradução Concluída",
                f"Textura traduzida com sucesso!\n\n"
                f"Texto Original: {extracted_text[:100]}\n\n"
                f"Tradução: {best_text[:100]}\n\n"
                f"Arquivo salvo em:\n{output_path}\n\n"
                f"Substitua o arquivo original no jogo para aplicar a tradução."
            )

            # Atualiza preview
            self.modern_texture = modified_texture
            self._display_modern_texture_preview()

        except Exception as e:
            self._log(f"<span style='color:#e74c3c;'>[ERRO]</span> {str(e)}")
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

    def _normalize_text_for_match(self, text: str) -> str:
        """Normaliza texto para comparação robusta OCR x alvo."""
        import re
        import unicodedata

        value = str(text or "")
        value = unicodedata.normalize("NFD", value)
        value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
        value = value.lower()
        value = re.sub(r"[^a-z0-9\s]", " ", value)
        value = re.sub(r"\s+", " ", value).strip()
        return value

    def _score_ocr_match(self, expected_text: str, ocr_text: str) -> float:
        """Score 0-100 para medir qualidade visual usando OCR de validação."""
        from difflib import SequenceMatcher

        expected = self._normalize_text_for_match(expected_text)
        observed = self._normalize_text_for_match(ocr_text)
        if not expected or not observed:
            return 0.0

        seq = SequenceMatcher(None, expected, observed).ratio()
        exp_tokens = set(expected.split())
        obs_tokens = set(observed.split())
        token_overlap = (
            len(exp_tokens & obs_tokens) / max(1, len(exp_tokens))
            if exp_tokens else 0.0
        )
        len_ratio = min(len(expected), len(observed)) / max(1, max(len(expected), len(observed)))

        score = (seq * 0.60) + (token_overlap * 0.25) + (len_ratio * 0.15)
        return max(0.0, min(100.0, score * 100.0))

    def _truncate_text_to_width(self, draw, text: str, font, max_width: int) -> str:
        """Trunca texto com reticências para caber na largura alvo."""
        if not text:
            return ""
        if draw.textbbox((0, 0), text, font=font)[2] <= max_width:
            return text

        ellipsis = "..."
        value = text
        while value and draw.textbbox((0, 0), value + ellipsis, font=font)[2] > max_width:
            value = value[:-1]
        return (value + ellipsis).strip() if value else ellipsis

    def _wrap_text_to_box(self, draw, text: str, font, max_width: int, max_lines: int = 3) -> str:
        """Quebra texto em múltiplas linhas para caber no box."""
        value = str(text or "").strip()
        if not value:
            return ""
        if draw.textbbox((0, 0), value, font=font)[2] <= max_width:
            return value

        words = value.split()
        if len(words) <= 1:
            return self._truncate_text_to_width(draw, value, font, max_width)

        lines = []
        current = words[0]
        for word in words[1:]:
            probe = f"{current} {word}"
            if draw.textbbox((0, 0), probe, font=font)[2] <= max_width:
                current = probe
            else:
                lines.append(current)
                current = word
        lines.append(current)

        if len(lines) > max_lines:
            lines = lines[:max_lines]
            lines[-1] = self._truncate_text_to_width(draw, lines[-1], font, max_width)

        return "\n".join(lines)

    def _build_graphics_text_candidates(self, original_text: str, translated_text: str) -> list[str]:
        """Gera variações de texto para tentativa automática de encaixe visual."""
        import re

        original = str(original_text or "").strip()
        translated = str(translated_text or "").strip()
        if not translated:
            return [original] if original else [""]

        cleaned = re.sub(r"\s+", " ", translated).strip()
        candidates = [cleaned]

        # Variação com quebra no meio para textos longos.
        if " " in cleaned and len(cleaned) >= 16:
            mid = len(cleaned) // 2
            left_space = cleaned.rfind(" ", 0, mid)
            right_space = cleaned.find(" ", mid)
            split_at = left_space if left_space > 0 else right_space
            if split_at and split_at > 0:
                two_lines = cleaned[:split_at].strip() + "\n" + cleaned[split_at + 1 :].strip()
                candidates.append(two_lines)

        # Variação compacta para telas apertadas.
        compact = cleaned
        replacements = {
            " para ": " p/ ",
            " você ": " vc ",
            " vocês ": " vcs ",
            " continuar ": " cont. ",
            " opções ": " opç. ",
            " e ": " & ",
        }
        for src, dst in replacements.items():
            compact = compact.replace(src, dst)
        compact = re.sub(r"\s+", " ", compact).strip()
        if compact and compact != cleaned:
            candidates.append(compact)

        # Dedupe preservando ordem.
        dedup = []
        seen = set()
        for item in candidates:
            key = item.strip()
            if key and key not in seen:
                dedup.append(key)
                seen.add(key)
        return dedup or [cleaned]

    def _auto_refine_modern_texture_translation(
        self,
        base_image,
        original_text: str,
        translated_text: str,
        max_attempts: int = 8,
    ) -> dict:
        """Tenta múltiplos renders e escolhe automaticamente o melhor por score OCR."""
        best = {
            "image": None,
            "text": str(translated_text or "").strip(),
            "ocr_back": "",
            "score": 0.0,
            "attempts": 0,
        }

        text_candidates = self._build_graphics_text_candidates(original_text, translated_text)
        render_profiles = [
            (1.00, 2, 3),
            (0.92, 2, 3),
            (0.84, 1, 3),
            (0.76, 1, 4),
            (0.68, 0, 4),
        ]

        combos = []
        for text in text_candidates:
            for font_scale, padding, max_lines in render_profiles:
                combos.append((text, font_scale, padding, max_lines))
        combos = combos[: max(1, int(max_attempts))]

        for attempt_idx, (candidate_text, font_scale, padding, max_lines) in enumerate(combos, start=1):
            try:
                candidate_image = self._render_text_on_modern_texture(
                    base_image.copy(),
                    original_text,
                    candidate_text,
                    font_scale=font_scale,
                    padding=padding,
                    max_lines=max_lines,
                )
            except Exception:
                continue

            ocr_back = ""
            score = 0.0
            if TESSERACT_AVAILABLE:
                try:
                    pre = self._preprocess_modern_texture_for_ocr(candidate_image)
                    ocr_back = self._perform_modern_texture_ocr(pre)
                    score = self._score_ocr_match(candidate_text, ocr_back)
                except Exception:
                    ocr_back = ""
                    score = 0.0

            if best["image"] is None or score >= float(best.get("score", 0.0)):
                best = {
                    "image": candidate_image,
                    "text": candidate_text,
                    "ocr_back": ocr_back,
                    "score": float(score),
                    "attempts": attempt_idx,
                }

            # Critério de parada: score já muito bom
            if score >= 92.0:
                break

        return best

    def _render_text_on_modern_texture(
        self,
        pil_image,
        original_text,
        translated_text,
        font_scale: float = 1.0,
        padding: int = 2,
        max_lines: int = 3,
    ):
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
        region_width = max(1, text_region[2] - text_region[0])
        region_height = max(1, text_region[3] - text_region[1])
        text_payload = str(translated_text or "").strip() or str(original_text or "").strip()
        base_font_size = max(
            10,
            min(max(10, region_height - 4), max(8, region_width // max(1, len(text_payload))))
        )
        font_size = max(8, int(base_font_size * max(0.45, min(float(font_scale), 1.4))))

        # Carrega fonte
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except:
            font = ImageFont.load_default()

        # Ajusta texto para caber no box.
        box_width = max(8, region_width - (2 * max(0, int(padding))))
        wrapped_text = self._wrap_text_to_box(
            draw,
            text_payload,
            font,
            box_width,
            max_lines=max(1, int(max_lines)),
        )
        lines = wrapped_text.split("\n") if wrapped_text else [text_payload]

        line_bboxes = [draw.textbbox((0, 0), ln, font=font) for ln in lines]
        line_widths = [(bb[2] - bb[0]) for bb in line_bboxes]
        line_heights = [(bb[3] - bb[1]) for bb in line_bboxes]
        line_spacing = max(1, font_size // 10)
        text_width = max(line_widths) if line_widths else 0
        text_height = sum(line_heights) + (line_spacing * max(0, len(lines) - 1))

        x_centered = text_region[0] + max(0, int(padding)) + ((box_width - text_width) // 2)
        y_centered = text_region[1] + ((region_height - text_height) // 2)

        # Cor do texto (branco se fundo escuro, preto se fundo claro)
        text_color = (255, 255, 255) if sum(background_color[:3]) < 384 else (0, 0, 0)
        shadow_color = (0, 0, 0) if text_color == (255, 255, 255) else (255, 255, 255)

        # Renderiza linha a linha com sombra de 1px para legibilidade.
        cursor_y = y_centered
        for line_idx, line in enumerate(lines):
            lw = line_widths[line_idx] if line_idx < len(line_widths) else 0
            lx = text_region[0] + max(0, int(padding)) + ((box_width - lw) // 2)
            draw.text((lx + 1, cursor_y + 1), line, fill=shadow_color, font=font)
            draw.text((lx, cursor_y), line, fill=text_color, font=font)
            lh = line_heights[line_idx] if line_idx < len(line_heights) else font_size
            cursor_y += lh + line_spacing

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

    # ========================================================================
    # AUTO GRAPHICS PIPELINE (headless)
    # ========================================================================

    def _get_out_dir(self) -> str | None:
        """Resolve pasta neutra de saída: out/{CRC32}_*"""
        if not self.rom_name or not self.rom_crc32:
            return None
        rom_dir = os.path.dirname(self.rom_name)
        out_dir = os.path.join(rom_dir, "out")
        os.makedirs(out_dir, exist_ok=True)
        return out_dir

    def _collect_modern_texture_regions(self, pil_image):
        """Extrai regiões de texto e confidência via pytesseract."""
        import pytesseract
        data = pytesseract.image_to_data(pil_image, output_type=pytesseract.Output.DICT)
        regions = []
        for i, word in enumerate(data.get("text", [])):
            if not word or not str(word).strip():
                continue
            try:
                conf = float(data.get("conf", [0])[i])
            except Exception:
                conf = 0.0
            region = {
                "text": str(word).strip(),
                "conf": conf,
                "left": int(data.get("left", [0])[i]),
                "top": int(data.get("top", [0])[i]),
                "width": int(data.get("width", [0])[i]),
                "height": int(data.get("height", [0])[i]),
            }
            regions.append(region)
        return regions

    def _collect_tile_regions(self, max_tiles: int = 64):
        """Gera regiões básicas a partir de tiles (sem OCR)."""
        regions = []
        if not self.tiles_info:
            return regions
        limit = min(len(self.tiles_info), max_tiles)
        for i in range(limit):
            info = self.tiles_info[i]
            regions.append(
                {
                    "tile_idx": info.get("tile_idx", i),
                    "block_offset": info.get("block_offset"),
                    "text": "",
                    "conf": 0.0,
                }
            )
        return regions

    def _build_block_canvas_from_tiles(self, block_offset: int):
        """Monta canvas RGB de um bloco LZ2 usando tiles 8x8 (layout 16 colunas)."""
        from PIL import Image

        block_tiles = [t for t in self.tiles_info if int(t.get("block_offset", -1)) == int(block_offset)]
        if not block_tiles:
            return None

        block_tiles = sorted(block_tiles, key=lambda t: int(t.get("tile_idx", 0)))
        cols = 16
        rows = max(1, (len(block_tiles) + cols - 1) // cols)
        canvas = Image.new("RGB", (cols * 8, rows * 8), color=(0, 0, 0))

        for idx, info in enumerate(block_tiles):
            try:
                tile_img = self._reconstruct_tile_image(info.get("pixels", []))
                tile_rgb = tile_img.convert("RGB")
            except Exception:
                continue
            tx = (idx % cols) * 8
            ty = (idx // cols) * 8
            canvas.paste(tile_rgb, (tx, ty))

        return {
            "canvas": canvas,
            "tiles": block_tiles,
            "cols": cols,
            "rows": rows,
            "block_offset": int(block_offset),
        }

    def _extract_text_from_block_canvas(self, canvas_image):
        """Extrai texto OCR e média de confiança de um canvas de bloco retro."""
        if canvas_image is None or not TESSERACT_AVAILABLE:
            return "", 0.0

        try:
            pre = self._preprocess_modern_texture_for_ocr(canvas_image)
            text = self._perform_modern_texture_ocr(pre)
            regions = self._collect_modern_texture_regions(pre)
            if regions:
                avg_conf = sum(float(r.get("conf", 0.0) or 0.0) for r in regions) / max(1, len(regions))
            else:
                avg_conf = 0.0
            return str(text or "").strip(), float(avg_conf)
        except Exception:
            return "", 0.0

    def _apply_canvas_back_to_block_tiles(self, block_data: dict, rendered_canvas):
        """Converte canvas renderizado em tiles 4bpp e atualiza raw_block do bloco."""
        if not block_data or rendered_canvas is None:
            return False, "block_or_canvas_missing"

        try:
            tiles = block_data.get("tiles", [])
            if not tiles:
                return False, "tiles_missing"

            # Usa uma cópia única para manter consistência do bloco inteiro.
            raw_block = bytearray(tiles[0].get("raw_block", b""))
            if not raw_block:
                return False, "raw_block_missing"

            for idx, info in enumerate(tiles):
                tx = (idx % int(block_data.get("cols", 16))) * 8
                ty = (idx // int(block_data.get("cols", 16))) * 8
                tile_rgb = rendered_canvas.crop((tx, ty, tx + 8, ty + 8))
                q_pixels = self._quantize_image_to_4bpp(tile_rgb)
                if len(q_pixels) != 64:
                    continue
                info["pixels"] = list(q_pixels)
                tile_bytes = encode_tile_4bpp(q_pixels)
                tile_idx = int(info.get("tile_idx", 0))
                start = tile_idx * 32
                if start + 32 > len(raw_block):
                    continue
                raw_block[start:start + 32] = tile_bytes
                info["raw_block"] = raw_block

            return True, raw_block
        except Exception as exc:
            return False, f"apply_canvas_error: {exc}"

    def _write_auto_gfx_block_rom(self, block_data: dict, raw_block: bytes):
        """Grava bloco recompresso em ROM de saída automática."""
        if not self.rom_name or not block_data:
            return False, "rom_missing", None

        try:
            new_compressed = lz2_compress_optimal(bytes(raw_block))
            orig_size = int(block_data["tiles"][0].get("orig_size", 0) or 0)
            if orig_size <= 0:
                return False, "orig_size_invalid", None
            if len(new_compressed) > orig_size:
                return False, f"expanded_block_{len(new_compressed)}>{orig_size}", None

            rom_dir = os.path.dirname(self.rom_name)
            rom_ext = os.path.splitext(self.rom_name)[1]
            crc_tag = self.rom_crc32 or "UNKNOWN"
            out_path = os.path.join(rom_dir, f"{crc_tag}_AUTO_GFX{rom_ext}")
            if not os.path.exists(out_path):
                shutil.copy(self.rom_name, out_path)

            with open(out_path, "r+b") as f:
                f.seek(int(block_data.get("block_offset", 0)))
                f.write(new_compressed)
                pad = orig_size - len(new_compressed)
                if pad > 0:
                    f.write(b"\xFF" * pad)

            return True, "", out_path
        except Exception as exc:
            return False, str(exc), None

    def auto_graphics_pipeline(
        self,
        api_key: str = "",
        target_language: str = "Portuguese (Brazil)",
        confidence_threshold: float = 70.0,
    ) -> dict:
        """Pipeline gráfico automático sem interação do usuário."""
        self._gfx_regions = []
        self._gfx_stats = {
            "gfx_total_regions": 0,
            "gfx_translated_regions": 0,
            "gfx_skipped_low_confidence": 0,
            "gfx_overflow": 0,
            "needs_review_gfx": 0,
            "gfx_auto_refine_attempts": 0,
            "gfx_auto_refine_best_score": 0.0,
            "gfx_auto_refine_best_ocr": "",
        }
        self._needs_review_gfx = 0

        if not self.rom_crc32:
            return self._gfx_stats

        # Modern texture OCR
        if self.modern_texture is not None:
            if not TESSERACT_AVAILABLE:
                self._needs_review_gfx += 1
                self._gfx_stats["needs_review_gfx"] = self._needs_review_gfx
                return self._gfx_stats
            regions = self._collect_modern_texture_regions(self.modern_texture)
            self._gfx_regions = regions
            self._gfx_stats["gfx_total_regions"] = len(regions)
            avg_conf = 0.0
            if regions:
                avg_conf = sum(r.get("conf", 0.0) for r in regions) / max(1, len(regions))

            if avg_conf < confidence_threshold:
                self._gfx_stats["gfx_skipped_low_confidence"] = len(regions)
                self._needs_review_gfx = len(regions)
            else:
                # Tenta traduzir o texto completo
                text_full = " ".join(r.get("text", "") for r in regions).strip()
                translated_text = ""
                translated_ok = False
                if api_key and GEMINI_AVAILABLE and text_full:
                    self.gemini_api_key = api_key
                    translated_text = self._translate_with_gemini(text_full, target_language)
                    translated_ok = bool(translated_text)
                if translated_ok:
                    try:
                        chosen_text = translated_text
                        modified = None

                        if self._gfx_auto_refine_enabled:
                            best = self._auto_refine_modern_texture_translation(
                                self.modern_texture,
                                text_full,
                                translated_text,
                                max_attempts=self._gfx_auto_refine_max_attempts,
                            )
                            self._gfx_stats["gfx_auto_refine_attempts"] = int(best.get("attempts", 0) or 0)
                            self._gfx_stats["gfx_auto_refine_best_score"] = float(best.get("score", 0.0) or 0.0)
                            self._gfx_stats["gfx_auto_refine_best_ocr"] = str(best.get("ocr_back", "") or "")
                            if best.get("image") is not None:
                                modified = best.get("image")
                                chosen_text = str(best.get("text") or translated_text)
                        if modified is None:
                            modified = self._render_text_on_modern_texture(
                                self.modern_texture.copy(), text_full, translated_text
                            )

                        self.modern_texture = modified
                        self._gfx_stats["gfx_translated_regions"] = len(regions)
                        for r in self._gfx_regions:
                            r["translated"] = chosen_text
                            r["auto_refine_score"] = float(self._gfx_stats.get("gfx_auto_refine_best_score", 0.0) or 0.0)
                            r["auto_refine_ocr"] = str(self._gfx_stats.get("gfx_auto_refine_best_ocr", "") or "")

                        # Se score ficar baixo, aplica mesmo assim mas sinaliza revisão.
                        if self._gfx_auto_refine_enabled:
                            best_score = float(self._gfx_stats.get("gfx_auto_refine_best_score", 0.0) or 0.0)
                            if best_score < float(self._gfx_auto_refine_min_score):
                                self._needs_review_gfx = len(regions)
                    except Exception:
                        self._needs_review_gfx = len(regions)
                else:
                    self._needs_review_gfx = len(regions)
            self._gfx_stats["needs_review_gfx"] = self._needs_review_gfx

        # Retro tiles (sem OCR automático)
        elif self.tiles_info:
            regions = self._collect_tile_regions()
            self._gfx_regions = regions
            self._gfx_stats["gfx_total_regions"] = len(regions)

            # FASE 2: tenta pipeline automático por bloco de tiles retro
            if not TESSERACT_AVAILABLE:
                self._needs_review_gfx = len(regions)
                self._gfx_stats["needs_review_gfx"] = self._needs_review_gfx
            else:
                block_offsets = sorted({int(t.get("block_offset", -1)) for t in self.tiles_info if t.get("block_offset") is not None})
                best_block = None
                best_text = ""
                best_conf = 0.0

                for off in block_offsets[:16]:
                    block_data = self._build_block_canvas_from_tiles(off)
                    if not block_data:
                        continue
                    text, conf = self._extract_text_from_block_canvas(block_data["canvas"])
                    text_norm = self._normalize_text_for_match(text)
                    if len(text_norm) < 4:
                        continue
                    # Prioriza mais texto útil, depois confiança OCR.
                    score = (len(text_norm) * 1.0) + (float(conf) * 0.5)
                    if not best_block or score > ((len(self._normalize_text_for_match(best_text)) * 1.0) + (best_conf * 0.5)):
                        best_block = block_data
                        best_text = text
                        best_conf = float(conf)

                if best_block and best_text and api_key and GEMINI_AVAILABLE:
                    self.gemini_api_key = api_key
                    translated_text = self._translate_with_gemini(best_text, target_language)
                    if translated_text:
                        refine = self._auto_refine_modern_texture_translation(
                            best_block["canvas"],
                            best_text,
                            translated_text,
                            max_attempts=self._gfx_auto_refine_max_attempts,
                        )
                        self._gfx_stats["gfx_auto_refine_attempts"] = int(refine.get("attempts", 0) or 0)
                        self._gfx_stats["gfx_auto_refine_best_score"] = float(refine.get("score", 0.0) or 0.0)
                        self._gfx_stats["gfx_auto_refine_best_ocr"] = str(refine.get("ocr_back", "") or "")

                        rendered = refine.get("image")
                        if rendered is None:
                            rendered = self._render_text_on_modern_texture(
                                best_block["canvas"].copy(),
                                best_text,
                                translated_text,
                            )

                        ok_apply, raw_or_err = self._apply_canvas_back_to_block_tiles(best_block, rendered)
                        if ok_apply:
                            ok_write, write_err, out_path = self._write_auto_gfx_block_rom(best_block, raw_or_err)
                            if ok_write:
                                self._gfx_stats["gfx_translated_regions"] = len(best_block.get("tiles", []))
                                self._gfx_regions = [{
                                    "source": "retro_block_auto",
                                    "block_offset": f"0x{int(best_block.get('block_offset', 0)):06X}",
                                    "text": best_text,
                                    "translated": str(refine.get("text", translated_text) or translated_text),
                                    "conf": float(best_conf),
                                    "auto_refine_score": float(self._gfx_stats.get("gfx_auto_refine_best_score", 0.0) or 0.0),
                                    "output_rom": out_path,
                                }]
                                best_score = float(self._gfx_stats.get("gfx_auto_refine_best_score", 0.0) or 0.0)
                                self._needs_review_gfx = 0 if best_score >= float(self._gfx_auto_refine_min_score) else 1
                            else:
                                self._log(f"[AUTO-GFX] Retro bloco não aplicado: {write_err}")
                                self._needs_review_gfx = len(regions)
                        else:
                            self._log(f"[AUTO-GFX] Falha ao aplicar canvas retro: {raw_or_err}")
                            self._needs_review_gfx = len(regions)
                    else:
                        self._needs_review_gfx = len(regions)
                else:
                    self._needs_review_gfx = len(regions)

                self._gfx_stats["needs_review_gfx"] = self._needs_review_gfx

        if self._needs_review_gfx > 0:
            self.export_gfx_debug_pack()

        return self._gfx_stats

    def export_gfx_debug_pack(self) -> str | None:
        """Gera debug pack de gráficos quando needs_review_gfx > 0."""
        if not self.rom_crc32:
            return None
        out_dir = self._get_out_dir()
        if not out_dir:
            return None
        pack_dir = os.path.join(out_dir, f"{self.rom_crc32}_gfx_debug_pack")
        os.makedirs(pack_dir, exist_ok=True)

        # Salva regiões e imagens
        regions_out = []
        for idx, reg in enumerate(self._gfx_regions):
            reg_copy = dict(reg)
            img_path = None
            try:
                if "tile_idx" in reg and self.tiles_info:
                    info = self.tiles_info[idx] if idx < len(self.tiles_info) else None
                    if info:
                        pil = self._reconstruct_tile_image(info.get("pixels", []))
                        img_path = os.path.join(pack_dir, f"region_{idx:03d}.png")
                        pil.save(img_path)
                elif self.modern_texture is not None and "left" in reg:
                    # recorte da textura moderna
                    box = (
                        reg.get("left", 0),
                        reg.get("top", 0),
                        reg.get("left", 0) + reg.get("width", 0),
                        reg.get("top", 0) + reg.get("height", 0),
                    )
                    crop = self.modern_texture.crop(box)
                    img_path = os.path.join(pack_dir, f"region_{idx:03d}.png")
                    crop.save(img_path)
            except Exception:
                img_path = None

            if img_path:
                reg_copy["image_file"] = os.path.basename(img_path)
            regions_out.append(reg_copy)

        regions_path = os.path.join(pack_dir, "regions.json")
        with open(regions_path, "w", encoding="utf-8") as f:
            json.dump(regions_out, f, ensure_ascii=False, indent=2)

        # before/after texts
        before_txt = "\n".join([r.get("text", "") for r in regions_out if r.get("text")])
        after_txt = "\n".join([r.get("translated", "") for r in regions_out if r.get("translated")])
        with open(os.path.join(pack_dir, "before.txt"), "w", encoding="utf-8") as f:
            f.write(before_txt)
        with open(os.path.join(pack_dir, "after.txt"), "w", encoding="utf-8") as f:
            f.write(after_txt)

        # report
        report_path = os.path.join(pack_dir, "gfx_report.txt")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("=== GFX DEBUG PACK ===\n")
            f.write(f"CRC32: {self.rom_crc32}\n")
            f.write(f"ROM_SIZE: {self.rom_size}\n")
            f.write(f"needs_review_gfx: {self._needs_review_gfx}\n")
            f.write(f"gfx_total_regions: {self._gfx_stats.get('gfx_total_regions', 0)}\n")
            f.write(f"gfx_translated_regions: {self._gfx_stats.get('gfx_translated_regions', 0)}\n")
            f.write(f"gfx_skipped_low_confidence: {self._gfx_stats.get('gfx_skipped_low_confidence', 0)}\n")
            f.write(f"gfx_auto_refine_attempts: {self._gfx_stats.get('gfx_auto_refine_attempts', 0)}\n")
            f.write(f"gfx_auto_refine_best_score: {self._gfx_stats.get('gfx_auto_refine_best_score', 0.0):.2f}\n")

        self._last_debug_pack = pack_dir
        return pack_dir

    # ========================================================================
    # EXPORT: 4 arquivos obrigatórios + glyphmap
    # ========================================================================

    def _get_output_dir(self) -> str | None:
        """Resolve diretório de saída CRC32."""
        if not self.rom_name or not self.rom_crc32:
            return None
        rom_dir = os.path.dirname(self.rom_name)
        out_dir = os.path.join(rom_dir, self.rom_crc32)
        os.makedirs(out_dir, exist_ok=True)
        return out_dir

    def export_lab_results(self):
        """Gera os 4 exports obrigatórios a partir dos resultados do lab."""
        if not self.rom_crc32:
            self.status.setText("Sem ROM carregada. Impossivel exportar.")
            return
        out_dir = self._get_output_dir()
        if not out_dir:
            self.status.setText("Diretorio de saida nao resolvido.")
            return

        crc = self.rom_crc32
        now_iso = datetime.datetime.now().isoformat()

        # Contadores de cobertura
        counts = {"lab_ocr": 0, "pointer": 0, "tilemap": 0, "runtime_only": 0}
        validation_failures = 0

        # 1. pure_text.jsonl (OCR sem offset -> no_offset=true)
        jsonl_path = os.path.join(out_dir, f"{crc}_pure_text.jsonl")
        existing_lines = []
        if os.path.isfile(jsonl_path):
            with open(jsonl_path, "r", encoding="utf-8") as f:
                existing_lines = f.readlines()
        with open(jsonl_path, "a", encoding="utf-8") as f:
            for entry in self._lab_results:
                line = json.dumps({
                    "original": entry["original"],
                    "translated": entry.get("translated", ""),
                    "source": entry.get("source", "lab_ocr"),
                    "no_offset": entry.get("no_offset", True),
                    "block_offset": entry.get("block_offset", ""),
                    "tile_idx": entry.get("tile_idx", -1),
                }, ensure_ascii=False)
                f.write(line + "\n")
                src = entry.get("source", "lab_ocr")
                if src in counts:
                    counts[src] += 1
                if entry.get("no_offset"):
                    counts["runtime_only"] = counts.get("runtime_only", 0)

        # 2. reinsertion_mapping.json (lab_ocr com no_offset NAO entra)
        mapping_path = os.path.join(out_dir, f"{crc}_reinsertion_mapping.json")
        mapping = []
        if os.path.isfile(mapping_path):
            try:
                with open(mapping_path, "r", encoding="utf-8") as f:
                    mapping = json.load(f)
            except Exception:
                mapping = []
        # Filtra: APENAS entradas com offset real (nao lab_ocr sem offset)
        for entry in self._lab_results:
            if entry.get("no_offset"):
                continue
            # Validação estrita antes de adicionar
            ok = True
            reason = ""
            orig_bytes = entry["original"].encode("utf-8")
            trans_bytes = entry.get("translated", "").encode("utf-8")
            if len(trans_bytes) > len(orig_bytes):
                ok = False
                reason = "byte-length excedido"
            if not ok:
                validation_failures += 1
                self._lab_failures.append({
                    "original": entry["original"],
                    "translated": entry.get("translated", ""),
                    "reason": reason,
                })
                continue
            mapping.append(entry)
        with open(mapping_path, "w", encoding="utf-8") as f:
            json.dump(mapping, f, ensure_ascii=False, indent=2)

        # 3. report.txt (cobertura)
        report_path = os.path.join(out_dir, f"{crc}_report.txt")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(f"=== GRAPHIC LAB REPORT ===\n")
            f.write(f"CRC32: {crc}\n")
            f.write(f"ROM_SIZE: {self.rom_size}\n")
            f.write(f"Generated: {now_iso}\n\n")
            f.write(f"--- Coverage by Source ---\n")
            for src, cnt in counts.items():
                f.write(f"  {src}: {cnt}\n")
            f.write(f"\n--- Validation Failures ---\n")
            f.write(f"  Total: {validation_failures}\n")
            for fail in self._lab_failures:
                f.write(f"  - [{fail['reason']}] '{fail['original'][:40]}'\n")
            f.write(f"\n--- Lab OCR Entries (no_offset=true) ---\n")
            no_off_count = sum(1 for e in self._lab_results if e.get("no_offset"))
            f.write(f"  Total no_offset: {no_off_count}\n")
            f.write(f"  (Estes NAO entram no reinsertion_mapping)\n")

        # 4. proof.json (SHA256 dos exports)
        proof = {
            "crc32": crc,
            "rom_size": self.rom_size,
            "generated": now_iso,
            "files": {}
        }
        for fname in [f"{crc}_pure_text.jsonl", f"{crc}_reinsertion_mapping.json", f"{crc}_report.txt"]:
            fpath = os.path.join(out_dir, fname)
            if os.path.isfile(fpath):
                with open(fpath, "rb") as fh:
                    proof["files"][fname] = hashlib.sha256(fh.read()).hexdigest()
        proof_path = os.path.join(out_dir, f"{crc}_proof.json")
        with open(proof_path, "w", encoding="utf-8") as f:
            json.dump(proof, f, ensure_ascii=False, indent=2)

        # Glyphmap
        self._persist_glyphmap(out_dir)

        self.status.setText(
            f"Exportado: {crc}_pure_text.jsonl, _reinsertion_mapping.json, _report.txt, _proof.json"
        )
        self._log(f"[OK] 4 exports gerados em {out_dir}")

    def _persist_glyphmap(self, out_dir: str | None = None):
        """Persiste glyphmap em out/{CRC32}_glyphmap.json."""
        if not self._glyphmap or not self.rom_crc32:
            return
        if out_dir is None:
            out_dir = self._get_output_dir()
        if not out_dir:
            return
        glyph_path = os.path.join(out_dir, f"{self.rom_crc32}_glyphmap.json")
        existing = {}
        if os.path.isfile(glyph_path):
            try:
                with open(glyph_path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except Exception:
                pass
        existing.update(self._glyphmap)
        with open(glyph_path, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)

    def detect_text_tiles_in_current_rom(self, charset_offset: int = 0x008000, max_tiles: int = 256):
        """
        Detecta tiles com texto no ROM atual e mantém cache em self._detected_text_tiles.
        """
        if not self.rom_data:
            self.status.setText("Carregue uma ROM antes de detectar tiles de texto.")
            return []
        detected = detect_text_tiles(
            rom_data=self.rom_data,
            charset_offset=int(charset_offset),
            tile_width=8,
            tile_height=8,
        )
        if int(max_tiles) > 0:
            detected = detected[: int(max_tiles)]
        self._detected_text_tiles = list(detected)
        self.status.setText(f"Detectados {len(detected)} tiles com provável texto.")
        return detected

    def show_detected_text_tiles(self, charset_offset: int = 0x008000, max_tiles: int = 64):
        """
        Exibe lista de tiles detectados para fluxo de tradução automática.
        """
        detected = self.detect_text_tiles_in_current_rom(
            charset_offset=charset_offset,
            max_tiles=max_tiles,
        )
        if not detected:
            QMessageBox.information(self, "Detectar Texto em Tiles", "Nenhum tile de texto detectado.")
            return []

        lines = []
        for i, row in enumerate(detected):
            lines.append(
                f"[{i:02d}] tile={row.get('tile_idx')} off=0x{int(row.get('offset', 0)):06X} "
                f"score={row.get('score')} dens={row.get('density')}"
            )
        msg = "\n".join(lines[:80])
        if len(lines) > 80:
            msg += f"\n... +{len(lines) - 80} itens"
        QMessageBox.information(self, "Tiles com Texto Detectado", msg)
        return detected

    def select_detected_text_tile(self, detected_index: int) -> bool:
        """
        Seleciona tile detectado (index da lista detectada) para edição.
        """
        detected = list(getattr(self, "_detected_text_tiles", []) or [])
        if not detected:
            return False
        if detected_index < 0 or detected_index >= len(detected):
            return False

        tile_idx = int(detected[detected_index].get("tile_idx", -1))
        if tile_idx < 0:
            return False

        # Garante que grid de tiles esteja carregada.
        if not self.tiles_info:
            self.scan()

        for ui_idx, info in enumerate(self.tiles_info):
            if int(info.get("tile_idx", -1)) == tile_idx:
                self.selected_tile_idx = ui_idx
                self.status.setText(
                    f"Tile selecionado: detect[{detected_index}] -> tile_idx={tile_idx} (ui_idx={ui_idx})"
                )
                return True
        return False

    def edit_detected_text_tile(self, detected_index: int) -> bool:
        """
        Abre editor pixel-a-pixel para tile detectado.
        """
        ok = self.select_detected_text_tile(detected_index)
        if not ok:
            return False
        try:
            self.edit(int(self.selected_tile_idx))
            return True
        except Exception:
            return False

    def save_detected_text_tile(self, detected_index: int):
        """
        Salva tile detectado editado de volta na ROM (gera ROM *_OCR_TRANSLATED).
        """
        ok = self.select_detected_text_tile(detected_index)
        if not ok:
            return False, ""
        try:
            info = self.tiles_info[int(self.selected_tile_idx)]
            self._reinsert_tile_in_rom(info, info.get("pixels", []))
            rom_dir = os.path.dirname(self.rom_name)
            rom_ext = os.path.splitext(self.rom_name)[1]
            crc_tag = self.rom_crc32 or "UNKNOWN"
            out_path = os.path.join(rom_dir, f"{crc_tag}_OCR_TRANSLATED{rom_ext}")
            return True, out_path
        except Exception:
            return False, ""

    def retranslate(self):
        pass
