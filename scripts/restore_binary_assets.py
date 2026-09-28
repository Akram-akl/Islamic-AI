# -*- coding: utf-8 -*-
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent.parent
quran_pwa_dir = r"C:\Users\akram\OneDrive\Desktop\appsakramakl\Quran_Al-Readings\Quran_PWA"

fonts = [
    "uthmanic_hafs_v20.ttf",
    "uthmanic_warsh_v21.ttf",
    "uthmanic_qaloun_v21.ttf",
    "uthmanic_douri_v20.ttf",
    "uthmanic_sousi_v20.ttf",
    "uthmanic_shuba_v20.ttf"
]

data_files = [
    ("data/hafsData_v2-0.json", "hafsData_v2-0.json"),
    ("data/warshData_v2-1.json", "warshData_v2-1.json"),
    ("data/QalounData_v2-1.json", "QalounData_v2-1.json"),
    ("data/DouriData_v2-0.json", "DouriData_v2-0.json"),
    ("data/SousiData_v2-0.json", "SousiData_v2-0.json"),
    ("data/shubaData_v2-0.json", "shubaData_v2-0.json")
]

# Ensure dirs exist
for d in [ROOT / "fonts", ROOT / "app" / "fonts", ROOT / "quran_data", ROOT / "app" / "quran_data"]:
    d.mkdir(parents=True, exist_ok=True)

print("1. Restoring fonts in pure binary mode...")
for f in fonts:
    git_path = f"fonts/{f}"
    res = subprocess.run(["git", "-C", quran_pwa_dir, "cat-file", "blob", f"HEAD:{git_path}"], capture_output=True)
    if res.returncode == 0 and len(res.stdout) > 0:
        data = res.stdout
        # Verify valid TTF magic number (0x00010000 or 'OTTO' or 'true')
        magic = data[:4]
        print(f"  {f}: size={len(data)} bytes, magic={magic.hex()}")
        for dest in [ROOT / "fonts" / f, ROOT / "app" / "fonts" / f]:
            with open(dest, "wb") as out:
                out.write(data)
    else:
        print(f"  ERROR restoring {f}: {res.stderr}")

print("\n2. Restoring quran_data in pure binary mode (UTF-8 without BOM)...")
for git_path, fname in data_files:
    res = subprocess.run(["git", "-C", quran_pwa_dir, "cat-file", "blob", f"HEAD:{git_path}"], capture_output=True)
    if res.returncode == 0 and len(res.stdout) > 0:
        data = res.stdout
        # If it was UTF-16, decode and re-encode as UTF-8
        if data.startswith(b"\xff\xfe"):
            print(f"  Converting {fname} from UTF-16 LE to UTF-8...")
            text = data.decode("utf-16-le")
            data = text.encode("utf-8")
        elif data.startswith(b"\xef\xbb\xbf"):
            data = data[3:]
        print(f"  {fname}: size={len(data)} bytes, starts_with={data[:10]}")
        for dest in [ROOT / "quran_data" / fname, ROOT / "app" / "quran_data" / fname]:
            with open(dest, "wb") as out:
                out.write(data)
    else:
        print(f"  ERROR restoring {fname}: {res.stderr}")

print("\nFinished restoring binary assets!")
