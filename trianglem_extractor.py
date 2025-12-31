#!/usr/bin/env python3
"""
TriangleM Engine Script Decompiler
by Sunnie Evergale
Extracts .tat script files from TriangleM engine games (memfs/membody format)
"""

import struct
import zlib
import os
import sys
import json
from pathlib import Path
from typing import List, Dict, Tuple, Optional


class RSONError(Exception):
    """RSON parsing error"""
    pass


class MemFSParser:
    """Parser for TriangleM .memfs files (RSON format)"""

    ENTRY_MARKER = 0x2002c800  # Marker that appears before entries
    PATH_PREFIX = 0x00003488  # Prefix before path strings (byteswapped)

    def __init__(self, memfs_data: bytes):
        self.data = memfs_data
        self.files: List[Dict[str, any]] = []
        self._parse()

    def _parse(self):
        """Parse the memfs RSON structure"""
        pos = 16  # Skip RSON header

        # First pass: find all paths and their metadata
        paths = []
        search_pos = 0

        while search_pos < len(self.data):
            # Look for slash in UTF-16LE to find paths
            if self.data[search_pos:search_pos+2] == b'\x2f\x00':
                end = search_pos
                while end + 1 < len(self.data) and self.data[end:end+2] != b'\x00\x00':
                    end += 2
                try:
                    path = self.data[search_pos:end].decode('utf-16le')
                    if '.tat' in path or '.json' in path or '.armd' in path:
                        paths.append((search_pos, path))
                except:
                    pass
                search_pos = end
            else:
                search_pos += 1

        # Second pass: extract entries with offsets and sizes
        # The structure appears to be pairs of values before each path
        i = 0
        for path_offset, path in paths:
            # Look back from the path to find the metadata
            # Pattern seems to be: [marker?] [offset] [size?] [path_prefix] [path]
            check_pos = path_offset - 16
            if check_pos < 0:
                continue

            # Check for path prefix
            path_prefix = struct.unpack('<H', self.data[check_pos+8:check_pos+10])[0]

            # Try to extract offset and size
            d1 = struct.unpack('<I', self.data[check_pos:check_pos+4])[0]
            d2 = struct.unpack('<I', self.data[check_pos+4:check_pos+8])[0]

            # One of these is likely the offset, one is size
            # We'll need to correlate with actual membody data
            self.files.append({
                'path': path,
                'metadata_offset': check_pos,
                'val1': d1,
                'val2': d2,
                'path_prefix': path_prefix,
            })
            i += 1

        print(f"Found {len(self.files)} files in memfs")

    def get_files(self) -> List[Dict[str, any]]:
        """Return list of files found"""
        return self.files


