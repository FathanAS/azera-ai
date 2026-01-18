import pyautogui
from PIL import Image
import io
import ollama

def capture_and_analyze(prompt="Apa yang sedang saya lakukan di layar ini? Jelaskan singkat."):
    print(">> Azera sedang melihat layar...")
    
    # 1. Tangkap Layar
    screenshot = pyautogui.screenshot()
    
    # 2. Convert ke Bytes (agar bisa dikirim ke Ollama)
    with io.BytesIO() as output:
        screenshot.save(output, format="PNG")
        img_bytes = output.getvalue()

    try:
        # 3. Kirim ke Ollama menggunakan model LLAVA (Vision Model)
        response = ollama.generate(
            model='llava',
            prompt=prompt,
            images=[img_bytes]
        )
        return response['response']
    except Exception as e:
        return f"Gagal melihat layar: {e}"