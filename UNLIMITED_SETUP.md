# 🚀 دليل التشغيل والنشر الشامل — نظام مجاني لـ 1,000,000 مستخدم

## 🧠 المعمارية الذكية (كيف يتحمل مليون مستخدم مجاناً؟)

```
                       طلب المستخدم من الجوال
                                 │
                                 ▼
0️⃣  كاش ذكي مسبق التجهيز (SQLite) ──▶ إجابة في 0.01 ثانية (يمتص 90% من الزيارات)
                                 │ (سؤال جديد لم يُسأل مسبقاً)
                                 ▼
1️⃣  بحث مباشر في قاعدة المصادر ────▶ قرآن (6,236 آية) + أحاديث (40,000+) + كتب
                                 │
                                 ▼
2️⃣  توليد الإجابة عبر Groq المجاني ──▶ 14,400 طلب/يوم لكل مفتاح (سريع جداً)
3️⃣  احتياطي: Gemini المجاني ──────▶ 1,500 طلب/يوم لكل مفتاح
                                 │
                                 ▼
        يتم حفظ الإجابة فوراً في الكاش ◀── فلا يُستهلك الذكاء الاصطناعي مرة أخرى!
```

---

## 🔑 1. مفاتيح الذكاء الاصطناعي المجانية (بدون فيزا)

### Groq (السرعة الفائقة — مجاني):
1. افتح: https://console.groq.com/keys
2. سجل دخول بحساب Google (مجاني، لا يطلب بطاقة بنكية).
3. اضغط **Create API Key** وانسخه.
4. ضعه في ملف `.env`:
```env
GROQ_API_KEYS=gsk_your_key_here
```
*(يمكنك إنشاء مفتاح من حساب آخر ووضعه مفصولاً بفاصلة لزيادة الحصة: `GROQ_API_KEYS=key1,key2`)*

### Gemini (احتياطي مجاني):
1. افتح: https://aistudio.google.com/app/apikey
2. اضغط **Create API key**.
3. ضعه في `.env`:
```env
GEMINI_API_KEYS=AIza_your_key_here
```

---

## ⚡ 2. ملء الكاش مسبقاً (Pre-fill Cache)

لتسريع التطبيق وحماية مفاتيح API من البداية:
```powershell
python data/prefill_cache.py
```
يقوم هذا السكربت بتجهيز إجابات أكثر من 200 سؤال إسلامي شائع (الوضوء، الصلاة، الصيام، الزكاة، السيرة) وحفظها في قاعدة البيانات.

---

## 🌐 3. النشر السحابي المجاني (Hugging Face Spaces — بدون بطاقة بنكية)

1. سجل دخول في https://huggingface.co
2. اضغط على أيقونة حسابك ⬅️ **New Space**
3. اختر:
   - **Space name**: `islamic-ai`
   - **Space SDK**: **Docker** (مهم جداً!)
   - **Choose a Docker template**: Blank
   - **Space Hardware**: CPU Basic (Free - 16 GB RAM)
4. اضغط **Create Space**.
5. من جهازك، ارفع المشروع عبر Git:
```powershell
cd "c:\Users\akram\OneDrive\Desktop\appsakramakl\Islamic-AI"
git add .
git commit -m "Deploy Islamic AI"
git remote add space https://huggingface.co/spaces/YOUR_USERNAME/islamic-ai
git push --force space main
```
6. في صفحة الـ Space على المتصفح: اذهب إلى **Settings** ➡️ **Variables and secrets** وأضف:
   - `GROQ_API_KEYS`
   - `GEMINI_API_KEYS`

---

## 📱 4. تشغيل التطبيق على الجوال للمستخدمين

بمجرد اكتمال البناء على Hugging Face، يحصل تطبيقك على رابط فوري، مثل:
`https://YOUR_USERNAME-islamic-ai.hf.space`

- يفتح المستخدم الرابط من أي جوال (iPhone أو Android).
- يضغط على القائمة ثم: **"إضافة إلى الشاشة الرئيسية" (Add to Home Screen)**.
- يصبح التطبيق مثبتاً بأيقونته كبرنامج مستقل فائق السرعة!
