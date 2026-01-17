#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Graphics Worker - Tile Viewer & Forensic Tool
==============================================

O SANTO GRAAL da tradução gráfica de ROMs:
- Decodificação de tiles (1bpp, 2bpp, 4bpp, 8bpp)
- Tile Sniffer (detecta padrões de fonte)
- Scanner de Entropia de Shannon
- Export/Import PNG com reconversão automática

Author: ROM Translation Framework
Version: 1.0.0 - EXPERIMENTAL
"""

import math
import struct
from typing import List, Tuple, Optional
from collections import Counter
from PIL import Image
import numpy as np


class GraphicsWorker:
    """Worker para análise forense e edição gráfica de ROMs."""

    def __init__(self, rom_data: bytes):
        """
        Initialize Graphics Worker.

        Args:
            rom_data: Raw ROM bytes
        """
        self.rom_data = bytearray(rom_data)
        self.rom_size = len(rom_data)

        # Paletas padrão (SNES/NES/GB)
        self.palette_gb = [
            (255, 255, 255),  # Branco
            (170, 170, 170),  # Cinza claro
            (85, 85, 85),     # Cinza escuro
            (0, 0, 0)         # Preto
        ]

        self.palette_snes_default = [
            (0, 0, 0), (255, 255, 255), (255, 0, 0), (0, 255, 0),
            (0, 0, 255), (255, 255, 0), (255, 0, 255), (0, 255, 255),
            (128, 128, 128), (192, 192, 192), (128, 0, 0), (0, 128, 0),
            (0, 0, 128), (128, 128, 0), (128, 0, 128), (0, 128, 128)
        ]

    # ═══════════════════════════════════════════════════════════
    # DECODIFICADORES DE TILES
    # ═══════════════════════════════════════════════════════════

    def decode_tile_1bpp(self, offset: int, tile_size: int = 8) -> np.ndarray:
        """
        Decodifica tile 1BPP (Game Boy, NES simples).

        1 bit por pixel = 2 cores (0=branco, 1=preto)

        Args:
            offset: Offset no ROM
            tile_size: Tamanho do tile (8x8 padrão)

        Returns:
            Array numpy (tile_size x tile_size) com índices de cor
        """
        tile = np.zeros((tile_size, tile_size), dtype=np.uint8)
        bytes_per_tile = tile_size  # 1 byte = 8 pixels

        for y in range(tile_size):
            if offset + y >= self.rom_size:
                break

            byte = self.rom_data[offset + y]

            for x in range(8):
                bit = (byte >> (7 - x)) & 1
                tile[y, x] = bit

        return tile

    def decode_tile_2bpp(self, offset: int, tile_size: int = 8) -> np.ndarray:
        """
        Decodifica tile 2BPP (SNES, Game Boy Color, NES).

        2 bits por pixel = 4 cores
        Formato planar: 2 bitplanes intercalados

        Args:
            offset: Offset no ROM
            tile_size: Tamanho do tile (8x8 padrão)

        Returns:
            Array numpy (tile_size x tile_size) com índices de cor (0-3)
        """
        tile = np.zeros((tile_size, tile_size), dtype=np.uint8)
        bytes_per_tile = tile_size * 2  # 2 bytes por linha (2 bitplanes)

        for y in range(tile_size):
            byte_offset = offset + (y * 2)

            if byte_offset + 1 >= self.rom_size:
                break

            # 2 bitplanes intercalados
            plane0 = self.rom_data[byte_offset]
            plane1 = self.rom_data[byte_offset + 1]

            for x in range(8):
                bit0 = (plane0 >> (7 - x)) & 1
                bit1 = (plane1 >> (7 - x)) & 1
                color_index = (bit1 << 1) | bit0
                tile[y, x] = color_index

        return tile

    def decode_tile_4bpp(self, offset: int, tile_size: int = 8) -> np.ndarray:
        """
        Decodifica tile 4BPP (SNES, GBA).

        4 bits por pixel = 16 cores
        Formato planar: 4 bitplanes intercalados (padrão SNES)

        Args:
            offset: Offset no ROM
            tile_size: Tamanho do tile (8x8 padrão)

        Returns:
            Array numpy (tile_size x tile_size) com índices de cor (0-15)
        """
        tile = np.zeros((tile_size, tile_size), dtype=np.uint8)

        for y in range(tile_size):
            # SNES 4bpp: bitplanes em pares intercalados
            # Linha 0: bytes 0,1 (plane 0,1), bytes 16,17 (plane 2,3)
            # Linha 1: bytes 2,3 (plane 0,1), bytes 18,19 (plane 2,3)
            byte_offset_low = offset + (y * 2)
            byte_offset_high = offset + 16 + (y * 2)

            if byte_offset_high + 1 >= self.rom_size:
                break

            plane0 = self.rom_data[byte_offset_low]
            plane1 = self.rom_data[byte_offset_low + 1]
            plane2 = self.rom_data[byte_offset_high]
            plane3 = self.rom_data[byte_offset_high + 1]

            for x in range(8):
                bit0 = (plane0 >> (7 - x)) & 1
                bit1 = (plane1 >> (7 - x)) & 1
                bit2 = (plane2 >> (7 - x)) & 1
                bit3 = (plane3 >> (7 - x)) & 1

                color_index = (bit3 << 3) | (bit2 << 2) | (bit1 << 1) | bit0
                tile[y, x] = color_index

        return tile

    def decode_tile_8bpp(self, offset: int, tile_size: int = 8) -> np.ndarray:
        """
        Decodifica tile 8BPP (GBA, SNES Mode 7).

        8 bits por pixel = 256 cores
        Formato linear (não planar)

        Args:
            offset: Offset no ROM
            tile_size: Tamanho do tile (8x8 padrão)

        Returns:
            Array numpy (tile_size x tile_size) com índices de cor (0-255)
        """
        tile = np.zeros((tile_size, tile_size), dtype=np.uint8)
        bytes_per_tile = tile_size * tile_size  # 1 byte por pixel

        for y in range(tile_size):
            for x in range(tile_size):
                byte_offset = offset + (y * tile_size) + x

                if byte_offset >= self.rom_size:
                    break

                tile[y, x] = self.rom_data[byte_offset]

        return tile

    def tile_to_image(self, tile_array: np.ndarray, palette: List[Tuple[int, int, int]],
                      scale: int = 1) -> Image.Image:
        """
        Converte tile array para imagem PIL.

        Args:
            tile_array: Array numpy com índices de cor
            palette: Lista de tuplas RGB
            scale: Escala de zoom (1=original, 2=2x, etc.)

        Returns:
            PIL Image
        """
        height, width = tile_array.shape
        img = Image.new('RGB', (width, height))

        pixels = []
        for y in range(height):
            for x in range(width):
                color_idx = int(tile_array[y, x])
                color_idx = min(color_idx, len(palette) - 1)  # Clamp
                pixels.append(palette[color_idx])

        img.putdata(pixels)

        # Scale se necessário
        if scale > 1:
            new_size = (width * scale, height * scale)
            img = img.resize(new_size, Image.NEAREST)

        return img

    # ═══════════════════════════════════════════════════════════
    # TILE SNIFFER (Detector de Padrões de Fonte)
    # ═══════════════════════════════════════════════════════════

    def calculate_tile_contrast(self, tile_array: np.ndarray) -> float:
        """
        Calcula contraste visual do tile (variação de cores).

        Fontes tendem a ter alto contraste (preto/branco).

        Args:
            tile_array: Array numpy com índices de cor

        Returns:
            Score de contraste (0.0-1.0)
        """
        if tile_array.size == 0:
            return 0.0

        unique_colors = len(np.unique(tile_array))
        max_color = np.max(tile_array)
        min_color = np.min(tile_array)

        # Contraste = diferença entre min e max
        if max_color == 0:
            return 0.0

        contrast = (max_color - min_color) / max(max_color, 1)

        # Bonus se tem 2-4 cores (típico de fonte)
        if 2 <= unique_colors <= 4:
            contrast *= 1.2

        return min(contrast, 1.0)

    def calculate_tile_density(self, tile_array: np.ndarray) -> float:
        """
        Calcula densidade de pixels "acesos" (não-zero).

        Fontes tendem a ter densidade 20-60%.

        Args:
            tile_array: Array numpy com índices de cor

        Returns:
            Densidade (0.0-1.0)
        """
        if tile_array.size == 0:
            return 0.0

        non_zero = np.count_nonzero(tile_array)
        density = non_zero / tile_array.size

        return density

    def is_likely_font_tile(self, tile_array: np.ndarray) -> Tuple[bool, float]:
        """
        Heurística: Detecta se tile parece ser uma letra/número.

        Critérios:
        - Alto contraste (>0.5)
        - Densidade 20-60% (não muito vazio, não muito cheio)
        - Pelo menos 2 cores diferentes

        Args:
            tile_array: Array numpy com índices de cor

        Returns:
            (is_font: bool, confidence: float)
        """
        contrast = self.calculate_tile_contrast(tile_array)
        density = self.calculate_tile_density(tile_array)
        unique_colors = len(np.unique(tile_array))

        # Score de confiança
        confidence = 0.0

        # Contraste alto = +30%
        if contrast > 0.5:
            confidence += 0.3

        # Densidade ideal = +40%
        if 0.2 <= density <= 0.6:
            confidence += 0.4

        # 2-4 cores = +30%
        if 2 <= unique_colors <= 4:
            confidence += 0.3

        is_font = confidence >= 0.6

        return is_font, confidence

    def scan_for_fonts(self, bpp_mode: str = '2bpp', tile_size: int = 8,
                       start_offset: int = 0, max_tiles: int = 1024) -> List[dict]:
        """
        TILE SNIFFER: Escaneia ROM procurando padrões de fonte.

        Args:
            bpp_mode: '1bpp', '2bpp', '4bpp', '8bpp'
            tile_size: Tamanho do tile (8x8 padrão)
            start_offset: Offset inicial
            max_tiles: Máximo de tiles a escanear

        Returns:
            Lista de dicts: {offset, confidence, preview_image}
        """
        results = []

        # Bytes por tile
        bytes_per_tile = {
            '1bpp': tile_size,
            '2bpp': tile_size * 2,
            '4bpp': tile_size * 4,
            '8bpp': tile_size * tile_size
        }

        tile_bytes = bytes_per_tile.get(bpp_mode, 16)

        for i in range(max_tiles):
            offset = start_offset + (i * tile_bytes)

            if offset + tile_bytes > self.rom_size:
                break

            # Decodifica tile
            if bpp_mode == '1bpp':
                tile = self.decode_tile_1bpp(offset, tile_size)
                palette = self.palette_gb
            elif bpp_mode == '2bpp':
                tile = self.decode_tile_2bpp(offset, tile_size)
                palette = self.palette_gb
            elif bpp_mode == '4bpp':
                tile = self.decode_tile_4bpp(offset, tile_size)
                palette = self.palette_snes_default
            elif bpp_mode == '8bpp':
                tile = self.decode_tile_8bpp(offset, tile_size)
                palette = self.palette_snes_default
            else:
                continue

            # Verifica se parece fonte
            is_font, confidence = self.is_likely_font_tile(tile)

            if is_font:
                img = self.tile_to_image(tile, palette, scale=4)
                results.append({
                    'offset': offset,
                    'offset_hex': hex(offset),
                    'confidence': confidence,
                    'tile_array': tile,
                    'preview_image': img
                })

        return results

    # ═══════════════════════════════════════════════════════════
    # SCANNER DE ENTROPIA (Shannon Entropy)
    # ═══════════════════════════════════════════════════════════

    def calculate_shannon_entropy(self, data: bytes) -> float:
        """
        Calcula Entropia de Shannon de um bloco de dados.

        Entropia alta (>7.8) = Dados comprimidos/criptografados
        Entropia baixa (<3.0) = Dados repetitivos/vazios

        Args:
            data: Bytes a analisar

        Returns:
            Entropia (0.0-8.0)
        """
        if not data:
            return 0.0

        # Conta frequência de cada byte
        byte_counts = Counter(data)
        total_bytes = len(data)

        # Calcula entropia
        entropy = 0.0
        for count in byte_counts.values():
            probability = count / total_bytes
            if probability > 0:
                entropy -= probability * math.log2(probability)

        return entropy

    def scan_entropy(self, chunk_size: int = 256) -> List[dict]:
        """
        Escaneia ROM inteira calculando entropia por chunks.

        Args:
            chunk_size: Tamanho do chunk em bytes

        Returns:
            Lista de dicts: {offset, entropy, is_compressed}
        """
        results = []
        total_chunks = self.rom_size // chunk_size

        for i in range(total_chunks):
            offset = i * chunk_size
            chunk = self.rom_data[offset:offset + chunk_size]

            entropy = self.calculate_shannon_entropy(chunk)
            is_compressed = entropy > 7.8  # Threshold para compressão

            results.append({
                'offset': offset,
                'offset_hex': hex(offset),
                'entropy': entropy,
                'is_compressed': is_compressed
            })

        return results

    # ═══════════════════════════════════════════════════════════
    # EXPORT / IMPORT PNG
    # ═══════════════════════════════════════════════════════════

    def export_tiles_to_png(self, start_offset: int, num_tiles: int,
                           bpp_mode: str = '2bpp', tile_size: int = 8,
                           tiles_per_row: int = 16,
                           palette: Optional[List[Tuple[int, int, int]]] = None,
                           output_path: str = 'exported_tiles.png') -> bool:
        """
        Exporta região de tiles para PNG.

        Args:
            start_offset: Offset inicial
            num_tiles: Número de tiles a exportar
            bpp_mode: '1bpp', '2bpp', '4bpp', '8bpp'
            tile_size: Tamanho do tile (8x8)
            tiles_per_row: Tiles por linha
            palette: Paleta customizada (None = usar padrão)
            output_path: Caminho do arquivo PNG

        Returns:
            True se sucesso
        """
        if palette is None:
            palette = self.palette_gb if bpp_mode in ['1bpp', '2bpp'] else self.palette_snes_default

        # Calcula dimensões da imagem
        rows = math.ceil(num_tiles / tiles_per_row)
        img_width = tiles_per_row * tile_size
        img_height = rows * tile_size

        # Cria imagem vazia
        output_img = Image.new('RGB', (img_width, img_height), color=(0, 0, 0))

        bytes_per_tile = {
            '1bpp': tile_size,
            '2bpp': tile_size * 2,
            '4bpp': tile_size * 4,
            '8bpp': tile_size * tile_size
        }

        tile_bytes = bytes_per_tile.get(bpp_mode, 16)

        # Decodifica e cola cada tile
        for i in range(num_tiles):
            offset = start_offset + (i * tile_bytes)

            if offset + tile_bytes > self.rom_size:
                break

            # Decodifica tile
            if bpp_mode == '1bpp':
                tile = self.decode_tile_1bpp(offset, tile_size)
            elif bpp_mode == '2bpp':
                tile = self.decode_tile_2bpp(offset, tile_size)
            elif bpp_mode == '4bpp':
                tile = self.decode_tile_4bpp(offset, tile_size)
            elif bpp_mode == '8bpp':
                tile = self.decode_tile_8bpp(offset, tile_size)
            else:
                continue

            # Converte para imagem
            tile_img = self.tile_to_image(tile, palette, scale=1)

            # Calcula posição
            tile_x = (i % tiles_per_row) * tile_size
            tile_y = (i // tiles_per_row) * tile_size

            # Cola na imagem final
            output_img.paste(tile_img, (tile_x, tile_y))

        # Salva
        output_img.save(output_path)
        return True

    def import_png_to_tiles(self, png_path: str, target_offset: int,
                           bpp_mode: str = '2bpp', tile_size: int = 8,
                           palette: Optional[List[Tuple[int, int, int]]] = None) -> bool:
        """
        Importa PNG e converte de volta para tiles na ROM.

        A MÁGICA: Converte PNG → pixels → bitplanes → bytes → ROM

        Args:
            png_path: Caminho do PNG editado
            target_offset: Offset onde reinserir
            bpp_mode: '1bpp', '2bpp', '4bpp', '8bpp'
            tile_size: Tamanho do tile (8x8)
            palette: Paleta para quantização

        Returns:
            True se sucesso
        """
        if palette is None:
            palette = self.palette_gb if bpp_mode in ['1bpp', '2bpp'] else self.palette_snes_default

        # Carrega PNG
        img = Image.open(png_path).convert('RGB')
        img_width, img_height = img.size

        # Calcula número de tiles
        tiles_per_row = img_width // tile_size
        tiles_per_col = img_height // tile_size
        total_tiles = tiles_per_row * tiles_per_col

        bytes_per_tile = {
            '1bpp': tile_size,
            '2bpp': tile_size * 2,
            '4bpp': tile_size * 4,
            '8bpp': tile_size * tile_size
        }

        tile_bytes = bytes_per_tile.get(bpp_mode, 16)
        current_offset = target_offset

        # Para cada tile
        for tile_idx in range(total_tiles):
            tile_x = (tile_idx % tiles_per_row) * tile_size
            tile_y = (tile_idx // tiles_per_row) * tile_size

            # Extrai tile da imagem
            tile_img = img.crop((tile_x, tile_y, tile_x + tile_size, tile_y + tile_size))

            # Converte para índices de paleta
            tile_array = self._image_to_tile_array(tile_img, palette, tile_size)

            # Codifica de volta para bytes
            if bpp_mode == '1bpp':
                tile_bytes_data = self._encode_tile_1bpp(tile_array)
            elif bpp_mode == '2bpp':
                tile_bytes_data = self._encode_tile_2bpp(tile_array)
            elif bpp_mode == '4bpp':
                tile_bytes_data = self._encode_tile_4bpp(tile_array)
            elif bpp_mode == '8bpp':
                tile_bytes_data = self._encode_tile_8bpp(tile_array)
            else:
                continue

            # Escreve na ROM
            if current_offset + len(tile_bytes_data) <= self.rom_size:
                self.rom_data[current_offset:current_offset + len(tile_bytes_data)] = tile_bytes_data
                current_offset += len(tile_bytes_data)

        return True

    def _image_to_tile_array(self, tile_img: Image.Image,
                            palette: List[Tuple[int, int, int]],
                            tile_size: int) -> np.ndarray:
        """
        Converte imagem PIL para array de índices de paleta.

        Args:
            tile_img: Imagem PIL (RGB)
            palette: Lista de cores RGB
            tile_size: Tamanho do tile

        Returns:
            Array numpy com índices de cor
        """
        tile_array = np.zeros((tile_size, tile_size), dtype=np.uint8)
        pixels = tile_img.load()

        for y in range(tile_size):
            for x in range(tile_size):
                rgb = pixels[x, y]

                # Encontra cor mais próxima na paleta
                closest_idx = 0
                min_distance = float('inf')

                for i, palette_color in enumerate(palette):
                    distance = sum((a - b) ** 2 for a, b in zip(rgb, palette_color))
                    if distance < min_distance:
                        min_distance = distance
                        closest_idx = i

                tile_array[y, x] = closest_idx

        return tile_array

    def _encode_tile_1bpp(self, tile_array: np.ndarray) -> bytes:
        """Codifica tile array para 1BPP bytes."""
        tile_bytes = bytearray()
        height, width = tile_array.shape

        for y in range(height):
            byte = 0
            for x in range(min(8, width)):
                if tile_array[y, x] > 0:
                    byte |= (1 << (7 - x))
            tile_bytes.append(byte)

        return bytes(tile_bytes)

    def _encode_tile_2bpp(self, tile_array: np.ndarray) -> bytes:
        """Codifica tile array para 2BPP bytes (planar)."""
        tile_bytes = bytearray()
        height, width = tile_array.shape

        for y in range(height):
            plane0 = 0
            plane1 = 0

            for x in range(min(8, width)):
                color_idx = int(tile_array[y, x])
                bit0 = color_idx & 1
                bit1 = (color_idx >> 1) & 1

                if bit0:
                    plane0 |= (1 << (7 - x))
                if bit1:
                    plane1 |= (1 << (7 - x))

            tile_bytes.append(plane0)
            tile_bytes.append(plane1)

        return bytes(tile_bytes)

    def _encode_tile_4bpp(self, tile_array: np.ndarray) -> bytes:
        """Codifica tile array para 4BPP bytes (planar SNES)."""
        tile_bytes = bytearray(32)  # 4bpp = 32 bytes por tile
        height, width = tile_array.shape

        for y in range(min(8, height)):
            plane0 = 0
            plane1 = 0
            plane2 = 0
            plane3 = 0

            for x in range(min(8, width)):
                color_idx = int(tile_array[y, x])
                bit0 = color_idx & 1
                bit1 = (color_idx >> 1) & 1
                bit2 = (color_idx >> 2) & 1
                bit3 = (color_idx >> 3) & 1

                if bit0:
                    plane0 |= (1 << (7 - x))
                if bit1:
                    plane1 |= (1 << (7 - x))
                if bit2:
                    plane2 |= (1 << (7 - x))
                if bit3:
                    plane3 |= (1 << (7 - x))

            # SNES format: planes 0,1 then planes 2,3
            tile_bytes[y * 2] = plane0
            tile_bytes[y * 2 + 1] = plane1
            tile_bytes[16 + y * 2] = plane2
            tile_bytes[16 + y * 2 + 1] = plane3

        return bytes(tile_bytes)

    def _encode_tile_8bpp(self, tile_array: np.ndarray) -> bytes:
        """Codifica tile array para 8BPP bytes (linear)."""
        return tile_array.flatten().tobytes()

    def save_rom(self, output_path: str) -> bool:
        """
        Salva ROM modificada.

        Args:
            output_path: Caminho do arquivo de saída

        Returns:
            True se sucesso
        """
        try:
            with open(output_path, 'wb') as f:
                f.write(self.rom_data)
            return True
        except Exception as e:
            print(f"Erro ao salvar ROM: {e}")
            return False
