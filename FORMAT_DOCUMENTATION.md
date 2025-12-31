# TriangleM Engine File Format Documentation

This document provides detailed technical information about the TriangleM engine file formats, decompilation process, and investigation findings.

## TriangleM Engine File Formats

### RSON Format (`.memfs` files)

RSON is TriangleM's binary file index format. It contains a catalog of files stored in the virtual filesystem.

**Structure:**
- Header: `"RSON"` magic bytes + version info
- File entries with UTF-16LE encoded strings
- Each entry contains:
  - `path`: File path in UTF-16LE (e.g., `/102_yosuke/102_00_001.tat`)
  - `metadata_offset`: Position of metadata in memfs
  - `val1`: UTF-16LE encoded type string (e.g., `0x00310030` = "01")
  - `val2`: UTF-16LE encoded extension (e.g., `0x0074002e` = ".t")
  - `path_prefix`: Prefix value for path strings

**Note:** `val1` and `val2` are NOT file offsets - they are metadata fields encoded as UTF-16LE strings.

### RZ Format (`.membody` files)

RZ is TriangleM's compressed data format containing the actual file contents.

**Structure:**
- Header: `"RZ"` (2 bytes)
- Unknown bytes (4 bytes)
- Deflate stream starting at offset 6
- Standard zlib/deflate compression

**Decompression:**
```python
# Find deflate stream (typically starts with 0x78 0x9c or 0x78 0xda)
for i in range(2, 100):
    if data[i:i+2] in [b'\x78\x9c', b'\x78\xda']:
        decompressed = zlib.decompress(data[i:])
        break
```

### TAT Format (`.tat` script files)

TAT is TriangleM's script format containing game dialogue and commands.

**Structure:**
```
[SCENE_NAME]

// Comments start with //
// Scene metadata

｛Speaker Name｝
「Dialogue text」<KW><WinClear>

// Script commands
<Mov VARIABLE,VALUE>
<TW milliseconds>
<SoundLoad id,filename>
<ImageLoad id,filename>
```

**Elements:**
- **Scene headers**: `[SCENE_NAME]` - Marks the beginning of a scene
- **Speaker names**: `｛Name｝` - Full-width curly braces (U+FF5B/U+FF5D)
- **Dialogue**: `「Text」` - Full-width quotation marks (U+300C/U+300D)
- **Commands**:
  - `<Mov var,val>` - Set variable
  - `<TW ms>` - Wait/timer
  - `<SoundLoad id,file>` - Load sound
  - `<ImageLoad id,file>` - Load image
  - `<KW>` - Continue/advance marker
  - `<WinClear ON/OFF>` - Window clear control

## Decompilation Process

The decompilation follows these steps:

1. **Locate script files**: Find `script.memfs` and `script.membody` in the game's `fsroot*/common/` directory

2. **Parse memfs index**: Extract file catalog from RSON format
   - Find UTF-16LE encoded paths (e.g., `/102_yosuke/102_00_001.tat`)
   - Parse metadata for each file entry

3. **Decompress membody**: Extract RZ compressed data
   - Skip "RZ" header (6 bytes)
   - Decompress using zlib

4. **Split into .tat files**: Find scene boundaries
   - Look for scene headers: `[XXX_XXX_XXX_TOP/START/END]`
   - Split decompressed data at each scene boundary

5. **Extract dialogue**: Parse .tat files for translatable content
   - Find speaker names: `｛Name｝`
   - Extract dialogue: `「Text」`
   - Preserve context (surrounding commands and scene info)

6. **Generate output**: Create translation-friendly files
   - JSON with all dialogue entries
   - Human-readable text template for translators

## File Structure Details

### RZ Format Header Structure

```
Offset | Size | Description
-------|------|-------------
0x00   | 2    | Magic: "RZ"
0x02   | 4    | Decompressed size (BIG-ENDIAN u32)
0x06   | var  | Deflate compressed data
```

**Note:** The decompressed size is stored as **big-endian** (unusual for Windows games). For example:
- `0x00021b0f` (big-endian) = 137,999 bytes

### Memfs Index vs Actual Content

The memfs index (`script.memfs`) serves as a **master catalog** for the entire game series, but individual games only contain specific character routes.

**Route-Based Game Structure:**

The 48 files in the index are organized by character routes:

| Route | Files | Description |
|-------|-------|-------------|
| 100_kyo2 | 7 files | Kyo's route |
| 101_wataru | 12 files | Wataru's route |
| 102_yosuke | 12 files | Yosuke's route |
| 103_toriai | 9 files | Toriai's route |
| 104_omake | 3 files | Bonus content |
| Other | 5 files | Common, start, etc. |

**Tlicolity Eyes Vol.2 - Extracted Content:**

This is "Vol.2" of the series, which contains content for specific routes:

| Scene | Size | Dialogue Lines |
|-------|------|----------------|
| [100_00_001_TOP] | 86KB | 676 (main Kyo chapter) |
| [GALLERY_SCENE_100_001_START] | 6KB | 60 |
| [GALLERY_SCENE_100_001_END] | 7KB | 53 |
| [GALLERY_SCENE_100_002_START] | 6KB | 62 |
| [GALLERY_SCENE_100_002_END] | 33KB | 225 |

