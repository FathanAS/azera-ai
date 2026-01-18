import google.generativeai as genai

# --- TEMPEL API KEY KAMU DI SINI ---
MY_KEY = "AIzaSyCmMJEoQsNuVn2rSBDbQQltO9kMTV1pwOI" 

genai.configure(api_key=MY_KEY)

print("Sedang menghubungi Google...")
print("Daftar model yang tersedia untuk kamu:")
print("-------------------------------------")

try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"NAMA: {m.name}")
except Exception as e:
    print(f"Error: {e}")

print("-------------------------------------")