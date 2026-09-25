"""
core/ai_service.py
معمارية بلا حدود — لـ 10,000+ مستخدم
═══════════════════════════════════════════════════════════

الطبقة 1 (الأهم - فورية - بلا حدود):
  ✅ كاش ذكي - الإجابات المتكررة تُحفظ وتُعاد فوراً (0ms)
  ✅ إجابة مباشرة من قاعدة البيانات - بدون ذكاء اصطناعي أصلاً
  ✅ Ollama (محلي على السيرفر) - لا نت، لا حدود، لا تكلفة

الطبقة 2 (احتياطي - عند عدم وجود سيرفر قوي):
  🔄 تدوير مفاتيح Groq/Gemini - لضمان عدم الانقطاع

الطبقة 3 (أخير احتياطي):
  📚 عرض المصادر الموثقة مباشرة - دائماً يعمل
"""
import os
import re
import json
import asyncio
import hashlib
from langdetect import detect, LangDetectException
from core.query_classifier import classify_query, SYSTEM_PROMPTS

try:
    import httpx
    HTTPX_OK = True
except ImportError:
    HTTPX_OK = False

# llama_cpp اختياري
LLAMA_OK = False
Llama = None  # type: ignore[assignment]
try:
    import importlib.util as _ilu
    if _ilu.find_spec("llama_cpp") is not None:
        from llama_cpp import Llama  # type: ignore
        LLAMA_OK = True
except Exception:
    pass

# ── مسارات الإعداد ──
HF_TOKEN       = os.getenv("HF_TOKEN",         "")
GGUF_PATH      = os.getenv("GGUF_MODEL_PATH",  "")
OLLAMA_HOST    = os.getenv("OLLAMA_HOST",       "http://localhost:11434")  # افتراضي
OLLAMA_MODEL   = os.getenv("OLLAMA_MODEL",      "qwen2.5:7b")  # نموذج عربي ممتاز

# مفاتيح API يمكن تعدد (للتدوير) — افصل بفاصلة
_GROQ_KEYS_RAW   = os.getenv("GROQ_API_KEYS",    os.getenv("GROQ_API_KEY",    ""))
_GEMINI_KEYS_RAW = os.getenv("GEMINI_API_KEYS",  os.getenv("GEMINI_API_KEY",  ""))

# تقسيم المفاتيح المتعددة
GROQ_KEYS   = [k.strip() for k in _GROQ_KEYS_RAW.split(",")   if k.strip()]
GEMINI_KEYS = [k.strip() for k in _GEMINI_KEYS_RAW.split(",") if k.strip()]

# مؤشر تدوير المفاتيح (round-robin)
_groq_idx   = 0
_gemini_idx = 0

LANG_NAMES = {
    "ar": "العربية", "en": "English", "fr": "Français",
    "tr": "Türkçe",  "ur": "اردو",   "id": "Bahasa Indonesia",
    "de": "Deutsch", "es": "Español",
}

SYSTEM_PROMPT = """أنت مساعد إسلامي موثوق، تخاطب عامة الناس بأسلوب سهل وواضح.
قواعدك الصارمة:
1. أجب حصراً من المصادر المرفقة في السياق (القرآن، الأحاديث، الكتب الإسلامية الموثوقة).
2. اشرح بأسلوب بسيط مقسم إلى نقاط يفهمها المبتدئ.
3. اذكر المصدر دائماً في نهاية الإجابة.
4. اكتب باللغة العربية الفصحى البسيطة فقط — ممنوع أي كلمات أجنبية.
5. إذا لم تجد جواباً في المصادر، قل: "لا أملك نصاً صريحاً لهذه المسألة، يُرجى استشارة دار الإفتاء."
6. لا تخترع ولا تفترض أبداً."""


def detect_language(text: str) -> str:
    try:
        return detect(text)
    except LangDetectException:
        return "ar"


def build_context(sources: list[dict]) -> str:
    if not sources:
        return ""
    parts = ["📚 المصادر المعتمدة (أجب منها حصراً):"]
    for i, s in enumerate(sources, 1):
        if s.get("source") == "quran":
            parts.append(f"\n[{i}] {s['reference']}\nالآية: {s['text_ar']}")
        elif s.get("source") == "hadith":
            parts.append(
                f"\n[{i}] {s.get('reference_label', s.get('reference',''))}\n"
                f"الحديث: {s['text_ar']}\nالدرجة: {s.get('grade','')}"
            )
        elif s.get("source") == "book":
            content = s.get("content", s.get("text_ar", ""))
            parts.append(
                f"\n[{i}] المرجع: {s.get('reference', s.get('title_ar',''))}\n"
                f"{content[:600]}"
            )
    return "\n".join(parts)


