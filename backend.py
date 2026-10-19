"""Loopback-only demo service. Not a production upload server."""
import importlib.util
import os
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import json
import re
from collections import deque
from pathlib import Path
from flask import Flask, jsonify, request, send_file

os.environ.setdefault('TORCH_HOME', str(Path(__file__).parent / '.models'))

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024
jobs = {}
lock = threading.Lock()
busy = False
ORIGINS = {'http://127.0.0.1:5184', 'http://localhost:5184'}

@app.before_request
def local_only():
    if request.headers.get('Origin') not in ORIGINS:
        return jsonify(error='Use the local Stemroom application.'), 403
    if request.method == 'OPTIONS':
        return '', 204

@app.after_request
def cors(response):
    origin = request.headers.get('Origin')
    if origin in ORIGINS:
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Vary'] = 'Origin'
        response.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS'
    response.headers['Cache-Control'] = 'no-store'
    return response

@app.get('/health')
def health():
    return jsonify(ready=all(importlib.util.find_spec(name) is not None for name in ['demucs', 'torch', 'imageio_ffmpeg']))

@app.route('/analyze', methods=['POST', 'OPTIONS'])
def analyze():
    import imageio_ffmpeg
    upload = request.files.get('audio')
    if not upload:
        return jsonify(error='Choose an audio file.'), 400
    with tempfile.TemporaryDirectory(prefix='stemroom-analysis-') as tmp:
        source = Path(tmp) / 'audio'
        upload.save(source)
        try:
            result = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-nostdin', '-i', str(source),
                '-t', '601', '-vn', '-af', 'loudnorm=print_format=json', '-f', 'null', '-'],
                capture_output=True, timeout=180)
            if result.returncode:
                return jsonify(error='Could not measure this recording.'), 400
            log = result.stderr.decode('utf-8', errors='replace')
            measured = json.loads(re.findall(r'\{[^{}]+\}', log)[-1])
            timeline_result = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-nostdin', '-i', str(source),
                '-t', '601', '-vn', '-af', 'ebur128=peak=true', '-f', 'null', '-'],
                capture_output=True, timeout=180)
            if timeline_result.returncode:
                return jsonify(error='Could not measure the loudness timeline.'), 400
            seconds = {}
            for match in re.finditer(r't:\s*([\d.]+).*?\bS:\s*(-?[\d.]+)', timeline_result.stderr.decode('utf-8', errors='replace')):
                t, value = map(float, match.groups())
                if t >= 3:
                    seconds[int(t)] = {'time': round(t, 2), 'lufs': value}
            def finite(key):
                value = float(measured[key])
                return value if abs(value) != float('inf') else None
            return jsonify(integrated=finite('input_i'), true_peak=finite('input_tp'),
                           lra=finite('input_lra'), short_term=list(seconds.values()), method='FFmpeg loudnorm + ebur128 / EBU R128',
                           scope='Original uploaded file, before mixer volume adjustments')
        except (ValueError, IndexError, subprocess.TimeoutExpired):
            return jsonify(error='Analysis failed or timed out.'), 400

