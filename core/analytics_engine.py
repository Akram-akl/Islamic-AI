"""
core/analytics_engine.py
محرك الإحصاء والمقارنات الرياضية الحتمي
100% دقة رياضية — لا يترك الحساب للذكاء الاصطناعي أبداً
"""
import re
import sqlite3
from core.db import get_conn, remove_diacritics


def count_word_in_quran(word: str, qiraah: str = "hafs") -> dict:
    """
    إحصاء تكرار كلمة (أو جذر) في القرآن الكريم
    نتيجة رياضية حتمية 100%
    """
    word_clean = remove_diacritics(word.strip())
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT surah_number, surah_name_ar, ayah_number, ayah_text_ar
               FROM quran WHERE qiraah=? AND ayah_text_clean LIKE ?""",
            (qiraah, f"%{word_clean}%")
        ).fetchall()

        occurrences = []
        total_count = 0
        surah_counts: dict[int, int] = {}

        for row in rows:
            text_clean = remove_diacritics(row["ayah_text_ar"])
            # عدد المرات داخل هذه الآية
            count_in_ayah = len(re.findall(re.escape(word_clean), text_clean))
            if count_in_ayah > 0:
                total_count += count_in_ayah
                s = row["surah_number"]
                surah_counts[s] = surah_counts.get(s, 0) + count_in_ayah
                occurrences.append({
                    "surah_number": s,
                    "surah_name_ar": row["surah_name_ar"],
                    "ayah_number": row["ayah_number"],
                    "count_in_ayah": count_in_ayah,
                    "ayah_text": row["ayah_text_ar"],
                })

        # السور الأعلى تكراراً
        top_surahs = sorted(surah_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        return {
            "word": word,
            "qiraah": qiraah,
            "total_count": total_count,
            "ayahs_count": len(occurrences),
            "top_surahs": [
                {"surah": s, "count": c} for s, c in top_surahs
            ],
            "occurrences": occurrences[:20],  # أول 20 نتيجة
            "source": "deterministic_sql_count",  # حتمي رياضي
        }
    finally:
        conn.close()


def compare_hadiths(
    collection1: str, number1: int,
    collection2: str, number2: int,
) -> dict:
    """
    مقارنة حديثين من مجموعتين مختلفتين
    مقارنة حرفية ودلالية رياضية
    """
    conn = get_conn()
    try:
        h1 = conn.execute(
            """SELECT * FROM hadiths WHERE collection=? AND hadith_number=?""",
            (collection1, number1)
        ).fetchone()
        h2 = conn.execute(
            """SELECT * FROM hadiths WHERE collection=? AND hadith_number=?""",
            (collection2, number2)
        ).fetchone()

        if not h1 or not h2:
            return {"error": "لم يُعثر على أحد الحديثين في قاعدة البيانات"}

        text1 = remove_diacritics(h1["text_ar"])
        text2 = remove_diacritics(h2["text_ar"])

        # تشابه Jaccard على المقاطع الثلاثية
        similarity = _jaccard_similarity(text1, text2)

        # الكلمات المشتركة والمختلفة
        words1 = set(text1.split())
        words2 = set(text2.split())
        common = words1 & words2
        only_in_1 = words1 - words2
        only_in_2 = words2 - words1

        return {
            "hadith_1": {
                "collection": collection1,
                "hadith_number": number1,
                "text_ar": h1["text_ar"],
                "grade": h1["grade"],
                "book": h1["book_name_ar"],
            },
            "hadith_2": {
                "collection": collection2,
                "hadith_number": number2,
                "text_ar": h2["text_ar"],
                "grade": h2["grade"],
                "book": h2["book_name_ar"],
            },
            "comparison": {
                "similarity_percent": round(similarity * 100, 2),
                "common_words_count": len(common),
                "words_only_in_h1": len(only_in_1),
                "words_only_in_h2": len(only_in_2),
                "are_same_hadith": similarity > 0.85,
                "verdict": (
                    "الحديثان متطابقان تقريباً (رواية مكررة)" if similarity > 0.85
                    else "الحديثان مختلفان"
                ),
            },
            "source": "deterministic_comparison",
        }
    finally:
        conn.close()


def get_surah_stats(surah_number: int, qiraah: str = "hafs") -> dict:
    """إحصاءات سورة كاملة"""
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT ayah_number, ayah_text_ar, ayah_text_clean
               FROM quran WHERE surah_number=? AND qiraah=?
               ORDER BY ayah_number""",
            (surah_number, qiraah)
        ).fetchall()

        if not rows:
            return {"error": f"لم يُعثر على سورة رقم {surah_number}"}

        all_text = " ".join(r["ayah_text_clean"] for r in rows)
        words = all_text.split()
        word_freq: dict[str, int] = {}
        for w in words:
            w = w.strip("،؛.؟!")
            if len(w) >= 2:
                word_freq[w] = word_freq.get(w, 0) + 1

        top_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:10]

        meta = conn.execute(
            """SELECT surah_name_ar, surah_name_en, surah_type
               FROM quran WHERE surah_number=? AND qiraah=? LIMIT 1""",
            (surah_number, qiraah)
        ).fetchone()

        return {
            "surah_number": surah_number,
            "surah_name_ar": meta["surah_name_ar"] if meta else f"سورة {surah_number}",
            "surah_name_en": meta["surah_name_en"] if meta else "",
            "surah_type": meta["surah_type"] if meta else "",
            "ayahs_count": len(rows),
            "words_count": len(words),
            "letters_count": sum(len(w) for w in words),
            "top_words": [{"word": w, "count": c} for w, c in top_words],
            "source": "deterministic_stats",
        }
    finally:
        conn.close()


def get_hadith_stats(collection: str) -> dict:
    """إحصاءات مجموعة حديثية"""
    conn = get_conn()
    try:
        total = conn.execute(
            "SELECT COUNT(*) as cnt FROM hadiths WHERE collection=?",
            (collection,)
        ).fetchone()["cnt"]

        grades = conn.execute(
            """SELECT grade, COUNT(*) as cnt FROM hadiths
               WHERE collection=? GROUP BY grade ORDER BY cnt DESC""",
            (collection,)
        ).fetchall()

        books = conn.execute(
            """SELECT book_name_ar, COUNT(*) as cnt FROM hadiths
               WHERE collection=? AND book_name_ar IS NOT NULL
               GROUP BY book_name_ar ORDER BY cnt DESC LIMIT 10""",
            (collection,)
        ).fetchall()

        return {
            "collection": collection,
            "total_hadiths": total,
            "grades": [{"grade": r["grade"] or "غير محدد", "count": r["cnt"]} for r in grades],
            "books": [{"book": r["book_name_ar"], "count": r["cnt"]} for r in books],
            "source": "deterministic_stats",
        }
    finally:
        conn.close()


def _jaccard_similarity(a: str, b: str, n: int = 3) -> float:
    set_a = {a[i:i+n] for i in range(max(0, len(a)-n+1))}
    set_b = {b[i:i+n] for i in range(max(0, len(b)-n+1))}
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)
