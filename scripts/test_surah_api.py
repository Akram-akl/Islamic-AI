import urllib.request
import json

req = urllib.request.Request('https://dev.surahapp.com/api/v1/projects', headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode())
        print(f"Total projects: {len(data)}")
        for p in data:
            print(f"type: {p.get('type'):<8} | slug: {p.get('slug'):<25} | title: {p.get('title')}")
except Exception as e:
    print("Error:", e)
