import { PhononTTS, encodeWav } from 'phonon-tts';
import VOICES from './voices.json';

// The voice catalogue lives in gradium/phonon-voices (Apache-2.0), separate from the model.
// Voices are addressed as `voices/<id>.safetensors` in that repo.
const VOICE_REPO = 'gradium/phonon-voices';
const VOICE_REV = 'main';

const MODEL = 'hf://gradium/phonon-31m-en';

const $ = (id) => document.getElementById(id);
const TEXT = $('text'), VOICE = $('voice'), VDESC = $('vdesc');
const TEMP = $('temp'), TEMPV = $('tempv'), SPEED = $('speed'), SEED = $('seed');
const GO = $('go'), STATUS = $('status'), BAR = $('bar'), BARF = BAR.firstElementChild;
const PLAYER = $('player'), POST = $('post'), META = $('meta');
const COUNT = $('count'), EST = $('est'), DLG = $('firstRun');

let tts = null;
let lastBlob = null;
let lastName = 'phonon';

// ── voices ───────────────────────────────────────────────────────────────────
const GROUPS = [
  { key: 'female', label: 'Female' },
  { key: 'male', label: 'Male' },
  { key: 'character', label: 'Character voices' },
];
for (const g of GROUPS) {
  const list = VOICES.filter((v) => v.gender === g.key);
  if (!list.length) continue;
  const og = document.createElement('optgroup');
  og.label = g.label;
  for (const v of list) {
    const o = document.createElement('option');
    o.value = v.id;
    const where = v.gender === 'character' ? '' : v.locale === 'en-gb' ? ' · UK' : ' · US';
    o.textContent = v.name + where;
    og.appendChild(o);
  }
  VOICE.appendChild(og);
}
// default to Edwin (a UK male) if present, else the first voice
VOICE.value = VOICES.find((v) => v.name === 'Edwin')?.id || VOICES[0].id;

// Descriptions are not in the repo README we mirrored, so show locale/character instead.
function describe() {
  const v = VOICES.find((x) => x.id === VOICE.value);
  if (!v) { VDESC.textContent = ''; return; }
  if (v.gender === 'character') {
    VDESC.textContent = `${v.name} — a designed character voice. Distinctive and strong; good for a character, not for a neutral read.`;
  } else {
    const accent = v.locale === 'en-gb' ? 'British' : 'American';
    VDESC.textContent = `${v.name} — a ${accent} ${v.gender} voice from the Phonon catalogue.`;
  }
}
VOICE.addEventListener('change', describe);
describe();

// ── counts ───────────────────────────────────────────────────────────────────
const WORDS_PER_SEC = 2.6;
function updateCounts() {
  const t = TEXT.value;
  COUNT.textContent = t.length.toLocaleString();
  const words = t.trim() ? t.trim().split(/\s+/).length : 0;
  EST.textContent = '~' + Math.round(words / WORDS_PER_SEC) + 's';
}
TEXT.addEventListener('input', updateCounts);
updateCounts();

TEMP.addEventListener('input', () => { TEMPV.textContent = Number(TEMP.value).toFixed(2); });

// ── samples ──────────────────────────────────────────────────────────────────
const SAMPLES = {
  intro: 'Hello. This is Phonon, reading your words on your own machine. No account, no upload, no bill — just text turning into a voice you can hear.',
  advert: 'Meet the board that turns a flat evening into an hour on the water. Light enough to carry under one arm. Quiet enough to hear the sea. And sealed properly, so the only thing that gets wet is you.',
  narration: 'The kitchen opens at six. By seven, the smell of bread has reached the end of the street, and someone always stops to ask what time it is. It is always the same answer.',
  explainer: 'There are three things that decide how a sentence sounds. The voice you choose. How much variation you allow it. And, more than either, the way the sentence is written. Short sentences land harder. Longer ones let the thought travel.',
};
document.querySelectorAll('.chip').forEach((chip) => {
  chip.addEventListener('click', () => {
    const k = chip.dataset.sample;
    TEXT.value = k === 'clear' ? '' : (SAMPLES[k] || '');
    updateCounts();
    TEXT.focus();
  });
});

// ── model loading ────────────────────────────────────────────────────────────
async function loadModel() {
  STATUS.textContent = 'Loading the model…';
  BAR.style.display = 'block';
  const seen = new Map();

  tts = await PhononTTS.load({
    lang: 'en',
    model: MODEL,
    // Pre-fetch only the default; other voices load on first use.
    voices: [],
    device: 'auto',
    cache: true,
    onProgress: (p) => {
      seen.set(p.file, p);
      let loaded = 0, total = 0;
      for (const v of seen.values()) {
        loaded += v.loaded || 0;
        total += v.total || 0;
      }
      const pct = total ? Math.min(100, (loaded / total) * 100) : 0;
      BARF.style.width = pct.toFixed(1) + '%';
      if (p.cached) {
        STATUS.textContent = 'Loading from cache…';
      } else if (p.total) {
        STATUS.textContent = `Downloading ${p.file} — ${(loaded / 1048576).toFixed(0)} of ${(total / 1048576).toFixed(0)} MB`;
      } else {
        STATUS.textContent = `Downloading ${p.file}…`;
      }
    },
  });

  BARF.style.width = '100%';
  setTimeout(() => { BAR.style.display = 'none'; }, 400);
  STATUS.textContent = `Ready · ${tts.device.toUpperCase()} · ${tts.threads} thread${tts.threads > 1 ? 's' : ''}`;
  GO.disabled = false;
}

