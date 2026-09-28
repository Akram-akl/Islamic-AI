# -*- coding: utf-8 -*-
"""
sync_for_deployment.py
يقوم بمزامنة جميع ملفات الواجهة من مجلد app إلى الجذر (Root) والعكس
لضمان عمل النشر التلقائي على Cloudflare Pages سواء تم توجيهه إلى الجذر / أو إلى /app
"""
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).parent.parent
APP = ROOT / "app"

def sync_files():
    print("🔄 جارٍ مزامنة الملفات لـ Cloudflare Pages...")
    
    # 1. نسخ index.html من app إلى الجذر
    if (APP / "index.html").exists():
        shutil.copy2(APP / "index.html", ROOT / "index.html")
        print("  ✓ تم نسخ app/index.html -> index.html (Root)")

    # 2. نسخ مجلد fonts إلى الجذر
    if (APP / "fonts").exists():
        dest_fonts = ROOT / "fonts"
        dest_fonts.mkdir(exist_ok=True)
        for item in (APP / "fonts").iterdir():
            if item.is_file():
                shutil.copy2(item, dest_fonts / item.name)
        print("  ✓ تم مزامنة مجلد fonts في الجذر")

    # 3. نسخ مجلد quran_data إلى الجذر
    if (APP / "quran_data").exists():
        dest_qdata = ROOT / "quran_data"
        dest_qdata.mkdir(exist_ok=True)
        for item in (APP / "quran_data").iterdir():
            if item.is_file():
                shutil.copy2(item, dest_qdata / item.name)
        print("  ✓ تم مزامنة مجلد quran_data في الجذر")

    # 4. التأكد من وجود encyclopedia.js في app والجذر
    if (ROOT / "encyclopedia.js").exists() and not (APP / "encyclopedia.js").exists():
        shutil.copy2(ROOT / "encyclopedia.js", APP / "encyclopedia.js")
    elif (APP / "encyclopedia.js").exists() and not (ROOT / "encyclopedia.js").exists():
        shutil.copy2(APP / "encyclopedia.js", ROOT / "encyclopedia.js")

    # 5. التأكد من وجود sw.js و manifest.json و icon.svg
    for fname in ["manifest.json", "icon.svg", "sw.js", "quran_ar.json", "adhan.mp3"]:
        src = APP / fname if (APP / fname).exists() else ROOT / fname
        if src.exists():
            if not (ROOT / fname).exists() or (APP / fname).exists() and src == (APP / fname):
                shutil.copy2(src, ROOT / fname)
            if not (APP / fname).exists():
                shutil.copy2(src, APP / fname)

    print("✅ اكتملت المزامنة بنجاح! الموقع جاهز 100% لـ Cloudflare Pages سواء من الجذر أو من مجلد app.")

if __name__ == "__main__":
    sync_files()
