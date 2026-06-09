BS.Player SOAP Subtitle Downloader
An automated Python script that calculates the unique BS.Player file hash of your videos, queries the BS.Player SOAP API, and downloads matching subtitles.

Features
Auto-Hash & Fetch: Automatically matches subtitles using the video's size and contents.

Greek & English: Prioritizes Greek subtitles (and auto-fixes character encoding to UTF-8-sig) with an English fallback.

Recursive Scan: Scans individual files or entire folders/subfolders for .mp4, .mkv, and .avi.

Usage
1. Install dependency: pip install requests
2. Scan current folder: python script_name.py
3. Scan specific path: python script_name.py "/path/to/movies"
4. Force re-download (creates .bak backups): python script_name.py "/path/to/movies" -f
