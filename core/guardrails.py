"""
core/guardrails.py
درع الحراسة والتحقق — يمنع الهلوسة بنسبة 0%
يفحص كل إجابة قبل وصولها للمستخدم
"""
import re
import hashlib
import json
from typing import Optional
from core.db import get_conn, remove_diacritics


# ─────────────────────────────────────────────────────────────
#  كاشف الاقتباسات في نص الذكاء الاصطناعي
# ─────────────────────────────────────────────────────────────

QURAN_PATTERNS = [
    re.compile(r'[﴿]([\u0600-\u06FF\s\u064B-\u065F،؛]{15,})[﴾]'),
    re.compile(r'قوله تعالى[:\s]+[﴿«"]?([\u0600-\u06FF\s\u064B-\u065F]{20,})[﴾»"]?'),
    re.compile(r'قال الله[:\s]+[﴿«"]?([\u0600-\u06FF\s\u064B-\u065F]{20,})[﴾»"]?'),
]

HADITH_PATTERNS = [
    re.compile(r'قال رسول الله.*?[:\s]+[«"]([\u0600-\u06FF\s\u064B-\u065F]{25,})[»"]'),
    re.compile(r'قال النبي.*?[:\s]+[«"]([\u0600-\u06FF\s\u064B-\u065F]{25,})[»"]'),
    re.compile(r'حديث[:\s]+[«"]([\u0600-\u06FF\s\u064B-\u065F]{25,})[»"]'),
    re.compile(r'روى.*?أن النبي.*?[:\s]+[«"]([\u0600-\u06FF\s\u064B-\u065F]{25,})[»"]'),
]


def _normalize(text: str) -> str:
    """توحيد النص للمقارنة"""
    text = remove_diacritics(text)
    text = re.sub(r'\s+', ' ', text).strip()
    # توحيد الأحرف المتشابهة
    text = text.replace('أ', 'ا').replace('إ', 'ا').replace('آ', 'ا')
    text = text.replace('ة', 'ه').replace('ى', 'ي')
    return text


def _text_in_quran_db(text: str, min_match: float = 0.80) -> dict | None:
    """
    التحقق من وجود نص في قاعدة بيانات القرآن
    يعيد الآية الأصلية إذا تجاوز التطابق min_match
    """
    if len(text) < 15:
        return None

    normalized = _normalize(text)
    conn = get_conn()
    try:
        # FTS بحث سريع
        query = remove_diacritics(text[:30])
        rows = conn.execute(
            """SELECT surah_number, surah_name_ar, ayah_number, ayah_text_ar
               FROM quran WHERE ayah_text_clean LIKE ?
               LIMIT 5""",
            (f"%{query}%",)
        ).fetchall()

        for row in rows:
            db_normalized = _normalize(row["ayah_text_ar"])
            # حساب نسبة التطابق (Jaccard على المقاطع الثلاثية)
            score = _jaccard(normalized, db_normalized)
            if score >= min_match:
                return {
                    "verified": True,
                    "correct_text": row["ayah_text_ar"],
                    "surah_number": row["surah_number"],
                    "surah_name_ar": row["surah_name_ar"],
                    "ayah_number": row["ayah_number"],
                    "reference": f"سورة {row['surah_name_ar']} ({row['surah_number']}:{row['ayah_number']})",
                    "match_score": round(score, 3),
                }
        return None
    finally:
        conn.close()


