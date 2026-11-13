"""Voice generation for 'Sirli Yo'lovchi' - 1-Qism (~2.5 minutes).
Two characters:
  - Haydovchi (Driver): voice='Charon'
  - Yo'lovchi (Hitchhiker): voice='Puck'
"""
import os
import sys
import json
import wave
import imageio_ffmpeg
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'shared'))
from gemini_tts import tts

HERE = os.path.dirname(os.path.abspath(__file__))
AUD = os.path.join(HERE, 'audio')
os.makedirs(AUD, exist_ok=True)

DIALOGUE = [
    # 0: Intro monolog
    {"id": "d01", "char": "haydovchi", "voice": "Charon", 
     "text": "Tungi soat ikki. Yomg'ir tinmayapti. Kimsasiz trassada ketayotib, yo'l chetida turgan qorani ko'rib qoldim."},
    
    # 1: Mashinaga chiqish
    {"id": "d02", "char": "haydovchi", "voice": "Charon",
     "text": "O'tiring, o'tiring tezroq! Tashqarida muzlab qolasiz."},
    {"id": "d03", "char": "yolovchi", "voice": "Puck",
     "text": "Rahmat, do'stim. Juda olijanob ekansiz."},

    # 2: Qayerga?
    {"id": "d04", "char": "haydovchi", "voice": "Charon",
     "text": "Bu vaqtda bu yo'lda odam zoti yurmaydi-ku. Qayerga yo'l oldingiz o'zi?"},
    {"id": "d05", "char": "yolovchi", "voice": "Puck",
     "text": "Poytaxtga. Siz ham o'sha yoqqami?"},
    {"id": "d06", "char": "haydovchi", "voice": "Charon",
     "text": "Ha. Lekin men shoshilmayapman. Yo'l sirpanchiq, yomg'ir qattiq."},
    {"id": "d07", "char": "yolovchi", "voice": "Puck",
     "text": "Afsus. Menga esa hozir tezlik kerak. Iloji bo'lsa juda katta tezlik."},

    # 3: Sabab
    {"id": "d08", "char": "haydovchi", "voice": "Charon",
     "text": "Nega buncha shoshasiz? Biror noxushlik yuz berdimi?"},
    {"id": "d09", "char": "yolovchi", "voice": "Puck",
     "text": "Ertaga tongda bitta uchrashuvim bor. Agar vaqtida bormasam, butun rejam barbod bo'ladi."},
    {"id": "d10", "char": "haydovchi", "voice": "Charon",
     "text": "Nima ish qilasiz o'zi? Savdogarmisiz?"},
    {"id": "d11", "char": "yolovchi", "voice": "Puck",
     "text": "Yo'q... Savdogarlar og'zi bilan ishlaydi. Men esa barmoqlarim bilan."},

    # 4: Barmoqlar
    {"id": "d12", "char": "haydovchi", "voice": "Charon",
     "text": "Barmoqlar bilan? Pianinochimisiz?"},
    {"id": "d13", "char": "yolovchi", "voice": "Puck",
     "text": "Pianinochi emish! Qanaqasiga pianinochi bo'lay? Yo'q, do'stim. Dunyoda eng qiyin narsa nima, bilasizmi?"},
    {"id": "d14", "char": "haydovchi", "voice": "Charon",
     "text": "Nima ekan?"},
    {"id": "d15", "char": "yolovchi", "voice": "Puck",
     "text": "Odamning ko'zi o'ngida turgan narsani, u qarab turgan paytda ko'rinmas qilish. Bir dona xato qilsangiz — tamom, panjara ortiga ketasiz."},

    # 5: Gumon
    {"id": "d16", "char": "haydovchi", "voice": "Charon",
     "text": "Shoshmang... Siz o'g'rimisiz? To'g'risini ayting, mashinamga kimni mindirdim?!"},
    {"id": "d17", "char": "yolovchi", "voice": "Puck",
     "text": "O'g'ri? Qanaqa qo'pol so'z! O'g'rilar eshik buzadi, kassa buzadi, qon to'kadi... Ular shunchaki nodonlar. Men esa — san'atkorman. Men barmoq ustasiman."},
    {"id": "d18", "char": "haydovchi", "voice": "Charon",
     "text": "Menga farqi yo'q. Tushing mashinamdan. Hozir to'xtataman!"},

    # 6: Kutilmagan burilish (Soat)
    {"id": "d19", "char": "yolovchi", "voice": "Puck",
     "text": "To'xtashga shoshilmang. Avval o'ng qo'lingizga qarang."},
    {"id": "d20", "char": "haydovchi", "voice": "Charon",
     "text": "Qo'limga? Nima bor ekan qo'limda... Shoshma... Qani mening soatim?! O'n yillik soatim qani?!"},
    {"id": "d21", "char": "yolovchi", "voice": "Puck",
     "text": "Mana, kaftimda. Qarang, qanchalik oson. Hatto ichki cho'ntagingizdagi hamyoningiz ham buni sezmadi."},

    # 7: Kulminatsiya va Politsiya
    {"id": "d22", "char": "haydovchi", "voice": "Charon",
     "text": "Sen... jinmisan?! Buni qachon olding?!"},
    {"id": "d23", "char": "yolovchi", "voice": "Puck",
     "text": "Siz menga savol berayotganingizda. Men sizga aytdim-ku, tezroq haydang deb. Chunki orqamizdan..."},
    {"id": "d24", "char": "haydovchi", "voice": "Charon",
     "text": "Orqamizdan nima?!"},
    {"id": "d25", "char": "yolovchi", "voice": "Puck",
     "text": "Qarang orqaga. Chiroqlar yaqinlashyapti. Ular mening orqamdan tushgan."},
    {"id": "d26", "char": "haydovchi", "voice": "Charon",
     "text": "La’nat bo'lsin... Gazni bosishga majburmiz!"}
]

def generate_all():
    print(f"Generating {len(DIALOGUE)} dialogue clips...")
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
