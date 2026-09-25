"""
Islamic-AI Data Downloader
يقوم بتحميل جميع الملفات الإسلامية المعتمدة من مصادرها الرسمية
"""
import os
import json
import urllib.request
import urllib.error
import time
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
QURAN_DIR = os.path.join(BASE_DIR, "quran")
HADITH_DIR = os.path.join(BASE_DIR, "hadith")
BOOKS_DIR = os.path.join(BASE_DIR, "books")

for d in [QURAN_DIR, HADITH_DIR, BOOKS_DIR]:
    os.makedirs(d, exist_ok=True)

CDN = "https://cdn.jsdelivr.net/gh/fawazahmed0/hadith-api@1/editions"
QURAN_RAW = "https://raw.githubusercontent.com/risan/quran-json/main/data"

FILES = {
    # ──────────────────── القرآن الكريم ────────────────────
    "quran/quran_hafs_ar.json": f"{QURAN_RAW}/quran.json",

    # ──────────────────── صحيح البخاري ────────────────────
    "hadith/bukhari_ar.json":  f"{CDN}/ara-bukhari.json",
    "hadith/bukhari_en.json":  f"{CDN}/eng-bukhari.json",
    "hadith/bukhari_ur.json":  f"{CDN}/urd-bukhari.json",
    "hadith/bukhari_tr.json":  f"{CDN}/tur-bukhari.json",
    "hadith/bukhari_fr.json":  f"{CDN}/fra-bukhari.json",
    "hadith/bukhari_id.json":  f"{CDN}/ind-bukhari.json",

    # ──────────────────── صحيح مسلم ────────────────────
    "hadith/muslim_ar.json":   f"{CDN}/ara-muslim.json",
    "hadith/muslim_en.json":   f"{CDN}/eng-muslim.json",
    "hadith/muslim_ur.json":   f"{CDN}/urd-muslim.json",
    "hadith/muslim_tr.json":   f"{CDN}/tur-muslim.json",
    "hadith/muslim_fr.json":   f"{CDN}/fra-muslim.json",
    "hadith/muslim_id.json":   f"{CDN}/ind-muslim.json",

    # ──────────────────── رياض الصالحين ────────────────────
    "hadith/riyadh_ar.json":   f"{CDN}/ara-riyadussalihin.json",
    "hadith/riyadh_en.json":   f"{CDN}/eng-riyadussalihin.json",

    # ──────────────────── الأربعون النووية ────────────────────
    "hadith/nawawi40_ar.json": f"{CDN}/ara-nawawi.json",
    "hadith/nawawi40_en.json": f"{CDN}/eng-nawawi.json",

    # ──────────────────── سنن أبي داود ────────────────────
    "hadith/abudawud_ar.json": f"{CDN}/ara-abudawud.json",
    "hadith/abudawud_en.json": f"{CDN}/eng-abudawud.json",

    # ──────────────────── جامع الترمذي ────────────────────
    "hadith/tirmidhi_ar.json": f"{CDN}/ara-tirmidhi.json",
    "hadith/tirmidhi_en.json": f"{CDN}/eng-tirmidhi.json",

    # ──────────────────── سنن ابن ماجه ────────────────────
    "hadith/ibnmajah_ar.json": f"{CDN}/ara-ibnmajah.json",
    "hadith/ibnmajah_en.json": f"{CDN}/eng-ibnmajah.json",

    # ──────────────────── المسند الموضوعاتي ────────────────────
    "hadith/qudsi_ar.json":    f"{CDN}/ara-qudsi.json",
    "hadith/qudsi_en.json":    f"{CDN}/eng-qudsi.json",
}


def download(rel_path: str, url: str) -> bool:
    dest = os.path.join(BASE_DIR, rel_path)
    if os.path.exists(dest):
        size = os.path.getsize(dest)
        if size > 1000:
            print(f"  ✅ موجود مسبقاً: {rel_path} ({size//1024} KB)")
            return True

    print(f"  ⬇️  جار التحميل: {rel_path}")
    print(f"      المصدر: {url}")

    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Islamic-AI/1.0"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read()

            # التحقق من صحة JSON
            parsed = json.loads(data.decode("utf-8"))
            if not parsed:
                raise ValueError("ملف JSON فارغ")

            with open(dest, "wb") as f:
                f.write(data)

            print(f"  ✅ تم التحميل: {rel_path} ({len(data)//1024} KB)")
            return True

        except urllib.error.HTTPError as e:
            print(f"  ⚠️  HTTP {e.code} - المحاولة {attempt+1}/3: {url}")
        except urllib.error.URLError as e:
            print(f"  ⚠️  خطأ شبكة - المحاولة {attempt+1}/3: {e.reason}")
        except json.JSONDecodeError:
            print(f"  ❌ ملف JSON تالف: {url}")
            return False
        except Exception as e:
            print(f"  ⚠️  خطأ غير متوقع: {e}")

        if attempt < 2:
            time.sleep(2)

    print(f"  ❌ فشل التحميل بعد 3 محاولات: {rel_path}")
    return False


def main():
    print("=" * 60)
    print("  Islamic-AI — تحميل الملفات الإسلامية المعتمدة")
    print("=" * 60)

    success, failed = [], []
    for rel_path, url in FILES.items():
        ok = download(rel_path, url)
        (success if ok else failed).append(rel_path)
        time.sleep(0.3)  # لا نضغط على الخادم

    print("\n" + "=" * 60)
    print(f"  ✅ تم تحميل: {len(success)} ملف")
    if failed:
        print(f"  ❌ فشل:       {len(failed)} ملف")
        for f in failed:
            print(f"     • {f}")
    else:
        print("  🎉 جميع الملفات حُمِّلت بنجاح!")
    print("=" * 60)

    # كتابة ملف فهرسة الإصدارات
    manifest = {
        "version": "1.0",
        "files": {k: os.path.exists(os.path.join(BASE_DIR, k)) for k in FILES}
    }
    with open(os.path.join(BASE_DIR, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
