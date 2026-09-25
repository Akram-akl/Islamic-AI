"""
core/db.py
قاعدة بيانات SQLite المركزية — القرآن الكريم + الأحاديث + الكتب
مع دعم كامل للقراءات وFTS5 وجميع اللغات
"""
import sqlite3
import json
import os
import re
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH  = BASE_DIR / "data" / "islamic.db"


# ─────────────────────────────────────────────────────────────
#  إنشاء قاعدة البيانات وجميع الجداول
# ─────────────────────────────────────────────────────────────
SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA foreign_keys=ON;

-- جدول القرآن الكريم (يدعم قراءات متعددة)
CREATE TABLE IF NOT EXISTS quran (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    qiraah          TEXT    NOT NULL DEFAULT 'hafs',   -- hafs | warsh | qaloun | duri
    surah_number    INTEGER NOT NULL,
    surah_name_ar   TEXT    NOT NULL,
    surah_name_en   TEXT    NOT NULL,
    surah_type      TEXT    NOT NULL DEFAULT 'meccan', -- meccan | medinan
    ayah_number     INTEGER NOT NULL,
    ayah_text_ar    TEXT    NOT NULL,                  -- النص الكامل المشكول
    ayah_text_clean TEXT    NOT NULL,                  -- النص بدون تشكيل للبحث
    juz             INTEGER,
    page            INTEGER,
    UNIQUE(qiraah, surah_number, ayah_number)
);

-- جدول ترجمات القرآن الكريم
CREATE TABLE IF NOT EXISTS quran_translations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    surah_number INTEGER NOT NULL,
    ayah_number  INTEGER NOT NULL,
    lang        TEXT    NOT NULL,  -- en, fr, ur, tr, id
    translator  TEXT    NOT NULL,  -- saheeh_international, etc.
    text        TEXT    NOT NULL
);

-- جدول الأحاديث الشريفة
CREATE TABLE IF NOT EXISTS hadiths (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    collection      TEXT    NOT NULL,  -- bukhari | muslim | riyadh | nawawi | abudawud | tirmidhi | ibnmajah | qudsi
    hadith_number   INTEGER NOT NULL,
    arabic_number   INTEGER,
    book_number     INTEGER,
    book_name_ar    TEXT,
    chapter_name_ar TEXT,
    text_ar         TEXT    NOT NULL,
    text_ar_clean   TEXT    NOT NULL,  -- بدون تشكيل للبحث
    grade           TEXT,             -- صحيح | حسن | ضعيف
    reference       TEXT,             -- الرقم في المرجع الأصلي
    UNIQUE(collection, hadith_number)
);

-- جدول ترجمات الأحاديث
CREATE TABLE IF NOT EXISTS hadith_translations (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    collection   TEXT    NOT NULL,
    hadith_number INTEGER NOT NULL,
    lang         TEXT    NOT NULL,
    text         TEXT    NOT NULL,
    narrator     TEXT
);

-- جدول الكتب الإسلامية (العقيدة، الفقه، التجويد، المسلمون الجدد)
CREATE TABLE IF NOT EXISTS islamic_books (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id     TEXT    NOT NULL UNIQUE,   -- al_usool_3, tajweed_tuhfa, etc.
    title_ar    TEXT    NOT NULL,
    title_en    TEXT,
    author_ar   TEXT,
    author_en   TEXT,
    category    TEXT    NOT NULL,  -- aqeeda | fiqh | tajweed | new_muslim | general
    lang        TEXT    NOT NULL DEFAULT 'ar',
    content     TEXT    NOT NULL,
    summary     TEXT
);

