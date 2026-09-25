"""
core/search_engine.py
محرك البحث الهجين: FTS5 (لفظي حرفي) + بحث رقمي حتمي
دقة 100% — لا هلوسة — النص من قاعدة البيانات مباشرة
"""
import re
import sqlite3
from typing import Optional
from core.db import get_conn, remove_diacritics


# ─────────────────────────────────────────────────────────────
#  البحث في القرآن الكريم
# ─────────────────────────────────────────────────────────────

def search_quran(
    query: str,
    qiraah: str = "hafs",
    limit: int = 10
) -> list[dict]:
    """
    البحث في القرآن الكريم باستخدام FTS5
    يعيد الآيات كما هي في قاعدة البيانات — لا توليد، لا هلوسة
    """
    query_clean = remove_diacritics(query.strip())
    results = []
    conn = get_conn()
    try:
        # 1) بحث FTS5 دلالي (يتجاهل التشكيل)
        rows = conn.execute(
            """
            SELECT q.surah_number, q.surah_name_ar, q.surah_name_en,
                   q.ayah_number, q.ayah_text_ar, q.surah_type, q.juz,
                   bm25(quran_fts) AS score
            FROM quran_fts
            JOIN quran q ON quran_fts.rowid = q.id
            WHERE quran_fts MATCH ? AND q.qiraah = ?
            ORDER BY score
            LIMIT ?
            """,
            (query_clean, qiraah, limit)
        ).fetchall()

        for r in rows:
            results.append({
                "source":       "quran",
                "qiraah":       qiraah,
                "surah_number": r["surah_number"],
                "surah_name_ar": r["surah_name_ar"],
                "surah_name_en": r["surah_name_en"],
                "ayah_number":  r["ayah_number"],
                "text_ar":      r["ayah_text_ar"],  # النص الأصلي المشكول
                "surah_type":   r["surah_type"],
                "juz":          r["juz"],
                "reference":    f"سورة {r['surah_name_ar']} ({r['surah_number']}:{r['ayah_number']})",
                "score":        round(abs(r["score"]), 4),
            })

        # 2) بحث رقمي إذا كان الاستعلام يحتوي على "سورة X:Y"
        m = re.search(r'(\d+)\s*[:،:]\s*(\d+)', query)
        if m and not results:
            s, v = int(m.group(1)), int(m.group(2))
            row = conn.execute(
                """SELECT * FROM quran
                   WHERE surah_number=? AND ayah_number=? AND qiraah=?""",
                (s, v, qiraah)
            ).fetchone()
            if row:
                results.insert(0, {
                    "source": "quran", "qiraah": qiraah,
                    "surah_number": row["surah_number"],
                    "surah_name_ar": row["surah_name_ar"],
                    "surah_name_en": row["surah_name_en"],
                    "ayah_number": row["ayah_number"],
                    "text_ar": row["ayah_text_ar"],
                    "reference": f"سورة {row['surah_name_ar']} ({s}:{v})",
                    "score": 1.0,
                })
    finally:
        conn.close()
    return results


def get_surah(surah_number: int, qiraah: str = "hafs") -> list[dict]:
    """إحضار سورة كاملة"""
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT * FROM quran
               WHERE surah_number=? AND qiraah=?
               ORDER BY ayah_number""",
            (surah_number, qiraah)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────
#  البحث في الأحاديث الشريفة
# ─────────────────────────────────────────────────────────────

def search_hadiths(
    query: str,
    collections: Optional[list[str]] = None,
    limit: int = 10
) -> list[dict]:
    """
    البحث الهجين في الأحاديث
    يعيد النص من قاعدة البيانات مباشرة — لا توليد
    """
    query_clean = remove_diacritics(query.strip())
    # إزالة علامات FTS الخاصة من المدخلات
    query_fts = re.sub(r'[*"\(\)]', '', query_clean).strip()

    conn = get_conn()
    results = []
    try:
        if collections:
            placeholders = ",".join("?" * len(collections))
            rows = conn.execute(
                f"""
                SELECT h.id, h.collection, h.hadith_number, h.arabic_number,
                       h.book_name_ar, h.chapter_name_ar,
                       h.text_ar, h.grade, h.reference,
                       bm25(hadith_fts) AS score
                FROM hadith_fts
                JOIN hadiths h ON hadith_fts.rowid = h.id
                WHERE hadith_fts MATCH ?
                  AND h.collection IN ({placeholders})
                ORDER BY score
                LIMIT ?
                """,
                (query_fts, *collections, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT h.id, h.collection, h.hadith_number, h.arabic_number,
                       h.book_name_ar, h.chapter_name_ar,
                       h.text_ar, h.grade, h.reference,
                       bm25(hadith_fts) AS score
                FROM hadith_fts
                JOIN hadiths h ON hadith_fts.rowid = h.id
                WHERE hadith_fts MATCH ?
                ORDER BY score
                LIMIT ?
                """,
                (query_fts, limit)
            ).fetchall()

        for r in rows:
            results.append({
                "source":      "hadith",
                "collection":  r["collection"],
                "hadith_number": r["hadith_number"],
                "arabic_number": r["arabic_number"],
                "book_name_ar": r["book_name_ar"],
                "chapter_name_ar": r["chapter_name_ar"],
                "text_ar":     r["text_ar"],
                "grade":       r["grade"],
                "reference":   r["reference"],
                "reference_label": _collection_label(r["collection"], r["hadith_number"]),
                "score":       round(abs(r["score"]), 4),
            })
    finally:
        conn.close()
    return results


