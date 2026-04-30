import yt_dlp
import json

ydl_opts = {
    'writesubtitles': True,
    'writeautomaticsub': True,
    'subtitleslangs': ['en'],
    'skip_download': True,
    'quiet': True,
}

with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    info = ydl.extract_info('https://www.youtube.com/watch?v=prTAsdltgHU', download=False)
    subs = info.get('subtitles', {})
    auto_subs = info.get('automatic_captions', {})
    print("Subs:", list(subs.keys()))
    print("Auto Subs:", list(auto_subs.keys()))
    if 'en' in auto_subs:
        print("Auto Sub formats:", [f['ext'] for f in auto_subs['en']])
