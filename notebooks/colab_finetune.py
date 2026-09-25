# noqa: F401
# ╔══════════════════════════════════════════════════════════════════╗
# ║         Islamic-AI — Colab Fine-Tuning Script                   ║
# ║  هذا الملف يعمل فقط داخل Google Colab (ليس على جهازك المحلي)   ║
# ║  أخطاء IDE طبيعية — المكتبات تُثبَّت داخل Colab تلقائياً        ║
# ╚══════════════════════════════════════════════════════════════════╝
# type: ignore  ← يُسكت تحذيرات IDE (torch/datasets/peft غير مثبتة محلياً)

# ════════════════════════════════════════════════════════════════════
# 📦 CELL 1 — تثبيت المكتبات (انسخ هذا في أول خلية في Colab)
# ════════════════════════════════════════════════════════════════════
"""
!pip install -q \
    transformers==4.46.3 \
    datasets==3.1.0 \
    peft==0.13.2 \
    accelerate==1.1.1 \
    bitsandbytes==0.45.0 \
    trl==0.12.1 \
    huggingface_hub \
    sentencepiece \
    protobuf
"""

# ════════════════════════════════════════════════════════════════════
# 🔑 CELL 2 — تسجيل الدخول لـ Hugging Face
# ════════════════════════════════════════════════════════════════════
"""
from huggingface_hub import login
login()  # سيطلب منك لصق التوكن
"""

# ════════════════════════════════════════════════════════════════════
# ⬆️ CELL 3 — رفع ملفات التدريب
# ════════════════════════════════════════════════════════════════════
"""
from google.colab import files
uploaded = files.upload()
# ارفع: train.jsonl و eval.jsonl من مجلد data/ في جهازك
"""

# ════════════════════════════════════════════════════════════════════
# 🚀 CELL 4 — التدريب الكامل (انسخ كل ما يلي في خلية واحدة)
# ════════════════════════════════════════════════════════════════════

import os          # type: ignore[import]
import json        # type: ignore[import]
import torch       # type: ignore[import]
from datasets import Dataset                                    # type: ignore[import]
from transformers import (                                      # type: ignore[import]
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
)
from peft import LoraConfig, get_peft_model, TaskType          # type: ignore[import]
from trl import SFTTrainer, SFTConfig                          # type: ignore[import]

# ─────────────────────────────────────────────────────────────
# ⚙️ الإعدادات — غيّر هذه القيم فقط
# ─────────────────────────────────────────────────────────────
MODEL_NAME  = "Qwen/Qwen2.5-1.5B-Instruct"   # النموذج الأساسي
HF_REPO_ID  = "akramakl/islamic-ai"       # ✅ تم إعداده
OUTPUT_DIR  = "./islamic-ai-model"

TRAIN_FILE  = "train.jsonl"
EVAL_FILE   = "eval.jsonl"

# ─────────────────────────────────────────────────────────────
# ⚙️ إعدادات الجودة القصوى — r=64 (10%) في ~7 ساعات
# ─────────────────────────────────────────────────────────────
MAX_TRAIN_SAMPLES = None   # كل الأمثلة (11,449)
NUM_EPOCHS        = 3      # 3 epochs = أفضل جودة
BATCH_SIZE        = 2      # آمن لـ T4 (15GB VRAM)
GRAD_ACCUM        = 4      # batch فعلي = 2×4 = 8
MAX_SEQ_LEN       = 1024   # نصوص طويلة كاملة



# ─────────────────────────────────────────────────────────────
# 1. تحميل البيانات
# ─────────────────────────────────────────────────────────────
def load_jsonl(path: str, limit: int = None) -> Dataset:
    with open(path, encoding="utf-8") as f:
        data = [json.loads(line) for line in f if line.strip()]
    if limit:
        # اختيار ذكي: توزيع متوازن على الأنواع الثلاثة
        islamic  = [d for d in data if "سورة" in str(d) or "حديث" in str(d)][:int(limit*0.7)]
        general  = [d for d in data if "كيف حالك" in str(d) or "Hello" in str(d)][:int(limit*0.1)]
        advisory = [d for d in data if "خطة" in str(d) or "plan" in str(d)][:int(limit*0.1)]
        rest     = [d for d in data if d not in islamic+general+advisory][:int(limit*0.1)]
        data     = islamic + general + advisory + rest
    import random; random.shuffle(data)
    return Dataset.from_list(data)


def format_chatml(example: dict) -> dict:
    msgs = example["messages"]
    text = ""
    for msg in msgs:
        text += f"<|im_start|>{msg['role']}\n{msg['content']}<|im_end|>\n"
    return {"text": text}


print("📚 تحميل بيانات التدريب...")
train_ds = load_jsonl(TRAIN_FILE, MAX_TRAIN_SAMPLES).map(format_chatml)
eval_ds  = load_jsonl(EVAL_FILE,  500).map(format_chatml)
print(f"  ✅ تدريب: {len(train_ds):,} | تقييم: {len(eval_ds):,}")
print(f"  ⏱️  الوقت المتوقع: ~{int(len(train_ds)/5000*3.5)} ساعات")


