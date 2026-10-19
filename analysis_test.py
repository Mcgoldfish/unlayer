import io
import math
import struct
import wave
from backend import app

def tone(amplitude):
    data = io.BytesIO()
    with wave.open(data, 'wb') as output:
        output.setparams((1, 2, 44100, 0, 'NONE', 'not compressed'))
        output.writeframes(b''.join(struct.pack('<h', int(amplitude * 32767 * math.sin(2 * math.pi * 1000 * i / 44100))) for i in range(44100 * 12)))
    data.seek(0)
    return data

with app.test_client() as client:
    measured = []
    for amplitude in [.1, .2]:
        response = client.post('/analyze', headers={'Origin': 'http://127.0.0.1:5184'}, data={'audio': (tone(amplitude), 'tone.wav')})
        assert response.status_code == 200, response.json
        measured.append(response.json)
    assert abs(measured[1]['integrated'] - measured[0]['integrated'] - 6.02) < .15, measured
    assert abs(measured[1]['true_peak'] - measured[0]['true_peak'] - 6.02) < .15, measured
    assert abs(measured[0]['true_peak'] + 20) < .2, measured
    assert measured[0]['lra'] < .2, measured
    for result in measured:
        assert len(result['short_term']) >= 8, result
        assert all(point['time'] >= 3 for point in result['short_term']), result
        assert all(math.isfinite(point['lufs']) for point in result['short_term']), result
    assert abs(measured[1]['short_term'][-1]['lufs'] - measured[0]['short_term'][-1]['lufs'] - 6.02) < .2
    invalid = client.post('/analyze', headers={'Origin': 'http://127.0.0.1:5184'}, data={'audio': (io.BytesIO(b'not audio'), 'bad.wav')})
    assert invalid.status_code == 400
    print('PASS: integrated/short-term LUFS and true peak gain, 3-second-window timeline, known peak, steady-tone LRA and invalid audio.')
