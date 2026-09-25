"""سكريبت تحديث قاعدة البيانات"""
import sys
sys.path.insert(0, '.')
from core.db import get_conn, init_db

# أولاً: إعادة تهيئة لإنشاء الجداول الجديدة
print("جار تحديث قاعدة البيانات...")
init_db()

conn = get_conn()
try:
    # إضافة الأعمدة الجديدة إذا لم تكن موجودة
    for col, col_type in [
        ("question_text", "TEXT NOT NULL DEFAULT ''"),
        ("answer",        "TEXT NOT NULL DEFAULT ''"),
        ("updated_at",    "TEXT NOT NULL DEFAULT (datetime('now'))"),
    ]:
        try:
            conn.execute(f"ALTER TABLE answer_cache ADD COLUMN {col} {col_type}")
            print(f"  ✅ Added column: {col}")
        except Exception as e:
            print(f"  ⚠️ {col}: {e}")

    conn.commit()

    # فحص البنية النهائية
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    print(f"\nالجداول: {[t[0] for t in tables]}")

    cols = conn.execute("PRAGMA table_info(answer_cache)").fetchall()
    print(f"أعمدة answer_cache: {[c[1] for c in cols]}")

    # عدد الإجابات المخزنة
    count = conn.execute("SELECT COUNT(*) FROM answer_cache").fetchone()[0]
    print(f"الإجابات المخزنة في الكاش: {count}")

    print("\n✅ قاعدة البيانات جاهزة!")
except Exception as e:
    print(f"❌ خطأ: {e}")
finally:
    conn.close()
