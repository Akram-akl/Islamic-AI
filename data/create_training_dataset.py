"""
data/create_training_dataset.py
ينشئ بيانات تدريب Q&A من قاعدة البيانات الإسلامية
المخرج: data/train.jsonl و data/eval.jsonl
الصيغة: ChatML — مناسب لـ QLoRA مع Qwen2.5 / Phi-3 / Llama-3
"""
import json
import random
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

DB_PATH = ROOT / "data" / "islamic.db"
OUT_TRAIN = ROOT / "data" / "train.jsonl"
OUT_EVAL  = ROOT / "data" / "eval.jsonl"

SYSTEM_PROMPT = """أنت مساعد إسلامي أمين ومتخصص. تُجيب حصراً من القرآن الكريم والسنة النبوية الصحيحة.
قواعدك الثابتة:
1. أذكر دائماً المصدر الدقيق: (سورة + رقم آية) أو (كتاب + رقم حديث).
2. أورد أولاً النص العربي الأصلي كما ورد في المصدر.
3. إذا لم يتوفر الجواب في المصادر المعتمدة أقول بوضوح: "لا أعلم، يُرجى الرجوع لعالم متخصص."
4. لا أفتي من رأسي ولا أتخيل نصوصاً."""

COLLECTION_LABELS = {
    "bukhari":  "صحيح البخاري",
    "muslim":   "صحيح مسلم",
    "nawawi":   "الأربعون النووية",
    "abudawud": "سنن أبي داود",
    "tirmidhi": "جامع الترمذي",
    "ibnmajah": "سنن ابن ماجه",
    "qudsi":    "الأحاديث القدسية",
}

# ─── قوالب الأسئلة (تنوع لتعليم النموذج) ───
QURAN_QUESTION_TEMPLATES = [
    "ما نص الآية {n} من سورة {s}؟",
    "ما قول الله تعالى في الآية {n} من سورة {s}؟",
    "اذكر الآية {n} من سورة {s} مع بيان سياقها.",
    "ما الآية الكريمة التي تتحدث عن {topic}؟",
    "هل ذُكر {topic} في القرآن الكريم؟ وأين؟",
    "أريد آية قرآنية عن {topic}.",
    "What does Quran say about {topic}?",
    "Which verse mentions {topic} in the Quran?",
]

HADITH_QUESTION_TEMPLATES = [
    "ما حديث النبي ﷺ عن {topic}؟",
    "هل ورد حديث في {topic}؟",
    "ما الحديث رقم {n} في {collection}؟",
    "اذكر حديثاً نبوياً في {topic} مع المصدر.",
    "ما قال النبي ﷺ في شأن {topic}؟",
    "What did the Prophet ﷺ say about {topic}?",
    "Is there a hadith about {topic} in Sahih Bukhari?",
    "Mention a hadith about {topic} with its reference.",
]

# موضوعات شائعة لتنويع الأسئلة
TOPICS = [
    "الصلاة", "الزكاة", "الصوم", "الحج", "الإيمان", "التوبة",
    "الصبر", "الشكر", "العلم", "الأمانة", "الصدق", "الرحمة",
    "الجنة", "النار", "القيامة", "الموت", "البر", "الحسد",
    "الغيبة", "النية", "الذكر", "الدعاء", "الطهارة", "الوضوء",
    "prayer", "fasting", "charity", "patience", "gratitude", "faith",
    "honesty", "mercy", "heaven", "hellfire", "repentance", "knowledge",
]

DONT_KNOW_EXAMPLES = [
    {
        "q": "ما هو حكم استخدام الهاتف أثناء الصلاة تفصيلاً دقيقاً؟",
        "a": "لا يتوفر نص صريح في المصادر المعتمدة لديّ يتناول هذه المسألة بتفصيلها الدقيق. يُرجى الرجوع لعالم متخصص أو موقع إسلامي موثوق كإسلام ويب أو دار الإفتاء."
    },
    {
        "q": "ما حكم العملات الرقمية في الإسلام؟",
        "a": "هذه مسألة معاصرة مستجدة لا يتوفر فيها نص قاطع في المصادر المعتمدة لديّ. يُرجى استشارة علماء متخصصين في الفقه المعاصر."
    },
    {
        "q": "What is the ruling on cryptocurrency in Islam?",
        "a": "This is a contemporary issue (masa'la mustajidda) that is not definitively addressed in the classical sources I have. Please consult specialized scholars in contemporary Islamic jurisprudence."
    },
]


