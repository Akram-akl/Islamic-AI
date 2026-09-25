"""
api/main.py — خادم FastAPI الرئيسي
مؤمَّن بالكامل، يدعم SSE (البث الفوري)، لا حدود للمستخدمين
"""
import os
import sys
import time
import json
import asyncio
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field, field_validator
from dotenv import load_dotenv

# إضافة مسار المشروع
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from core.db import get_conn
from core.search_engine import search_quran, search_hadiths, search_books, get_hadith_translations
from core.guardrails import (
    verify_and_fix_response, get_cached_answer,
    save_to_cache, is_prompt_injection, sanitize_question
)
from core.analytics_engine import (
    count_word_in_quran, compare_hadiths,
    get_surah_stats, get_hadith_stats
)
from core.ai_service import generate_answer, detect_language

# ─────────────────────────────────────────────────────────────
app = FastAPI(
    title="Islamic-AI API",
    description="نظام الذكاء الاصطناعي الإسلامي فائق الدقة — صفر هلوسة",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# تقديم ملفات الواجهة الأمامية
APP_DIR = ROOT / "app"
if APP_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(APP_DIR)), name="static")


@app.on_event("startup")
async def startup_check():
    """التأكد من جاهزية قاعدة البيانات والموسوعة الإسلامية عند الإقلاع"""
    try:
        from core.db import get_conn, build_database
        conn = get_conn()
        quran_count = conn.execute("SELECT COUNT(*) FROM quran WHERE qiraah='hafs'").fetchone()[0]
        conn.close()
        if quran_count < 6000:
            print("🏗️ قاعدة البيانات تحتاج إلى بناء... جار البناء التلقائي...")
            build_database()
            try:
                from data.populate_knowledge_base import populate
                populate()
            except Exception as pe:
                print(f"⚠️ تنبيه الموسوعة: {pe}")
        else:
            print(f"✅ قاعدة البيانات جاهزة وموثقة ({quran_count} آية)")
    except Exception as e:
        print(f"⚠️ خطأ في فحص قاعدة البيانات: {e}")



# ─────────────────────────────────────────────────────────────
#  نماذج البيانات (Pydantic — llm-structured-output)
# ─────────────────────────────────────────────────────────────

class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000)
    collections: Optional[list[str]] = None  # ["bukhari","muslim",...]
    qiraah: str = "hafs"
    lang: Optional[str] = None
    limit: int = Field(default=8, ge=1, le=20)

    @field_validator("question")
    @classmethod
    def clean_question(cls, v):
        return sanitize_question(v)


class StatsRequest(BaseModel):
    type: str  # "word_in_quran" | "surah_stats" | "hadith_stats"
    word: Optional[str] = None
    surah_number: Optional[int] = None
    collection: Optional[str] = None
    qiraah: str = "hafs"


class CompareRequest(BaseModel):
    collection1: str
    hadith_number1: int
    collection2: str
    hadith_number2: int


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=500)
    source: str = "all"  # "quran" | "hadith" | "all"
    collections: Optional[list[str]] = None
    qiraah: str = "hafs"
    limit: int = Field(default=10, ge=1, le=30)


# ─────────────────────────────────────────────────────────────
#  نقطة الدخول الرئيسية
# ─────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    index = APP_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return {"message": "Islamic-AI API جاهز", "docs": "/docs"}


@app.get("/health")
async def health():
    """فحص صحة الخادم"""
    conn = get_conn()
    try:
        quran_count = conn.execute(
            "SELECT COUNT(*) as c FROM quran WHERE qiraah='hafs'"
        ).fetchone()["c"]
        hadith_count = conn.execute(
            "SELECT COUNT(*) as c FROM hadiths"
        ).fetchone()["c"]
        return {
            "status": "ok",
            "quran_ayahs": quran_count,
            "hadiths": hadith_count,
            "db": "islamic.db",
        }
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────
#  1. السؤال الذكي مع درع الحراسة (RAG + Guardrails)
# ─────────────────────────────────────────────────────────────

