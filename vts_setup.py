import asyncio
import pyvts
import json

# Settingan Standar
plugin_info = {
    "plugin_name": "Azera AI Controller",
    "developer": "Fathan",
    "authentication_token_path": "./token.txt"
}

myvts = pyvts.vts(plugin_info=plugin_info)

async def connect_auth():
    print("Menghubungkan ke VTube Studio...")
    try:
        await myvts.connect()
        print("Terhubung! Cek layar VTube Studio kamu sekarang.")
        print("Klik 'ALLOW' pada popup yang muncul di VTube Studio.")
        
        await myvts.request_authenticate_token()
        await myvts.request_authenticate()
        
        print("Sukses! Token tersimpan di 'token.txt'")
        
        # Simpan token ke file biar besok gak perlu minta izin lagi
        with open("token.txt", "w") as f:
            f.write(myvts.authentic_token)
            
        await myvts.close()
    except Exception as e:
        print(f"Gagal: {e}")
        print("Pastikan VTube Studio sudah terbuka dan 'Start API' sudah ON.")

if __name__ == "__main__":
    asyncio.run(connect_auth())