def get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def make_chatml(question: str, answer: str) -> dict:
    """صيغة ChatML الموحدة لكل أنواع النماذج"""
    return {
        "messages": [
            {"role": "system",    "content": SYSTEM_PROMPT},
            {"role": "user",      "content": question},
            {"role": "assistant", "content": answer},
        ]
    }


def make_chatml_typed(question: str, answer: str, system: str) -> dict:
    """نسخة مع system prompt مخصص لكل نوع"""
    return {
        "messages": [
            {"role": "system",    "content": system},
            {"role": "user",      "content": question},
            {"role": "assistant", "content": answer},
        ]
    }


SYSTEM_GENERAL = """أنت مساعد ذكي ومفيد. أُجيب بشكل طبيعي وودّي على أي سؤال.
- للأسئلة العامة أُجيب مباشرة كأي مساعد AI.
- أكون لطيفاً ومختصراً."""

SYSTEM_ADVISORY = """أنت مساعد إسلامي مفيد. للأسئلة التي تحتاج خططاً ونصائح عملية:
- أُجيب بشكل مفيد وعملي.
- أُراعي الثوابت الإسلامية في نصائحي.
- يمكنني إضافة آيات ذات صلة إن وُجدت."""


def generate_general_samples() -> list[dict]:
    """أمثلة محادثة عامة — النموذج يُجيب طبيعياً"""
    examples = [
        ("كيف حالك؟", "بخير الحمدلله! كيف أستطيع مساعدتك اليوم؟"),
        ("صباح الخير", "صباح النور! كيف يمكنني مساعدتك؟"),
        ("مساء الخير", "مساء النور! كيف أستطيع خدمتك؟"),
        ("شكراً جزيلاً", "العفو! يسعدني دائماً مساعدتك."),
        ("من أنت؟", "أنا مساعد ذكاء اصطناعي إسلامي. أستطيع مساعدتك في أسئلة القرآن والحديث والشريعة الإسلامية."),
        ("ما اسمك؟", "أنا المساعد الإسلامي. كيف أستطيع مساعدتك؟"),
        ("Hello!", "Hello! How can I assist you today?"),
        ("How are you?", "I'm doing well, thank you for asking! How can I help you?"),
        ("Thank you", "You're welcome! Feel free to ask anything."),
        ("Who are you?", "I'm an Islamic AI assistant. I can help you with questions about Quran, Hadith, and Islamic knowledge."),
        ("هل أنت ذكاء اصطناعي؟", "نعم، أنا مساعد ذكاء اصطناعي متخصص في المعلومات الإسلامية."),
        ("ما هو الطقس اليوم؟", "لا أملك إمكانية الوصول لبيانات الطقس الحية، لكن يمكنني مساعدتك في أسئلة إسلامية!"),
        ("اشرح لي كيف تعمل؟", "أعمل بالبحث في قاعدة بيانات تضم القرآن الكريم وأكثر من 100,000 حديث نبوي، ثم أُجيب بناءً على هذه المصادر المعتمدة."),
    ]
    return [make_chatml_typed(q, a, SYSTEM_GENERAL) for q, a in examples]


