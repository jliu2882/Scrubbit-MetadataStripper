# Scrubbit

![Python](https://img.shields.io/badge/python-3.10%2B-blue) ![License](https://img.shields.io/badge/license-MIT-lightgrey)

Many files contain metadata that can reveal sensitive information, including GPS location. Metadata Stripper gives you more control over your digital footprint by showing you what you are about to upload to the web, before you upload it.

Photos often carry GPS coordinates, device serial numbers, owner names, and timestamps. The tool shows you what is there, rates how risky it is, and removes it without touching your originals.

Available as a desktop app and a command-line tool.

## Features

- **Non-destructive by default.** Cleaned copies are saved as `name_clean.ext`. In-place editing is optional and always creates a backup first.
- **Privacy risk scoring.** Every item is rated High, Medium, or Low so you can see what matters at a glance (GPS location is High, a timestamp is Medium, exposure settings are Low).
- **Suggested removal.** For users who don't want to review every tag, one click selects the most sensitive information (High and Medium risk).
- **Strip all or choose.** Remove everything, or pick individual items.
- **Batch processing.** Clean multiple files or entire folders, with a progress bar in the app.
- **Lossless where possible.** JPEG, PNG, and WebP are edited at the file-structure level, so image data is never re-compressed.
- **Keeps photos upright.** The rotation flag is preserved by default so cleaned photos don't turn sideways.
- **Search and sort.** Filter the tag table by any text and sort by risk, group, tag, or value.
- **Metadata reports.** Export what was found to JSON or CSV before changing anything.
- **Safe writes.** Output is re-read and verified before it is saved, and files are written atomically.

## Supported formats

| Format | See metadata | Remove selected items | Remove everything | How it is cleaned |
|---|---|---|---|---|
| JPEG | EXIF, GPS, XMP, IPTC, comments, thumbnail | Yes | Yes | File segments edited, pixels untouched |
| PNG | EXIF, text chunks, XMP, timestamp | Yes | Yes | Chunks edited, pixels untouched |
| WebP | EXIF, XMP | Yes | Yes | Chunks edited, pixels untouched |
| TIFF | EXIF, GPS, XMP, IPTC, base tags | No | Yes | Re-written losslessly |
| HEIC / HEIF | EXIF | No | Yes | Re-encoded losslessly (needs `pillow-heif`) |

Files are identified by their contents, not their extension.

## Installation

### Prebuilt binaries (easiest)

Download the build for Windows, macOS, or Linux from the [Releases](../../releases) page. No Python required.

### From source

```bash
pip install ".[gui,heic]"
```

| Extra | Adds |
|---|---|
| `gui` | The desktop app (`customtkinter`) |
| `heic` | HEIC/HEIF support (`pillow-heif`) |

The command-line tool works with a plain `pip install .`.

## Usage

### Desktop app

```bash
metastrip-gui
```

1. Click **Add Files** or **Add Folder**.
2. Pick a file to see its metadata and risk levels.
3. Click **Select Suggested** (or choose rows yourself), then **Remove Selected**. Or click **Strip All Tags**.
4. To clean every loaded file at once, choose a mode and click **Clean All Files**.

Cleaned copies are saved next to the originals unless "Edit originals in place" is ticked.

### Command line

```bash
# See what is inside (only the risky items)
metastrip inspect photo.jpg --min-risk high

# Clean a file: writes photo_clean.jpg
metastrip clean photo.jpg

# Clean a folder and its subfolders, removing only High and Medium risk items
metastrip clean ./photos --recursive --suggested

# Remove specific items
metastrip clean photo.jpg --remove GPS.GPSLatitude GPS.GPSLongitude

# Preview without writing anything
metastrip clean ./photos --dry-run

# Edit the original in place (photo.jpg.bak is created first)
metastrip clean photo.jpg --in-place

# Export a report
metastrip report ./photos --recursive --format csv -o report.csv
```

Item ids look like `GPS.GPSLatitude` (group, then tag). Run `metastrip inspect` to see them. Run `metastrip --help` for all options.

When scanning a folder, files that already end in `_clean` are skipped so repeated runs don't re-clean earlier output.

## Risk levels

| Level | Meaning | Examples |
|---|---|---|
| High | Can identify a person or place | GPS coordinates, serial numbers, owner/artist name, XMP and IPTC blocks |
| Medium | Reveals when or how a file was made | Timestamps, camera make/model, software, comments, embedded thumbnail |
| Low | Technical settings | Exposure, ISO, color space |

## How it works

```
        ┌───────────┐   ┌───────────┐
        │    GUI    │   │    CLI    │
        └─────┬─────┘   └─────┬─────┘
              └───────┬───────┘
                ┌─────▼─────┐
                │   Core    │  scan · score · strip · report · backup
                └─────┬─────┘
          ┌───────────┼───────────┐
      ┌───▼───┐   ┌───▼──┐   ┌────▼────┐
      │ JPEG  │   │ PNG  │   │ WebP …  │   one handler per format
      └───────┘   └──────┘   └─────────┘
```

The core library has no interface dependencies, so the GUI and CLI behave identically and the logic is tested on its own.

## Limitations

- Only embedded metadata is removed. File names, file system dates, and what is visible in the picture itself (faces, street signs) are not touched.
- TIFF and HEIC support removing everything only, not individual items.
- HEIC cleaning re-encodes the image losslessly, which can make the file larger. HDR/10-bit data and depth maps are not preserved.
- Multi-page TIFF, animated images, and RAW formats are not supported.
- Check a cleaned file with `metastrip inspect` if the stakes are high.

## Privacy

All processing happens locally. Files are never uploaded anywhere.

## Development

```bash
pip install -e ".[gui,heic,dev]"
pytest --cov
ruff check src tests
python scripts/build.py   # standalone executables in dist/
```

Tests run on Linux, Windows, and macOS through GitHub Actions. Pushing a tag like `v1.0.0` builds binaries for all three and attaches them to a release. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Roadmap

- **"Lying" mode.** For the more digitally cautious: rewrite metadata values (for example, a fake location or device) instead of just deleting them, so files don't look suspiciously blank.
- **Documents beyond images.** PDF support first, then Office documents.
- Removing individual items from TIFF and HEIC
- Drag-and-drop input
- GPS location preview
- Before/after comparison view
- Undo from backup

## License

MIT. See [LICENSE](LICENSE).
