import math
import random
import asyncio

async def idle_movement_loop(vts):
    """Membuat Azera bergerak halus secara otomatis (Swaying & Looking)"""
    print(">> Azera Autonomous Life: Aktif")
    t = 0
    while True:
        t += 0.05
        # 1. Goyang halus (Swaying) menggunakan gelombang Sinus
        body_z = math.sin(t * 0.5) * 5  # Goyang kiri-kanan pelan
        face_x = math.sin(t * 0.2) * 10 # Menoleh pelan
        
        # 2. Sesekali melirik secara acak
        eye_x = random.uniform(-0.5, 0.5) if random.random() > 0.95 else 0
        
        # Kirim ke VTube Studio
        # Parameter standar Live2D: ParamFaceAngleX, ParamBodyAngleZ, dll.
        params = [
            {"id": "ParamFaceAngleX", "value": face_x},
            {"id": "ParamBodyAngleZ", "value": body_z},
            {"id": "ParamEyeBallX", "value": eye_x}
        ]
        
        for p in params:
            await vts.request(vts.vts_request.requestParameterValueAdd(
                parameterName=p["id"],
                value=p["value"]
            ))
            
        await asyncio.sleep(0.1) # Update setiap 100ms agar smooth