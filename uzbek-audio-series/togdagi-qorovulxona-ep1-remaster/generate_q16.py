import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'shared'))
from gemini_tts import tts

text = "Sen qimirlama, Rustam bolam! Qurolga teginma, bularni o'zim kutib olaman!"
out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'audio', 'q16_new_raw.wav')
tts(text, out_path, voice='Charon')
print("Successfully generated q16_new_raw.wav")
