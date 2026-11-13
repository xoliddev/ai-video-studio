"""Voice generation for 'Tog'dagi Qorovulxona: Qor Bo'roni' - 1-Qism (~2.5 minutes).
Characters:
  - Qorovul (Polkovnik Samadov, old watchman): voice='Charon'
  - Begona (Yaralangan yigit, Rustam): voice='Puck'
"""
import os
import sys
import json
import wave

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'shared'))
from gemini_tts import tts

HERE = os.path.dirname(os.path.abspath(__file__))
AUD = os.path.join(HERE, 'audio')
os.makedirs(AUD, exist_ok=True)

DIALOGUE = [
    # 0: Intro monolog
    {"id": "q01", "char": "qorovul", "voice": "Charon",
     "text": "Tog'da qish boshqacha bo'ladi. Bo'ron uvillashi xuddi qadimgi sharpalarning faryodiga o'xshaydi. Bu balandlikda odam yo yolg'izlikka o'rganadi... yoki aqldan ozadi."},
    
    # 1: Eshik taqillashi
    {"id": "q02", "char": "qorovul", "voice": "Charon",
     "text": "Bu qahratonda qanday qilib tirik qolish mumkin?! Kim u?!"},
    {"id": "q03", "char": "begona", "voice": "Puck",
     "text": "Yordam bering... Iltimos, oching! Mashinam jarga quladi... Ular... ular ortimdan kelyapti!"},

    # 2: Ichkariga kirish
    {"id": "q04", "char": "qorovul", "voice": "Charon",
     "text": "Kir, tezroq! Kir ichkariga. Eshikni zanjirla. Olovga yaqinroq o'tir, mana issiq choy."},
    {"id": "q05", "char": "begona", "voice": "Puck",
     "text": "Rahmat... Qo'llarimni sezmayapman. Lekin siz eshikni mustahkamroq qulflang. Ular bu yerga yetib kelishdi."},

    # 3: Savol-javob
    {"id": "q06", "char": "qorovul", "voice": "Charon",
     "text": "O'zingni bos, yigit. Bu dovonda bo'rilardan boshqa hech qanday tirik jon yo'q. Kim seni ta'qib qiladi?"},
    {"id": "q07", "char": "begona", "voice": "Puck",
     "text": "Ular bo'rilar emas! Ular odamlar. Uch kishi. Qora kiyingan, qo'llarida qurol bor. Ular butun qor bo'ylab izimdan kelishyapti."},
    {"id": "q08", "char": "qorovul", "voice": "Charon",
     "text": "Nega? Oddiy yo'lovchining orqasidan uchta qurolli odam tushmaydi. Kimning yo'lini kesding?"},

    # 4: Sir ochilishi
    {"id": "q09", "char": "begona", "voice": "Puck",
     "text": "Men ularning qora daftarchasini ko'rib qoldim. O'n ikki yil oldin tog'da g'oyib bo'lgan o'sha samolyot haqidagi haqiqatni."},
    {"id": "q10", "char": "qorovul", "voice": "Charon",
     "text": "Nima deding?! Qaysi samolyot?!"},
    {"id": "q11", "char": "begona", "voice": "Puck",
     "text": "Shimoliy reys. Yuz qirqta yo'lovchisi bilan g'oyib bo'lgan o'sha mashhur samolyot... Siz bilmaysiz, u texnik nosozlik emasdi. U ataylab portlatilgan!"},

    # 5: Shok va Haqiqat
    {"id": "q12", "char": "qorovul", "voice": "Charon",
     "text": "Men bilmaymanmi?.. O'sha samolyotning birinchi uchuvchisi... mening yagona o'g'lim edi."},
    {"id": "q13", "char": "begona", "voice": "Puck",
     "text": "Nima?! Siz... siz o'sha polkovnik Samadovmisiz?!"},
    {"id": "q14", "char": "qorovul", "voice": "Charon",
     "text": "Ha. Men o'n ikki yildan beri mana shu kulbada o'tirib, o'g'limning qotillari qachon bu tog'dan o'tishini kutardim."},

    # 6: Cliffhanger - Ostonadagi dushman
    {"id": "q15", "char": "begona", "voice": "Puck",
     "text": "Eshityapsizmi?.. Qor g'irchillayapti. Ular eshik orqasida!"},
    {"id": "q16", "char": "qorovul", "voice": "Charon",
     "text": "Eshikdan uzoqroq tur, bolam. Haqiqat o'zi eshigimizni taqillatib keldi. Miltiqqa tegmang, o'zim kutib olaman!"}
]

def generate_all():
    print(f"Generating {len(DIALOGUE)} dialogue clips for Tog'dagi Qorovulxona...")
    for item in DIALOGUE:
        wav_path = os.path.join(AUD, f"{item['id']}.wav")
        if os.path.exists(wav_path) and os.path.getsize(wav_path) > 1000:
            print(f"Skipping {item['id']} (already exists)")
            continue
        print(f"Generating {item['id']} ({item['char']}: {item['voice']})...")
        tts(item['text'], wav_path, voice=item['voice'])
    print("All audio generated!")

if __name__ == '__main__':
    generate_all()
