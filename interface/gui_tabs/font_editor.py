# -*- coding: utf-8 -*-
"""
FONT EDITOR PT-BR - Editor de fontes para caracteres acentuados
================================================================
Widget PyQt6 integrado ao Graphics Lab.
Permite visualizar, editar e gerar glifos acentuados PT-BR.

Autor: ROM Translation Framework v6.0
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton,
    QLabel, QScrollArea, QWidget, QMessageBox, QFileDialog,
    QGroupBox, QComboBox, QFrame, QSpinBox
)
from PyQt6.QtGui import QImage, QPixmap, QColor
from PyQt6.QtCore import Qt, pyqtSignal

from core.font_tools import (
    FontMap, FontGlyph, PTBR_ACCENTED_CHARS,
    generate_all_ptbr_accents, apply_accents_to_fontmap
)


class FontTileWidget(QLabel):
    """Widget clicavel para um tile de fonte."""
    clicked = pyqtSignal(int)

    def __init__(self, idx: int, img: QImage, char_label: str = ""):
        super().__init__()
        self.idx = idx
        self.char_label = char_label
        self.setPixmap(QPixmap.fromImage(img).scaled(32, 32,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.FastTransformation))
        self.setFixedSize(34, 34)
        self.setFrameStyle(QFrame.Shape.Box)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(f"Tile 0x{idx:02X} ({idx}) {char_label}")

    def mousePressEvent(self, e):
        self.clicked.emit(self.idx)


class FontPixelEditor(QDialog):
    """Editor de pixel para glifos de fonte (8x8, monocromo)."""

    def __init__(self, pixels: List[int], ink_color: int = 1, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Editor de Glifo - Font Editor PT-BR")
        self.pixels = list(pixels)
        self.ink_color = ink_color
        self.selected_color = ink_color
        self.zoom = 40
        self._init_ui()

    def _init_ui(self):
        self.setFixedSize(420, 460)
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
        self.lbl.mousePressEvent = self._paint
        self.lbl.mouseMoveEvent = self._paint
        clayout.addWidget(self.lbl)
        layout.addWidget(canvas_container)
        self._update_canvas()

        tools = QHBoxLayout()
        be = QPushButton("BORRACHA (Apagar)")
        be.setStyleSheet("background:#e74c3c; padding:8px; font-weight:bold; border-radius:5px;")
        be.setCursor(Qt.CursorShape.PointingHandCursor)
        be.clicked.connect(lambda: self._set_color(0))

        bp = QPushButton("PINCEL (Desenhar)")
        bp.setStyleSheet("background:#3498db; padding:8px; font-weight:bold; border-radius:5px;")
        bp.setCursor(Qt.CursorShape.PointingHandCursor)
        bp.clicked.connect(lambda: self._set_color(self.ink_color))

        tools.addWidget(be)
        tools.addWidget(bp)
        layout.addLayout(tools)

        btn_save = QPushButton("SALVAR GLIFO")
        btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save.clicked.connect(self.accept)
        btn_save.setStyleSheet("background:#2ecc71; padding:10px; font-weight:bold; color:black;")
        layout.addWidget(btn_save)

    def _set_color(self, c: int):
        self.selected_color = c
        cursor = Qt.CursorShape.ForbiddenCursor if c == 0 else Qt.CursorShape.CrossCursor
        self.lbl.setCursor(cursor)

    def _paint(self, e):
        x = int(e.position().x()) // self.zoom
        y = int(e.position().y()) // self.zoom
        if 0 <= x < 8 and 0 <= y < 8:
            self.pixels[y * 8 + x] = self.selected_color
            self._update_canvas()

    def _update_canvas(self):
        img = QImage(8, 8, QImage.Format.Format_RGB32)
        for y in range(8):
            for x in range(8):
                val = self.pixels[y * 8 + x]
                if val > 0:
                    img.setPixelColor(x, y, QColor(255, 255, 255))
                else:
                    img.setPixelColor(x, y, QColor(0, 0, 0))
        self.lbl.setPixmap(QPixmap.fromImage(img).scaled(
            self.lbl.size(),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.FastTransformation))

    def get_pixels(self) -> List[int]:
        return self.pixels


class FontEditorDialog(QDialog):
    """Dialog principal do Font Editor PT-BR."""

    def __init__(self, rom_path: str, font_offset: int = 0,
                 bpp: int = 1, num_tiles: int = 256,
                 rom_crc32: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Font Editor PT-BR")
        self.setMinimumSize(700, 600)
        self.rom_path = rom_path
        self.rom_crc32 = rom_crc32
        self.bpp = bpp
        self.ink_color = 1 if bpp == 1 else 15
        self.accent_tbl_entries: Dict[int, str] = {}

        with open(rom_path, 'rb') as f:
            self.rom_data = bytearray(f.read())

        self.font_map = FontMap(self.rom_data, font_offset, bpp, num_tiles)
        self._init_ui()
        self._refresh_grid()

    def _init_ui(self):
        self.setStyleSheet("""
            QDialog { background-color: #1e1e1e; color: #e0e0e0; }
            QGroupBox { border: 1px solid #555; border-radius: 5px;
                        margin-top: 10px; padding-top: 15px; color: #aaa; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; }
            QPushButton { border-radius: 4px; }
        """)
        layout = QVBoxLayout(self)

        # Barra de ferramentas
        toolbar = QHBoxLayout()

        btn_gen = QPushButton("GERAR ACENTOS PT-BR")
        btn_gen.setStyleSheet("background:#9b59b6; color:white; padding:10px; font-weight:bold;")
        btn_gen.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_gen.clicked.connect(self._generate_accents)
        btn_gen.setToolTip("Gera automaticamente glifos acentuados (a,e,i,o,u + maiusculas + c)")

        btn_save = QPushButton("SALVAR NA ROM")
        btn_save.setStyleSheet("background:#2ecc71; color:black; padding:10px; font-weight:bold;")
        btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save.clicked.connect(self._save_to_rom)

        btn_tbl = QPushButton("EXPORTAR .TBL")
        btn_tbl.setStyleSheet("background:#3498db; color:white; padding:10px; font-weight:bold;")
        btn_tbl.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_tbl.clicked.connect(self._export_tbl)

        # Offset selector
        lbl_offset = QLabel("Font Offset:")
        self.spin_offset = QSpinBox()
        self.spin_offset.setRange(0, len(self.rom_data) - 1)
        self.spin_offset.setValue(self.font_map.font_offset)
        self.spin_offset.setPrefix("0x")
        self.spin_offset.setDisplayIntegerBase(16)
        self.spin_offset.setStyleSheet("background:#333; color:white; padding:4px;")

        btn_reload = QPushButton("RECARREGAR")
        btn_reload.setStyleSheet("background:#e67e22; color:white; padding:10px; font-weight:bold;")
        btn_reload.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_reload.clicked.connect(self._reload_at_offset)

        toolbar.addWidget(lbl_offset)
        toolbar.addWidget(self.spin_offset)
        toolbar.addWidget(btn_reload)
        toolbar.addStretch()
        toolbar.addWidget(btn_gen)
        toolbar.addWidget(btn_save)
        toolbar.addWidget(btn_tbl)
        layout.addLayout(toolbar)

        # Info
        self.info_label = QLabel(f"ROM: {Path(self.rom_path).name} | "
                                 f"Offset: 0x{self.font_map.font_offset:04X} | "
                                 f"BPP: {self.bpp} | Tiles: {self.font_map.num_tiles}")
        self.info_label.setStyleSheet("color: #888; padding: 5px;")
        layout.addWidget(self.info_label)

        # Grid de tiles
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.gridw = QWidget()
        self.grid = QGridLayout(self.gridw)
        self.grid.setSpacing(2)
        self.scroll.setWidget(self.gridw)
        layout.addWidget(self.scroll)

        # Status
        self.status_label = QLabel("Clique em um tile para editar. Use 'GERAR ACENTOS PT-BR' para criar glifos automaticamente.")
        self.status_label.setStyleSheet("color: #aaa; padding: 5px;")
        layout.addWidget(self.status_label)

    def _refresh_grid(self):
        """Reconstroi a grid com todos os tiles."""
        # Remove widgets anteriores
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        cols = 16
        for i, glyph in self.font_map.glyphs.items():
            img = self._pixels_to_qimage(glyph.pixels)
            char_label = glyph.char or (chr(0x20 + i) if 0x20 + i < 0x7F and i < 0x60 else "")
            tile_w = FontTileWidget(i, img, char_label)
            tile_w.clicked.connect(self._edit_tile)
            row = i // cols
            col = i % cols
            self.grid.addWidget(tile_w, row, col)

    def _pixels_to_qimage(self, pixels: List[int]) -> QImage:
        """Converte pixels para QImage."""
        img = QImage(8, 8, QImage.Format.Format_RGB32)
        for y in range(8):
            for x in range(8):
                val = pixels[y * 8 + x]
                if val > 0:
                    bright = min(255, val * (255 // max(1, (2 ** self.bpp) - 1)))
                    img.setPixelColor(x, y, QColor(bright, bright, bright))
                else:
                    img.setPixelColor(x, y, QColor(0, 0, 0))
        return img

    def _edit_tile(self, idx: int):
        """Abre editor de pixel para um tile."""
        glyph = self.font_map.get_glyph(idx)
        if not glyph:
            return

        editor = FontPixelEditor(glyph.pixels, self.ink_color, self)
        if editor.exec():
            new_pixels = editor.get_pixels()
            self.font_map.set_glyph(idx, new_pixels, glyph.char)
            self._refresh_grid()
            self.status_label.setText(f"Tile 0x{idx:02X} atualizado.")

    def _reload_at_offset(self):
        """Recarrega a fonte em um novo offset."""
        new_offset = self.spin_offset.value()
        self.font_map = FontMap(self.rom_data, new_offset, self.bpp, self.font_map.num_tiles)
        self.info_label.setText(f"ROM: {Path(self.rom_path).name} | "
                                f"Offset: 0x{new_offset:04X} | "
                                f"BPP: {self.bpp} | Tiles: {self.font_map.num_tiles}")
        self._refresh_grid()
        self.status_label.setText(f"Fonte recarregada no offset 0x{new_offset:04X}.")

    def _generate_accents(self):
        """Gera todos os glifos acentuados PT-BR automaticamente."""
        free_count = len(self.font_map.find_free_tile_slots())
        needed = len(PTBR_ACCENTED_CHARS)

        if free_count < needed:
            reply = QMessageBox.question(
                self, "Slots Insuficientes",
                f"Encontrados {free_count} tiles vazios, mas sao necessarios {needed} "
                f"para todos os acentos PT-BR.\n\n"
                f"Deseja gerar os {free_count} que cabem?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return

        accents = generate_all_ptbr_accents(self.font_map, ink_color=self.ink_color)
        self.accent_tbl_entries = apply_accents_to_fontmap(self.font_map, accents)

        self._refresh_grid()

        generated = list(self.accent_tbl_entries.values())
        chars_str = ", ".join(generated[:10])
        if len(generated) > 10:
            chars_str += f"... (+{len(generated) - 10})"

        self.status_label.setText(
            f"{len(generated)} glifos acentuados gerados: {chars_str}")

        QMessageBox.information(
            self, "Acentos Gerados",
            f"{len(generated)} caracteres acentuados PT-BR criados!\n\n"
            f"Caracteres: {', '.join(generated)}\n\n"
            f"Use 'SALVAR NA ROM' para gravar e 'EXPORTAR .TBL' para gerar a tabela.")

    def _save_to_rom(self):
        """Salva a fonte modificada em uma copia da ROM."""
        rom_dir = os.path.dirname(self.rom_path)
        rom_ext = os.path.splitext(self.rom_path)[1]
        crc_tag = self.rom_crc32 or "MODIFIED"
        out_name = os.path.join(rom_dir, f"{crc_tag}_FONT_MOD{rom_ext}")

        if not os.path.exists(out_name):
            shutil.copy(self.rom_path, out_name)

        with open(out_name, 'r+b') as f:
            offset = self.font_map.font_offset
            for i, glyph in self.font_map.glyphs.items():
                tile_offset = offset + i * self.font_map.bytes_per_tile
                tile_bytes = self.font_map._encode_tile(glyph.pixels)
                f.seek(tile_offset)
                f.write(tile_bytes)

        self.status_label.setText(f"ROM salva: {out_name}")
        QMessageBox.information(
            self, "ROM Salva",
            f"Fonte modificada salva em:\n{out_name}\n\n"
            f"Teste no emulador para verificar os caracteres acentuados.")

    def _export_tbl(self):
        """Exporta arquivo .tbl com mapeamentos."""
        if not self.accent_tbl_entries:
            QMessageBox.warning(
                self, "Sem Dados",
                "Gere os acentos primeiro usando 'GERAR ACENTOS PT-BR'.")
            return

        # Monta tabela completa: ASCII base + acentos
        full_map: Dict[int, str] = {}
        for i in range(0x20, 0x7F):
            tile_idx = i - 0x20
            if tile_idx < self.font_map.num_tiles:
                full_map[tile_idx] = chr(i)

        # Mantém mesma regra de encoding do pipeline: code = tile_index - 0x20.
        accent_code_map: Dict[int, str] = {}
        for tile_idx, ch in (self.accent_tbl_entries or {}).items():
            code = int(tile_idx) - 0x20
            if 0 <= code <= 0xFF:
                accent_code_map[int(code)] = ch
        full_map.update(accent_code_map)

        rom_dir = os.path.dirname(self.rom_path)
        crc_tag = self.rom_crc32 or "MODIFIED"
        tbl_path = os.path.join(rom_dir, f"{crc_tag}_ptbr.tbl")

        self.font_map.export_tbl(tbl_path, full_map)

        self.status_label.setText(f"Tabela exportada: {tbl_path}")
        QMessageBox.information(
            self, "Tabela Exportada",
            f"Arquivo .TBL salvo em:\n{tbl_path}\n\n"
            f"Use este arquivo no reinsertor para mapear os caracteres acentuados.")
