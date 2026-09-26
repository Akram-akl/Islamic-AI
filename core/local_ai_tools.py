"""
core/local_ai_tools.py
أدوات الذكاء الاصطناعي المحلية مع استيراد آمن وديناميكي
"""
import sys
import importlib

class IslamicAITools:
    def __init__(self):
        self.stt_model = None
        self.translator = None

    def load_stt(self):
        """تحميل نموذج تحويل الصوت إلى نص عند الحاجة فقط"""
        try:
            faster_whisper = importlib.import_module("faster_whisper")
            WhisperModel = getattr(faster_whisper, "WhisperModel")
            print("جاري تحميل نموذج تحويل الصوت إلى نص...")
            self.stt_model = WhisperModel("small", device="cpu", compute_type="int8")
        except ImportError:
            print("تنبيه: مكتبة faster-whisper غير مثبتة. لتثبيتها: pip install faster-whisper")

    def load_translator(self):
        """تحميل نموذج الترجمة عند الحاجة فقط"""
        try:
            transformers = importlib.import_module("transformers")
            pipeline = getattr(transformers, "pipeline")
            print("جاري تحميل نموذج الترجمة...")
            self.translator = pipeline("translation", model="Helsinki-NLP/opus-mt-ar-en")
        except ImportError:
            print("تنبيه: مكتبة transformers غير مثبتة. لتثبيتها: pip install transformers")

    def transcribe_audio(self, audio_file_path: str):
        """تحويل البودكاست (ملف صوتي) إلى نص"""
        if not self.stt_model:
            self.load_stt()
        if not self.stt_model:
            return "مكتبة faster-whisper غير متوفرة في بيئة بايثون الحالية."
            
        print(f"جاري تفريغ الملف: {audio_file_path}")
        segments, _ = self.stt_model.transcribe(audio_file_path, beam_size=5, language="ar")
        full_text = " ".join(seg.text for seg in segments)
        return full_text.strip()

    def translate_arabic_text(self, text: str) -> str:
        """ترجمة النص العربي إلى الإنجليزية"""
        if not self.translator:
            self.load_translator()
        if not self.translator:
            return "مكتبة transformers غير متوفرة في بيئة بايثون الحالية."
        result = self.translator(text)
        return result[0]['translation_text']

    async def text_to_speech(self, text: str, output_file: str):
        """تحويل النص إلى صوت (مجاني وبلا حدود عبر Edge TTS)"""
        try:
            edge_tts = importlib.import_module("edge_tts")
            Communicate = getattr(edge_tts, "Communicate")
            voice = "ar-SA-HamedNeural"
            communicate = Communicate(text, voice)
            await communicate.save(output_file)
            print(f"تم حفظ الملف الصوتي بنجاح: {output_file}")
        except ImportError:
            print("تنبيه: مكتبة edge-tts غير مثبتة. لتثبيتها: pip install edge-tts")
