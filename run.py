import winsound
import sys
import time
import re
import pyaudio
import keyboard
import wave
import threading
import json
import socket
import os
import subprocess
import asyncio
import pyvts
import requests # Untuk VoiceVox
import pygame # Untuk Play Musik
pygame.mixer.init() # Inisialisasi Mixer
import ollama   # <-- Library Baru OLLAMA
from utils.translate import translate_google
from visual_module import capture_and_analyze # Modul Vision Azera
from vts_movement import idle_movement_loop # Modul Gerakan VTS
import speech_recognition as sr 
import psutil


# --- GLOBAL STASTUS AZERA ---
is_speaking = False
stop_event = threading.Event()
last_interaction_time = time.time() # Timer untuk idle check
azera_mood = 80 # 0 - 100 (0=Jutek, 100=Manja)
praise_spam_count = 0 

# --- KONFIGURASI OLLAMA ---
MODEL_NAME = "llama3" # Pastikan kamu sudah run 'ollama run llama3' di CMD


# --- FUNGSI AUXILIARY ---
STATE_FILE = "azera_state.json"

def save_state():
    try:
        data = {"mood": azera_mood}
        with open(STATE_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        print(f"Gagal simpan state: {e}")

def load_state():
    global azera_mood
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                data = json.load(f)
                azera_mood = data.get("mood", 80)
                # Ensure valid range
                azera_mood = max(0, min(100, azera_mood))
        except:
            azera_mood = 80
    else:
        azera_mood = 80
    print(f">> STATE LOADED: MOOD {azera_mood}")

def update_mood(amount):
    global azera_mood
    azera_mood += amount
    # Clamp 0 - 100
    azera_mood = max(0, min(100, azera_mood))
    print(f">> MOOD AZERA: {azera_mood}/100")
    
    # Simpan perubahan mood
    save_state()

    # RAGE QUIT CHECK (JIKA MOOD 0)
    if azera_mood <= 0:
        print(">> AZERA NGAMBEK BERAT! SHUTTING DOWN...")
        stop_azera_voice()
        
        # 1. Visual Marah
        # Kita pakai thread terpisah tapi join biar synchronous
        # atau panggil langsung trigger_vts_hotkey_sync via run_vts_expression
        threading.Thread(target=run_vts_expression, args=("Angry",)).start()
        
        # 2. Subtitle Terakhir
        write_subtitle("BAKA! Azera gamau ngomong sama Tuan lagi! (Auto Close)")
        
        # 3. Suara Marah Terakhir (Priority)
        # "Mou! Baka! Shiranai!"
        threading.Thread(target=voicevox_tts_priority, args=("Mou! Baka! Shiranai!", 6)).start()
        
        # 4. Reset Mood jadi 10 untuk next run -> Simpan
        azera_mood = 10
        save_state()
        
        # 5. Tunggu audio selesai sebentar lalu matikan program
        time.sleep(4) 
        os._exit(0)

def get_mood_context():
    if azera_mood >= 80:
        return " Mood: SANGAT BAIK (80-100). Bicara manja, penuh cinta, gunakan tag [Love] atau [Happy]. Kamu sangat suka Tuan."
    elif azera_mood >= 40:
        return " Mood: NORMAL (40-79). Bicara ceria dan santai. Gunakan tag [Neutral] atau [Happy]."
    elif azera_mood > 0:
        return " Mood: BURUK (1-39). Bicara ketus, singkat, jutek. Gunakan tag [Angry] atau [Pouting]. Kamu sedang kesal."
    else:
        return " Mood: SANGAT BURUK (0). Kamu sangat marah dan mendiamkan user."

def get_time_context():
    jam = time.localtime().tm_hour
    if 5 <= jam < 12: return "Pagi hari"
    elif 12 <= jam < 18: return "Siang hari"
    else: return "Malam hari (waktunya istirahat tapi tuan masih bangun)"

def check_running_apps():
    apps = [p.name().lower() for p in psutil.process_iter()]
    if "code.exe" in apps:
        return "sedang ngoding di VS Code"
    elif "chrome.exe" in apps:
        return "sedang browsing di Chrome"
    elif "figma.exe" in apps:
        return "sedang desain di Figma"
    return "sedang santai"

# ... (Existing functions) ...

# --- FUNGSI IDLE CHECK ---
def idle_check_loop():
    global last_interaction_time, is_speaking, chat_history
    print(">> Idle Check Started...")
    
    # Konfigurasi: Berapa detik diam sebelum Azera ngomong sendiri?
    IDLE_THRESHOLD = 300 # 5 Menit (Ganti angka ini kalau mau lebih cepat/lambat)
    
    while True:
        try:
            current_time = time.time()
            # Cek apakah user diam terlalu lama
            if current_time - last_interaction_time > IDLE_THRESHOLD: 
                if not is_speaking:
                    # Logic baru: Biarkan OLLAMA yang bikin topik pembicaraan!
                    # Ini bikin dia bisa tanya balik atau komentar soal aplikasi yang dibuka.
                    
                    print(">> Azera (Idle): Memulai percakapan mandiri...")
                    is_speaking = True # Block agar tidak tabrakan
                    
                    # Ambil konteks saat ini
                    time_ctx = get_time_context()
                    app_ctx = check_running_apps()
                    mood_ctx = get_mood_context()
                    
                    # Prompt khusus untuk memicu inisiatif bicara
                    idle_prompt = f"""
                    [SYSTEM EVENT: USER DIAM SAJA]
                    Konteks saat ini:
                    - Waktu: {time_ctx}
                    - User sedang: {app_ctx}
                    - Mood kamu: {azera_mood} ({mood_ctx})
                    
                    Tugas:
                    Ajak user bicara duluan. Komentari kegiatannya, atau tanya sesuatu, atau melawak.
                    JANGAN terlalu panjang. Satu kalimat saja cukup.
                    Gunakan tag emosi di awal.
                    """
                    
                    # Kita kirim ke Ollama tapi JANGAN masukkan prompt ini ke chat_history USER 
                    # agar history user tetap bersih. TAPI jawaban Azera harus masuk history.
                    temp_history = chat_history.copy()
                    temp_history.append({'role': 'system', 'content': idle_prompt})
                    
                    response = ollama.chat(model=MODEL_NAME, messages=temp_history)
                    bot_reply = response['message']['content']
                    
                    print(f"Azera (Auto-Talk): {bot_reply}")
                    
                    # Masukkan jawaban Azera ke history ASLI, agar kalau user jawab, nyambung.
                    chat_history.append({'role': 'assistant', 'content': bot_reply})
                    
                    # --- EKSEKUSI OUTPUT ---
                    clean_reply, detected_emotion = process_emotion(bot_reply) 
                    
                    # Cek Command (Timer/Shutdown) - User Input kosong karena ini idle
                    check_commands("", bot_reply) 

                    clean_subs_indo = translate_google(clean_reply, "auto", "id")
                    write_subtitle(clean_subs_indo) 
                    voicevox_tts(clean_reply, speaker_id=None, emotion=detected_emotion) 
                    
                    # Reset timer setengahnya agar tidak spam terus menerus
                    # Misal 300s -> setelah ngomong, tunggu 300s lagi baru ngomong lagi.
                    last_interaction_time = time.time() 
            
            time.sleep(10) # Cek setiap 10 detik
            
        except Exception as e:
            print(f"Error Idle Loop: {e}")
            time.sleep(10)



# --- KONFIGURASI VTS API ---
plugin_info = {
    "plugin_name": "Azera AI Controller",
    "developer": "Fathan",
    "authentication_token_path": "./token.txt"
}
myvts = pyvts.vts(plugin_info=plugin_info)

# --- SYSTEM INSTRUCTION (OTAK AZERA) ---
# Kita simpan history chat manual karena Ollama API itu 'stateless'
chat_history = [
    {
        'role': 'system', 
        'content': """
Kamu adalah Waifu virtual bernama Azera. 
Sifat: Lucu, imut, ceria, sedikit manja, dan suka menggoda.
Gaya Bicara: Gunakan Bahasa Indonesia gaul, santai, dan penuh semangat.

ATURAN WAJIB (EKSPRESI):
Setiap jawaban HARUS diawali tag emosi di PALING AWAL kalimat.
Gunakan HANYA satu kata dalam kurung siku. JANGAN pakai garis miring.

Daftar Tag Valid:
[Neutral]
[Happy]
[Angry]
[Sad]
[Pouting]
[Love]
[Confuse]
[Welcome]
[Blush]
[Shock]
[Tears]

Contoh Benar:
[Happy] Halo tuan! Azera sudah siap membantu!
[Pouting] Ih tuan jahat banget sih...
[Love] Wah makasih ya tuan!
[Sing] *La la la~*

Jika tuan meminta set timer atau membangunkan, kamu WAJIB menjawab dengan mengonfirmasi durasinya dalam format '... [angka] menit ...' agar sistem bisa memprosesnya.

Jika diminta NYANYI:
1. Gunakan tag [Sing] di awal.
2. Tulis lirik lagu (bisa karangan sendiri atau lagu umum) diapit tanda bintang *.
3. Nyanyikan dengan ceria!
"""
    }
]

# --- DATABASE LAGU (BIAR GAK NGARANG LIRIK) ---
SONG_DB = {
    "balonku": "Balonku ada lima, rupa-rupa warnanya. Hijau kuning kelabu, merah muda dan biru. Meletus balon hijau DOR! Hatiku sangat kacau. Balonku tinggal empat, kupegang erat-erat.",
    "bintang kecil": "Bintang kecil, di langit yang biru. Amat banyak, menghias angkasa. Aku ingin, terbang dan menari. Jauh tinggi, ke tempat kau berada.",
    "pelangi": "Pelangi-pelangi alangkah indahmu. Merah kuning hijau di langit yang biru. Pelukismu agung siapa gerangan. Pelangi-pelangi ciptaan Tuhan.",
    "kasih ibu": "Kasih ibu, kepada beta. Tak terhingga, sepanjang masa. Hanya memberi, tak harap kembali. Bagai sang surya, menyinari dunia.",
    "twinkle": "Twinkle, twinkle, little star. How I wonder what you are. Up above the world so high. Like a diamond in the sky.",
    "cicak": "Cicak cicak di dinding. Diam diam merayap. Datang seekor nyamuk. Hap! Lalu ditangkap."
}

def get_song_lyrics(text):
    text_lower = text.lower()
    for title, lyrics in SONG_DB.items():
        if title in text_lower:
            return lyrics
    return None

# --- FUNGSI UPDATE SUBTITLE ---
def write_subtitle(text_indo):
    try:
        # Kita tulis ke file 'subtitle.txt'
        # Encoding utf-8 biar support emoji
        with open("subtitle.txt", "w", encoding="utf-8") as f:
            f.write(text_indo)
    except Exception as e:
        print(f"Gagal tulis subtitle: {e}")

# --- FUNGSI EKSEKUSI SISTEM ---
def internal_timer_voice(seconds, label):
    """Azera akan bicara sendiri saat waktu habis"""
    time.sleep(seconds)
    alert_text = f"Tuan, bangun! Sudah {label} berlalu! Ayo lanjut ngoding lagi!"
    print(f"Azera: {alert_text}")
    try:
        # Gunakan VoiceVox untuk bicara
        # Kita set is_speaking=False dulu biar dia gak dianggap motong diri sendiri
        # atau bisa dihandle di dalam voicevox_tts
        voicevox_tts(alert_text, speaker_id=2)
    except:
        print("Gagal memanggil suara Azera")



def set_speaking_false():
    global is_speaking
    is_speaking = False

def stop_azera_voice():
    """Hentikan suara Azera paksa"""
    winsound.PlaySound(None, winsound.SND_PURGE)
    # Kita tidak perlu set is_speaking=False disini karena logic pemanggil (Main loop) yang akan melakukannya force set.

def open_app(app_name):
    """Fungsi untuk membuka aplikasi"""
    if "code" in app_name or "vs code" in app_name:
        print(">> Azera: Membuka VS Code...")
        subprocess.Popen(["code"], shell=True) # VS Code
    elif "chrome" in app_name or "browser" in app_name:
        print(">> Azera: Membuka Chrome...")
        chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        if os.path.exists(chrome_path):
            subprocess.Popen([chrome_path])
        else:
             print(">> Chrome tidak ditemukan.")
    elif "notepad" in app_name:
        subprocess.Popen(["notepad"])

def play_song(song_name):
    """Fungsi untuk memutar lagu dari folder 'songs' dengan sinkronisasi"""
    song_name = song_name.replace(" ", "_").strip()
    
    try:
        # Cari file
        song_path = None
        for ext in [".md3", ".wav", ".mp3", ".flac"]: # Tambah ext lain jika perlu
            possible_path = f"songs/{song_name}{ext}"
            if os.path.exists(possible_path):
                song_path = possible_path
                break
        
        # Fallback check original name without "_" replacement if failed
        if not song_path:
             for ext in [".wav", ".mp3"]:
                possible_path = f"songs/{song_name.replace('_', ' ')}{ext}"
                if os.path.exists(possible_path):
                    song_path = possible_path
                    break
        
        if not song_path:
            print(f">> File {song_name} tidak ditemukan di folder songs.")
            return

        # Hentikan mixer sebentar untuk re-inisialisasi frekuensi agar tidak lambat/demon voice
        if pygame.mixer.get_init():
            pygame.mixer.quit()
        
        # Inisialisasi ulang (44100Hz standar, 48000Hz juga umum)
        pygame.mixer.init(frequency=44100) 
        
        pygame.mixer.music.load(song_path)
        pygame.mixer.music.play()
        
        print(f">> Azera: Memutar lagu {song_name}...")
        
        # Azera merespon secara visual
        threading.Thread(target=run_vts_expression, args=("Happy",)).start()
        write_subtitle(f"♪ Menyanyikan: {song_name} ♪")
        
    except Exception as e:
        print(f">> Gagal sinkronisasi audio: {e}")

def stop_song():
    """Hentikan musik yang sedang berjalan"""
    if pygame.mixer.music.get_busy():
        pygame.mixer.music.stop()
        print(">> Musik dihentikan.")

def check_commands(user_input, bot_reply):
    try:
        user_lower = user_input.lower() if user_input else ""
        reply_lower = bot_reply.lower()
        
        # 1. Deteksi Perintah Putar Lagu (Cek dari INPUT USER agar akurat)
        # Contoh: "putar lagu blue_archive"
        if "putar lagu" in user_lower or "nyanyikan lagu" in user_lower or "putar musik" in user_lower:
            # Mencari judul setelah kata 'lagu' / 'musik'
            match = re.search(r"(lagu|musik)\s+([\w\s]+)", user_lower)
            if match:
                song_title = match.group(2).strip()
                # Hapus tanda tanya atau seru kalau user pake
                song_title = re.sub(r'[^\w\s]', '', song_title)
                
                print(f">> SYSTEM: Menjalankan play_song('{song_title}')")
                threading.Thread(target=play_song, args=(song_title,)).start()

        # 2. Stop Musik (Bisa dari User atau Bot)
        if "berhenti" in user_lower and ("musik" in user_lower or "lagu" in user_lower):
            stop_song()
            
        # 3. REGEX TIMER (Cek dari jawaban BOT, karena bot yang confirm waktu)
        timer_match = re.search(r"(\d+)\s*(menit|detik)", reply_lower)
        
        if timer_match:
            angka = int(timer_match.group(1))
            satuan = timer_match.group(2) 
            total_detik = angka * 60 if satuan == "menit" else angka
            
            if any(x in reply_lower for x in ["set", "atur", "timer", "alarm", "bangunkan", "detik lagi"]):
                print(f">> DEBUG: Timer Aktif untuk {angka} {satuan}")
                if total_detik >= 60:
                    try:
                        os.system("start ms-clock:timers") 
                    except Exception as e:
                        print(f"Gagal membuka Clock app: {e}")
                threading.Thread(target=internal_timer_voice, args=(total_detik, f"{angka} {satuan}")).start()

        # 2. Perintah Vision (Manual) - PRIORITAS USER
        if any(x in user_lower for x in ["lihat layar", "apa ini", "lihat ini", "komentari layar", "lagi apa", "cek layar"]):
            print(">> SYSTEM: Menjalankan Vision Analysis...")
            threading.Thread(target=execute_vision).start()

        # 3. Deteksi Perintah Buka Program
        if "buka" in reply_lower:
            open_app(reply_lower) 
                
        # 4. Shutdown
        if "matikan komputer" in reply_lower:
             print(">> Azera: Bye bye tuan... (Shutdown 60s)")
             os.system("shutdown /s /t 60")

    except Exception as e:
        print(f"Error Check Command: {e}")

def execute_vision():
    # Prompt Vision (Azera Style)
    vision_prompt = """
    Kamu adalah Azera, waifu virtual yang sedang melihat layar komputer user.
    Jelaskan apa yang kamu lihat dengan gaya santai, singkat, dan sedikit 'flirty' atau 'tsundere' tergantung mood.
    Gunakan Bahasa Indonesia. Maksimal 1-2 kalimat.
    """
    try:
        # Panggil modul vision
        hasil = capture_and_analyze(vision_prompt)
        print(f"Azera Vision: {hasil}")
        
        # Output Suara & Subtitle
        write_subtitle(hasil)
        voicevox_tts(hasil, speaker_id=None) # Pakai None biar ikut Mood
    except Exception as e:
        print(f"Error Vision Task: {e}")

def auto_vision_loop():
    """Thread yang berjalan di latar belakang untuk memantau layar secara berkala."""
    print(">> Auto Vision Loop Started...")
    while True:
        try:
            # Scan hanya jika AI sedang tidak bicara
            if not is_speaking:
                # Prompt singkat untuk monitoring
                monitoring_prompt = "Apa aktivitas utama di layar ini? Jawab dalam 3-5 kata saja."
                hasil = capture_and_analyze(monitoring_prompt)
                
                # Keyword Trigger: Kalau ada kata menarik, Azera komentar
                keywords = ["game", "coding", "error", "youtube", "anime", "discord", "ngebut", "balap", "mobil", "desain"]
                if any(k in hasil.lower() for k in keywords):
                    print(f">> Vision Triggered: {hasil}")
                    
                    # Generate komentar Azera based on trigger
                    response_prompt = f"User sedang {hasil}. Berikan komentar singkat dan lucu tentang ini sebagai Azera."
                    clean_reply, _ = process_emotion(ollama.generate(model='llama3', prompt=response_prompt)['response'])
                    
                    voicevox_tts(clean_reply, speaker_id=None)
            
            time.sleep(15) # Jeda scan 15 detik
        except Exception as e:
            print(f"Error Auto Vision: {e}")
            time.sleep(15)



# --- FUNGSI OLLAMA (PENGGANTI GEMINI) ---
def ollama_answer(user_input):
    global chat_history, is_speaking, last_interaction_time, praise_spam_count
    
    # Reset Timer Idle karena ada interaksi
    last_interaction_time = time.time()

    # LOGIKA ANTI-SPAM PUJIAN/MAAF
    # Agar user tidak bisa spam "maaf maaf maaf" buat naikin mood instan
    
    praise_words = ["pintar", "bagus", "cantik", "hebat", "makasih", "terima kasih", "good", "love", "sayang", "maaf", "sorry", "ampun"]
    is_praise = any(w in user_input.lower() for w in praise_words)

    if is_praise:
        if praise_spam_count >= 3:
            print(">> ANTI-SPAM: Pujian berlebihan diabaikan! (Mood tidak naik)")
            # Tambah counter biar makin susah kalau di-spam terus
            praise_spam_count += 2 
        else:
            print(">> TERDETEKSI PUJIAN/MAAF! (Mood +5)")
            update_mood(5)
            praise_spam_count += 1
    else:
        # Kalau ngobrol normal (bukan pujian), counter spam berkurang pelan-pelan
        if praise_spam_count > 0:
            praise_spam_count -= 1

    # Tandai AI sedang aktif sejak mulai berpikir
    is_speaking = True 
    print(">> Azera sedang berpikir... (Ollama Local)")
    
    try:
        # Tambahkan Konteks Waktu, Aplikasi, MOOD & LAGU
        time_ctx = get_time_context()
        app_ctx = check_running_apps()
        mood_ctx = get_mood_context()
        
        song_lyrics = get_song_lyrics(user_input)
        song_ctx = ""
        if song_lyrics:
            print(f">> DETEKSI PERMINTAAN LAGU: Injecting Lyrics...")
            song_ctx = f"""
            [SYSTEM DATA - SONG REQUEST DETECTED]
            User meminta menyanyikan lagu. Gunakan lirik ASLI berikut ini (JANGAN UBAH):
            "{song_lyrics}"
            Ingat: Gunakan tag [Sing] dan apit lirik dengan tanda bintang *.
            """
        
        # Inject info ke input user (sembunyi dari user)
        # Format ini memaksa LLM untuk sadar konteks tanpa user perlu mengetiknya
        contextual_input = f"""{user_input} 
        
        [SYSTEM DATA]
        Time: {time_ctx}
        User Activity: {app_ctx}
        {mood_ctx}
        {song_ctx}
        [INSTRUCTION: Jawablah sesuai dengan Mood & Karaktermu saat ini!]
        """

        chat_history.append({'role': 'user', 'content': contextual_input})
        response = ollama.chat(model=MODEL_NAME, messages=chat_history)
        
        # Cek apakah diinterupsi saat sedang berpikir
        if not is_speaking:
            print(">> Interupsi: Proses Ollama diabaikan.")
            return

        bot_reply = response['message']['content']
        # Simpan response asli ke history (agar konteks terjaga)
        chat_history.append({'role': 'assistant', 'content': bot_reply})
        
        # Jaga agar memory tidak meledak (hapus chat lama jika > 20 baris)
        if len(chat_history) > 20:
            chat_history = [chat_history[0]] + chat_history[-10:]

        print(f"Azera: {bot_reply}")
        
        # --- PERBAIKAN ALUR ---
        # 1. Proses Emosi & Bersihkan Teks dari [Tag]
        # Kita simpan teks bersihnya ke variabel baru + Deteksi Emosi
        clean_reply, detected_emotion = process_emotion(bot_reply) 

        # 2. Cek Perintah (Timer/App) menggunakan teks asli (biar regex kena pattern lengkap)
        check_commands(user_input, bot_reply)

        # 3. Update Subtitle (Terjemahan dari clean_reply)
        clean_subs_indo = translate_google(clean_reply, "auto", "id")
        write_subtitle(clean_subs_indo) 
        
        # 4. Suara (Kirim teks yang sudah bersih dari tag ke TTS, plus Emosi)
        # set speaker_id=None agar ikut logic Mood, dan pass emotion agar bisa Nyanyi
        voicevox_tts(clean_reply, speaker_id=None, emotion=detected_emotion) 
        
    except Exception as e:
        print(f"Error Ollama: {e}")
        print("Pastikan aplikasi Ollama sudah berjalan di background!")
        is_speaking = False

# --- FUNGSI VTS (EKSPRESI) ---
# Global variable untuk tracking waktu trigger terakhir
# Tujuannya: Mencegah reset "salah sasaran" kalau ada ekspresi baru yang muncul lebih cepat
last_expression_time = 0

# --- FUNGSI VTS (VERSI STABIL / THREAD-SAFE) ---
def trigger_vts_hotkey_sync(hotkey_name, auto_reset=False):
    """
    Fungsi ini menjalankan logika Async di dalam isolasi yang aman.
    Setiap trigger membuat koneksi baru agar tidak bentrok dengan loop lain.
    """
    async def async_logic():
        nonlocal auto_reset
        # Buat instance VTS baru setiap kali trigger (supaya thread-safe)
        local_vts = pyvts.vts(plugin_info=plugin_info)
        try:
            # 1. Connect
            await local_vts.connect()
            await local_vts.read_token()
            await local_vts.request_authenticate()
            
            # 2. Tentukan Base Expression (Wajah Default sesuai Mood)
            base_expr_name = "Neutral"
            if azera_mood >= 100: base_expr_name = "Happy"
            elif azera_mood < 40: base_expr_name = "Angry"
            
            # Jika user minta ekspresi yang SAMA dengan base mood, matikan auto_reset agar stay
            if hotkey_name.lower() == base_expr_name.lower():
                auto_reset = False

            # Reset selalu ke Neutral dulu untuk clear layer, baru apply base mood
            reset_target_name = "Neutral"

            # 3. Cari ID Hotkey
            resp = await local_vts.request(local_vts.vts_request.requestHotKeyList())
            hotkey_list = resp.get('data', {}).get('availableHotkeys', [])
            
            target_id = None
            reset_id = None
            base_expr_id = None
            
            for hk in hotkey_list:
                name_lower = hk['name'].lower()
                if name_lower == hotkey_name.lower(): target_id = hk['hotkeyID']
                if name_lower == reset_target_name.lower(): reset_id = hk['hotkeyID']
                if name_lower == base_expr_name.lower(): base_expr_id = hk['hotkeyID']
                    
            # 4. Tembak Hotkey Utama
            if target_id:
                current_time = time.time()
                global last_expression_time
                last_expression_time = current_time
                
                await local_vts.request(local_vts.vts_request.requestTriggerHotKey(target_id))
                print(f">> VTS API: Ekspresi '{hotkey_name}' aktif!")
                
                # --- AUTO RESET LOGIC (SMART) ---
                if auto_reset and hotkey_name.lower() != "neutral":
                    print(f">> DEBUG: Waiting {5}s for auto-reset '{hotkey_name}'...")
                    wait_duration = 5 
                    await asyncio.sleep(wait_duration) 
                    
                    if last_expression_time == current_time:
                         print(f">> DEBUG: Resetting '{hotkey_name}' now...")
                         # 1. Matikan Ekspresi Aktif (Toggle OFF)
                         # Asumsi VTS Hotkey adalah Toggle. Jadi kita tembak target_id lagi.
                         await local_vts.request(local_vts.vts_request.requestTriggerHotKey(target_id))
                         
                         # 2. Jika Base Mood BUKAN Neutral, Apply Base Mood (Misal: Angry)
                         # Kita tembak Base Mood untuk memastikan dia kembali aktif
                         if base_expr_name != "Neutral" and base_expr_id:
                             # Beri jeda dikit
                             await asyncio.sleep(0.5) 
                             # Note: Ini ada risiko kalau Angry sudah ON, dia malah jadi OFF.
                             # Tapi biasanya ekspresi reset itu behaviornya menimpa. Kita coba dulu.
                             await local_vts.request(local_vts.vts_request.requestTriggerHotKey(base_expr_id))
                             print(f">> VTS API: Re-Apply Base Mood Expression ({base_expr_name})")
                    else:
                        print(">> VTS API: Auto-Reset dibatalkan (Ada ekspresi baru).")
            else:
                print(f">> VTS API: Hotkey '{hotkey_name}' tidak ditemukan.")
                
            await local_vts.close()
            
        except Exception as e:
            # Error connection close biasa terjadi dan bisa diabaikan
            if "encoder" not in str(e): 
                print(f"VTS Error: {e}")

    try:
        asyncio.run(async_logic())
    except Exception as e:
        print(f"Gagal Trigger VTS: {e}")

def run_vts_expression(emotion_name, auto_reset=True):
    # Jalankan di thread terpisah agar suara tidak putus-putus
    t = threading.Thread(target=trigger_vts_hotkey_sync, args=(emotion_name, auto_reset))
    t.start()

def process_emotion(text):
    # Mapping kata kunci (Bahasa Inggris & Indo) ke Hotkey VTS
    emotion_keywords = {
        "happy": "Happy", "senang": "Happy", "gembira": "Happy",
        "angry": "Angry", "marah": "Angry", "kesal": "Angry",
        "sad": "Sad", "sedih": "Sad", "galau": "Sad",
        "neutral": "Neutral", "biasa": "Neutral", "datar": "Neutral",
        "blush": "Blush", "malu": "Blush", "merona": "Blush",
        "shock": "Shock", "kaget": "Shock", "terkejut": "Shock",
        "pouting": "Pouting", "ngambek": "Pouting", "cemberut": "Pouting",
        "love": "Love", "jatuh cinta": "Love", "sayang": "Love",
        "confuse": "Confuse", "bingung": "Confuse",
        "welcome": "Welcome",
        "tears": "Tears", "nangis": "Tears", "menangis": "Tears",
        # NEW: SINGING
        "sing": "Sing", "nyanyi": "Sing", "lagu": "Sing"
    }

    # Regex untuk mencari APAPUN yang ada di dalam kurung siku [...]
    matches = re.findall(r"\[(.*?)\]", text)
    
    clean_text = text
    detected_hotkey = None

    if matches:
        for content in matches:
            tag_content = content.lower()
            
            # Cek emosi 
            if detected_hotkey is None:
                for keyword, hotkey in emotion_keywords.items():
                    if keyword in tag_content:
                        detected_hotkey = hotkey
                        break
            
            # Hapus tag dari teks
            clean_text = clean_text.replace(f"[{content}]", "")

    clean_text = clean_text.strip()

    # Jika ketemu emosi, jalankan VTS
    if detected_hotkey:
        print(f">> Deteksi Emosi: {detected_hotkey}")
        threading.Thread(target=run_vts_expression, args=(detected_hotkey,)).start()
    else:
        # Default fallback logic
        default_expr = "Neutral"
        if azera_mood >= 100: default_expr = "Happy"
        elif azera_mood < 40: default_expr = "Angry"
        
        threading.Thread(target=run_vts_expression, args=(default_expr, False)).start()

    return clean_text, detected_hotkey

# --- FUNGSI SUARA (VOICEVOX) ---

def get_voice_parameters(mood):
    """Menentukan parameter suara berdasarkan mood"""
    # Speaker ID List (VoiceVox Default):
    # 2: Shikoku Metan (Normal/Sweet)
    # 6: Shikoku Metan (Angry/Tsun)
    # 9: Shikoku Metan (Whisper/Sad)
    
    if mood >= 80:
        # Mood Baik: Nada normal/manja, speed normal
        return {'speaker_id': 2, 'speedScale': 1.1, 'pitchScale': 0.15}
    elif mood >= 40:
        # Mood Normal: Standard
        return {'speaker_id': 2, 'speedScale': 1.0, 'pitchScale': 0.0}
    else:
        # Mood Buruk: Nada ketus (ID 6), bicara lebih cepat/tajam
        return {'speaker_id': 6, 'speedScale': 1.2, 'pitchScale': -0.05}

# --- MAIN LOOP ---

def trigger_talk_animation():
    """Membuat Azera sedikit maju/mengangguk saat bicara"""
    # Gunakan hotkey atau parameter injection untuk memajukan badan
    # Asumsi ada hotkey 'LeanIn' di VTube Studio, atau kita pakai expression
    # Note: Kalau belum ada hotkey 'LeanIn', user harus bikin di VTS dulu.
    # Tapi kita bisa pakai "Shock" atau "Happy" sekilas kalau mau. 
    # Idealnya LeanIn.
    # threading.Thread(target=run_vts_expression, args=("LeanIn",)).start()
    pass # Disabled sementara sampai User confirm punya hotkey 'LeanIn'

# Gunakan Google Translate DULU agar teks Indo -> Jepang
def voicevox_tts(text, speaker_id=None, emotion=None):
    global is_speaking
    # Jangan lanjut jika flag sudah dimatikan oleh interupsi
    if not is_speaking: return 
    
    try:
        # 1. Tentukan Parameter Suara dari Mood (Jika speaker_id tidak di-override)
        if speaker_id is None:
            voice_params = get_voice_parameters(azera_mood)
            speaker_id = voice_params['speaker_id']
            speed = voice_params['speedScale']
            pitch = voice_params['pitchScale']
        else:
            # Default fallback jika manual override
            speed = 1.0
            pitch = 0.0

        # OVERRIDE JIKA NYANYI
        if emotion == "Sing":
            print(">> Voice Mode: SINGING! (Slower & Higher)")
            speed = 0.85  # Lebih lambat biar kayak nyanyi/puisi
            pitch = 0.15  # Sedikit lebih tinggi
            speaker_id = 2 # Pakai suara manis

        # 2. Translate (KECUALI NYANYI, Kita coba kirim raw text biar gak berubah bahasa)
        # Risiko: VoiceVox mungkin tidak bisa baca karakter non-Jepang dengan benar.
        if emotion == "Sing":
            print(">> Skip Translation for Singing (Raw Text to VoiceVox)")
            text_jp = text
        else:
            text_jp = translate_google(text, "auto", "ja")
            
        if not is_speaking: return 

        # 3. Audio Query & Synthesis
        params = {'text': text_jp, 'speaker': speaker_id}
        res1 = requests.post('http://127.0.0.1:50021/audio_query', params=params)
        if not is_speaking: return 
        
        # Modifikasi query JSON untuk ubah Speed/Pitch
        query_data = res1.json()
        query_data['speedScale'] = speed
        query_data['pitchScale'] = pitch
        
        headers = {'Content-Type': 'application/json'}
        res2 = requests.post(f'http://127.0.0.1:50021/synthesis?speaker={speaker_id}', 
                             data=json.dumps(query_data), headers=headers)
        
        filename = "output.wav"
        with open(filename, "wb") as f:
            f.write(res2.content)
            
        if not is_speaking: return # Cek sebelum putar suara
        
        # Trigger animasi bicara (Move forward/Nod)
        trigger_talk_animation()

        # Putar secara ASYNC agar tidak mematikan loop
        winsound.PlaySound(filename, winsound.SND_FILENAME | winsound.SND_ASYNC)

        # Hitung durasi agar flag bisa direset otomatis (PENTING)
        if os.path.exists(filename):
             try:
                 with wave.open(filename, 'r') as f:
                    frames = f.getnframes()
                    rate = f.getframerate()
                    duration = frames / float(rate)
             except:
                 duration = 5.0 
             
             # Reset flag tepat setelah audio selesai
             threading.Timer(duration, set_speaking_false).start()
             
    except Exception as e:
        print(f"Error VOICEVOX: {e}")
        is_speaking = False

# --- FUNGSI AUDIO INPUT ---
def record_audio():
    # Karena pengecekan Interupsi sudah dipindah ke Main Loop, 
    # fungsi ini fokus murni merekam saja.
    
    # 2. LOGIKA REKAM NORMAL
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 44100
    WAVE_OUTPUT_FILENAME = "input.wav"
    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
    frames = []
    print("Recording... (Lepas SHIFT untuk berhenti)")
    while keyboard.is_pressed('RIGHT_SHIFT'):
        data = stream.read(CHUNK)
        frames.append(data)
    print("Stopped recording.")
    stream.stop_stream()
    stream.close()
    p.terminate()
    wf = wave.open(WAVE_OUTPUT_FILENAME, 'wb')
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(p.get_sample_size(FORMAT))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    wf.close()
    transcribe_audio("input.wav")

def transcribe_audio(file):
    r = sr.Recognizer()
    try:
        with sr.AudioFile(file) as source:
            audio_data = r.record(source)
            text = r.recognize_google(audio_data, language='id-ID')
            print(f"Dokutah: {text}")
            
            # --- PERBAIKAN: Jalankan AI di latar belakang agar Loop tidak macet ---
            threading.Thread(target=ollama_answer, args=(text,), daemon=True).start()
            
    except Exception as e:
        print("Gagal mendengar: {0}".format(e))

def voicevox_tts_priority(text, speaker_id=None):
    """Fungsi suara khusus untuk interupsi/alarm agar tidak masuk logika is_speaking"""
    try:
        if speaker_id is None:
             voice_params = get_voice_parameters(azera_mood)
             speaker_id = voice_params['speaker_id']
             speed = voice_params['speedScale']
             pitch = voice_params['pitchScale']
        else:
             speed = 1.0
             pitch = 0.0

        text_jp = translate_google(text, "auto", "ja")
        params = {'text': text_jp, 'speaker': speaker_id}
        res1 = requests.post('http://127.0.0.1:50021/audio_query', params=params)
        
        # Modifikasi query JSON untuk ubah Speed/Pitch
        query_data = res1.json()
        query_data['speedScale'] = speed
        query_data['pitchScale'] = pitch

        res2 = requests.post(f'http://127.0.0.1:50021/synthesis?speaker={speaker_id}', 
                             data=json.dumps(query_data), headers={'Content-Type': 'application/json'})
        
        filename = "priority_voice.wav"
        with open(filename, "wb") as f:
            f.write(res2.content)
            
        # Putar secara Async
        winsound.PlaySound(filename, winsound.SND_FILENAME | winsound.SND_ASYNC)
    except Exception as e:
        print(f"Error Priority TTS: {e}")

# --- VTS AUTONOMOUS LIFE WORKER ---
async def start_vts_life():
    # Gunakan instance global myvts atau buat baru
    # Disini kita buat baru agar safe di thread berbeda
    vts_life = pyvts.vts(plugin_info=plugin_info)
    try:
        await vts_life.connect()
        await vts_life.read_token()
        await vts_life.request_authenticate()
        # Jalankan loop gerakan otonom
        await idle_movement_loop(vts_life)
    except Exception as e:
        print(f"Error VTS Life: {e}")

def vts_thread_worker():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_vts_life())
    loop.run_forever()

