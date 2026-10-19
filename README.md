# Unlayer

Upload a recording, explore its instrument parts, and inspect its loudness in one listening workspace.

- Six synchronized parts: vocals, drums, bass, guitar, keyboard (piano), and other.
- Shared playback, waveform seeking, Solo/Mute, and WAV mix download.
- Separation progress with preparation, inference, and loading stages.
- RMS and short-term loudness charts; integrated LUFS, true peak, sample peak, and loudness range.
- Black background, animated wave contours, and white instrument waveforms. Reduced motion is respected.

## Run locally

Requires Node.js and Python 3.12. From this folder, create the Python environment and install dependencies (Windows PowerShell):

```powershell
py -3.12 -m venv .venv
./.venv/Scripts/python.exe -m pip install torch==2.5.1 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cpu
./.venv/Scripts/python.exe -m pip install -r requirements.txt
./start.ps1
```

Open http://127.0.0.1:5184. The audio service listens at http://127.0.0.1:5185. Alternatively, run `npm run dev` and `./.venv/Scripts/python.exe backend.py` in separate terminals. FFmpeg is supplied through imageio-ffmpeg.

The first separation downloads the pretrained Demucs htdemucs_6s model into `.models/`. CPU processing can take several minutes. Select an audio file to start measurement and separation automatically. Limits: 50 MB and 10 minutes per file, with one separation job at a time.

## Measurements and limits

Instrument parts are estimates and may contain overlap. The keyboard part estimates piano; synthesizers may remain in Other. Loudness uses FFmpeg loudnorm and ebur128. Digital dBFS/dBTP measurements are not acoustic sound pressure; loudness range is not a TT DR score. No commercial recordings or model weights are bundled.

Decoded audio stays in browser memory. Uploaded files are deleted after processing; temporary output stems expire after one hour. Abrupt termination may leave temporary files. Reloading clears the current browser session.

This is a loopback-only local application. Public deployment needs a separate production inference service, authentication, quotas, worker isolation, and storage lifecycle controls. Static hosting alone cannot run the Python model.

## Checks

```powershell
npm run check
npm test
./.venv/Scripts/python.exe analysis_test.py
./.venv/Scripts/python.exe smoke_separation.py --wav
```

The last check runs actual model inference and requires downloaded weights. The audio unit test uses an original synthesized fixture; it does not measure model separation quality.

Model: [Demucs](https://github.com/facebookresearch/demucs). No application source license has been selected.