class MemBodyExtractor:
    """Extract files from .membody (RZ compressed format)"""

    def __init__(self, membody_data: bytes):
        self.data = membody_data

        # Verify header
        if self.data[:2] != b'RZ':
            raise ValueError(f"Invalid membody header: {self.data[:2]}")

        # Skip RZ header (2 bytes) and unknown bytes
        # The deflate stream starts after some header bytes
        self._find_deflate_start()

    def _find_deflate_start(self):
        """Find the start of the deflate stream"""
        # Look for zlib header (78 9c or 78 da)
        for i in range(2, min(100, len(self.data))):
            if self.data[i:i+2] == b'\x78\x9c' or self.data[i:i+2] == b'\x78\xda':
                self.compress_offset = i
                print(f"Found deflate stream at offset: {i}")
                return
        raise ValueError("Could not find deflate stream")

    def decompress(self) -> bytes:
        """Decompress the membody data"""
        stream = self.data[self.compress_offset:]
        try:
            decompressed = zlib.decompress(stream)
            print(f"Decompressed: {len(stream)} -> {len(decompressed)} bytes")
            return decompressed
        except zlib.error as e:
            # Try raw deflate
            try:
                decompressor = zlib.decompressobj(-15)
                decompressed = decompressor.decompress(stream)
                print(f"Decompressed (raw deflate): {len(stream)} -> {len(decompressed)} bytes")
                return decompressed
            except:
                raise ValueError(f"Failed to decompress: {e}")

    def find_file_data(self, decompressed: bytes, files: List[Dict]) -> Dict[str, bytes]:
        """Find individual files within the decompressed data"""
        result = {}

        # The decompressed data contains concatenated .tat files
        # Each file starts with a scene header like [XXX_XX_XXX_TOP] or [GALLERY_SCENE_XXX_START]
        # Skip UTF-8 BOM if present
        pos = 3 if decompressed[:3] == b'\xef\xbb\xbf' else 0

        file_num = 0
        while pos < len(decompressed):
            # Look for scene header pattern: [text]
            if decompressed[pos:pos+1] == b'[':
                # Find the end of the header
                end = pos + 1
                while end < len(decompressed) and decompressed[end:end+1] != b']':
                    end += 1

                if end < len(decompressed):
                    header = decompressed[pos:end+1].decode('utf-8', errors='ignore')
                    # Check if this looks like a scene header
                    if '_TOP]' in header or '_START]' in header or '_END]' in header:
                        # Found a scene boundary
                        start_pos = pos

                        # Look for next scene header or end of data
                        next_pos = end + 1
                        while next_pos < len(decompressed):
                            if decompressed[next_pos:next_pos+1] == b'[':
                                # Check if this is a scene header
                                check_end = next_pos + 1
                                while check_end < len(decompressed) and decompressed[check_end:check_end+1] != b']':
                                    check_end += 1
                                if check_end < len(decompressed):
                                    next_header = decompressed[next_pos:check_end+1].decode('utf-8', errors='ignore')
                                    if '_TOP]' in next_header or '_START]' in next_header or '_END]' in next_header:
                                        break
                            next_pos += 1

                        # Extract the file data
                        file_data = decompressed[start_pos:next_pos]

                        # Generate filename from header
                        # Remove brackets and create .tat filename
                        scene_name = header.strip('[]')
                        # Try to map to actual file paths
                        filename = f"{scene_name}.tat"

                        # Also try to find matching path from files list
                        for f in files:
                            if scene_name.split('_')[0] in f['path']:
                                filename = f['path'].lstrip('/')
                                break

                        result[filename] = file_data
                        file_num += 1
                        pos = next_pos
                        continue

            pos += 1

        print(f"Split into {len(result)} files")
        return result


class TATParser:
    """Parser for .tat script files"""

    def __init__(self, tat_data: bytes, filename: str = "unknown"):
        self.data = tat_data
        self.filename = filename
        self.text_content = tat_data.decode('utf-8', errors='ignore')

    def extract_dialogue(self) -> List[Dict[str, str]]:
        """Extract dialogue lines from .tat file for translation

        Script format:
        ｛Speaker Name｝
        「Dialogue text」<KW><WinClear ON>

        Or text without speaker:
        「Dialogue text」<KW><WinClear>
        """
        results = []

        lines = self.text_content.split('\n')

        current_speaker = None
        current_context = []

        for line_num, line in enumerate(lines):
            original_line = line
            line = line.rstrip()

            # Check for speaker name in curly braces
            if line.startswith('｛') and '｝' in line:
                current_speaker = line.strip('｛｝')
                current_context.append(f"// Line {line_num}: {line}")
                continue

            # Check for dialogue in quotes
            if '「' in line and '」' in line:
                # Extract dialogue text
                start = line.find('「') + 1
                end = line.find('」')
                if start > 0 and end > start:
                    dialogue = line[start:end].strip()

                    # Check if dialogue contains Japanese text and is meaningful
                    if self._has_japanese(dialogue) and len(dialogue) >= 2:
                        # Build context string
                        context_lines = []
                        # Include previous 2 lines of context (skip comments and empty lines)
                        count = 0
                        for i in range(line_num - 1, max(0, line_num - 3), -1):
                            ctx_line = lines[i].strip()
                            if ctx_line and not ctx_line.startswith('//'):
                                context_lines.insert(0, ctx_line)
                                count += 1
                            if count >= 2:
                                break

                        # Get scene header if available
                        scene_header = self._get_scene_header()

                        results.append({
                            'file': self.filename,
                            'line': line_num + 1,
                            'speaker': current_speaker or '',
                            'text': dialogue,
                            'full_line': line,
                            'context': '\n'.join(context_lines),
                            'scene': scene_header
                        })

                current_speaker = None

            # Also check for narrative text (outside dialogue quotes)
            # Skip lines that are purely script commands
            elif (not line.startswith('//') and
                  not line.startswith('<') and
                  not line.startswith('｛') and
                  self._has_japanese(line)):

                # Remove any trailing script commands
                cleaned_text = line
                for tag in ['<KW>', '<WinClear>', '<WinClear ON>', '<WinClear OFF>', '</n>', '<TW']:
                    cleaned_text = cleaned_text.replace(tag, '')

                cleaned_text = cleaned_text.strip()

                # Check if this is meaningful narrative text
                if (len(cleaned_text) >= 4 and
                    len(cleaned_text) < 200 and
                    self._has_japanese(cleaned_text) and
                    not cleaned_text.startswith('[')):

                    # Build context
                    context_lines = []
                    count = 0
                    for i in range(line_num - 1, max(0, line_num - 3), -1):
                        ctx_line = lines[i].strip()
                        if ctx_line and not ctx_line.startswith('//'):
                            context_lines.insert(0, ctx_line)
                            count += 1
                        if count >= 2:
                            break

                    scene_header = self._get_scene_header()

                    results.append({
                        'file': self.filename,
                        'line': line_num + 1,
                        'speaker': '',
                        'text': cleaned_text,
                        'full_line': line,
                        'context': '\n'.join(context_lines),
                        'scene': scene_header,
                        'type': 'narrative'
                    })

        return results

    def _has_japanese(self, text: str) -> bool:
        """Check if text contains Japanese characters"""
        # Hiragana (3040-309F), Katakana (30A0-30FF), Kanji (4E00-9FFF)
        return any(0x3040 <= ord(c) <= 0x9FFF for c in text)

    def _get_scene_header(self) -> str:
        """Extract the scene header from the file"""
        lines = self.text_content.split('\n')
        for line in lines[:20]:  # Check first 20 lines
            if line.startswith('[') and ']' in line:
                return line.strip()
        return ""


