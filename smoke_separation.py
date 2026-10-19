"""Real model integration check using an original generated 35-second M4A."""
import io
import math
import struct
import subprocess
import tempfile
import time
import wave
from pathlib import Path
import imageio_ffmpeg
import soundfile as sf
from backend import app, jobs, parse_model_progress

assert parse_model_progress(' 42%|====| 40/95 [00:02<00:03, 12.5seconds/s]') == 42
assert parse_model_progress(' 42%|====| 40/95 [00:02<00:03, 12.5MB/s]') is None
origin = {'Origin': 'http://127.0.0.1:5184'}
with tempfile.TemporaryDirectory(prefix='stemroom-check-') as tmp:
    root = Path(tmp)
    with wave.open(str(root / 'test.wav'), 'wb') as wav:
        wav.setparams((1, 2, 22050, 0, 'NONE', 'not compressed'))
        samples = bytearray()
        for i in range(35 * 22050):
            t = i / 22050
            sample = (.15 * math.sin(2 * math.pi * 110 * t)
                      + .08 * math.sin(2 * math.pi * 440 * t)
                      * math.exp(-(t % .5) * 12))
            samples.extend(struct.pack('<h', int(sample * 32767)))
        wav.writeframes(samples)
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-nostdin', '-y', '-i',
                    str(root / 'test.wav'), '-c:a', 'aac', str(root / 'test.m4a')],
                   check=True, capture_output=True)
    with app.test_client() as client:
        assert client.get('/health').status_code == 403
        assert client.get('/health', headers=origin).json['ready']
        fixture = root / ('test.wav' if '--wav' in __import__('sys').argv else 'test.m4a')
        result = client.post('/separate', headers=origin,
                             data={'audio': (io.BytesIO(fixture.read_bytes()), fixture.name)})
        assert result.status_code == 202, result.json
        job_id = result.json['id']
        observed = []
        deadline = time.time() + 1200
        while time.time() < deadline:
            status = client.get('/jobs/' + job_id, headers=origin).json
            observed.append((status.get('stage'), status.get('progress')))
            if status['status'] in {'completed', 'failed'}:
                break
            time.sleep(2)
        assert status['status'] == 'completed', status
        assert len(status['stems']) == 6, status
        assert status['progress'] == 100, status
        assert any(stage == 'Separating instrument parts' and isinstance(value, int) and 0 <= value < 100 for stage, value in observed), observed
        print('Observed real progress:', observed, flush=True)
        for stem in status['stems']:
            response = client.get(stem['url'], headers=origin)
            assert response.status_code == 200
            metadata = sf.info(io.BytesIO(response.data))
            assert abs(metadata.duration - 35) < .2, metadata
            print(f"{stem['name']}: {metadata.duration:.3f} seconds, {len(response.data)} bytes", flush=True)
            response.close()
        jobs.pop(job_id)['temp'].cleanup()
        print(f'PASS: real {fixture.suffix} upload -> Demucs -> six full-duration stems.', flush=True)