def generate_advisory_samples() -> list[dict]:
    """أمثلة استشارية — النموذج يُجيب من عنده بشكل إسلامي"""
    examples = [
        (
            "أنشئ لي خطة لحفظ القرآن الكريم",
            """بسم الله، إليك خطة مقترحة لحفظ القرآن الكريم:

**خطة الستة أشهر:**
- الأسبوع 1-2: سور قصار (الضحى → الناس) — حفظ سورة يومياً
- الشهر 1-2: جزء عم كاملاً بمراجعة يومية
- الشهر 3-4: جزء تبارك مع المراجعة
- الشهر 5-6: الجزء 28 مع تثبيت ما حُفظ

**نصائح للثبات:**
1. حدد وقتاً ثابتاً يومياً (الفجر أفضل وقت)
2. استمع للآيات قبل حفظها
3. راجع ما حفظته كل يوم قبل الجديد
4. ابدأ بالقليل والمنتظم خير من الكثير المتقطع

قال الله تعالى: ﴿وَلَقَدْ يَسَّرْنَا الْقُرْآنَ لِلذِّكْرِ﴾ (القمر: 17)
بالتوفيق والسداد!"""
        ),
        (
            "كم وقت يحتاج لختم القرآن الكريم؟",
            """يعتمد ذلك على وتيرتك، لكن إليك أنماطاً شائعة:

| الوتيرة | الوقت اليومي | مدة الختم |
|---|---|---|
| صفحة واحدة | 10-15 دقيقة | 20 شهراً |
| ربع جزء | 20-30 دقيقة | 4 أشهر |
| نصف جزء | 40-50 دقيقة | شهران |
| جزء كامل | 60-90 دقيقة | شهر واحد |

**توصيتي:** ابدأ بصفحة واحدة يومياً والمداومة أهم من الكمية. الختم في رمضان سنة متبعة وكان النبي ﷺ يراجع القرآن مع جبريل مرة في كل رمضان."""
        ),
        (
            "ما أفضل وقت للقيام بالليل؟",
            """أفضل وقت لقيام الليل هو الثلث الأخير من الليل.

إذا كان الفجر مثلاً الساعة 5:00 صباحاً:
- الثلث الأخير يبدأ من الساعة 3:00 - 3:30 صباحاً تقريباً

**خطوات عملية للبدء:**
1. نَمْ مبكراً (10-11 مساءً)
2. اضبط المنبه على 3:30 صباحاً
3. ابدأ بركعتين خفيفتين
4. زد تدريجياً حسب استطاعتك

الأمر يحتاج عادةً 2-3 أسابيع لتكوين العادة."""
        ),
        (
            "Create a plan to memorize the Quran",
            """Here's a practical Quran memorization plan:

**6-Month Plan:**
- Weeks 1-4: Short surahs (Al-Ikhlas → An-Nas) — 1 surah/day
- Month 2: Complete Juz Amma with daily review
- Month 3-4: Juz Tabarak
- Month 5-6: Consolidate and review

**Key Tips:**
1. Set a fixed daily time (after Fajr is ideal)
2. Listen before you memorize
3. Review previous portions before new ones
4. Consistency beats quantity

Allah says: ﴿And We have certainly made the Quran easy for remembrance﴾ (54:17)
May Allah bless your journey!"""
        ),
        (
            "ما الفرق بين الفرض والواجب والسنة؟",
            """هذه تصنيفات فقهية للأحكام الشرعية:

**الفرض (الفريضة):** ما أوجبه الله بدليل قطعي، تاركه آثم ومؤديه مأجور.
مثال: الصلوات الخمس، الزكاة، صيام رمضان.

**الواجب:** عند الحنفية: ما ثبت بدليل ظني، تاركه آثم لكن أخف من الفرض.
مثال عندهم: صلاة الوتر، صدقة الفطر.

**السنة (المستحب/النافلة):** ما فعله النبي ﷺ ولم يُوجبه. تاركه لا يأثم ومؤديه مأجور.
مثال: السنن الرواتب قبل الصلوات وبعدها.

ملاحظة: قد يختلف العلماء في تصنيف بعض المسائل."""
        ),
    ]
    return [make_chatml_typed(q, a, SYSTEM_ADVISORY) for q, a in examples]

