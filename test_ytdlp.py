import subprocess
import os

url = "https://www.youtube.com/@nikhil.kamath/videos"
base_url = "https://www.youtube.com/@nikhil.kamath"

strategies = [
    ["--flat-playlist", "--print", "id", url],
    ["--flat-playlist", "--print", "id", base_url],
    ["--playlist-end", "5", "--print", "id", url],
    ["--dump-json", "--playlist-items", "0", base_url]
]

# Try to find yt-dlp
paths = ["yt-dlp", "/usr/bin/yt-dlp", "/usr/local/bin/yt-dlp", os.path.expanduser("~/.local/bin/yt-dlp"), "/snap/bin/yt-dlp"]
ytdlp = "yt-dlp"
for p in paths:
    if os.path.exists(p) or subprocess.run(["which", p], capture_output=True).returncode == 0:
        ytdlp = p
        break

print(f"Using yt-dlp at: {ytdlp}")

for args in strategies:
    cmd = [ytdlp, "--no-download", "--no-check-certificate", "--force-ipv4"] + args
    print(f"\nRunning: {' '.join(cmd)}")
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        print(f"Return code: {res.returncode}")
        print(f"Stdout (first 100 chars): {res.stdout[:100]!r}")
        print(f"Stderr (first 100 chars): {res.stderr[:100]!r}")
        lines = [l for l in res.stdout.strip().split("\n") if l.strip()]
        print(f"Found {len(lines)} items")
    except Exception as e:
        print(f"Error: {e}")
