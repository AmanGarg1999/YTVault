import yt_dlp
import json
import urllib.request

ydl_opts = {
    'writesubtitles': True,
    'writeautomaticsub': True,
    'subtitleslangs': ['en'],
    'skip_download': True,
    'quiet': True,
}

with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    info = ydl.extract_info('https://www.youtube.com/watch?v=prTAsdltgHU', download=False)
    auto_subs = info.get('automatic_captions', {}).get('en', [])
    json3_sub = next((s for s in auto_subs if s['ext'] == 'json3'), None)
    if json3_sub:
        url = json3_sub['url']
        print("URL:", url[:100], "...")
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            print("Events count:", len(data.get('events', [])))
            if data.get('events'):
                print("First event:", data['events'][0])
