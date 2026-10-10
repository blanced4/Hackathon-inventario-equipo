"""
Punto de entrada principal del Servicio de Inventario Inteligente.

Ejecutar con:
    uvicorn main:app --reload --port 8000
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.inventory import router as inventory_router


import asyncio
import logging
from app.services.event_consumer import start_consumer, stop_consumer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
)
logger = logging.getLogger("main")


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestiona recursos que requieren ciclo de vida (Kafka, DB pool, etc.)."""
    logger.info("Iniciando background consumer en lifespan...")
    consumer_task = asyncio.create_task(start_consumer(), name="kafka-consumer-task")
    yield
    logger.info("Deteniendo background consumer en shutdown...")
    await stop_consumer()


# ── Instancia de la aplicación ────────────────────────────────────────────────
app = FastAPI(
    title="Servicio de Inventario Inteligente del Taller",
    description=(
        "API REST para gestión de inventario de husillos y motores industriales. "
        "Consume eventos de Redpanda y publica en inventory.events."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js dev server
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routers Oficiales (OpenAPI) ───────────────────────────────────────────────
app.include_router(inventory_router)


from fastapi.responses import FileResponse, HTMLResponse
import os

DASHBOARD_HTML_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "frontend", "index.html")
)


# ── Endpoints base ────────────────────────────────────────────────────────────
@app.get("/health", tags=["ops"], summary="Health check")
async def health_check():
    """Verifica que el servicio está levantado y accesible."""
    return {
        "status": "ok",
        "service": "inventory",
        "env": settings.APP_ENV,
    }


@app.get("/", tags=["ui"], include_in_schema=False)
@app.get("/dashboard", tags=["ui"], summary="Panel de Control Industrial (Dashboard)")
async def get_dashboard():
    """Sirve la interfaz web Cyber-Industrial Kraftwerk SpindleOS."""
    if os.path.exists(DASHBOARD_HTML_PATH):
        return FileResponse(DASHBOARD_HTML_PATH, media_type="text/html")
    return HTMLResponse("<h1>Dashboard no encontrado</h1>", status_code=404)

