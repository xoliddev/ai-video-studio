
import base64, json, os, subprocess, urllib.request
PROJECT=os.environ.get("GOOGLE_CLOUD_PROJECT", ""); REGION=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
tok=subprocess.run(["gcloud","auth","print-access-token"],capture_output=True,text=True,shell=True).stdout.strip()
for m in ["gemini-3.8-flash-tts","gemini-3-flash-tts","gemini-3-pro-tts","gemini-2.5-pro-preview-tts","gemini-2.5-pro-tts"]:
    body={"contents":[{"role":"user","parts":[{"text":"Salom"}]}],
          "generationConfig":{"responseModalities":["AUDIO"],"speechConfig":{"voiceConfig":{"prebuiltVoiceConfig":{"voiceName":"Charon"}}}}}
    u=f"https://{REGION}-aiplatform.googleapis.com/v1/projects/{PROJECT}/locations/{REGION}/publishers/google/models/{m}:generateContent"
    try:
        r=urllib.request.Request(u,data=json.dumps(body).encode(),headers={"Content-Type":"application/json","Authorization":"Bearer "+tok})
        d=json.loads(urllib.request.urlopen(r,timeout=90).read())
        pcm=base64.b64decode(d["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
        print(m,"OK",len(pcm))
    except Exception as e:
        body_msg=getattr(e,"read",lambda:b"")()
        print(m,"ERR",getattr(e,"code",""),body_msg[:160])
