import requests
import json
import sys
from deep_translator import GoogleTranslator

# Mengatur encoding output agar support karakter Jepang/Emoji di terminal
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf8', buffering=1)

# Fungsi DeepL X (Biarkan saja, siapa tahu nanti kamu butuh)
def translate_deeplx(text, source, target):
    url = "http://localhost:1188/translate"
    headers = {"Content-Type": "application/json"}
    
    # DeepLx biasanya butuh kode bahasa uppercase (ID, EN, JA)
    params = {
        "text": text,
        "source_lang": source.upper(),
        "target_lang": target.upper()
    }

    try:
        payload = json.dumps(params)
        response = requests.post(url, headers=headers, data=payload)
        data = response.json()
        translated_text = data['data']
        return translated_text
    except Exception as e:
        print(f"Error DeepLx: {e}")
        # Fallback ke Google jika DeepLx mati
        return translate_google(text, source, target)

# Fungsi Google Translate (DIPERBAIKI: Menggunakan deep-translator)
def translate_google(text, source, target):
    try:
        # deep-translator butuh kode bahasa lowercase (id, en, ja)
        target = target.lower()
        
        # Mapping manual kode bahasa jika perlu (menghindari error kode)
        if target == 'jp': target = 'ja'
        
        # Kita set source='auto' agar otomatis mendeteksi bahasa asal
        # Ini lebih aman daripada mengandalkan deteksi manual yang sering error
        translator = GoogleTranslator(source='auto', target=target)
        result = translator.translate(text)
        return result
    except Exception as e:
        print(f"Error translate: {e}")
        return text

# Fungsi Deteksi Bahasa
def detect_google(text):
    # Karena deep-translator sudah otomatis mendeteksi (auto),
    # kita tidak perlu fungsi deteksi yang berat.
    # Cukup return 'auto' agar fungsi translate_google di atas bekerja.
    return "auto"

if __name__ == "__main__":
    # Test area
    text = "aku tidak menyukaimu"
    print("Original:", text)
    
    # Test Google Translate (JA)
    res_ja = translate_google(text, "auto", "ja")
    print("Japanese:", res_ja)
    
    # Test Google Translate (EN)
    res_en = translate_google(text, "auto", "en")
    print("English:", res_en)