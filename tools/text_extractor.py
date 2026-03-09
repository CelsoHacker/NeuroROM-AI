#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROM Text Extractor - Generic Text Extraction Tool
==================================================

Universal text extraction utility for retro game ROMs.
Supports multiple platforms and encoding formats.

Author: ROM Translation Framework
Version: 1.0.0
License: Proprietary
"""

import os
import sys
import struct
import json
from pathlib import Path
from typing import List, Dict, Tuple, Optional


class TextExtractor:
    """Generic text extractor for ROM files."""
    
    def __init__(self, rom_path: str, config: Optional[Dict] = None):
        """
        Initialize the text extractor.
        
        Args:
            rom_path: Path to the ROM file
            config: Optional configuration dictionary
        """
        self.rom_path = Path(rom_path)
        self.config = config or {}
        self.rom_data = None
        self.texts = []
        self.encoding = self.config.get('encoding', 'shift-jis')
        
    def load_rom(self) -> bytes:
        """Load ROM file into memory."""
        with open(self.rom_path, 'rb') as f:
            self.rom_data = f.read()
        print(f"✅ ROM loaded: {len(self.rom_data):,} bytes")
        return self.rom_data
    
    def extract_texts(self, 
                     start_offset: int = 0,
                     end_offset: Optional[int] = None,
                     min_length: int = 4) -> List[Dict]:
        """
        Extract text strings from ROM data.
        
        Args:
            start_offset: Starting offset for extraction
            end_offset: Ending offset (None = end of file)
            min_length: Minimum text length to extract
            
        Returns:
            List of dictionaries containing text data
        """
        if self.rom_data is None:
            self.load_rom()
        
        if end_offset is None:
            end_offset = len(self.rom_data)
        
        extracted = []
        current_text = bytearray()
        text_start = None
        
        for offset in range(start_offset, end_offset):
            byte = self.rom_data[offset]
            
            # Check if byte is valid text character
            if self._is_valid_text_byte(byte):
                if text_start is None:
                    text_start = offset
                current_text.append(byte)
            else:
                # Text string ended
                if len(current_text) >= min_length:
                    try:
                        decoded = current_text.decode(self.encoding, errors='ignore')
                        if decoded.strip():
                            extracted.append({
                                'offset': hex(text_start),
                                'size': len(current_text),
                                'text': decoded.strip(),
                                'raw': current_text.hex()
                            })
                    except:
                        pass
                
                current_text = bytearray()
                text_start = None
        
        self.texts = extracted
        print(f"✅ Extracted {len(extracted)} text strings")
        return extracted
    
    def _is_valid_text_byte(self, byte: int) -> bool:
        """
        Check if byte is a valid text character.
        
        Args:
            byte: Byte value to check
            
        Returns:
            True if valid text character
        """
        # ASCII printable range
        if 0x20 <= byte <= 0x7E:
            return True
        
        # Shift-JIS ranges
        if 0x81 <= byte <= 0x9F or 0xE0 <= byte <= 0xFC:
            return True
        
        return False
    
    def save_to_file(self, output_path: str, format: str = 'txt'):
        """
        Save extracted texts to file.
        
        Args:
            output_path: Output file path
            format: Output format ('txt', 'json', 'csv')
        """
        output_path = Path(output_path)
        
        if format == 'txt':
            with open(output_path, 'w', encoding='utf-8') as f:
                for item in self.texts:
                    f.write(f"{item['text']}\n")
        
        elif format == 'json':
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(self.texts, f, ensure_ascii=False, indent=2)
        
        elif format == 'csv':
            import csv
            with open(output_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['offset', 'size', 'text', 'raw'])
                writer.writeheader()
                writer.writerows(self.texts)
        
        print(f"✅ Saved to: {output_path}")
    
    def extract_with_pointers(self, pointer_table_offset: int, 
                             pointer_count: int,
                             base_address: int = 0) -> List[Dict]:
        """
        Extract texts using pointer table.
        
        Args:
            pointer_table_offset: Offset of pointer table in ROM
            pointer_count: Number of pointers in table
            base_address: Base address for pointer calculation
            
        Returns:
            List of extracted texts with pointer info
        """
        if self.rom_data is None:
            self.load_rom()
        
        extracted = []
        
        for i in range(pointer_count):
            ptr_offset = pointer_table_offset + (i * 4)
            
            if ptr_offset + 4 > len(self.rom_data):
                break
            
            # Read 32-bit pointer
            pointer = struct.unpack('<I', self.rom_data[ptr_offset:ptr_offset+4])[0]
            text_offset = pointer - base_address
            
            if 0 <= text_offset < len(self.rom_data):
                # Extract null-terminated string
                text_bytes = bytearray()
                offset = text_offset
                
                while offset < len(self.rom_data) and self.rom_data[offset] != 0:
                    text_bytes.append(self.rom_data[offset])
                    offset += 1
                
                try:
                    decoded = text_bytes.decode(self.encoding, errors='ignore')
                    if decoded.strip():
                        extracted.append({
                            'index': i,
                            'pointer_offset': hex(ptr_offset),
                            'text_offset': hex(text_offset),
                            'pointer_value': hex(pointer),
                            'text': decoded.strip(),
                            'size': len(text_bytes)
                        })
                except:
                    pass
        
        self.texts = extracted
        print(f"✅ Extracted {len(extracted)} texts using pointers")
        return extracted


def main():
    """Main CLI interface."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='ROM Text Extractor - Extract text strings from ROM files'
    )
    parser.add_argument('rom_file', help='Path to ROM file')
    parser.add_argument('-o', '--output', default='extracted_texts.txt',
                       help='Output file path')
    parser.add_argument('-f', '--format', choices=['txt', 'json', 'csv'],
                       default='txt', help='Output format')
    parser.add_argument('--encoding', default='shift-jis',
                       help='Text encoding (default: shift-jis)')
    parser.add_argument('--min-length', type=int, default=4,
                       help='Minimum text length to extract')
    parser.add_argument('--start', type=lambda x: int(x, 0), default=0,
                       help='Start offset (supports hex: 0x1000)')
    parser.add_argument('--end', type=lambda x: int(x, 0), default=None,
                       help='End offset (supports hex: 0x1000)')
    
    args = parser.parse_args()
    
    # Create extractor
    config = {'encoding': args.encoding}
    extractor = TextExtractor(args.rom_file, config)
    
    # Extract texts
    extractor.extract_texts(
        start_offset=args.start,
        end_offset=args.end,
        min_length=args.min_length
    )
    
    # Save results
    extractor.save_to_file(args.output, args.format)
    
    print("\n✅ Extraction complete!")
    print(f"   Total texts: {len(extractor.texts)}")
    print(f"   Output file: {args.output}")


if __name__ == '__main__':
    main()
