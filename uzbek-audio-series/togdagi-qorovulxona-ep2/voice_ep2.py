"""Voice synthesis & bespoke vocal mastering for Episode 2:
'Tog'dagi Qorovulxona — 2-Qism: Ostonadagi To'qnashuv'
- Samadov (old veteran watchman): deep chest resonance, aged, slow, raspy baritone.
- Rustam (terrified young informant): breathless, high pitch, trembling.
- Boshliq (mercenary leader): cold, cynical, steely tactical command tone.
- Strictly ZERO 'trs' clicks / pops (full zero-crossing fades).
"""
import asyncio
import os
import subprocess
import wave
import numpy as np
import edge_tts
import imageio_ffmpeg

FF = imageio_ffmpeg.get_ffmpeg_exe()
HERE = os.path.dirname(os.path.abspath(__file__))
AUD_RAW = os.path.join(HERE, 'audio_raw')
AUD = os.path.join(HERE, 'audio')
os.makedirs(AUD_RAW, exist_ok=True)
os.makedirs(AUD, exist_ok=True)

DIALOGUE = [
    # Shot 01: Breach
    {
        "id": "e2_01", "char": "samadov", "shot": 1,
        "edge_rate": "-14%", "edge_pitch": "-28Hz",
        "text": "Eshikni sindirishdi... Qimirlama, Rustam!"
    },
    # Shot 02: Leader in silhouette
    {
        "id": "e2_02", "char": "boshliq", "shot": 2,
        "edge_rate": "-6%", "edge_pitch": "-10Hz",
        "text": "Miltiqni tushir, chol. Bu yerda buyruqni men beraman."
    },
    # Shot 03: Samadov aim
    {
        "id": "e2_03", "char": "samadov", "shot": 3,
        "edge_rate": "-14%", "edge_pitch": "-28Hz",
        "text": "Mening ostonamga qurol bilan bostirib kirgan odam buyruq berolmaydi. Yana bir qadam bossang, ko'kragingga qo'rg'oshin kiradi."
    },
    # Shot 04: Leader steps into firelight
    {
        "id": "e2_04", "char": "boshliq", "shot": 4,
        "edge_rate": "-6%", "edge_pitch": "-10Hz",
        "text": "Qaribsan, polkovnik Samadov... Haliyam o'sha eski gvardiyaning o'jar tabiati. O'g'ling Temur ham o'sha samolyot kabinasida xuddi shunday gapirgan edi."
    },
    # Shot 05: Rustam shivering behind bench
    {
        "id": "e2_05", "char": "rustam", "shot": 5,
        "edge_rate": "+6%", "edge_pitch": "+20Hz",
        "text": "Polkovnik, unga quloq solmang! Ular tirik qoldirmaydi, hech kimni tirik qoldirmaydi!"
    },
    # Shot 06: Samadov's eyes burning with grief and rage
    {
        "id": "e2_06", "char": "samadov", "shot": 6,
        "edge_rate": "-14%", "edge_pitch": "-28Hz",
        "text": "Demak, o'g'limning samolyotini portlatgan vijdonsiz qotil sen ekansanda?! Yuz qirqta begunoh yo'lovchining uvoli tutmadimi seni?!"
    },
    # Shot 07: Leader cocking silenced pistol
    {
        "id": "e2_07", "char": "boshliq", "shot": 7,
        "edge_rate": "-6%", "edge_pitch": "-10Hz",
        "text": "Bu shaxsiy masala emasdi, polkovnik. Shunchaki katta buyruq. O'sha reysda xoinlikni fosh qiluvchi komissiya uchayotgan edi. Ular yerga sog'-omon qo'nishi mumkin emasdi."
    },
    # Shot 07 cont: Leader cold smile
    {
        "id": "e2_08", "char": "boshliq", "shot": 7,
        "edge_rate": "-6%", "edge_pitch": "-10Hz",
        "text": "Va bugun ham o'sha qoidamiz o'zgarmagan: bu sirni bilgan hech kim bu tog'dan tirik tushmaydi!"
    },
    # Shot 08: Rustam reveals the notebook's secret
    {
        "id": "e2_09", "char": "rustam", "shot": 8,
        "edge_rate": "+6%", "edge_pitch": "+20Hz",
        "text": "Daftarchada barcha buyurtmachilarning ismi bor... Ular orasida general Karimov ham bor, polkovnik!"
    },
    # Shot 03: Samadov reaction
    {
        "id": "e2_10", "char": "samadov", "shot": 3,
        "edge_rate": "-14%", "edge_pitch": "-28Hz",
        "text": "Karimov?.. Demak, sotqin eng tepada o'tirgan ekan..."
    },
    # Shot 09: Mercenaries raise assault rifles
    {
        "id": "e2_11", "char": "boshliq", "shot": 9,
        "edge_rate": "-6%", "edge_pitch": "-10Hz",
        "text": "Ortiqcha gapirdingiz. Yigitlar, ikkalasini ham joyida yo'qotinglar!"
    },
    # Shot 05: Rustam panic
    {
        "id": "e2_12", "char": "rustam", "shot": 5,
        "edge_rate": "+7%", "edge_pitch": "+22Hz",
        "text": "Polkovnik, otishyapti!!"
    },
    # Shot 10: Samadov kicks lantern, fires shotgun
    {
        "id": "e2_13", "char": "samadov", "shot": 10,
        "edge_rate": "-12%", "edge_pitch": "-24Hz",
        "text": "Yot pastga, Rustam! Qorong'uda jang qilamiz!!"
    }
]