def generate_quran_samples(conn, limit=3000) -> list[dict]:
    """توليد أمثلة تدريبية من القرآن الكريم"""
    rows = conn.execute(
        """SELECT surah_number, surah_name_ar, ayah_number, ayah_text_ar
           FROM quran WHERE qiraah='hafs'
           ORDER BY RANDOM() LIMIT ?""",
        (limit,)
    ).fetchall()

    samples = []
    for row in rows:
        s = row["surah_number"]
        v = row["ayah_number"]
        text = row["ayah_text_ar"]
        name = row["surah_name_ar"]
        ref = f"سورة {name} ({s}:{v})"
        topic = random.choice(TOPICS)

        # سؤال مباشر برقم
        q = random.choice([
            f"ما نص الآية {v} من سورة {name}؟",
            f"اذكر الآية {v} من سورة {s}.",
            f"What is verse {v} of Surah {name}?",
        ])
        a = f"قال الله تعالى في {ref}:\n\n﴿{text}﴾\n\nالمصدر: {ref}"
        samples.append(make_chatml(q, a))

        # سؤال بالموضوع (بدون رقم)
        if len(text) > 30 and random.random() < 0.3:
            q2 = random.choice([
                f"هل ورد في القرآن الكريم آية عن {topic}؟",
                f"Is there a Quranic verse about {topic}?",
            ])
            a2 = (
                f"نعم، ومن ذلك قوله تعالى في {ref}:\n\n"
                f"﴿{text}﴾\n\n"
                f"المصدر: {ref}"
            )
            samples.append(make_chatml(q2, a2))

    return samples


def generate_hadith_samples(conn, limit=5000) -> list[dict]:
    """توليد أمثلة تدريبية من الأحاديث"""
    rows = conn.execute(
        """SELECT h.collection, h.hadith_number, h.text_ar, h.grade,
                  t_en.text as text_en, t_fr.text as text_fr
           FROM hadiths h
           LEFT JOIN hadith_translations t_en
             ON t_en.collection=h.collection AND t_en.hadith_number=h.hadith_number AND t_en.lang='en'
           LEFT JOIN hadith_translations t_fr
             ON t_fr.collection=h.collection AND t_fr.hadith_number=h.hadith_number AND t_fr.lang='fr'
           WHERE h.text_ar IS NOT NULL AND length(h.text_ar) > 50
           ORDER BY RANDOM() LIMIT ?""",
        (limit,)
    ).fetchall()

    samples = []
    for row in rows:
        col   = row["collection"]
        num   = row["hadith_number"]
        ar    = row["text_ar"]
        en    = row["text_en"]
        grade = row["grade"] or ""
        col_label = COLLECTION_LABELS.get(col, col)
        ref   = f"{col_label} — حديث رقم {num}"
        topic = random.choice(TOPICS)

        # سؤال عربي مباشر
        q = random.choice([
            f"ما حديث النبي ﷺ عن {topic}؟",
            f"هل ورد حديث صحيح عن {topic}؟",
            f"اذكر حديثاً نبوياً عن {topic} مع المصدر.",
            f"ما الحديث رقم {num} في {col_label}؟",
        ])
        a = f"روى الإمام في {ref}:\n\nعن النبي ﷺ: «{ar}»"
        if grade:
            a += f"\n\nدرجة الحديث: {grade}"
        a += f"\n\nالمصدر: {ref}"
        samples.append(make_chatml(q, a))

        # سؤال إنجليزي إذا توفرت الترجمة
        if en and random.random() < 0.5:
            q_en = random.choice([
                f"What did the Prophet ﷺ say about {topic}?",
                f"Is there a hadith about {topic} in {col_label}?",
                f"Share a hadith about {topic} with its source.",
            ])
            a_en = (
                f"The Prophet ﷺ said (narrated in {col_label}, Hadith #{num}):\n\n"
                f"Arabic: «{ar}»\n\n"
                f"Translation: {en}"
            )
            if grade:
                a_en += f"\n\nGrade: {grade}"
            a_en += f"\n\nSource: {ref}"
            samples.append(make_chatml(q_en, a_en))

    return samples


def generate_laidont_know_samples() -> list[dict]:
    """أمثلة 'لا أعلم' لتعليم النموذج التواضع"""
    samples = []
    for ex in DONT_KNOW_EXAMPLES:
        samples.append(make_chatml(ex["q"], ex["a"]))

    # توليد إضافي
    extras = [
        ("ما حكم ركوب السيارة الكهربائية؟",
         "لا يتوفر نص في المصادر الكلاسيكية لهذه المسألة المعاصرة. يُرجى استشارة عالم متخصص."),
        ("ما رأيك في السياسة؟",
         "هذا خارج نطاق تخصصي في المصادر الإسلامية المعتمدة. أُرشدك لاستشارة العلماء المتخصصين."),
        ("من سيفوز في كأس العالم؟",
         "هذا السؤال خارج نطاقي — أنا متخصص في القرآن الكريم والسنة النبوية فقط."),
        ("ما هو أفضل هاتف؟",
         "لا يتعلق هذا بتخصصي في العلوم الشرعية. يمكنني مساعدتك في أسئلة القرآن والحديث."),
    ]
    for q, a in extras:
        samples.append(make_chatml(q, a))
    return samples