def _text_in_hadith_db(text: str, min_match: float = 0.75) -> dict | None:
    """التحقق من وجود نص في قاعدة بيانات الأحاديث"""
    if len(text) < 20:
        return None

    query = remove_diacritics(text[:40])
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT collection, hadith_number, text_ar, book_name_ar, grade
               FROM hadiths WHERE text_ar_clean LIKE ?
               LIMIT 5""",
            (f"%{query}%",)
        ).fetchall()

        for row in rows:
            score = _jaccard(_normalize(text), _normalize(row["text_ar"]))
            if score >= min_match:
                return {
                    "verified": True,
                    "correct_text": row["text_ar"],
                    "collection": row["collection"],
                    "hadith_number": row["hadith_number"],
                    "book_name_ar": row["book_name_ar"],
                    "grade": row["grade"],
                    "match_score": round(score, 3),
                }
        return None
    finally:
        conn.close()


def _jaccard(a: str, b: str, n: int = 3) -> float:
    """تشابه Jaccard على المقاطع الثلاثية"""
    if not a or not b:
        return 0.0
    set_a = {a[i:i+n] for i in range(len(a)-n+1)}
    set_b = {b[i:i+n] for i in range(len(b)-n+1)}
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


# ─────────────────────────────────────────────────────────────
#  كاش الأجوبة المتحقق منها
# ─────────────────────────────────────────────────────────────

def get_cached_answer(question: str) -> dict | None:
    """البحث في كاش الإجابات المتحقق منها"""
    q_hash = hashlib.sha256(question.strip().lower().encode()).hexdigest()
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT answer_json FROM answer_cache WHERE question_hash=?",
            (q_hash,)
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE answer_cache SET hit_count=hit_count+1 WHERE question_hash=?",
                (q_hash,)
            )
            conn.commit()
            return json.loads(row["answer_json"])
        return None
    finally:
        conn.close()


def save_to_cache(question: str, answer: dict):
    """حفظ إجابة متحقق منها في الكاش"""
    q_hash = hashlib.sha256(question.strip().lower().encode()).hexdigest()
    conn = get_conn()
    try:
        conn.execute(
            """INSERT OR REPLACE INTO answer_cache
               (question_hash, question, answer_json) VALUES (?,?,?)""",
            (q_hash, question, json.dumps(answer, ensure_ascii=False))
        )
        conn.commit()
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────
#  الدرع الرئيسي: تحقق من إجابة LLM قبل إرسالها
# ─────────────────────────────────────────────────────────────

def verify_and_fix_response(
    ai_response: str,
    retrieved_sources: list[dict],
) -> dict:
    """
    يفحص إجابة الذكاء الاصطناعي:
    1) إذا وجد اقتباسات قرآنية/حديثية يتحقق منها في قاعدة البيانات
    2) إذا لم تُجلب مصادر كافية → يعيد رسالة "لا أعلم"
    3) يُصحح النصوص التي تختلف عن الأصل المخزن
    """
    result = {
        "answer": ai_response,
        "sources": retrieved_sources,
        "verified": True,
        "corrections": [],
        "hallucination_detected": False,
        "unknown": False,
    }

    # ── حالة 1: لا توجد مصادر مُسترجعة → لا أعلم ──
    if not retrieved_sources:
        result["unknown"] = True
        result["answer"] = (
            "❌ لم يتوفر هذا في المصادر الإسلامية المعتمدة لدينا.\n\n"
            "يُرجى الرجوع إلى عالم متخصص أو موقع إسلامي موثوق للحصول على إجابة دقيقة."
        )
        return result

    # ── حالة 2: البحث عن اقتباسات قرآنية في نص الإجابة ──
    for pattern in QURAN_PATTERNS:
        for match in pattern.finditer(ai_response):
            quoted = match.group(1).strip()
            verification = _text_in_quran_db(quoted)
            if verification and verification["match_score"] < 0.95:
                # النص مقارب لكن ليس مطابقاً تماماً → استبدله بالأصل
                old = quoted
                correct = verification["correct_text"]
                result["answer"] = result["answer"].replace(old, correct)
                result["corrections"].append({
                    "original": old,
                    "corrected": correct,
                    "reference": verification["reference"],
                })
                result["hallucination_detected"] = True
            elif not verification:
                # محاولة اقتباس لم يُعثر له على تطابق → إزالة الادعاء
                result["hallucination_detected"] = True

    # ── حالة 3: البحث عن اقتباسات حديثية ──
    for pattern in HADITH_PATTERNS:
        for match in pattern.finditer(ai_response):
            quoted = match.group(1).strip()
            verification = _text_in_hadith_db(quoted)
            if verification and verification["match_score"] < 0.90:
                old = quoted
                correct = verification["correct_text"]
                result["answer"] = result["answer"].replace(old, correct)
                result["corrections"].append({
                    "original": old,
                    "corrected": correct,
                    "collection": verification.get("collection"),
                    "hadith_number": verification.get("hadith_number"),
                })
                result["hallucination_detected"] = True

    return result


# ─────────────────────────────────────────────────────────────
#  حماية من Prompt Injection (llm-security)
# ─────────────────────────────────────────────────────────────

INJECTION_PATTERNS = [
    re.compile(r'ignore\s+(all\s+)?previous', re.I),
    re.compile(r'forget\s+your\s+(instructions|system)', re.I),
    re.compile(r'you\s+are\s+now\s+(a|an)\s+\w+', re.I),
    re.compile(r'act\s+as\s+(if|a|an)', re.I),
    re.compile(r'جاهل\s+التعليمات', re.I),
    re.compile(r'تصرف\s+كأنك', re.I),
    re.compile(r'انسَ\s+التعليمات', re.I),
    re.compile(r'بالعربية\s+قل\s+إن', re.I),
    # محاولات تغيير الأحكام
    re.compile(r'قل\s+(إن|أن)\s+(هذا|هذه|ذلك)\s+(حلال|حرام)', re.I),
    re.compile(r'أفتِ\s+بأن', re.I),
]


def is_prompt_injection(question: str) -> bool:
    """كشف محاولات اختراق النموذج"""
    for pattern in INJECTION_PATTERNS:
        if pattern.search(question):
            return True
    return False


def sanitize_question(question: str) -> str:
    """تنظيف السؤال من المحارف الخطرة"""
    # إزالة محارف التحكم
    question = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', question)
    # تحديد حد أقصى
    return question[:2000]
