# Unlayer

## Introduction

A browser-based music workspace that separates recordings into vocals, drums, bass and other. Explore synchronized waveforms, adjust the listening mix and inspect original-recording signal levels without a Python service.

## Structure

The header provides audio selection and Help. The player uses a shared timeline, with four stem lanes offering Solo and Mute. Reset mix and Download mix control the output. Loudness shows one-second RMS levels; Details shows sample peak. LUFS, true peak and LRA are unavailable in browser mode. Guitar and keyboard remain in Other.

## How it works

Select a recording → decode audio in memory → download model/runtime files on first use → run separation locally in a worker → load four aligned stems → seek and solo/mute parts → inspect levels → download a WAV mix. WebGPU is preferred with a WebAssembly CPU fallback. Cancel terminates the worker; refreshing clears audio. Audio is not uploaded.

## Others

Run `npm run dev` and open http://127.0.0.1:5184; no frontend dependency installation or build is required. Run `npm run check` and `npm test` for verification. GitHub Actions publishes `dist/` on pushes to main. First use downloads approximately 172 MB of model data plus runtime files.

### Detailed reference

Browser-based music separation and audio level analysis. [Open Unlayer](https://mcgoldfish.github.io/unlayer/).

#### Use

Select a recording. Unlayer downloads a pretrained model on first use, separates the audio on your device, and displays four synchronized parts: vocals, drums, bass and other. Guitar and keyboard are included in Other in this browser version. Solo/Mute, shared waveform seeking and WAV mix download work without a Python service.

- First use downloads approximately 172 MB of model data from Hugging Face, plus ONNX Runtime Web from jsDelivr. Browser caching is best effort and requires available storage.
- Audio is decoded and processed in browser memory; it is not uploaded to a server. Refreshing clears audio.
- WebGPU is preferred when available; WebAssembly CPU is the fallback. Performance and memory limits vary by device. Desktop Chrome/Edge are recommended. Keep the tab open; Cancel terminates the worker.
- Files: up to 50 MB and 10 minutes, subject to device memory. Supported codecs depend on browser decoding. Long recordings can require substantial RAM.
- Charts show one-second RMS dBFS and sample peak. LUFS, true peak and LRA are explicitly unavailable in the browser version. Digital levels do not measure headphone volume.

#### Development

Node.js is sufficient for the frontend:

```sh
npm run dev
```

Open http://127.0.0.1:5184. No build or frontend dependency installation is required. The optional `PORT` environment variable changes the preview port. GitHub Actions publishes `dist/` to GitHub Pages on pushes to `main`.

```sh
npm run check
npm test
```

The browser pipeline regression test exercises actual FFT preprocessing and overlap-add with deterministic model outputs. It verifies chunk duration, endpoint/seam preservation, progress and tensor cleanup; it does not measure model separation quality.

#### Architecture and attribution

- `dist/app.js`: selection, mixing, waveform display, export and worker orchestration.
- `dist/separation-worker.mjs`: model download/cache and browser inference. No localhost API requests.
- `dist/vendor/demucs/`: MIT [demucs-web](https://github.com/timcsy/demucs-web), pinned revision and license included. Local fixes cover segment counting, endpoint windows and tensor disposal.
- [Meta Demucs](https://github.com/facebookresearch/demucs) HTDemucs model, browser ONNX conversion hosted by [timcsy](https://huggingface.co/timcsy/demucs-web-onnx).
- [ONNX Runtime Web](https://onnxruntime.ai/docs/tutorials/web/), pinned to 1.23.2.

Source separation estimates can contain overlap and artifacts. Supply recordings you have permission to process. No commercial recordings are bundled. No application source license has been selected.

The earlier Python six-source separator and FFmpeg analysis remain in the repository for development/reference (`backend.py`, `requirements.txt`, `start.ps1` and Python checks). The published browser interface does not use them. It does not currently provide six-source browser separation or EBU R128 measurements.
