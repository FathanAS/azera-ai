import tkinter as tk
import os
import time

# Variable Global
last_modified = 0
current_display_task = None
chunks = []
chunk_index = 0

# Variable Drag Window
x_start = 0
y_start = 0

def split_text_into_chunks(text, max_words=10):
    words = text.split()
    for i in range(0, len(words), max_words):
        yield " ".join(words[i:i + max_words])

def display_next_chunk():
    global chunk_index, current_display_task
    
    if chunk_index < len(chunks):
        # 1. Tampilkan Chunk saat ini
        text_chunk = chunks[chunk_index]
        label.config(text=text_chunk)
        
        # 2. Hitung durasi baca untuk chunk ini
        # 500ms per kata + 1.5 detik buffer baca
        word_count = len(text_chunk.split())
        duration_ms = int((word_count * 500) + 1500)
        
        # 3. Jadwalkan chunk berikutnya
        chunk_index += 1
        current_display_task = root.after(duration_ms, display_next_chunk)
    else:
        # Jika sudah habis, kosongkan teks
        label.config(text="")
        current_display_task = None

def check_subtitle():
    global last_modified, current_display_task, chunks, chunk_index
    
    try:
        if os.path.exists("subtitle.txt"):
            # Cek timestamps file
            current_modified = os.path.getmtime("subtitle.txt")
            
            # Jika ada update baru dari file
            if current_modified != last_modified:
                try:
                    with open("subtitle.txt", "r", encoding="utf-8") as f:
                        text = f.read().strip()
                except Exception:
                    text = ""
                
                if text:
                    # Hentikan task display sebelumnya jika ada (biar gak bentrok)
                    if current_display_task:
                        root.after_cancel(current_display_task)
                    
                    # Reset variable
                    chunks = list(split_text_into_chunks(text, max_words=8)) # Max 8 kata per slide
                    chunk_index = 0
                    
                    # Mulai tampilkan dari chunk pertama
                    display_next_chunk()
                
                last_modified = current_modified
                
    except Exception as e:
        print(f"Error checking subtitle: {e}")

    # Loop fungsi ini setiap 500ms
    root.after(500, check_subtitle)

# --- FUNGSI DRAG WINDOW ---
def start_move(event):
    global x_start, y_start
    x_start = event.x
    y_start = event.y

def do_move(event):
    x = root.winfo_x() + (event.x - x_start)
    y = root.winfo_y() + (event.y - y_start)
    root.geometry(f"+{x}+{y}")

# --- SETUP GUI TKINTER ---
root = tk.Tk()
root.overrideredirect(True)
root.attributes("-topmost", True)
root.attributes("-transparentcolor", "black") 
root.config(bg='black')

# Ukuran window
root.geometry("1000x200+100+800") 

label = tk.Label(root, text="Waiting for Azera... (Drag me)", font=("Segoe UI", 24, "bold"), 
                 fg="white", bg="black", wraplength=950, cursor="fleur")
label.pack(expand=True, fill='both')

# Bind Mouse Events
root.bind("<Button-1>", start_move)
root.bind("<B1-Motion>", do_move)
label.bind("<Button-1>", start_move)
label.bind("<B1-Motion>", do_move)

# Mulai Loop
check_subtitle()
root.mainloop()