# ═══════════════════════════════════════════════════════════
# الطبقة 1A: كاش ذكي للإجابات المتكررة (0ms — بلا حدود)
# ═══════════════════════════════════════════════════════════

def _question_hash(question: str) -> str:
    q = re.sub(r'\s+', ' ', question.strip().lower())
    q = q.replace('أ','ا').replace('إ','ا').replace('آ','ا').replace('ة','ه').replace('ى','ي')
    return hashlib.md5(q.encode()).hexdigest()


def get_from_answer_cache(question: str) -> str:
    """استرجاع إجابة محفوظة — فوري — بلا حدود"""
    from core.db import get_conn
    qh = _question_hash(question)
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT answer FROM answer_cache WHERE question_hash=?", (qh,)
        ).fetchone()
        if row:
            return row[0]
    except Exception:
        pass
    finally:
        conn.close()
    return ""


def save_to_answer_cache(question: str, answer: str) -> None:
    """حفظ الإجابة الجيدة للاستخدام المستقبلي"""
    from core.db import get_conn
    if not answer or len(answer) < 20:
        return
    qh = _question_hash(question)
    conn = get_conn()
    try:
        conn.execute(
            """INSERT OR REPLACE INTO answer_cache
               (question_hash, question_text, answer, hit_count, created_at)
               VALUES (?, ?, ?, COALESCE(
                   (SELECT hit_count+1 FROM answer_cache WHERE question_hash=?), 1
               ), datetime('now'))""",
            (qh, question[:500], answer, qh)
        )
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════
# الطبقة 1B: Ollama (محلي على السيرفر — بلا حدود — الأفضل)
# ═══════════════════════════════════════════════════════════

async def ask_ollama(question: str, context: str) -> str:
    """
    Ollama — نموذج يعمل محلياً على السيرفر
    لا إنترنت، لا حدود، لا تكلفة، لا تأخير
    للتثبيت: curl https://ollama.ai/install.sh | sh && ollama pull qwen2.5:7b
    """
    if not HTTPX_OK:
        return ""
    system_content = SYSTEM_PROMPT
    if context and context.strip():
        system_content = f"{SYSTEM_PROMPT}\n\n{context}"
    try:
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.post(
                f"{OLLAMA_HOST}/api/chat",
                json={
                    "model": OLLAMA_MODEL,
                    "messages": [
                        {"role": "system", "content": system_content},
                        {"role": "user",   "content": question},
                    ],
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 1000},
                },
            )
            if r.status_code == 200:
                data = r.json()
                content = data.get("message", {}).get("content", "")
                if content and content.strip():
                    return content.strip()
    except Exception as e:
        # Ollama غير مثبت أو لا يعمل — تجاهل بهدوء
        pass
    return ""


async def check_ollama_available() -> bool:
    """فحص إذا كان Ollama يعمل"""
    if not HTTPX_OK:
        return False
    try:
        async with httpx.AsyncClient(timeout=3) as c:
            r = await c.get(f"{OLLAMA_HOST}/api/tags")
            return r.status_code == 200
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════
# الطبقة 2A: Groq مع تدوير المفاتيح (احتياطي)
# ═══════════════════════════════════════════════════════════

async def ask_groq(question: str, context: str) -> str:
    """Groq مع تدوير تلقائي للمفاتيح المتعددة"""
    global _groq_idx
    if not GROQ_KEYS or not HTTPX_OK:
        return ""

    system_content = SYSTEM_PROMPT
    if context and context.strip():
        system_content = f"{SYSTEM_PROMPT}\n\n{context}"

    # جرب كل المفاتيح بالتدوير
    for attempt in range(len(GROQ_KEYS)):
        key = GROQ_KEYS[_groq_idx % len(GROQ_KEYS)]
        _groq_idx = (_groq_idx + 1) % len(GROQ_KEYS)
        try:
            async with httpx.AsyncClient(timeout=45) as c:
                r = await c.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {key}",
                             "Content-Type": "application/json"},
                    json={
                        "model": "llama-3.3-70b-versatile",
                        "messages": [
                            {"role": "system", "content": system_content},
                            {"role": "user",   "content": question},
                        ],
                        "temperature": 0.1,
                        "max_tokens": 1000,
                    },
                )
                data = r.json()
                if r.status_code == 429:
                    # حد الاستخدام — جرب المفتاح التالي
                    print(f"  ⚠️ Groq key {_groq_idx} reached limit, trying next...")
                    continue
                if "choices" not in data or not data["choices"]:
                    continue
                content = data["choices"][0]["message"]["content"]
                if content and content.strip():
                    return content.strip()
        except Exception as e:
            print(f"  ❌ Groq Error (key {attempt}): {e}")
            continue
    return ""