**Total: 5 scenes, 1,076 dialogue lines extracted**

### Why Are Some Routes Missing?

The TriangleM games use a **route-based structure** where:
1. Each character route may be sold as a separate volume (Vol.1, Vol.2, etc.)
2. The memfs index is a master catalog for the entire series
3. Individual games only contain the routes included in that volume
4. To extract Wataru, Yosuke, or Toriai routes, you would need their respective game volumes

**Investigation Results:**
- All 32 membody files in the game directory were checked
- Only `script.membody` contains RZ-format script data
- ssdata RSON files contain textures (.rtex) and binary assets, not scripts
- No other script sources exist in this game directory

### Extraction Statistics for Tlicolity Eyes Vol.2

| Metric | Count |
|--------|-------|
| Memfs index entries | 48 |
| Actual scenes extracted | 5 |
| Total dialogue lines | 1,076 |
| Lines with speakers | 136 |
| Narrative lines | 940 |
| Unique speakers | 10 |
| Decompressed size | 137,999 bytes |

### Character Routes in the Index (Not Extracted)

The following routes are indexed but not present in Vol.2:
- **101_wataru** (12 files) - Wataru's route → Likely in another volume
- **102_yosuke** (12 files) - Yosuke's route → Likely in another volume
- **103_toriai** (9 files) - Toriai's route → Likely in another volume
- **104_omake** (3 files) - Bonus content → May be DLC

## Investigation of All membody Files

### Overview

The game directory contains 32 membody files across multiple locations. Each was investigated to determine if it contains script data.

### File Locations and Formats

| Location | Format | Contains Scripts? |
|----------|--------|-------------------|
| `fsroot*/common/script.membody` | RZ (deflate) | **YES** - Only source of dialogue |
| `fsroot2/spec_win/ssdata/*.membody` (17 files) | RSON | No - Textures and assets |
| Other membody files | Various | No - System/config data |

### script.membody (fsroot*/common/)

**Format:** RZ compressed format

**Content:**
- 5 TAT scenes with dialogue (137,999 bytes decompressed)
- Only Kyo route content (100_kyo2)
- Gallery scenes (GALLERY_SCENE_100_001/002)

**Extracted Scenes:**
| Scene | Size | Dialogue Lines |
|-------|------|----------------|
| [100_00_001_TOP] | 86KB | 676 |
| [GALLERY_SCENE_100_001_START] | 6KB | 60 |
| [GALLERY_SCENE_100_001_END] | 7KB | 53 |
| [GALLERY_SCENE_100_002_START] | 6KB | 62 |
| [GALLERY_SCENE_100_002_END] | 33KB | 225 |

### ssdata membody Files (fsroot2/spec_win/ssdata/)

**Files Found (17 total):**
- `bg00.membody`, `bg00.memfs` - Background images
- `bg000a.membody`, `bg000a.memfs` - Background variants
- `bg000b.membody`, `bg000b.memfs` - Background variants
- `bg001.membody`, `bg001.memfs` - Background images
- `bg002.membody`, `bg002.memfs` - Background images
- `chara_ami.membody`, `chara_ami.memfs` - Character sprites (Ami)
- `chara_kyo2.membody`, `chara_kyo2.memfs` - Character sprites (Kyo)
- `chara_tori.membody`, `chara_tori.memfs` - Character sprites (Tori)
- `chara_wataru.membody`, `chara_wataru.memfs` - Character sprites (Wataru)
- `chara_yosuke.membody`, `chara_yosuke.memfs` - Character sprites (Yosuke)
- `event_*.membody`, `event_*.memfs` - Event CG images

**Format:** RSON format (NOT RZ compressed like script.membody)

**Content Analysis:**
- Texture references (`.rtex` files)
- Character sprite data
- Background image data
- Event CG data
- Binary asset metadata

**Verification:**
- Searched all 17 files for `.tat` references: **None found**
- Searched for scene header patterns `[XXX_XXX_XXX_TOP]`: **None found**
- Searched for dialogue patterns `「...」`: **None found**

### Other membody Files

Additional membody files in the game directory were investigated:

| File | Location | Purpose |
|------|----------|---------|
| `*.membody` (various) | Multiple fsroot directories | System data, configuration |
| `app_info.membody` | Root | Application metadata |
| `message_*.membody` | spec_win | UI messages (non-script) |

**Result:** None contain game script dialogue - these are system/configuration files.

### Summary of Findings

| membody File | Format | Script Content | Route Coverage |
|--------------|--------|----------------|----------------|
| script.membody | RZ | 5 scenes, 1,076 lines | 100_kyo2 only |
| ssdata/*.membody (17 files) | RSON | None | N/A (graphics) |
| Others | Various | None | N/A (system) |

**Conclusion:**
- **Only `script.membody` contains game dialogue scripts**
- The 43 missing indexed files (Wataru, Yosuke, Toriai routes) are not present in this game's data
- To extract those routes, you would need the respective game volumes (Vol.1, Vol.3, etc.)
- The ssdata membody files contain exclusively graphical assets (textures, sprites, backgrounds)
