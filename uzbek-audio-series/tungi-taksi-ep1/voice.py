"""Voice generation for 'Tungi Taksi: Oynadagi Yomg'ir' - 1-Qism (~2.5 minutes).
Characters:
  - Taksichi (Taxi Driver): voice='Charon'
  - Mijoz (Akmal aka, passenger): voice='Puck'
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
    # 0: Monolog intro
    {"id": "t01", "char": "taksichi", "voice": "Charon",
     "text": "Tungi soat ikkiyu qirq. Yomg'ir shahar ko'chalarini yuvib yotibdi. Bunday paytda yo'lovchilar ikki toifaga bo'linadi: uylariga oshiqayotganlar... va boradigan joyi yo'qlar."},
    
    # 1: Mijoz chiqadi
    {"id": "t02", "char": "taksichi", "voice": "Charon",
     "text": "Assalomu alaykum aka. Qayerga haydaymiz?"},
    {"id": "t03", "char": "mijoz", "voice": "Puck",
     "text": "Bilmayman... Faqat haydang. Shaharni aylaning. Qayerga bo'lsa ham... faqat to'xtamang."},
    
    # 2: To'lov
    {"id": "t04", "char": "taksichi", "voice": "Charon",
     "text": "To'xtamaslik qimmatga tushadi, aka. Benzin suv emas."},
    {"id": "t05", "char": "mijoz", "voice": "Puck",
     "text": "Mana. Shu yetadimi? Yana kerak bo'lsa aytasiz."},
    {"id": "t06", "char": "taksichi", "voice": "Charon",
     "text": "Yetadi... Bir haftaga yetadi. Rahmat. Biror noxushlik bo'ldimi aka? Tinchlikmi?"},

    # 3: Dard
    {"id": "t07", "char": "mijoz", "voice": "Puck",
     "text": "Tinchlik bo'lganda shu yomg'irda ko'chada yurarmidim, uka... Odam o'ttiz yil bitta narsani deb yashasa-yu, bir kechada o'sha narsa qog'oz ekanini bilsa nima bo'ladi?"},
    {"id": "t08", "char": "taksichi", "voice": "Charon",
     "text": "Qog'oz yirtiladi, aka. Odam esa yashashda davom etadi."},
    {"id": "t09", "char": "mijoz", "voice": "Puck",
     "text": "Men yashamay qo'yganimga o'n besh yil bo'libdi. O'g'lim... bugun u yuzimga qarab aytdi. 'Sen bizga hech qachon ota bo'lmagansan, sen shunchaki pul bo'lgansan' dedi."},

    # 4: Tushunish
    {"id": "t10", "char": "taksichi", "voice": "Charon",
     "text": "Yoshlar ba'zan achchiq ustida ko'p narsani o'ylamay gapiradi, aka."},
    {"id": "t11", "char": "mijoz", "voice": "Puck",
     "text": "To'g'ri aytdi u. Men butun umr 'oila uchun, bolalarim uchun' deb tongdan tungacha yugurdim. Katta uylar qurdik, qimmat mashinalar oldik... Lekin eng kerakli narsani berolmagan ekanman. Vaqtni."},
    {"id": "t12", "char": "taksichi", "voice": "Charon",
     "text": "Vaqt... hammamizdan o'tib ketadi, aka. Lekin hali kech emas. Uyga qayting. O'g'lingiz bilan yuzma-yuz o'tirib gaplashing."},

    # 5: Kulminatsiya - Eshik qulflangan
    {"id": "t13", "char": "mijoz", "voice": "Puck",
     "text": "Kech, uka... Eshikni ichkaridan qulflab olishdi. 'Boshqa bu eshikka qadam bosmang' deyishdi. Mana, cho'ntagimda nima qolibdi..."},
    {"id": "t14", "char": "taksichi", "voice": "Charon",
     "text": "Bu nima?"},
    {"id": "t15", "char": "mijoz", "voice": "Puck",
     "text": "O'g'lim yetti yoshida menga yasab bergan kichkina yog'och mashinacha. Yigirma yil oldin. O'shandan beri hamyonimda olib yurardim... O'shanda kambag'al edik, lekin baxtli edik."},

    # 6: Qaror va Cliffhanger
    {"id": "t16", "char": "taksichi", "voice": "Charon",
     "text": "Unda yaxshilab eshiting, aka. Siz hozir bu mashinadan tushmaysiz. Biz orqaga qaytamiz."},
    {"id": "t17", "char": "mijoz", "voice": "Puck",
     "text": "Nega? Axir aytdim-ku sizga, eshik qulflangan deb!"},
    {"id": "t18", "char": "taksichi", "voice": "Charon",
     "text": "Qulfni ochishadi. Agar ochishmasa, eshikni birga buzamiz. Ota o'z uyidan qochmaydi. Gazni bosdim!"}
]

def generate_all():
    print(f"Generating {len(DIALOGUE)} dialogue clips for Tungi Taksi...")
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