@app.post("/api/ask")
async def ask(req: AskRequest, background: BackgroundTasks):
    """
    السؤال الرئيسي — يمر بـ:
    1. فحص Injection
    2. كاش الأجوبة (سرعة فورية)
    3. بحث هجين في القرآن + الأحاديث
    4. توليد مع السياق فقط
    5. درع التحقق ومنع الهلوسة
    """
    t0 = time.time()

    # ── حماية من الاختراق (llm-security) ──
    if is_prompt_injection(req.question):
        raise HTTPException(
            status_code=400,
            detail="⚠️ تم رصد محاولة اختراق. يُرجى طرح سؤالك بشكل مباشر."
        )

    # ── كاش الأجوبة — سرعة فورية ──
    cached = get_cached_answer(req.question)
    if cached:
        cached["cached"] = True
        cached["ms"] = round((time.time() - t0) * 1000)
        return cached

    # ── البحث الهجين الشامل (كتب ومراجع + أحاديث + قرآن) ──
    books_results = search_books(req.question, limit=3)
    hadith_results = search_hadiths(req.question, req.collections, req.limit)
    quran_results = search_quran(req.question, req.qiraah, req.limit // 2)
    sources = books_results + hadith_results + quran_results

    # ── كشف اللغة ──
    lang = req.lang or detect_language(req.question)

    # ── توليد الإجابة مع السياق المُسترجع ──
    ai_result = await generate_answer(req.question, sources, lang)

    # ── درع الحراسة — تحقق ومنع الهلوسة ──
    verified = verify_and_fix_response(ai_result["answer"], sources)

    result = {
        "question": req.question,
        "answer": verified["answer"],
        "sources": verified["sources"],
        "lang": lang,
        "unknown": verified["unknown"],
        "hallucination_detected": verified["hallucination_detected"],
        "corrections": verified["corrections"],
        "provider": ai_result.get("provider"),
        "cached": False,
        "ms": round((time.time() - t0) * 1000),
    }

    # ── حفظ في الكاش ──
    if not verified["unknown"] and not verified["hallucination_detected"]:
        background.add_task(save_to_cache, req.question, result)

    # ── سجل الاستعلام ──
    background.add_task(_log_query, req.question, lang, "qa", result["ms"])

    return result


# ─────────────────────────────────────────────────────────────
#  2. البحث النصي المباشر (فوري — لا ذكاء اصطناعي)
# ─────────────────────────────────────────────────────────────

@app.post("/api/search")
async def search(req: SearchRequest):
    """
    بحث نصي فوري في القرآن والأحاديث
    نتائج من قاعدة البيانات مباشرة — 0.01 ثانية
    """
    t0 = time.time()
    results = {"quran": [], "hadiths": [], "ms": 0}

    if req.source in ("quran", "all"):
        results["quran"] = search_quran(req.query, req.qiraah, req.limit)

    if req.source in ("hadith", "all"):
        results["hadiths"] = search_hadiths(req.query, req.collections, req.limit)

    results["ms"] = round((time.time() - t0) * 1000)
    results["total"] = len(results["quran"]) + len(results["hadiths"])
    return results


# ─────────────────────────────────────────────────────────────
#  3. محرك الإحصاء والمقارنات (mathguard — 100% حتمي)
# ─────────────────────────────────────────────────────────────

@app.post("/api/stats")
async def stats(req: StatsRequest):
    """
    إحصاءات رياضية حتمية — لا يترك الحساب للذكاء الاصطناعي
    """
    if req.type == "word_in_quran":
        if not req.word:
            raise HTTPException(400, "يلزم تحديد الكلمة المراد إحصاؤها")
        return count_word_in_quran(req.word, req.qiraah)

    elif req.type == "surah_stats":
        if not req.surah_number:
            raise HTTPException(400, "يلزم تحديد رقم السورة")
        return get_surah_stats(req.surah_number, req.qiraah)

    elif req.type == "hadith_stats":
        if not req.collection:
            raise HTTPException(400, "يلزم تحديد اسم المجموعة الحديثية")
        return get_hadith_stats(req.collection)

    raise HTTPException(400, f"نوع غير معروف: {req.type}")


@app.post("/api/compare")
async def compare(req: CompareRequest):
    """مقارنة حديثين بدقة رياضية"""
    return compare_hadiths(
        req.collection1, req.hadith_number1,
        req.collection2, req.hadith_number2,
    )


# ─────────────────────────────────────────────────────────────
#  4. نقاط اتصال إضافية
# ─────────────────────────────────────────────────────────────

@app.get("/api/quran/{surah}/{ayah}")
async def get_ayah(surah: int, ayah: int, qiraah: str = "hafs"):
    """إحضار آية معينة"""
    conn = get_conn()
    try:
        row = conn.execute(
            """SELECT * FROM quran
               WHERE surah_number=? AND ayah_number=? AND qiraah=?""",
            (surah, ayah, qiraah)
        ).fetchone()
        if not row:
            raise HTTPException(404, f"لم تُعثر على الآية {surah}:{ayah}")
        return dict(row)
    finally:
        conn.close()


@app.get("/api/hadith/{collection}/{number}")
async def get_hadith(collection: str, number: int):
    """إحضار حديث معين مع ترجماته"""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM hadiths WHERE collection=? AND hadith_number=?",
            (collection, number)
        ).fetchone()
        if not row:
            raise HTTPException(404, f"لم يُعثر على الحديث {collection}:{number}")
        result = dict(row)
        result["translations"] = get_hadith_translations(collection, number)
        return result
    finally:
        conn.close()


@app.get("/api/collections")
async def list_collections():
    """قائمة المجموعات الحديثية المتاحة مع أعدادها"""
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT collection, COUNT(*) as count
               FROM hadiths GROUP BY collection ORDER BY count DESC"""
        ).fetchall()
        return {
            "collections": [
                {"id": r["collection"], "count": r["count"]} for r in rows
            ]
        }
    finally:
        conn.close()


async def _log_query(q: str, lang: str, qtype: str, ms: int):
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO query_log (question,lang,query_type,duration_ms) VALUES (?,?,?,?)",
            (q[:500], lang, qtype, ms)
        )
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