def process(job_id, folder, source):
    global busy
    try:
        jobs[job_id].update(stage='Preparing audio', progress=None)
        import soundfile as sf
        import imageio_ffmpeg
        decoded = folder / 'input.wav'
        converted = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-nostdin', '-y', '-i', str(source),
                                    '-vn', '-t', '601', '-ac', '2', '-ar', '44100', str(decoded)],
                                   capture_output=True, timeout=120)
        if converted.returncode:
            raise ValueError('The audio file could not be decoded. Try a valid MP3, WAV or M4A recording.')
        info = sf.info(str(decoded))
        if info.duration <= 0 or info.duration > 600:
            raise ValueError('Recording must be between 0 and 600 seconds.')
        jobs[job_id].update(stage='Loading separation model', progress=None)
        command = [sys.executable, '-m', 'demucs', '-n', 'htdemucs_6s', '--device', 'cpu',
                                 '-o', str(folder / 'output'), str(decoded)]
        logs = deque(maxlen=30)
        child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, encoding='utf-8', errors='replace',
                                 env={**os.environ, 'OMP_NUM_THREADS': '4', 'PYTHONUNBUFFERED': '1'})
        def read_progress():
            for line in child.stdout:
                logs.append(line)
                percentage = parse_model_progress(line)
                if percentage is not None:
                    previous = jobs[job_id].get('progress') or 0
                    jobs[job_id].update(stage='Separating instrument parts', progress=max(previous, percentage))
                    if percentage == 100:
                        jobs[job_id].update(stage='Saving audio stems', progress=None)
        reader = threading.Thread(target=read_progress, daemon=True)
        reader.start()
        try:
            child.wait(timeout=1800)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
            raise RuntimeError('Separation timed out. Try a shorter recording.')
        finally:
            reader.join(timeout=5)
            child.stdout.close()
        if child.returncode:
            print(''.join(logs)[-5000:], flush=True)
            raise RuntimeError('Model processing failed. Check model dependencies, FFmpeg and server logs.')
        output = folder / 'output' / 'htdemucs_6s' / 'input'
        stems = {}
        for name in ['vocals', 'drums', 'bass', 'guitar', 'piano', 'other']:
            file = output / (name + '.wav')
            if not file.is_file():
                raise RuntimeError('Model did not produce the expected stems.')
            stems[name] = file
        jobs[job_id].update(status='completed', files=stems, stage='Stems ready', progress=100)
    except Exception as exc:
        jobs[job_id].update(status='failed', error=str(exc), stage='Separation failed', progress=None)
    finally:
        source.unlink(missing_ok=True)
        (folder / 'input.wav').unlink(missing_ok=True)
        jobs[job_id]['finished'] = time.time()
        with lock:
            busy = False

@app.route('/separate', methods=['POST', 'OPTIONS'])
def separate():
    global busy
    upload = request.files.get('audio')
    if not upload:
        return jsonify(error='Choose an audio file.'), 400
    suffix = Path(upload.filename or '').suffix.lower()
    if suffix not in {'.wav', '.mp3', '.flac', '.m4a', '.ogg'}:
        return jsonify(error='Unsupported file extension.'), 400
    with lock:
        if busy:
            return jsonify(error='The local model is busy. Please try again after it finishes.'), 429
        busy = True
    job_id = uuid.uuid4().hex
    temp = tempfile.TemporaryDirectory(prefix='stemroom-')
    folder = Path(temp.name)
    source = folder / ('upload' + suffix)
    try:
        upload.save(source)
    except Exception:
        temp.cleanup()
        with lock:
            busy = False
        return jsonify(error='Could not save the upload.'), 500
    jobs[job_id] = dict(status='processing', temp=temp, stage='Preparing audio', progress=None)
    threading.Thread(target=process, args=(job_id, folder, source), daemon=True).start()
    return jsonify(id=job_id), 202

@app.get('/jobs/<job_id>')
def status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify(error='Job expired or not found.'), 404
    return jsonify(status=job['status'], error=job.get('error'), stage=job.get('stage'), progress=job.get('progress'),
                   stems=[dict(name=('Keyboard (piano)' if name == 'piano' else name.title()), url=f'/jobs/{job_id}/stems/{name}')
                          for name in job.get('files', {})])

@app.get('/jobs/<job_id>/stems/<name>')
def stem(job_id, name):
    file = jobs.get(job_id, {}).get('files', {}).get(name)
    if not file:
        return jsonify(error='Stem not found.'), 404
    return send_file(file, mimetype='audio/wav')

def cleanup():
    while True:
        time.sleep(60)
        for key, job in list(jobs.items()):
            if job.get('finished', float('inf')) < time.time() - 3600:
                try:
                    job['temp'].cleanup()
                except PermissionError:
                    continue
                jobs.pop(key, None)

def parse_model_progress(line):
    """Only inference seconds, never model-download byte progress."""
    if 'seconds' not in line:
        return None
    match = re.search(r'(?<!\d)(\d{1,3})%\|', line)
    return min(100, int(match.group(1))) if match else None

if __name__ == '__main__':
    threading.Thread(target=cleanup, daemon=True).start()
    app.run(host='127.0.0.1', port=5185, threaded=True, debug=False)