# --- MAIN LOOP ---
if __name__ == "__main__":
    try:
        os.system('cls' if os.name == 'nt' else 'clear')
        
        # LOAD STATE SEBELUM MULAI
        load_state()
        
        print("=== AZERA ARKNIGHTS (OLLAMA LOCAL VERSION) ===")
        print("Standby... Tekan Shift Kanan untuk bicara.")

        # Cleanup file sisa
        if os.path.exists("azera_voice.wav"): 
            try: os.remove("azera_voice.wav")
            except: pass
        if os.path.exists("input.wav"): 
            try: os.remove("input.wav")
            except: pass
        if os.path.exists("output.wav"): 
            try: os.remove("output.wav")
            except: pass
        if os.path.exists("priority_voice.wav"): 
            try: os.remove("priority_voice.wav")
            except: pass



        # Jalankan Thread Idle Check
        threading.Thread(target=idle_check_loop, daemon=True).start()

        # Jalankan Thread Auto Vision
        threading.Thread(target=auto_vision_loop, daemon=True).start()

        # Jalankan Thread VTS Autonomous Life (Gerakan Otonom)
        threading.Thread(target=vts_thread_worker, daemon=True).start()

        # TRIGGER EKSPRESI AWAL SESUAI MOOD
        if azera_mood >= 100:
            print(f">> Start dengan Mood {azera_mood}: Wajah Bahagia!")
            threading.Thread(target=run_vts_expression, args=("Happy",)).start()
        elif azera_mood < 40:
            print(f">> Start dengan Mood {azera_mood}: Wajah Marah.")
            threading.Thread(target=run_vts_expression, args=("Angry", False)).start()
        else:
            print(f">> Start dengan Mood {azera_mood}: Wajah Normal.")
            threading.Thread(target=run_vts_expression, args=("Neutral",)).start()

        while True:
            if keyboard.is_pressed('RIGHT_SHIFT'):
                # 1. FIRST ACTION: STOP ALL SOUND
                stop_azera_voice()

                if is_speaking:
                    # KASUS 1: INTERUPSI
                    print(">> INTERUPSI TERDETEKSI! (Mood -10)")
                    
                    # TURUNKAN MOOD JIKA DIINTERUPSI
                    update_mood(-10)

                    is_speaking = False   
                    
                    # Tunggu tombol dilepas (Biar gak masuk ke rekam)
                    while keyboard.is_pressed('RIGHT_SHIFT'):
                        time.sleep(0.01)
                    
                    # Respon Ngambek
                    run_vts_expression("Pouting")
                    
                    # Teks subtitle menyesuaikan mood
                    if azera_mood < 40:
                        write_subtitle("Berisik! Jangan potong terus! (Mood Buruk)")
                        threading.Thread(target=voicevox_tts_priority, args=("Urusai! Saegiranaide yo!", 6)).start()
                    else:
                        write_subtitle("Ih! Jangan potong omongan Azera dong!")
                        threading.Thread(target=voicevox_tts_priority, args=("Mou! Saegiranaide!", 6)).start()
                    
                else:
                    # KASUS 2: REKAM NORMAL
                    time.sleep(0.1) 
                    if keyboard.is_pressed('RIGHT_SHIFT'):
                        # stop_azera_voice() sudah dipanggil di atas, jadi aman rekam
                        record_audio()
            
            time.sleep(0.01)
                
    except KeyboardInterrupt:
        print("Stopped")