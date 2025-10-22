import sys
import os
from pathlib import Path
from fastapi import FastAPI

# === 경로 문제 방지 (src 폴더를 import 경로에 추가) ===
current_dir = Path(__file__).parent
src_dir = current_dir.parent

if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))


# === FastAPI 앱 생성 ===
app = FastAPI(title="BDSP Sub Backend API", version="1.0")

# === 라우터 import ===
from .baseRoutes import router as base_router
from .interfacesRoutes import router as interfaces_router
from .modalityRoutes import router as modality_router



# === 라우터 entrypoint ===
app.include_router(base_router, prefix="/api", tags=["base"])
app.include_router(interfaces_router, prefix="/api/interfaces", tags=["interfaces"])
app.include_router(modality_router, prefix="/api/modality", tags=["modality"])