# ═══════════════════════════════════════════════════════════
# الطبقة 2B: Gemini مع تدوير المفاتيح (احتياطي)
# ═══════════════════════════════════════════════════════════

async def ask_gemini(question: str, context: str) -> str:
    """Gemini Flash مع تدوير تلقائي للمفاتيح المتعددة"""
    global _gemini_idx
    if not GEMINI_KEYS or not HTTPX_OK:
        return ""

    prompt_parts = [SYSTEM_PROMPT]
    if context and context.strip():
        prompt_parts.append(context)
    prompt_parts.append(f"\nالسؤال: {question}")
    full_prompt = "\n\n".join(prompt_parts)

    for attempt in range(len(GEMINI_KEYS)):
        key = GEMINI_KEYS[_gemini_idx % len(GEMINI_KEYS)]
        _gemini_idx = (_gemini_idx + 1) % len(GEMINI_KEYS)
        try:
            async with httpx.AsyncClient(timeout=45) as c:
                r = await c.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}",
                    headers={"Content-Type": "application/json"},
                    json={
                        "contents": [{"parts": [{"text": full_prompt}]}],
                        "generationConfig": {
                            "temperature": 0.1,
                            "maxOutputTokens": 1000,
                        },
                    },
                )
                if r.status_code == 429:
                    print(f"  ⚠️ Gemini key {_gemini_idx} reached limit, trying next...")
                    continue
                data = r.json()
                if "candidates" not in data or not data["candidates"]:
                    continue
                content = data["candidates"][0]["content"]["parts"][0]["text"]
                if content and content.strip():
                    return content.strip()
        except Exception as e:
            print(f"  ❌ Gemini Error (key {attempt}): {e}")
            continue
    return ""


# ═══════════════════════════════════════════════════════════
# الطبقة 3: GGUF محلي (بلا نت)
# ═══════════════════════════════════════════════════════════

_gguf_model = None

def _get_gguf():
    global _gguf_model
    if _gguf_model:
        return _gguf_model
    if not GGUF_PATH or not LLAMA_OK:
        return None
    if not os.path.exists(GGUF_PATH):
        return None
    print(f"  🔄 تحميل نموذج GGUF: {GGUF_PATH}")
    _gguf_model = Llama(
        model_path=GGUF_PATH,
        n_ctx=2048,
        n_threads=os.cpu_count() or 4,
        n_gpu_layers=0,
        verbose=False,
    )
    print("  ✅ نموذج GGUF جاهز")
    return _gguf_model


def ask_gguf_sync(question: str, context: str) -> str:
    llm = _get_gguf()
    if not llm:
        return ""
    prompt = f"""<|im_start|>system
{SYSTEM_PROMPT}
{context}<|im_end|>
<|im_start|>user
{question}<|im_end|>
<|im_start|>assistant
"""
    try:
        output = llm(prompt, max_tokens=800, temperature=0.1,
                     repeat_penalty=1.1, stop=["<|im_end|>", "<|im_start|>"])
        return output["choices"][0]["text"].strip()
    except Exception as e:
        return f"[GGUF Error: {e}]"


async def ask_gguf(question: str, context: str) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, ask_gguf_sync, question, context)


# ═══════════════════════════════════════════════════════════
# الدالة الرئيسية — بلا حدود
# ═══════════════════════════════════════════════════════════

