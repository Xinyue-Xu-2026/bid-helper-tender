from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import config
from app.db import Database
from app.routers import assets, compliance, export, materials, projects, requirements, settings, templates, write

app = FastAPI(title="投标Web平台")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite 开发服务器
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    config.ensure_dirs()
    Database().init_schema()


app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(requirements.router, prefix="/api", tags=["requirements"])
app.include_router(export.router, prefix="/api", tags=["export"])
app.include_router(compliance.router, prefix="/api", tags=["compliance"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(assets.router, prefix="/api/assets", tags=["assets"])
app.include_router(templates.router, prefix="/api/templates", tags=["templates"])
app.include_router(write.router, prefix="/api", tags=["write"])
app.include_router(materials.router, prefix="/api", tags=["materials"])

_dist = config.APP_ROOT / "frontend" / "dist"
if _dist.exists():
    app.mount("/assets", StaticFiles(directory=str(_dist / "assets")), name="assets")

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str):
        candidate = _dist / full_path
        if full_path and candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(_dist / "index.html"))
