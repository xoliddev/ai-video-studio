import base64, json, os, sys, urllib.request, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gemini_tts import api_key
spec = json.load(open('script.json', encoding='utf-8'))
def text_of(s): return s['say'] if 'say' in s else s['ask'] + '\n\n' + s['answer']
model = sys.argv[1]
for s in spec['segments']:
    p = os.path.join('audio', hashlib.md5(f"{spec['voice']}|{text_of(s)}".encode()).hexdigest()[:16] + '.wav')
    b64 = base64.b64encode(open(p, 'rb').read()).decode()
    body = {'contents': [{'parts': [{'inlineData': {'mimeType': 'audio/wav', 'data': b64}},
        {'text': "Transcribe this Uzbek audio exactly (Latin script). Mark each sentence start time as [m:ss.s]. Then on a new line list any mispronounced or unclear words, or extra speech not part of normal narration."}]}]}
    req = urllib.request.Request(f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
        data=json.dumps(body).encode(), headers={'Content-Type': 'application/json', 'x-goog-api-key': api_key()})
    d = json.load(urllib.request.urlopen(req, timeout=180))
    print('==', s['id'], '\n', d['candidates'][0]['content']['parts'][0]['text'].strip(), flush=True)
