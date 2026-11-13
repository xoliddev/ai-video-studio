
import base64, json, os, subprocess, sys, time, urllib.request, wave

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "")  # your GCP project with Vertex AI enabled
REGION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
MODELS = ["gemini-2.5-flash-preview-tts", "gemini-2.5-pro-preview-tts", "gemini-2.5-flash-tts"]

def token():
    return subprocess.run(["gcloud", "auth", "print-access-token"], capture_output=True, text=True, shell=True).stdout.strip()

def call(model, text, voice="Puck"):
    body = {
        "contents": [{"role": "user", "parts": [{"text": text}]}],
        "generationConfig": {"responseModalities": ["AUDIO"],
                             "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}},
    }
    url = f"https://{REGION}-aiplatform.googleapis.com/v1/projects/{PROJECT}/locations/{REGION}/publishers/google/models/{model}:generateContent"
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "Authorization": "Bearer " + token()})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())

for m in MODELS:
    try:
        d = call(m, "Har kuni bir xil savol.")
        parts = d["candidates"][0]["content"]["parts"]
        audio = [p for p in parts if "inlineData" in p]
        if audio:
            pcm = base64.b64decode(audio[0]["inlineData"]["data"])
            print(m, "OK", len(pcm), "bytes", round(len(pcm)/2/24000, 2), "s")
            break
        print(m, "no audio", str(d)[:200])
    except Exception as e:
        msg = getattr(e, "read", lambda: b"")()
        print(m, "ERR", str(e)[:120], msg[:300])