# ─────────────────────────────────────────────────────────────
# 2. إعداد 4-bit Quantization
# ─────────────────────────────────────────────────────────────
print("\n🔧 إعداد 4-bit QLoRA...")
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_use_double_quant=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16,
)

tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)
tokenizer.pad_token = tokenizer.eos_token
tokenizer.padding_side = "right"

model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME,
    quantization_config=bnb_config,
    device_map="auto",
    trust_remote_code=True,
    torch_dtype=torch.bfloat16,
)
model.config.use_cache = False
print(f"  ✅ النموذج محمّل: {MODEL_NAME}")


# ─────────────────────────────────────────────────────────────
# 3. LoRA — r=64 (~10%)
# ─────────────────────────────────────────────────────────────
lora_config = LoraConfig(
    r=64,           # 10% من المعاملات
    lora_alpha=128, # دائماً = r × 2
    target_modules=[
        "q_proj", "k_proj", "v_proj", "o_proj",   # Attention
        "gate_proj", "up_proj", "down_proj",        # MLP
    ],
    lora_dropout=0.05,
    bias="none",
    task_type=TaskType.CAUSAL_LM,
)
model = get_peft_model(model, lora_config)
model.print_trainable_parameters()


# ─────────────────────────────────────────────────────────────
# 4. إعدادات التدريب
# ─────────────────────────────────────────────────────────────
training_args = SFTConfig(
    output_dir=OUTPUT_DIR,
    num_train_epochs=NUM_EPOCHS,
    per_device_train_batch_size=BATCH_SIZE,
    per_device_eval_batch_size=2,
    gradient_accumulation_steps=GRAD_ACCUM,
    learning_rate=2e-4,
    lr_scheduler_type="cosine",
    warmup_ratio=0.05,
    logging_steps=25,
    eval_strategy="steps",
    eval_steps=100,
    save_steps=200,
    save_total_limit=1,
    load_best_model_at_end=True,
    bf16=True,
    fp16=False,
    max_seq_length=MAX_SEQ_LEN,
    dataset_text_field="text",
    report_to="none",
    push_to_hub=True,
    hub_model_id=HF_REPO_ID,
    hub_strategy="end",          # يرفع فقط في النهاية (أسرع)
    dataloader_num_workers=2,
    group_by_length=True,        # يجمّع النصوص المتشابهة الطول (أسرع 20%)
    optim="paged_adamw_8bit",   # optimizer مُحسَّن للذاكرة
)


# ─────────────────────────────────────────────────────────────
# 5. بدء التدريب
# ─────────────────────────────────────────────────────────────
print(f"\n🚀 بدء التدريب...")
print(f"   النموذج: {MODEL_NAME}")
print(f"   r=64 (10%) | {NUM_EPOCHS} epochs | {len(train_ds)} مثال")
print(f"   الوقت المتوقع: ~3-4 ساعات على T4\n")

trainer = SFTTrainer(
    model=model,
    args=training_args,
    train_dataset=train_ds,
    eval_dataset=eval_ds,
    tokenizer=tokenizer,
)

trainer.train()
print("✅ التدريب اكتمل!")


# ─────────────────────────────────────────────────────────────
# 6. رفع النموذج على Hugging Face
# ─────────────────────────────────────────────────────────────
print(f"\n📤 رفع النموذج: {HF_REPO_ID}")
trainer.push_to_hub()
tokenizer.push_to_hub(HF_REPO_ID)
print(f"✅ النموذج منشور: https://huggingface.co/{HF_REPO_ID}")


# ════════════════════════════════════════════════════════════════════
# 📱 CELL 5 (اختياري) — تحويل لـ GGUF للعمل بلا نت على الجوال
# ════════════════════════════════════════════════════════════════════
"""
# دمج LoRA weights مع النموذج الأصلي
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

print("دمج LoRA...")
base = AutoModelForCausalLM.from_pretrained(MODEL_NAME, torch_dtype=torch.float16)
peft_model = PeftModel.from_pretrained(base, OUTPUT_DIR)
merged = peft_model.merge_and_unload()
merged.save_pretrained("./merged_model")
AutoTokenizer.from_pretrained(MODEL_NAME).save_pretrained("./merged_model")
print("✅ دمج اكتمل")

# تحويل لـ GGUF (حجم ≈ 900MB)
!git clone https://github.com/ggerganov/llama.cpp --depth=1
!pip install -q -r llama.cpp/requirements.txt
!python llama.cpp/convert_hf_to_gguf.py ./merged_model \
    --outtype q4_K_M \
    --outfile islamic_ai_q4.gguf

# تحميل الملف لجهازك
from google.colab import files
files.download("islamic_ai_q4.gguf")
print("✅ ملف GGUF جاهز للتحميل! (حجمه ≈ 900MB)")
"""