def get_hadith_translations(collection: str, hadith_number: int) -> dict[str, str]:
    """إحضار ترجمات حديث معين بجميع اللغات"""
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT lang, text FROM hadith_translations
               WHERE collection=? AND hadith_number=?""",
            (collection, hadith_number)
        ).fetchall()
        return {r["lang"]: r["text"] for r in rows}
    finally:
        conn.close()


def get_quran_translation(surah: int, ayah: int, lang: str = "en") -> Optional[str]:
    """إحضار ترجمة آية"""
    conn = get_conn()
    try:
        row = conn.execute(
            """SELECT text FROM quran_translations
               WHERE surah_number=? AND ayah_number=? AND lang=?
               LIMIT 1""",
            (surah, ayah, lang)
        ).fetchone()
        return row["text"] if row else None
    finally:
        conn.close()


def _collection_label(collection: str, number: int) -> str:
    labels = {
        "bukhari":  "صحيح البخاري",
        "muslim":   "صحيح مسلم",
        "riyadh":   "رياض الصالحين",
        "nawawi":   "الأربعون النووية",
        "abudawud": "سنن أبي داود",
        "tirmidhi": "جامع الترمذي",
        "ibnmajah": "سنن ابن ماجه",
        "qudsi":    "الأحاديث القدسية",
    }
    name = labels.get(collection, collection)
    return f"{name} — حديث رقم {number}"


CATEGORY_LABELS = {
    "fiqh": "الفقه والمسائل الشرعية",
    "seerah": "السيرة النبوية",
    "aqeeda": "العقيدة الإسلامية",
    "adhkar": "الأذكار والأدعية",
    "tafseer": "التفسير القرآني",
    "general": "المعرفة الإسلامية العامة",
}


def search_books(
    query: str,
    category: Optional[str] = None,
    limit: int = 5
) -> list[dict]:
    """
    البحث في موسوعة الكتب والمراجع الإسلامية (السيرة، الفقه، العقيدة، الأذكار، التفسير)
    """
    query_clean = remove_diacritics(query.strip())
    query_fts = re.sub(r'[*"\(\)]', '', query_clean).strip()
    if not query_fts:
        return []

    conn = get_conn()
    results = []
    try:
        # 1. محاولة FTS5
        try:
            if category:
                rows = conn.execute(
                    """
                    SELECT b.id, b.book_id, b.title_ar, b.category, b.author_ar, b.summary, b.content,
                           bm25(books_fts) AS score
                    FROM books_fts
                    JOIN islamic_books b ON books_fts.rowid = b.id
                    WHERE books_fts MATCH ? AND b.category = ?
                    ORDER BY score
                    LIMIT ?
                    """,
                    (query_fts, category, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT b.id, b.book_id, b.title_ar, b.category, b.author_ar, b.summary, b.content,
                           bm25(books_fts) AS score
                    FROM books_fts
                    JOIN islamic_books b ON books_fts.rowid = b.id
                    WHERE books_fts MATCH ?
                    ORDER BY score
                    LIMIT ?
                    """,
                    (query_fts, limit)
                ).fetchall()
        except Exception:
            rows = []

        # 2. إذا لم يعطِ FTS نتائج، بحث LIKE مباشر في المحتوى والعنوان
        if not rows:
            tokens = [t for t in query_fts.split() if len(t) > 2]
            for token in tokens[:3]:
                like_pat = f"%{token}%"
                if category:
                    rows = conn.execute(
                        """
                        SELECT id, book_id, title_ar, category, author_ar, summary, content, -1.0 as score
                        FROM islamic_books
                        WHERE (title_ar LIKE ? OR content LIKE ? OR summary LIKE ?)
                          AND category = ?
                        LIMIT ?
                        """,
                        (like_pat, like_pat, like_pat, category, limit)
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """
                        SELECT id, book_id, title_ar, category, author_ar, summary, content, -1.0 as score
                        FROM islamic_books
                        WHERE title_ar LIKE ? OR content LIKE ? OR summary LIKE ?
                        LIMIT ?
                        """,
                        (like_pat, like_pat, like_pat, limit)
                    ).fetchall()
                if rows:
                    break

        seen_ids = set()
        for r in rows:
            if r["id"] in seen_ids:
                continue
            seen_ids.add(r["id"])
            cat = r["category"]
            cat_label = CATEGORY_LABELS.get(cat, cat)
            results.append({
                "source": "book",
                "book_id": r["book_id"],
                "title_ar": r["title_ar"],
                "author_ar": r["author_ar"],
                "category": cat,
                "category_label": cat_label,
                "summary": r["summary"],
                "content": r["content"],
                "text_ar": r["content"][:800],
                "reference": f"{r['title_ar']} — ({cat_label})",
                "reference_label": f"{r['title_ar']}",
                "score": round(abs(r["score"]), 4) if "score" in r.keys() else 1.0,
            })
    finally:
        conn.close()
    return results