-- كاش ذكي للإجابات (يحل 60-80% من الطلبات بلا ذكاء اصطناعي)
CREATE TABLE IF NOT EXISTS answer_cache (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    question_hash   TEXT    NOT NULL UNIQUE,
    question_text   TEXT    NOT NULL,
    answer          TEXT    NOT NULL,
    hit_count       INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- سجل الأسئلة للإحصائيات
CREATE TABLE IF NOT EXISTS query_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    question    TEXT    NOT NULL,
    lang        TEXT,
    query_type  TEXT,   -- search | stats | compare | qa
    duration_ms INTEGER,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ─── فهارس FTS5 للبحث الكامل النصي الفائق السرعة ───
CREATE VIRTUAL TABLE IF NOT EXISTS quran_fts USING fts5(
    ayah_text_ar, ayah_text_clean, surah_name_ar,
    content='quran', content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);

CREATE VIRTUAL TABLE IF NOT EXISTS hadith_fts USING fts5(
    text_ar, text_ar_clean, book_name_ar, chapter_name_ar,
    content='hadiths', content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);

-- ─── Triggers لمزامنة FTS تلقائياً ───
CREATE TRIGGER IF NOT EXISTS quran_ai AFTER INSERT ON quran BEGIN
    INSERT INTO quran_fts(rowid, ayah_text_ar, ayah_text_clean, surah_name_ar)
    VALUES (new.id, new.ayah_text_ar, new.ayah_text_clean, new.surah_name_ar);
END;

CREATE TRIGGER IF NOT EXISTS hadith_ai AFTER INSERT ON hadiths BEGIN
    INSERT INTO hadith_fts(rowid, text_ar, text_ar_clean, book_name_ar, chapter_name_ar)
    VALUES (new.id, new.text_ar, new.text_ar_clean,
            new.book_name_ar, new.chapter_name_ar);
END;
"""


def remove_diacritics(text: str) -> str:
    """إزالة التشكيل لتسهيل البحث"""
    if not text:
        return ""
    # نقاط Unicode للتشكيل العربي
    diacritics = re.compile(r'[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06DC\u06DF-\u06E4\u06E7\u06E8\u06EA-\u06ED]')
    return diacritics.sub('', text)


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-32000")  # 32MB cache
    return conn


def init_db():
    """تهيئة قاعدة البيانات وإنشاء الجداول"""
    conn = get_conn()
    try:
        for stmt in SCHEMA.split(";"):
            stmt = stmt.strip()
            if stmt:
                try:
                    conn.execute(stmt)
                except sqlite3.OperationalError as e:
                    if "already exists" not in str(e):
                        print(f"  ⚠️  DB Schema: {e}")
        conn.commit()
        print("  ✅ قاعدة البيانات جاهزة")
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────
#  استيراد بيانات القرآن الكريم
# ─────────────────────────────────────────────────────────────
SURAH_NAMES_EN = {
    1: "Al-Fatiha", 2: "Al-Baqara", 3: "Al-Imran", 4: "An-Nisa",
    5: "Al-Maida", 6: "Al-Anam", 7: "Al-Araf", 8: "Al-Anfal",
    9: "At-Tawba", 10: "Yunus", 11: "Hud", 12: "Yusuf",
    13: "Ar-Rad", 14: "Ibrahim", 15: "Al-Hijr", 16: "An-Nahl",
    17: "Al-Isra", 18: "Al-Kahf", 19: "Maryam", 20: "Ta-Ha",
    21: "Al-Anbiya", 22: "Al-Hajj", 23: "Al-Muminun", 24: "An-Nur",
    25: "Al-Furqan", 26: "Ash-Shuara", 27: "An-Naml", 28: "Al-Qasas",
    29: "Al-Ankabut", 30: "Ar-Rum", 31: "Luqman", 32: "As-Sajda",
    33: "Al-Ahzab", 34: "Saba", 35: "Fatir", 36: "Ya-Sin",
    37: "As-Saffat", 38: "Sad", 39: "Az-Zumar", 40: "Ghafir",
    41: "Fussilat", 42: "Ash-Shura", 43: "Az-Zukhruf", 44: "Ad-Dukhan",
    45: "Al-Jathiya", 46: "Al-Ahqaf", 47: "Muhammad", 48: "Al-Fath",
    49: "Al-Hujurat", 50: "Qaf", 51: "Adh-Dhariyat", 52: "At-Tur",
    53: "An-Najm", 54: "Al-Qamar", 55: "Ar-Rahman", 56: "Al-Waqia",
    57: "Al-Hadid", 58: "Al-Mujadila", 59: "Al-Hashr", 60: "Al-Mumtahana",
    61: "As-Saf", 62: "Al-Jumua", 63: "Al-Munafiqun", 64: "At-Taghabun",
    65: "At-Talaq", 66: "At-Tahrim", 67: "Al-Mulk", 68: "Al-Qalam",
    69: "Al-Haqqa", 70: "Al-Maarij", 71: "Nuh", 72: "Al-Jinn",
    73: "Al-Muzzammil", 74: "Al-Muddaththir", 75: "Al-Qiyama", 76: "Al-Insan",
    77: "Al-Mursalat", 78: "An-Naba", 79: "An-Naziat", 80: "Abasa",
    81: "At-Takwir", 82: "Al-Infitar", 83: "Al-Mutaffifin", 84: "Al-Inshiqaq",
    85: "Al-Buruj", 86: "At-Tariq", 87: "Al-Ala", 88: "Al-Ghashiya",
    89: "Al-Fajr", 90: "Al-Balad", 91: "Ash-Shams", 92: "Al-Layl",
    93: "Ad-Duha", 94: "Ash-Sharh", 95: "At-Tin", 96: "Al-Alaq",
    97: "Al-Qadr", 98: "Al-Bayyina", 99: "Az-Zalzala", 100: "Al-Adiyat",
    101: "Al-Qaria", 102: "At-Takathur", 103: "Al-Asr", 104: "Al-Humaza",
    105: "Al-Fil", 106: "Quraysh", 107: "Al-Maun", 108: "Al-Kawthar",
    109: "Al-Kafirun", 110: "An-Nasr", 111: "Al-Masad", 112: "Al-Ikhlas",
    113: "Al-Falaq", 114: "An-Nas"
}

MECCAN_SURAHS = {
    1,6,7,8,10,11,12,13,14,15,16,17,18,19,20,21,23,25,26,27,28,29,30,31,32,
    34,35,36,37,38,39,40,41,42,43,44,45,46,50,51,52,53,54,55,56,67,68,69,70,
    71,72,73,74,75,76,77,78,79,80,81,82,83,84,85,86,87,88,89,90,91,92,93,94,
    95,96,97,100,101,102,103,104,105,106,107,108,109,111,112,113,114
}


def import_quran_hafs():
    """استيراد القرآن الكريم برواية حفص"""
    quran_file = DATA_DIR / "quran" / "quran_hafs_ar.json"
    if not quran_file.exists():
        print("  ⚠️  ملف القرآن غير موجود: data/quran/quran_hafs_ar.json")
        return

    print("  📖 جار استيراد القرآن الكريم (حفص)...")
    with open(quran_file, encoding="utf-8") as f:
        data = json.load(f)

    conn = get_conn()
    try:
        # تحقق من عدم التكرار
        existing = conn.execute(
            "SELECT COUNT(*) FROM quran WHERE qiraah='hafs'"
        ).fetchone()[0]
        if existing > 1000:
            print(f"  ✅ القرآن محمّل مسبقاً ({existing} آية)")
            return

        rows = []
        surahs = data.get("quran", data) if isinstance(data, dict) else data

        # محاولة تحليل هياكل JSON مختلفة
        if isinstance(surahs, list):
            # هيكل: [{surah: 1, verse: 1, text: "..."}, ...]
            for item in surahs:
                s = item.get("surah") or item.get("chapter") or item.get("sura")
                v = item.get("verse") or item.get("aya") or item.get("ayah")
                t = item.get("text") or item.get("aya_text") or ""
                name_ar = item.get("name_ar") or item.get("surah_name") or f"سورة {s}"
                if s and v and t:
                    rows.append((
                        "hafs", int(s), name_ar,
                        SURAH_NAMES_EN.get(int(s), f"Surah {s}"),
                        "meccan" if int(s) in MECCAN_SURAHS else "medinan",
                        int(v), t, remove_diacritics(t)
                    ))
        elif isinstance(surahs, dict):
            # هيكل الملف الفعلي: {"1": [{chapter:1, verse:1, text:"..."}, ...], ...}
            for s_num, ayahs in surahs.items():
                if isinstance(ayahs, list):
                    for item in ayahs:
                        if not isinstance(item, dict):
                            continue
                        v = item.get("verse") or item.get("ayah") or item.get("aya")
                        t = item.get("text") or ""
                        if v and t:
                            rows.append((
                                "hafs", int(s_num),
                                f"سورة {s_num}",
                                SURAH_NAMES_EN.get(int(s_num), f"Surah {s_num}"),
                                "meccan" if int(s_num) in MECCAN_SURAHS else "medinan",
                                int(v), t, remove_diacritics(t)
                            ))
                elif isinstance(ayahs, dict):
                    for v_num, text in ayahs.items():
                        if isinstance(text, str):
                            rows.append((
                                "hafs", int(s_num),
                                f"سورة {s_num}",
                                SURAH_NAMES_EN.get(int(s_num), f"Surah {s_num}"),
                                "meccan" if int(s_num) in MECCAN_SURAHS else "medinan",
                                int(v_num), text, remove_diacritics(text)
                            ))

        conn.executemany(
            """INSERT OR IGNORE INTO quran
               (qiraah, surah_number, surah_name_ar, surah_name_en,
                surah_type, ayah_number, ayah_text_ar, ayah_text_clean)
               VALUES (?,?,?,?,?,?,?,?)""",
            rows
        )
        conn.commit()
        print(f"  ✅ القرآن الكريم: {len(rows)} آية مُستوردة")
    except Exception as e:
        print(f"  ❌ خطأ في استيراد القرآن: {e}")
        import traceback; traceback.print_exc()
    finally:
        conn.close()


def import_hadith_collection(collection: str, lang: str, filepath: Path):
    """استيراد مجموعة حديثية من ملف JSON"""
    if not filepath.exists():
        print(f"  ⚠️  ملف غير موجود: {filepath.name}")
        return 0

    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)

    # استخراج الأحاديث من الهياكل المختلفة للـ API
    hadiths_raw = []
    if isinstance(data, dict):
        hadiths_raw = data.get("hadiths", [])

    if not hadiths_raw:
        print(f"  ⚠️  لا توجد أحاديث في: {filepath.name}")
        return 0

    conn = get_conn()
    try:
        count = 0
        for h in hadiths_raw:
            hnum  = h.get("hadithnumber") or h.get("id") or 0
            text  = h.get("text") or h.get("hadith") or ""
            grade_raw = h.get("grades")
            if isinstance(grade_raw, list):
                grade = grade_raw[0].get("grade", "") if grade_raw else ""
            elif isinstance(grade_raw, str):
                grade = grade_raw
            else:
                grade = ""
            ref_raw = h.get("reference", "")
            ref = json.dumps(ref_raw, ensure_ascii=False) if isinstance(ref_raw, dict) else str(ref_raw)

            if not text or not hnum:
                continue

            if lang == "ar":
                conn.execute(
                    """INSERT OR IGNORE INTO hadiths
                       (collection, hadith_number, arabic_number,
                        text_ar, text_ar_clean, grade, reference)
                       VALUES (?,?,?,?,?,?,?)""",
                    (collection, int(hnum), int(hnum),
                     text, remove_diacritics(text), grade, ref)
                )
            else:
                # ترجمة — نضيف إلى جدول الترجمات
                conn.execute(
                    """INSERT OR IGNORE INTO hadith_translations
                       (collection, hadith_number, lang, text)
                       VALUES (?,?,?,?)""",
                    (collection, int(hnum), lang, text)
                )
            count += 1

        conn.commit()
        return count
    except Exception as e:
        print(f"  ❌ خطأ: {e}")
        return 0
    finally:
        conn.close()


HADITH_FILES = {
    ("bukhari",  "ar"): "hadith/bukhari_ar.json",
    ("bukhari",  "en"): "hadith/bukhari_en.json",
    ("bukhari",  "ur"): "hadith/bukhari_ur.json",
    ("bukhari",  "tr"): "hadith/bukhari_tr.json",
    ("bukhari",  "fr"): "hadith/bukhari_fr.json",
    ("bukhari",  "id"): "hadith/bukhari_id.json",
    ("muslim",   "ar"): "hadith/muslim_ar.json",
    ("muslim",   "en"): "hadith/muslim_en.json",
    ("muslim",   "ur"): "hadith/muslim_ur.json",
    ("muslim",   "tr"): "hadith/muslim_tr.json",
    ("muslim",   "fr"): "hadith/muslim_fr.json",
    ("muslim",   "id"): "hadith/muslim_id.json",
    ("riyadh",   "ar"): "hadith/riyadh_ar.json",
    ("riyadh",   "en"): "hadith/riyadh_en.json",
    ("nawawi",   "ar"): "hadith/nawawi40_ar.json",
    ("nawawi",   "en"): "hadith/nawawi40_en.json",
    ("abudawud", "ar"): "hadith/abudawud_ar.json",
    ("abudawud", "en"): "hadith/abudawud_en.json",
    ("tirmidhi", "ar"): "hadith/tirmidhi_ar.json",
    ("tirmidhi", "en"): "hadith/tirmidhi_en.json",
    ("ibnmajah", "ar"): "hadith/ibnmajah_ar.json",
    ("ibnmajah", "en"): "hadith/ibnmajah_en.json",
    ("qudsi",    "ar"): "hadith/qudsi_ar.json",
    ("qudsi",    "en"): "hadith/qudsi_en.json",
}


def build_database():
    """بناء قاعدة البيانات الكاملة من ملفات JSON المحملة"""
    print("\n🏗️  بناء قاعدة البيانات الإسلامية...")
    init_db()
    import_quran_hafs()

    total_hadiths = 0
    for (collection, lang), rel_path in HADITH_FILES.items():
        filepath = DATA_DIR / rel_path
        count = import_hadith_collection(collection, lang, filepath)
        if count > 0:
            label = "ع" if lang == "ar" else lang
            print(f"  ✅ {collection} ({label}): {count} حديث")
            total_hadiths += count

    print(f"\n  🎉 إجمالي الأحاديث المستوردة: {total_hadiths}")
    print("  📚 قاعدة البيانات الإسلامية جاهزة تماماً!\n")


if __name__ == "__main__":
    build_database()