// ── generate ─────────────────────────────────────────────────────────────────
async function generate() {
  const text = TEXT.value.trim();
  if (!text) { STATUS.textContent = 'Type something first.'; return; }
  if (!tts) { STATUS.textContent = 'The model is still loading.'; return; }

  GO.disabled = true;
  STATUS.className = 'status';
  STATUS.textContent = 'Adding the voice…';
  PLAYER.style.display = 'none';
  POST.style.display = 'none';
  META.textContent = '';

  const t0 = performance.now();
  try {
    const voiceId = VOICE.value;
    // Register the chosen voice (fetches one small .safetensors, then cached).
    const url = `https://huggingface.co/${VOICE_REPO}/resolve/${VOICE_REV}/voices/${voiceId}.safetensors`;
    if (!tts.voices.includes(voiceId)) {
      await tts.addVoice(voiceId, url);
    }

    STATUS.textContent = 'Generating…';
    const seedVal = SEED.value.trim();
    const seed = seedVal ? BigInt(seedVal) : undefined;

    let pcm = await tts.synth(text, {
      voice: voiceId,
      temperature: parseFloat(TEMP.value),
      seed,
    });

    // pacing, done by resampling (no ffmpeg in the browser)
    const speed = parseFloat(SPEED.value);
    if (Math.abs(speed - 1) > 0.01) pcm = resample(pcm, 1 / speed);

    const wav = encodeWav(pcm, tts.sampleRate);
    const secs = ((performance.now() - t0) / 1000).toFixed(1);
    const dur = pcm.length / tts.sampleRate;

    lastBlob = wav;
    const v = VOICES.find((x) => x.id === voiceId);
    lastName = `phonon-${(v?.name || 'voice').toLowerCase().replace(/\s+/g, '-')}`;

    PLAYER.src = URL.createObjectURL(wav);
    PLAYER.style.display = 'block';
    POST.style.display = 'flex';
    PLAYER.play().catch(() => {});

    STATUS.textContent = `Done in ${secs}s`;
    META.innerHTML =
      `<span>${dur.toFixed(1)}s of audio</span>` +
      `<span>${v?.name || voiceId}</span>` +
      `<span>delivery ${Number(TEMP.value).toFixed(2)}</span>` +
      `<span>${(wav.size / 1024).toFixed(0)} KB</span>`;
  } catch (err) {
    STATUS.className = 'status err';
    STATUS.textContent = 'That failed: ' + (err?.message || err);
  } finally {
    GO.disabled = false;
  }
}

// Linear resampling changes speed and pitch together — acceptable for reading pace,
// and it keeps the app free of a server-side audio step.
function resample(pcm, ratio) {
  const outLen = Math.max(1, Math.floor(pcm.length * ratio));
  const out = new Float32Array(outLen);
  for (let i = 0; i < outLen; i++) {
    const src = i / ratio;
    const i0 = Math.floor(src);
    const i1 = Math.min(pcm.length - 1, i0 + 1);
    const f = src - i0;
    out[i] = pcm[i0] * (1 - f) + pcm[i1] * f;
  }
  return out;
}

GO.addEventListener('click', generate);

$('dl').addEventListener('click', () => {
  if (!lastBlob) return;
  const a = document.createElement('a');
  a.href = URL.createObjectURL(lastBlob);
  a.download = lastName + '.wav';
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 4000);
});

$('again').addEventListener('click', () => {
  // nudge the seed so the next take differs
  const cur = SEED.value.trim();
  const next = cur ? (BigInt(cur) + 7919n) : 4242424242424242n;
  SEED.value = next.toString();
  generate();
});

// ── first-run gate ───────────────────────────────────────────────────────────
const FIRST_RUN_KEY = 'phonon-studio:welcomed';
function start() {
  loadModel().catch((err) => {
    STATUS.className = 'status err';
    STATUS.textContent = 'Could not load the model: ' + (err?.message || err);
    BAR.style.display = 'none';
  });
}

if (localStorage.getItem(FIRST_RUN_KEY)) {
  start();
} else {
  DLG.showModal();
  $('dlgOk').addEventListener('click', () => {
    localStorage.setItem(FIRST_RUN_KEY, '1');
    DLG.close();
    start();
  });
}
