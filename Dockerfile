FROM python:3.11-slim

# إنشاء مستخدم عادي بصلاحيات UID 1000 المعتمدة في Hugging Face Spaces
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1

WORKDIR $HOME/app

# تثبيت المتطلبات أولاً للاستفادة من كاش Docker
COPY --chown=user requirements.txt $HOME/app/requirements.txt
RUN pip install --no-cache-dir --user -r $HOME/app/requirements.txt

# نسخ كامل ملفات المشروع
COPY --chown=user . $HOME/app

# بناء قاعدة البيانات والكتب الإسلامية
RUN python setup.py --skip-download || true

# المنفذ الافتراضي لـ Hugging Face Spaces
EXPOSE 7860

# تشغيل خادم Uvicorn
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "7860"]
