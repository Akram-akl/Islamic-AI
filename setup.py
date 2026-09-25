"""
setup.py — سكريبت الإعداد الشامل
يحمّل البيانات ويبني قاعدة البيانات بأمر واحد
"""
import os
import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))


def check_env():
    env_file = ROOT / ".env"
    if not env_file.exists():
        print("⚠️  ملف .env غير موجود — سأنشئه لك...")
        with open(env_file, "w") as f:
            f.write("# مفاتيح API — أضف مفتاحاً واحداً على الأقل\n")
            f.write("GEMINI_API_KEY=\n")
            f.write("GROQ_API_KEY=\n")
        print("📝 تم إنشاء ملف .env — أضف مفتاح Gemini أو Groq")
    else:
        from dotenv import load_dotenv
        load_dotenv(env_file)
        gemini = os.getenv("GEMINI_API_KEY", "")
        groq   = os.getenv("GROQ_API_KEY", "")
        if not gemini and not groq:
            print("⚠️  لم يُضف أي مفتاح API في ملف .env")
            print("   • مفتاح Gemini مجاني: https://aistudio.google.com/app/apikey")
            print("   • مفتاح Groq مجاني:   https://console.groq.com/keys")
        else:
            providers = []
            if gemini: providers.append("Gemini ✅")
            if groq:   providers.append("Groq ✅")
            print(f"  ✅ مزودو الذكاء الاصطناعي: {', '.join(providers)}")


def download_data():
    print("\n📥 تحميل الملفات الإسلامية...")
    result = subprocess.run(
        [sys.executable, "data/download_all.py"],
        cwd=str(ROOT)
    )
    return result.returncode == 0


def build_db():
    print("\n🏗️  بناء قاعدة البيانات...")
    from core.db import build_database
    build_database()
    try:
        from data.populate_knowledge_base import populate
        populate()
    except Exception as e:
        print(f"  ⚠️ خطأ في تغذية الموسوعة: {e}")



def main():
    print("=" * 60)
    print("  Islamic-AI — إعداد المشروع الكامل")
    print("=" * 60)

    check_env()

    if "--skip-download" not in sys.argv:
        ok = download_data()
        if not ok:
            print("⚠️  فشل تحميل بعض الملفات، سنكمل البناء بما تم تحميله")

    build_db()

    print("\n" + "=" * 60)
    print("  🎉 الإعداد اكتمل! لتشغيل الخادم:")
    print("     python -m uvicorn api.main:app --host 0.0.0.0 --port 8000")
    print("  ثم افتح: http://localhost:8000")
    print("=" * 60)


if __name__ == "__main__":
    main()