def extract_game_files(game_dir: str, output_dir: str):
    """Main extraction function"""
    game_path = Path(game_dir)
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    # Find fsroot directories
    fsroot_dirs = sorted([d for d in game_path.glob("fsroot*") if d.is_dir()])

    if not fsroot_dirs:
        print(f"No fsroot directories found in {game_dir}")
        return

    for fsroot in fsroot_dirs:
        print(f"\n=== Processing {fsroot} ===")

        # Find script files
        script_dir = fsroot / "common"
        if not script_dir.exists():
            print(f"  No common directory in {fsroot}")
            continue

        memfs_file = script_dir / "script.memfs"
        membody_file = script_dir / "script.membody"

        if not memfs_file.exists() or not membody_file.exists():
            print(f"  No script.memfs/membody in {script_dir}")
            continue

        print(f"  Found: {memfs_file.name} + {membody_file.name}")

        # Read files
        memfs_data = memfs_file.read_bytes()
        membody_data = membody_file.read_bytes()

        # Parse memfs
        print("\n  Parsing memfs...")
        parser = MemFSParser(memfs_data)
        files = parser.get_files()

        # Decompress membody
        print("\n  Decompressing membody...")
        extractor = MemBodyExtractor(membody_data)
        decompressed = extractor.decompress()

        # Save decompressed data for inspection
        decompressed_file = output_path / f"{fsroot.name}_decompressed.bin"
        decompressed_file.write_bytes(decompressed)
        print(f"  Saved decompressed data to: {decompressed_file}")

        # Also save the file list
        files_json = output_path / f"{fsroot.name}_files.json"
        with open(files_json, 'w', encoding='utf-8') as f:
            json.dump(files, f, ensure_ascii=False, indent=2)
        print(f"  Saved file list to: {files_json}")

        # Save first 1000 bytes of decompressed data for inspection
        inspect_file = output_path / f"{fsroot.name}_inspect.txt"
        with open(inspect_file, 'w', encoding='utf-8') as f:
            f.write(f"First 1000 bytes of decompressed data:\n")
            f.write("=" * 50 + "\n")
            f.write(decompressed[:1000].hex() + "\n")
            f.write("=" * 50 + "\n")
            # Try to find printable strings
            f.write("\nPrintable strings:\n")
            pos = 0
            while pos < len(decompressed) - 20:
                try:
                    # Look for Japanese text
                    if decompressed[pos] >= 0xE0:
                        end = pos
                        while end < len(decompressed) and decompressed[end] != 0:
                            end += 1
                        if end - pos > 3:
                            text = decompressed[pos:end].decode('utf-8')
                            if any(0x3040 <= ord(c) <= 0x9FFF for c in text):
                                f.write(f"0x{pos:06x}: {text}\n")
                        pos = end
                    else:
                        pos += 1
                except:
                    pos += 1
        print(f"  Saved inspection data to: {inspect_file}")

        # Split decompressed data into individual .tat files
        print("\n  Splitting into individual .tat files...")
        tat_files = extractor.find_file_data(decompressed, files)

        # Save individual .tat files
        tat_dir = output_path / "tat_files"
        tat_dir.mkdir(exist_ok=True)

        for filename, data in tat_files.items():
            # Sanitize filename
            safe_filename = filename.replace('/', '_').replace('\\', '_')
            if not safe_filename.endswith('.tat'):
                safe_filename += '.tat'

            tat_path = tat_dir / safe_filename
            tat_path.write_bytes(data)

        print(f"  Saved {len(tat_files)} .tat files to: {tat_dir}")

        # Print summary of files found vs extracted
        print("\n  === File Extraction Summary ===")
        print(f"  Memfs index entries: {len(files)}")
        print(f"  Scenes with content: {len(tat_files)}")
        print(f"  Index entries without content: {len(files) - len(tat_files)}")
        print(f"  ")

        # Show route breakdown
        from collections import defaultdict
        routes = defaultdict(list)
        for f in files:
            if '/' in f['path']:
                route = f['path'].split('/')[1]
            else:
                route = '(root)'
            routes[route].append(f['path'])

        print(f"  Routes in memfs index:")
        for route in sorted(routes.keys()):
            print(f"    {route}/: {len(routes[route])} files")

        print(f"  ")
        print(f"  NOTE: This game uses a route-based structure. The memfs index")
        print(f"  is a master catalog for the entire series. Only {len(tat_files)} scenes")
        print(f"  have actual content in THIS volume. Other routes (101_wataru,")
        print(f"  102_yosuke, 103_toriai) are likely in separate game volumes.")

        # Extract dialogue from all .tat files
        print("\n  Extracting dialogue text...")
        all_dialogue = []

        for filename, data in tat_files.items():
            parser = TATParser(data, filename)
            dialogue = parser.extract_dialogue()
            all_dialogue.extend(dialogue)

        print(f"  Extracted {len(all_dialogue)} dialogue lines")

        # Save dialogue to JSON
        dialogue_json = output_path / f"{fsroot.name}_dialogue.json"
        with open(dialogue_json, 'w', encoding='utf-8') as f:
            json.dump(all_dialogue, f, ensure_ascii=False, indent=2)
        print(f"  Saved dialogue to: {dialogue_json}")

        # Also save a human-readable translation template
        template_file = output_path / f"{fsroot.name}_translation_template.txt"
        with open(template_file, 'w', encoding='utf-8') as f:
            for i, entry in enumerate(all_dialogue, 1):
                f.write(f"=== Entry {i} ===\n")
                f.write(f"File: {entry['file']}\n")
                f.write(f"Line: {entry['line']}\n")
                f.write(f"Scene: {entry['scene']}\n")
                if entry.get('speaker'):
                    f.write(f"Speaker: {entry['speaker']}\n")
                f.write(f"Context:\n{entry['context']}\n")
                f.write(f"\nOriginal Text:\n{entry['text']}\n")
                f.write(f"\nTranslation:\n[ENTER TRANSLATION HERE]\n")
                f.write("\n" + "-" * 60 + "\n\n")

        print(f"  Saved translation template to: {template_file}")

        # Print detailed statistics
        dialogue_with_speakers = [d for d in all_dialogue if d.get('speaker')]
        narrative = [d for d in all_dialogue if d.get('type') == 'narrative']
        scenes = set(d.get('scene', '') for d in all_dialogue)
        speakers = set(d.get('speaker', '') for d in all_dialogue if d.get('speaker'))

        print("\n  === Dialogue Extraction Statistics ===")
        print(f"  Total dialogue entries: {len(all_dialogue)}")
        print(f"  - With speaker names: {len(dialogue_with_speakers)}")
        print(f"  - Narrative text: {len(narrative)}")
        print(f"  Unique scenes: {len(scenes)}")
        print(f"  Unique speakers: {len(speakers)}")

        # List all scenes found
        print(f"\n  Scenes found:")
        for scene in sorted(scenes):
            entries = [d for d in all_dialogue if d.get('scene') == scene]
            print(f"    {scene}: {len(entries)} dialogue lines")


def main():
    if len(sys.argv) < 2:
        print("Usage: python trianglem_extractor.py <game_dir> [output_dir]")
        print("\nExample:")
        print('  python trianglem_extractor.py "C:\\Program Files (x86)\\triangle\\Tlicolity Eyes Vol.2"')
        sys.exit(1)

    game_dir = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "extracted_output"

    extract_game_files(game_dir, output_dir)
    print(f"\n=== Extraction complete! Check {output_dir} ===")


if __name__ == "__main__":
    main()
