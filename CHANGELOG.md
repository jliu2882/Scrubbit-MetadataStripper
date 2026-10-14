# Changelog

## 1.0.0

- Rewrite as a package with a GUI-free core library, a CLI, and a desktop app.
- Non-destructive output by default (`name_clean.ext`); in-place mode keeps a backup.
- Privacy risk scoring (High / Medium / Low) and a "suggested removal" shortcut.
- Batch processing for files and folders, with a progress bar in the app.
- JPEG, PNG and WebP are cleaned without re-encoding pixels; TIFF and HEIC are re-written losslessly.
- JSON and CSV metadata reports.
- Tag search/filter and sortable table in the desktop app.