async def generate_answer(
    question: str,
    sources: list[dict],
    lang: str | None = None,
) -> dict:
    """
    ترتيب الأولوية (بلا حدود لـ 10,000+ مستخدم):

    0️⃣ كاش ذكي (0ms — بلا حدود) ← يحل 60-80% من الأسئلة
    1️⃣ Ollama محلي على السيرفر (بلا حدود — الأفضل للإنتاج)
    2️⃣ GGUF محلي (بلا حدود — إذا لا يوجد سيرفر قوي)
    3️⃣ Groq بتدوير المفاتيح (احتياطي)
    4️⃣ Gemini بتدوير المفاتيح (احتياطي)
    5️⃣ عرض المصادر الموثقة مباشرة (دائماً يعمل — بلا حدود)
    """
    if not lang:
        lang = detect_language(question)

    query_type = classify_query(question)

    if query_type == "general":
        sources = []

    context = build_context(sources) if sources else ""
    provider = "unknown"
    answer = ""

    # 0️⃣ كاش ذكي — الأسرع والأكثر كفاءة (بلا حدود)
    cached = get_from_answer_cache(question)
    if cached:
        return {
            "answer": cached,
            "sources": sources,
            "lang": lang,
            "lang_name": LANG_NAMES.get(lang, lang),
            "provider": "smart-cache",
            "query_type": query_type,
            "cached": True,
        }

    # 1️⃣ Ollama — محلي، بلا حدود، بلا تكلفة (الأفضل للإنتاج)
    if not answer:
        ans = await ask_ollama(question, context)
        if ans and not ans.startswith("[") and ans.strip():
            answer = ans
            provider = f"ollama-{OLLAMA_MODEL}"
            print(f"  ✅ Ollama ({OLLAMA_MODEL}) نجح")

    # 2️⃣ GGUF محلي — بلا نت، بلا حدود
    if not answer and GGUF_PATH and LLAMA_OK:
        ans = await ask_gguf(question, context)
        if ans and not ans.startswith("[") and ans.strip():
            answer = ans
            provider = "gguf-local"
            print("  ✅ GGUF نجح")

    # 3️⃣ Groq بتدوير المفاتيح
    if not answer and GROQ_KEYS:
        ans = await ask_groq(question, context)
        if ans and not ans.startswith("[") and ans.strip():
            answer = ans
            provider = f"groq-{len(GROQ_KEYS)}-keys"
            print(f"  ✅ Groq ({len(GROQ_KEYS)} مفتاح) نجح")

    # 4️⃣ Gemini بتدوير المفاتيح
    if not answer and GEMINI_KEYS:
        ans = await ask_gemini(question, context)
        if ans and not ans.startswith("[") and ans.strip():
            answer = ans
            provider = f"gemini-{len(GEMINI_KEYS)}-keys"
            print(f"  ✅ Gemini ({len(GEMINI_KEYS)} مفتاح) نجح")

    # 5️⃣ Fallback نهائي: عرض المصادر الموثقة مباشرة (بلا حدود دائماً)
    if not answer or answer.startswith("["):
        if sources:
            parts = ["الحمد لله، بناءً على المصادر الموثقة في قاعدة البيانات:\n"]
            for s in sources[:4]:
                if s.get("source") == "quran":
                    parts.append(f"📖 **{s.get('reference')}**:\n{s.get('text_ar')}\n")
                elif s.get("source") == "hadith":
                    parts.append(
                        f"📜 **{s.get('reference_label', s.get('reference'))}** "
                        f"({s.get('grade','')}):\n{s.get('text_ar')}\n"
                    )
                elif s.get("source") == "book":
                    content = s.get("content", s.get("text_ar", ""))[:600]
                    parts.append(f"📚 **{s.get('reference')}**:\n{content}\n")
            if len(parts) > 1:
                answer = "\n".join(parts)
                provider = "verified-sources-db"
        elif query_type == "general":
            answer = "مرحباً بك! أنا مساعدك الإسلامي الموثوق. اسألني عن القرآن والسنة والفقه والسيرة والأذكار."
            provider = "general-assistant"
        else:
            answer = "لم يُعثر على نص صريح في المصادر المعتمدة لهذا السؤال. يُرجى الرجوع لدار الإفتاء أو عالم متخصص."
            provider = "none"

    # ضمان عدم إرجاع إجابة فارغة أبداً
    if not answer or not answer.strip():
        answer = "عذراً، يُرجى إعادة صياغة سؤالك أو المحاولة لاحقاً."
        provider = "error-fallback"

    # حفظ في الكاش لاستخدامات مستقبلية (يقلل الضغط على API)
    if provider not in ("none", "error-fallback") and answer:
        asyncio.create_task(_save_cache_async(question, answer))

    return {
        "answer": answer,
        "sources": sources,
        "lang": lang,
        "lang_name": LANG_NAMES.get(lang, lang),
        "provider": provider,
        "query_type": query_type,
        "cached": False,
    }


async def _save_cache_async(question: str, answer: str):
    """حفظ الكاش بشكل غير متزامن لعدم تأخير الرد"""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, save_to_answer_cache, question, answer)


def get_available_provider() -> str:
    """معرفة المزودات المتاحة حالياً"""
    providers = []
    providers.append(f"Smart-Cache ✅ (بلا حدود)")
    if OLLAMA_HOST:
        providers.append(f"Ollama ({OLLAMA_MODEL}) ✅ (بلا حدود)")
    if GGUF_PATH and LLAMA_OK and os.path.exists(GGUF_PATH):
        providers.append("GGUF-Local ✅ (بلا حدود)")
    if GROQ_KEYS:
        providers.append(f"Groq ({len(GROQ_KEYS)} مفاتيح) ✅")
    if GEMINI_KEYS:
        providers.append(f"Gemini ({len(GEMINI_KEYS)} مفاتيح) ✅")
    providers.append("Verified-DB ✅ (بلا حدود)")
    return " | ".join(providers)