async def generate_raw():
    for item in DIALOGUE:
        mp3_path = os.path.join(AUD_RAW, f"{item['id']}.mp3")
        wav_raw = os.path.join(AUD_RAW, f"{item['id']}_raw.wav")
        print(f"Generating TTS for {item['id']} ({item['char']})...")
        comm = edge_tts.Communicate(
            item['text'],
            voice='uz-UZ-SardorNeural',
            rate=item['edge_rate'],
            pitch=item['edge_pitch']
        )
        await comm.save(mp3_path)
        subprocess.run([FF, '-y', '-loglevel', 'error', '-i', mp3_path, '-ar', '44100', wav_raw], check=True)

def process_and_master():
    print("Mastering dialogue takes with bespoke vocal timbre & zero clicks...")
    for item in DIALOGUE:
        raw_wav = os.path.join(AUD_RAW, f"{item['id']}_raw.wav")
        final_wav = os.path.join(AUD, f"{item['id']}.wav")
        
        with wave.open(raw_wav, 'rb') as w:
            sr = w.getframerate()
            dur = w.getnframes() / float(sr)
            
        fade_out_st = max(0, dur - 0.04)
        
        if item['char'] == 'samadov':
            # Samadov: 65yo weathered colonel. Deep, gruff chest resonance, aged rasp
            filt = (
                "equalizer=f=190:t=q:w=1.2:g=5.5,"
                "equalizer=f=3300:t=q:w=1.0:g=-2.5,"
                f"afade=t=in:d=0.02,afade=t=out:st={fade_out_st:.3f}:d=0.04,"
                "volume=1.35"
            )
        elif item['char'] == 'rustam':
            # Rustam: 24yo panicked, breathless informant
            filt = (
                "highpass=f=250,"
                "equalizer=f=2900:t=q:w=1.0:g=3.0,"
                f"afade=t=in:d=0.02,afade=t=out:st={fade_out_st:.3f}:d=0.04,"
                "volume=1.3"
            )
        else: # boshliq
            # Boshliq: Cold, cynical, tactical combat commander
            filt = (
                "equalizer=f=240:t=q:w=1.0:g=2.5,"
                "equalizer=f=1400:t=q:w=1.0:g=3.5,"
                "equalizer=f=4500:t=q:w=1.0:g=-1.5,"
                f"afade=t=in:d=0.02,afade=t=out:st={fade_out_st:.3f}:d=0.04,"
                "volume=1.4"
            )
            
        subprocess.run([FF, '-y', '-loglevel', 'error', '-i', raw_wav, '-af', filt, final_wav], check=True)
        
        # Verify tail RMS
        with wave.open(final_wav, 'rb') as w:
            fdata = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
            fsr = w.getframerate()
            tail_rms = np.sqrt(np.mean(fdata[-int(0.05 * fsr):].astype(float)**2))
            print(f"Mastered {item['id']} ({item['char']}): {len(fdata)/fsr:.2f}s, last 50ms RMS = {tail_rms:.2f}")

async def main():
    await generate_raw()
    process_and_master()

if __name__ == '__main__':
    asyncio.run(main())
