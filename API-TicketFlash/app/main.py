"""
TicketFlash API — FastAPI Application

Plataforma de venda de ingressos com MongoDB (dados permanentes)
e Redis (cache, reservas temporárias, ranking e rate limiting).
"""

from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.database import eventos_col, usuarios_col, pedidos_col, redis_client
from app.routes import eventos, usuarios, reservas, pedidos


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Cria índices no MongoDB ao iniciar a aplicação (Req. 3)."""
    # Índice único em usuarios.email
    usuarios_col.create_index("email", unique=True)

    # Índice composto em eventos (categoria + data)
    eventos_col.create_index([("categoria", 1), ("data", 1)])

    # Índice em pedidos.usuarioId
    pedidos_col.create_index("usuarioId")

    print("📇 Índices criados com sucesso.")
    yield


app = FastAPI(
    title="TicketFlash API",
    description=(
        "API REST para a plataforma de ingressos TicketFlash. "
        "Usa MongoDB como banco principal e Redis para cache, "
        "reservas temporárias, ranking e controle de requisições."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ─── Registrar rotas ────────────────────────────────────────────────────────
app.include_router(eventos.router)
app.include_router(usuarios.router)
app.include_router(reservas.router)
app.include_router(pedidos.router)


@app.get("/", tags=["Health"])
def health_check():
    """Verifica se a API está online e os bancos acessíveis."""
    try:
        # Testar MongoDB
        from app.database import mongo_client
        mongo_client.admin.command("ping")
        mongo_status = "online"
    except Exception:
        mongo_status = "offline"

    try:
        # Testar Redis
        redis_client.ping()
        redis_status = "online"
    except Exception:
        redis_status = "offline"

    return {
        "status": "ok",
        "api": "TicketFlash",
        "mongodb": mongo_status,
        "redis": redis_status,
    }
