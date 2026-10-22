# Phonon Studio

Text to speech in the browser. Type, pick a voice, get audio. Nothing is uploaded.

**Live:** https://sambawy01.github.io/phonon-studio/

## What it is

A thin, honest front end for [Phonon-31m](https://huggingface.co/gradium/phonon-31m-en) —
an Apache-2.0 speech model — running as WebAssembly in the visitor's browser via the
[`phonon-tts`](https://www.npmjs.com/package/phonon-tts) package.

No server. No account. No API key. The model (~65 MB) downloads once and is then cached by
the browser, so later visits start instantly and work offline.

## Voices

37 English voices from the [Gradium catalogue](https://huggingface.co/gradium/phonon-voices)
(Apache-2.0): 13 female, 12 male, 12 character voices. Each is a small embedding file fetched
on first use, then cached.

## Controls

| Control | What it actually does |
|---|---|
| **Speaker** | Changes the voice embedding — the single biggest factor in tone |
| **Delivery** (temperature) | Low = even and controlled; high = livelier, more variation between takes |
| **Pacing** | Resamples the output: brisk / normal / measured |
| **Take** (seed) | Same words + same seed = identical audio. Change it for another performance |

There is **no emotion dial** on this model, so there is none in this UI. Tone comes from the
voice you choose, the delivery, and — more than either — how the text is written.

## Limits

- **English only.** Phonon-31m has an English tokenizer; other languages need the 40M models,
  which are CC BY-NC and gated on Hugging Face.
- **Single-threaded on GitHub Pages.** The threaded WASM build needs cross-origin isolation
  (`COOP`/`COEP` headers), which GitHub Pages cannot send. Generation is slower but correct.
  Serve with those headers to get ~3× the speed.
- **~65 MB first load.** Cached after that.

## Develop

```bash
npm install
npm run dev     # http://localhost:5173/phonon-studio/
npm run build   # -> dist/
```

`BASE_PATH=/` when deploying to a custom domain or a user pages repo.

## Licence

The app is MIT. Phonon-31m and the voice catalogue are Apache-2.0 (Gradium). See
`LICENSE-APACHE` and `LICENSE-MIT` from the `phonon-tts` package.

## Verified

Generated in headless Chromium under GitHub Pages conditions (no COOP/COEP):
`Ready · CPU · 1 thread`, 7.12 s of audio, 332 KB WAV.
