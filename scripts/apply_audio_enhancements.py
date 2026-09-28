# -*- coding: utf-8 -*-
import sys

with open('app/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update updateMaxAyah to also render the ayah
old_update_max = """function updateMaxAyah() {
  const surahId = parseInt(document.getElementById('quran-surah-picker').value);
  const surah = SURAHS.find(s => s.id === surahId);
  const ayahInput = document.getElementById('quran-ayah-picker');
  if (surah && ayahInput) {
    ayahInput.max = surah.ayahs;
    if (parseInt(ayahInput.value) > surah.ayahs) ayahInput.value = 1;
  }
}"""

new_update_max = """function updateMaxAyah() {
  const surahId = parseInt(document.getElementById('quran-surah-picker').value);
  const surah = SURAHS.find(s => s.id === surahId);
  const ayahInput = document.getElementById('quran-ayah-picker');
  if (surah && ayahInput) {
    ayahInput.max = surah.ayahs;
    if (parseInt(ayahInput.value) > surah.ayahs) ayahInput.value = 1;
  }
  if (typeof renderAudioAyahBox === 'function') {
    renderAudioAyahBox();
  }
}"""

# 2. Replacement for playSelectedAyah and audio interactive functions
audio_js_block = """// ─── 6. تشغيل تلاوات المشايخ القرآنية حصراً بالقراءات العشر والعلوم التفاعلية ───
let currentQuranAudioUrl = '';
const mainQuranAudio = document.getElementById('main-quran-audio');

// ذاكرة كاش لبيانات الروايات لتسريع التصفح والاستماع
const quranRiwayaDataCache = {};

async function getRiwayaData(riwayaKey) {
  if (quranRiwayaDataCache[riwayaKey]) return quranRiwayaDataCache[riwayaKey];
  const config = (typeof RIWAYA_CONFIG !== 'undefined' && RIWAYA_CONFIG[riwayaKey]) 
    ? RIWAYA_CONFIG[riwayaKey] 
    : { file: 'quran_data/hafsData_v2-0.json' };
  try {
    const res = await fetch(config.file);
    if (res.ok) {
      const data = await res.json();
      quranRiwayaDataCache[riwayaKey] = data;
      return data;
    }
  } catch (e) {
    console.warn('تعذر تحميل ملف الرواية محلياً:', config.file, e);
  }
  return null;
}

function extractAyahTextFromData(data, surahNum, ayahNum) {
  if (!data) return null;
  if (Array.isArray(data)) {
    const found = data.find(a => (a.sura === surahNum || a.sura_number === surahNum) && (a.aya === ayahNum || a.aya_number === ayahNum));
    if (found) {
      if (found.words && Array.isArray(found.words)) {
        return found.words.map(w => w.text || w.word || w).join(' ');
      }
      return found.text || found.aya_text || found.content || found.ayah_text_ar;
    }
  } else if (data.suras && Array.isArray(data.suras)) {
    const s = data.suras.find(s => s.number === surahNum || s.sura === surahNum);
    if (s && s.ayas) {
      const a = s.ayas.find(a => a.number === ayahNum || a.aya === ayahNum);
      if (a) return a.text;
    }
  }
  return null;
}

function detectRiwayaFromReciter() {
  const selectEl = document.getElementById('sheikh-reciter-select');
  if (!selectEl) return 'hafs';
  const opt = selectEl.selectedOptions[0];
  const txt = ((opt ? opt.text : '') + ' ' + (opt ? opt.value : '')).toLowerCase();
  
  if (txt.includes('warsh') || txt.includes('ورش')) return 'warsh';
  if (txt.includes('qalon') || txt.includes('qaloun') || txt.includes('قالون')) return 'qaloun';
  if (txt.includes('aldori') || txt.includes('douri') || txt.includes('الدوري')) return 'douri';
  if (txt.includes('assosi') || txt.includes('sousi') || txt.includes('السوسي')) return 'sousi';
  if (txt.includes('sho-bah') || txt.includes('shuba') || txt.includes('شعبة')) return 'shuba';
  return 'hafs';
}

async function renderAudioAyahBox() {
  const surahPicker = document.getElementById('quran-surah-picker');
  const ayahPicker = document.getElementById('quran-ayah-picker');
  if (!surahPicker || !ayahPicker) return;

  const surahId = parseInt(surahPicker.value) || 1;
  const ayahId = parseInt(ayahPicker.value) || 1;

  const surahObj = (typeof SURAHS !== 'undefined') ? SURAHS.find(s => s.id === surahId) : null;
  const surahName = surahObj ? surahObj.name : `السورة ${surahId}`;

  const riwayaKey = detectRiwayaFromReciter();
  const riwayaConfig = (typeof RIWAYA_CONFIG !== 'undefined' && RIWAYA_CONFIG[riwayaKey]) 
    ? RIWAYA_CONFIG[riwayaKey] 
    : { font: 'UthmanicHafs', name: 'حفص عن عاصم', color: '#2D9E68' };

  const infoBadge = document.getElementById('audio-ayah-info-badge');
  if (infoBadge) {
    infoBadge.textContent = `📖 سورة ${surahName} — الآية ${ayahId}`;
  }

  const riwayaBadge = document.getElementById('audio-riwaya-badge');
  if (riwayaBadge) {
    riwayaBadge.textContent = riwayaConfig.name;
    riwayaBadge.style.borderColor = riwayaConfig.color;
    riwayaBadge.style.color = riwayaConfig.color;
    riwayaBadge.style.background = riwayaConfig.color + '22';
  }

  const displayEl = document.getElementById('audio-ayah-text-display');
  if (!displayEl) return;
  displayEl.style.fontFamily = `'${riwayaConfig.font}', 'Amiri', serif`;

  // محاولة جلب نص الآية برواية القارئ
  let text = null;
  const riwayaData = await getRiwayaData(riwayaKey);
  if (riwayaData) {
    text = extractAyahTextFromData(riwayaData, surahId, ayahId);
  }

  // في حال لم تتوفر الرواية بعد نستخدم نص القرآن العام المتاح
  if (!text) {
    const qData = await getQuranData();
    const found = qData.find(item => item.surah_number === surahId && item.ayah_number === ayahId);
    if (found) text = found.ayah_text_ar;
  }

  if (text) {
    const words = text.trim().split(/\\s+/);
    displayEl.innerHTML = words.map((w, idx) => {
      const num = idx + 1;
      return `<span class="audio-word-span" data-word-num="${num}" onclick="audioSelectWord(this, ${surahId}, ${ayahId}, ${num})" title="اضغط لعرض علوم وغريب وإعراب الكلمة">${w}</span>`;
    }).join(' ') + ` <span style="font-family:'Amiri',serif; color:var(--gold); font-size:22px; cursor:default">۝${ayahId}</span>`;
  } else {
    displayEl.innerHTML = `<span style="font-size:16px; color:var(--text-muted);">جارٍ تحميل نص الآية الكريمة...</span>`;
  }
}

let audioSelectedWordNum = 1;

function audioSelectWord(el, sura, aya, wordNum) {
  document.querySelectorAll('.audio-word-span').forEach(s => s.classList.remove('selected'));
  el.classList.add('selected');
  audioSelectedWordNum = wordNum;
  
  const wordText = el.textContent.trim().replace(/[۝۞]/g, '').trim();
  const wordSelectedEl = document.getElementById('audio-word-selected');
  if (wordSelectedEl) wordSelectedEl.textContent = wordText;
  
  const wordPanel = document.getElementById('audio-word-panel');
  if (wordPanel) wordPanel.style.display = 'block';
  
  // تفعيل تبويب معنى الكلمة تلقائياً وجلبه فوراً
  const firstTab = document.querySelector('#audio-word-tabs .audio-tab-btn');
  audioFetchWord('meaning-word', firstTab);
}

async function audioFetchWord(slug, btn) {
  document.querySelectorAll('#audio-word-tabs .audio-tab-btn').forEach(t => t.classList.remove('active'));
  if (btn) btn.classList.add('active');

  const sura = parseInt(document.getElementById('quran-surah-picker').value) || 1;
  const aya = parseInt(document.getElementById('quran-ayah-picker').value) || 1;
  const word = audioSelectedWordNum;

  const loadEl = document.getElementById('audio-word-loading');
  const contentEl = document.getElementById('audio-word-content');
  if (loadEl) loadEl.style.display = 'block';
  if (contentEl) contentEl.innerHTML = '';

  try {
    const url = (slug === 'word-pic')
      ? `https://dev.surahapp.com/api/v1/word/word-pic/${sura}/${aya}/${word}`
      : `https://dev.surahapp.com/api/v1/word/${slug}/${sura}/${aya}/${word}`;
    
    const resp = await fetch(url);
    if (resp.status === 404) {
      if (contentEl) contentEl.innerHTML = '<span style="color:var(--text-muted)">لا تتوفر بيانات لهذه الكلمة في هذا القسم.</span>';
      return;
    }
    if (!resp.ok) throw new Error('server error');
    const data = await resp.json();

    if (slug === 'word-pic' && data.media && data.media.length > 0) {
      if (contentEl) contentEl.innerHTML = `<img src="${data.media[0].large_url}" style="max-width:100%; border-radius:10px; margin:6px 0;">`;
    } else {
      const text = Array.isArray(data)
        ? data.map(d => d.content || '').join('<br>')
        : (data.content || data.text || 'لا يوجد محتوى.');
      if (contentEl) contentEl.innerHTML = text.replace(/\\n/g, '<br>');
    }
  } catch (err) {
    if (contentEl) contentEl.innerHTML = '<span style="color:var(--text-muted)">تعذر جلب البيانات (تحقق من الاتصال بالإنترنت).</span>';
  } finally {
    if (loadEl) loadEl.style.display = 'none';
  }
}

async function audioFetchAya(slug, btn) {
  document.querySelectorAll('#audio-aya-tabs .audio-tab-btn').forEach(t => t.classList.remove('active'));
  if (btn) btn.classList.add('active');

  const sura = parseInt(document.getElementById('quran-surah-picker').value) || 1;
  const aya = parseInt(document.getElementById('quran-ayah-picker').value) || 1;

  const loadEl = document.getElementById('audio-aya-loading');
  const contentEl = document.getElementById('audio-aya-content');
  if (loadEl) loadEl.style.display = 'block';
  if (contentEl) contentEl.innerHTML = '';

  try {
    const url = `https://dev.surahapp.com/api/v1/aya/${slug}/${sura}/${aya}`;
    const resp = await fetch(url);
    if (resp.status === 404) {
      if (contentEl) contentEl.innerHTML = '<span style="color:var(--text-muted)">لا توجد بيانات لهذه الآية في هذا التبويب.</span>';
      return;
    }
    if (!resp.ok) throw new Error('server error');
    const data = await resp.json();

    const text = Array.isArray(data)
      ? data.map(d => d.content || '').join('<hr style="border-color:rgba(255,255,255,0.1); margin:10px 0">')
      : (data.content || data.text || 'لا يوجد محتوى.');
    if (contentEl) contentEl.innerHTML = text.replace(/\\n/g, '<br>');
  } catch (err) {
    if (contentEl) contentEl.innerHTML = '<span style="color:var(--text-muted)">تعذر جلب التفسير من موسوعة سورة (تحقق من الاتصال).</span>';
  } finally {
    if (loadEl) loadEl.style.display = 'none';
  }
}

function audioNextAyah() {
  const surahId = parseInt(document.getElementById('quran-surah-picker').value) || 1;
  const ayahInput = document.getElementById('quran-ayah-picker');
  const currentAyah = parseInt(ayahInput.value) || 1;
  const surah = (typeof SURAHS !== 'undefined') ? SURAHS.find(s => s.id === surahId) : null;
  const maxAyah = surah ? surah.ayahs : 286;

  if (currentAyah < maxAyah) {
    ayahInput.value = currentAyah + 1;
  } else if (surahId < 114) {
    document.getElementById('quran-surah-picker').value = surahId + 1;
    updateMaxAyah();
    ayahInput.value = 1;
  }
  renderAudioAyahBox();
  const mainAudio = document.getElementById('main-quran-audio');
  if (mainAudio && !mainAudio.paused && mainAudio.currentTime > 0) {
    playSelectedAyah();
  }
}

function audioPrevAyah() {
  const surahId = parseInt(document.getElementById('quran-surah-picker').value) || 1;
  const ayahInput = document.getElementById('quran-ayah-picker');
  const currentAyah = parseInt(ayahInput.value) || 1;

  if (currentAyah > 1) {
    ayahInput.value = currentAyah - 1;
  } else if (surahId > 1) {
    document.getElementById('quran-surah-picker').value = surahId - 1;
    updateMaxAyah();
    const prevSurah = (typeof SURAHS !== 'undefined') ? SURAHS.find(s => s.id === surahId - 1) : null;
    ayahInput.value = prevSurah ? prevSurah.ayahs : 1;
  }
  renderAudioAyahBox();
  const mainAudio = document.getElementById('main-quran-audio');
  if (mainAudio && !mainAudio.paused && mainAudio.currentTime > 0) {
    playSelectedAyah();
  }
}

function audioJumpToEncyclopedia() {
  const sura = parseInt(document.getElementById('quran-surah-picker').value) || 1;
  const aya = parseInt(document.getElementById('quran-ayah-picker').value) || 1;
  switchTab('quran-enc');
  const encSura = document.getElementById('enc-sura');
  if (encSura) {
    encSura.value = sura;
    if (typeof encLoadAyas === 'function') encLoadAyas();
    const encAya = document.getElementById('enc-aya');
    if (encAya) {
      encAya.value = aya;
      if (typeof encRenderAya === 'function') encRenderAya();
    }
  }
}

async function playSelectedAyah() {
  const surah = parseInt(document.getElementById('quran-surah-picker').value);
  const ayah = parseInt(document.getElementById('quran-ayah-picker').value);
  const selectEl = document.getElementById('sheikh-reciter-select');
  const selectedOption = selectEl.selectedOptions[0];
  const reciterVal = selectedOption.value;
  const playType = selectedOption.getAttribute('data-type') || 'ayah';

  stopSpeech();

  const sStr = String(surah).padStart(3, '0');
  const aStr = String(ayah).padStart(3, '0');

  if (playType === 'ayah') {
    currentQuranAudioUrl = `https://everyayah.com/data/${reciterVal}/${sStr}${aStr}.mp3`;
  } else {
    currentQuranAudioUrl = `${reciterVal}${sStr}.mp3`;
  }

  mainQuranAudio.src = currentQuranAudioUrl;
  mainQuranAudio.style.display = 'block';
  mainQuranAudio.play().catch(e => {
    showToast('تعذر تشغيل التسجيل الصوتي، جرب رواية أو شيخاً آخر', 'error');
  });

  // انتقال تلقائي للآية التالية عند نهاية التلاوة
  mainQuranAudio.onended = function() {
    if (playType === 'ayah') {
      audioNextAyah();
    }
  };

  const sObj = (typeof SURAHS !== 'undefined') ? SURAHS.find(s => s.id === surah) : null;
  const sName = sObj ? sObj.name : surah;
  showGlobalAudioBar(`سورة ${sName} — ${selectedOption.text}`, playType === 'ayah' ? `آية ${ayah}` : 'تلاوة سورة كاملة مباركة');

  // تحديث الصندوق التفاعلي للآية والكلمات والتفسير
  renderAudioAyahBox();
}"""

# Execute replacements with CRLF normalization
content_normalized = content.replace('\r\n', '\n')

if old_update_max.replace('\r\n', '\n') in content_normalized:
    content_normalized = content_normalized.replace(old_update_max.replace('\r\n', '\n'), new_update_max.replace('\r\n', '\n'))
    print("Updated updateMaxAyah successfully!")
else:
    print("Warning: old_update_max not found directly")

# Locate playSelectedAyah block
target_start = "// ─── 6. تشغيل تلاوات المشايخ القرآنية حصراً بالقراءات العشر ───"
target_end = "function playAyahReciter(surah, ayah, btn) {"

if target_start in content_normalized and target_end in content_normalized:
    idx1 = content_normalized.find(target_start)
    idx2 = content_normalized.find(target_end)
    content_normalized = content_normalized[:idx1] + audio_js_block + "\n\n" + content_normalized[idx2:]
    print("Updated audio_js_block successfully!")
else:
    print(f"Warning: target_start in content: {target_start in content_normalized}, target_end in content: {target_end in content_normalized}")

# Also add initial call to renderAudioAyahBox() when page loads
init_call = "\n  setTimeout(() => { if (typeof renderAudioAyahBox === 'function') renderAudioAyahBox(); }, 400);\n"
if "encInit();" in content_normalized and init_call not in content_normalized:
    content_normalized = content_normalized.replace("encInit();", "encInit();" + init_call)
    print("Added renderAudioAyahBox initialization!")

# Write back with original or standard CRLF
with open('app/index.html', 'w', encoding='utf-8', newline='\r\n') as f:
    f.write(content_normalized)

print("Done updating app/index.html!")
