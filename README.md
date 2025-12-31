# TriangleM Engine Script Decompiler

A tool to extract and decompile script files from visual novel games built with the TriangleM engine (e.g., "Tlicolity Eyes Vol.2").

*Developed by Sunnie Evergale*


## Overview

This tool extracts Japanese dialogue text from TriangleM engine games for translation purposes. It handles the proprietary memfs/membody virtual filesystem format used by TriangleM games to store compressed script data, and outputs translation-friendly JSON and text files.

---


## 🎯 Targeted Games

This tool is specifically designed for the **Tlicolity Eyes Series** on PC

---



## Support

If you found this project helpful, consider supporting my work:

[![ko-fi](https://media4.giphy.com/media/v1.Y2lkPTc5MGI3NjExdXpoa2NnaHdhNDl2ajNneXFkemxzbzhxdm1nYXZiYTNsazlxeHJkZCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9cw/DzBUMIyTeHDuigQOoh/giphy.gif)](https://ko-fi.com/sunnieevergale)


---

## Features

- Parses RSON format memfs index files
- Decompresses RZ format membody data files
- Extracts .tat script files with scene headers, speaker names, and dialogue
- Generates translation-friendly output (JSON and human-readable templates)
- Preserves context for each dialogue line

## Usage

### Basic Usage

```bash
python3 trianglem_extractor.py "/path/to/game" [output_dir]
```

**Example:**
```bash
python3 trianglem_extractor.py "C:\Program Files (x86)\triangle\Tlicolity Eyes Vol.2" extracted_output
```

### Output Files

After extraction, the output directory will contain:

| File | Description |
|------|-------------|
| `fsroot*_files.json` | File index from memfs |
| `fsroot*_decompressed.bin` | Raw decompressed membody data |
| `fsroot*_inspect.txt` | Inspection dump of first bytes |
| `tat_files/*.tat` | Individual extracted scene files |
| `fsroot*_dialogue.json` | Machine-readable dialogue data |
| `fsroot*_translation_template.txt` | Human-readable translation template |

### Dialogue JSON Format

```json
{
  "file": "100_kyo2/100_02_001.tat",
  "line": 38,
  "scene": "[100_00_001_TOP]",
  "speaker": "東地　${FirstName}",
  "text": "い、嫌です！　やめてぇ！",
  "full_line": "「い、嫌です！　やめてぇ！」<KW><WinClear ON>",
  "context": "｛東地　${FirstName}｝"
}
```

## Requirements

- Python 3.6+
- Standard library: `struct`, `zlib`, `json`, `pathlib`

## Technical Documentation

For detailed information about TriangleM engine file formats (RSON, RZ, TAT), decompilation process, and investigation findings, see [FORMAT_DOCUMENTATION.md](FORMAT_DOCUMENTATION.md).

## License

This tool is provided as-is for educational and translation purposes.

## Credits

- TriangleM engine by Triangle (game company)
- Decompression uses standard zlib library