def generate_stats_samples(conn) -> list[dict]:
    """أمثلة إحصاءات يُجيب فيها بالحسابات الرياضية"""
    samples = []

    # عدد آيات القرآن
    count = conn.execute("SELECT COUNT(*) as c FROM quran WHERE qiraah='hafs'").fetchone()["c"]
    samples.append(make_chatml(
        "كم عدد آيات القرآن الكريم؟",
        f"عدد آيات القرآن الكريم برواية حفص عن عاصم هو {count:,} آية، موزعة على 114 سورة.\n\nالمصدر: قاعدة البيانات القرآنية المعتمدة (حفص)."
    ))
    samples.append(make_chatml(
        "How many verses are in the Quran?",
        f"The Quran contains {count:,} verses (ayat) in the Hafs recitation, distributed across 114 surahs.\n\nSource: Verified Quranic database (Hafs narration)."
    ))

    # عدد أحاديث البخاري
    buk_count = conn.execute(
        "SELECT COUNT(*) as c FROM hadiths WHERE collection='bukhari'"
    ).fetchone()["c"]
    samples.append(make_chatml(
        "كم عدد أحاديث صحيح البخاري؟",
        f"يحتوي صحيح البخاري على {buk_count:,} حديث في قاعدة بياناتنا المعتمدة.\n\nالمصدر: صحيح البخاري."
    ))

    return samples


def main():
    if not DB_PATH.exists():
        print("❌ قاعدة البيانات غير موجودة. شغّل أولاً: python setup.py")
        sys.exit(1)

    print("🏗️  إنشاء بيانات التدريب...")
    conn = get_conn()

    all_samples = []

    print("  📖 توليد أمثلة قرآنية...")
    quran = generate_quran_samples(conn, 3000)
    all_samples.extend(quran)
    print(f"     → {len(quran)} مثال")

    print("  📜 توليد أمثلة حديثية...")
    hadith = generate_hadith_samples(conn, 5000)
    all_samples.extend(hadith)
    print(f"     → {len(hadith)} مثال")

    print("  🚫 توليد أمثلة 'لا أعلم'...")
    dk = generate_laidont_know_samples()
    all_samples.extend(dk * 5)  # تضخيم لتعليم النموذج التواضع
    print(f"     → {len(dk)*5} مثال")

    print("  📊 توليد أمثلة إحصائية...")
    stats = generate_stats_samples(conn)
    all_samples.extend(stats)
    print(f"     → {len(stats)} مثال")

    print("  💬 توليد أمثلة محادثة عامة...")
    general = generate_general_samples()
    all_samples.extend(general * 8)  # تكرار لأهميتها
    print(f"     → {len(general)*8} مثال")

    print("  📋 توليد أمثلة استشارية...")
    advisory = generate_advisory_samples()
    all_samples.extend(advisory * 5)
    print(f"     → {len(advisory)*5} مثال")


    conn.close()

    # خلط عشوائي
    random.shuffle(all_samples)

    # تقسيم 95% تدريب / 5% تقييم
    split = int(len(all_samples) * 0.95)
    train = all_samples[:split]
    eval_ = all_samples[split:]

    # كتابة الملفات
    with open(OUT_TRAIN, "w", encoding="utf-8") as f:
        for item in train:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    with open(OUT_EVAL, "w", encoding="utf-8") as f:
        for item in eval_:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"\n✅ بيانات التدريب جاهزة:")
    print(f"   📄 data/train.jsonl  → {len(train):,} مثال")
    print(f"   📄 data/eval.jsonl   → {len(eval_):,} مثال")
    print(f"   📦 الإجمالي: {len(all_samples):,} مثال تدريبي")


if __name__ == "__main__":
    main()
