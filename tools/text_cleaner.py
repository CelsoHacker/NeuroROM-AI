#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROM Text Cleaner - Professional Text Cleaning Tool
===================================================

Advanced text cleaning and optimization utility for ROM translation projects.
Handles special characters, formatting codes, and text normalization.

Author: ROM Translation Framework
Version: 3.0.0
License: Proprietary
"""

import re
import sys
import json
from pathlib import Path
from typing import List, Dict, Set, Tuple, Optional
from collections import Counter


class TextCleaner:
    """Professional text cleaning and optimization tool."""
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize the text cleaner.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self.stats = {
            'total_lines': 0,
            'cleaned_lines': 0,
            'removed_lines': 0,
            'special_chars_found': Counter(),
            'control_codes_found': Counter()
        }
        
    def clean_text_file(self, 
                       input_path: str,
                       output_path: str,
                       remove_control_codes: bool = True,
                       normalize_whitespace: bool = True,
                       remove_duplicates: bool = False,
                       min_length: int = 1) -> Dict:
        """
        Clean a text file with multiple optimization passes.
        
        Args:
            input_path: Input file path
            output_path: Output file path
            remove_control_codes: Remove control/formatting codes
            normalize_whitespace: Normalize spaces and line breaks
            remove_duplicates: Remove duplicate lines
            min_length: Minimum line length to keep
            
        Returns:
            Dictionary with cleaning statistics
        """
        print(f"🧹 Cleaning text file: {input_path}")
        
        # Read input file
        with open(input_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        self.stats['total_lines'] = len(lines)
        print(f"   📄 Total lines: {len(lines):,}")
        
        # Clean each line
        cleaned_lines = []
        seen = set()
        
        for line in lines:
            # Clean the line
            cleaned = self._clean_line(
                line,
                remove_control_codes=remove_control_codes,
                normalize_whitespace=normalize_whitespace
            )
            
            # Skip if too short
            if len(cleaned.strip()) < min_length:
                self.stats['removed_lines'] += 1
                continue
            
            # Skip duplicates if requested
            if remove_duplicates:
                if cleaned in seen:
                    self.stats['removed_lines'] += 1
                    continue
                seen.add(cleaned)
            
            cleaned_lines.append(cleaned)
            self.stats['cleaned_lines'] += 1
        
        # Write output file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(cleaned_lines))
        
        print(f"   ✅ Cleaned lines: {self.stats['cleaned_lines']:,}")
        print(f"   🗑️  Removed lines: {self.stats['removed_lines']:,}")
        print(f"   💾 Saved to: {output_path}")
        
        return self.stats
    
    def _clean_line(self,
                   line: str,
                   remove_control_codes: bool = True,
                   normalize_whitespace: bool = True) -> str:
        """
        Clean a single line of text.
        
        Args:
            line: Input line
            remove_control_codes: Remove control codes
            normalize_whitespace: Normalize whitespace
            
        Returns:
            Cleaned line
        """
        # Remove BOM if present
        line = line.replace('\ufeff', '')
        
        # Remove control codes if requested
        if remove_control_codes:
            line = self._remove_control_codes(line)
        
        # Normalize whitespace if requested
        if normalize_whitespace:
            line = self._normalize_whitespace(line)
        
        return line.strip()
    
    def _remove_control_codes(self, text: str) -> str:
        """
        Remove common control and formatting codes.
        
        Args:
            text: Input text
            
        Returns:
            Text with control codes removed
        """
        # Common control code patterns
        patterns = [
            r'\[.*?\]',           # [CODE]
            r'\{.*?\}',           # {CODE}
            r'<.*?>',             # <CODE>
            r'\\x[0-9A-Fa-f]{2}', # \xHH
            r'\\[nrt]',           # \n \r \t
            r'\$[0-9A-Fa-f]+',    # $HEX
            r'@[0-9A-Fa-f]+',     # @HEX
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                self.stats['control_codes_found'][match] += 1
            text = re.sub(pattern, '', text)
        
        return text
    
    def _normalize_whitespace(self, text: str) -> str:
        """
        Normalize whitespace in text.
        
        Args:
            text: Input text
            
        Returns:
            Text with normalized whitespace
        """
        # Replace multiple spaces with single space
        text = re.sub(r' +', ' ', text)
        
        # Replace tabs with spaces
        text = text.replace('\t', ' ')
        
        # Remove leading/trailing whitespace
        text = text.strip()
        
        return text
    
    def analyze_special_characters(self, input_path: str) -> Dict:
        """
        Analyze special characters in text file.
        
        Args:
            input_path: Input file path
            
        Returns:
            Dictionary with character analysis
        """
        print(f"🔍 Analyzing special characters in: {input_path}")
        
        with open(input_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find all non-ASCII characters
        special_chars = Counter()
        for char in content:
            if ord(char) > 127:  # Non-ASCII
                special_chars[char] += 1
        
        # Sort by frequency
        sorted_chars = sorted(special_chars.items(), 
                            key=lambda x: x[1], 
                            reverse=True)
        
        print(f"\n📊 Special Characters Found: {len(special_chars)}")
        print("\nTop 20 most frequent:")
        print("-" * 50)
        for char, count in sorted_chars[:20]:
            print(f"  '{char}' (U+{ord(char):04X}): {count:,} occurrences")
        
        return {
            'total_special_chars': len(special_chars),
            'characters': dict(sorted_chars)
        }
    
    def deduplicate_file(self, 
                        input_path: str,
                        output_path: str,
                        case_sensitive: bool = True) -> Tuple[int, int]:
        """
        Remove duplicate lines from file.
        
        Args:
            input_path: Input file path
            output_path: Output file path
            case_sensitive: Case-sensitive comparison
            
        Returns:
            Tuple of (original count, deduplicated count)
        """
        print(f"🔄 Deduplicating file: {input_path}")
        
        with open(input_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        original_count = len(lines)
        
        # Deduplicate
        seen = set()
        unique_lines = []
        
        for line in lines:
            key = line.strip()
            if not case_sensitive:
                key = key.lower()
            
            if key not in seen and key:
                seen.add(key)
                unique_lines.append(line.strip())
        
        # Write output
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(unique_lines))
        
        final_count = len(unique_lines)
        removed = original_count - final_count
        
        print(f"   ✅ Original lines: {original_count:,}")
        print(f"   ✅ Unique lines: {final_count:,}")
        print(f"   🗑️  Removed duplicates: {removed:,}")
        print(f"   💾 Saved to: {output_path}")
        
        return (original_count, final_count)
    
    def optimize_for_translation(self,
                                input_path: str,
                                output_path: str) -> None:
        """
        Optimize text file for AI translation.
        
        Applies all recommended cleaning and optimization steps.
        
        Args:
            input_path: Input file path
            output_path: Output file path
        """
        print("\n🚀 Optimizing for AI Translation")
        print("=" * 60)
        
        # Step 1: Clean
        self.clean_text_file(
            input_path,
            output_path + '.temp1',
            remove_control_codes=True,
            normalize_whitespace=True,
            remove_duplicates=False,
            min_length=2
        )
        
        # Step 2: Deduplicate
        self.deduplicate_file(
            output_path + '.temp1',
            output_path,
            case_sensitive=True
        )
        
        # Step 3: Analyze
        self.analyze_special_characters(output_path)
        
        # Cleanup temp file
        Path(output_path + '.temp1').unlink()
        
        print("\n✅ Optimization complete!")


def main():
    """Main CLI interface."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='ROM Text Cleaner - Professional text cleaning tool'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Clean command
    clean_parser = subparsers.add_parser('clean', help='Clean text file')
    clean_parser.add_argument('input', help='Input file')
    clean_parser.add_argument('output', help='Output file')
    clean_parser.add_argument('--no-control-codes', action='store_true',
                            help='Keep control codes')
    clean_parser.add_argument('--no-normalize', action='store_true',
                            help='Don\'t normalize whitespace')
    clean_parser.add_argument('--remove-duplicates', action='store_true',
                            help='Remove duplicate lines')
    clean_parser.add_argument('--min-length', type=int, default=1,
                            help='Minimum line length')
    
    # Analyze command
    analyze_parser = subparsers.add_parser('analyze', 
                                          help='Analyze special characters')
    analyze_parser.add_argument('input', help='Input file')
    
    # Deduplicate command
    dedup_parser = subparsers.add_parser('deduplicate', 
                                        help='Remove duplicates')
    dedup_parser.add_argument('input', help='Input file')
    dedup_parser.add_argument('output', help='Output file')
    dedup_parser.add_argument('--case-insensitive', action='store_true',
                            help='Case-insensitive comparison')
    
    # Optimize command
    optimize_parser = subparsers.add_parser('optimize',
                                           help='Full optimization for translation')
    optimize_parser.add_argument('input', help='Input file')
    optimize_parser.add_argument('output', help='Output file')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    cleaner = TextCleaner()
    
    if args.command == 'clean':
        cleaner.clean_text_file(
            args.input,
            args.output,
            remove_control_codes=not args.no_control_codes,
            normalize_whitespace=not args.no_normalize,
            remove_duplicates=args.remove_duplicates,
            min_length=args.min_length
        )
    
    elif args.command == 'analyze':
        cleaner.analyze_special_characters(args.input)
    
    elif args.command == 'deduplicate':
        cleaner.deduplicate_file(
            args.input,
            args.output,
            case_sensitive=not args.case_insensitive
        )
    
    elif args.command == 'optimize':
        cleaner.optimize_for_translation(args.input, args.output)


if __name__ == '__main__':
    main()
