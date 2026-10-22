from fastapi import APIRouter, HTTPException
from bson import ObjectId
from bson.errors import InvalidId
from app.database import eventos_col, redis_client
from app.models.schemas import ReservaCreate
import json

router = APIRouter(prefix="/reservas", tags=["Reservas"])


@router.post("/", status_code=201)
def criar_reserva(reserva: ReservaCreate):
    """
    Cria uma reserva temporária no Redis.

    Fluxo (Req. 10):
      1. Req. 8 — Verifica rate limit (máx. 10 reservas/usuário/minuto).
      2. Confere no MongoDB se o setor tem vagas suficientes.
      3. Req. 6 — Cria a reserva no Redis com SET NX EX 600 (10 minutos).

    Retorna a chave da reserva e o TTL restante.
    """
    usuario_id = reserva.usuario_id
    evento_id = reserva.evento_id
    setor_nome = reserva.setor
    quantidade = reserva.quantidade

    # ── Req. 8 — Rate Limiting (INCR + EXPIRE) ──────────────────────────
    rate_key = f"limite:{usuario_id}"
    contador = redis_client.incr(rate_key)
    if contador == 1:
        redis_client.expire(rate_key, 60)

    if contador > 10:
        raise HTTPException(
            status_code=429,
            detail="Limite de reservas excedido (máx. 10 por minuto). Tente novamente em breve."
        )

    # ── Validar evento e setor no MongoDB ────────────────────────────────
    try:
        obj_id = ObjectId(evento_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="ID de evento inválido")

    evento = eventos_col.find_one({"_id": obj_id})
    if not evento:
        raise HTTPException(status_code=404, detail="Evento não encontrado")

    setor = None
    for s in evento.get("setores", []):
        if s["nome"] == setor_nome:
            setor = s
            break

    if not setor:
        raise HTTPException(status_code=404, detail="Setor não encontrado neste evento")

    vagas_disponiveis = setor["capacidade"] - setor["vendidos"]
    if quantidade > vagas_disponiveis:
        raise HTTPException(
            status_code=400,
            detail=f"Vagas insuficientes. Disponíveis: {vagas_disponiveis}"
        )

    # ── Req. 6 — Reserva temporária (SET NX EX 600) ─────────────────────
    reserva_key = f"reserva:{usuario_id}:{evento_id}:{setor_nome}"
    reserva_data = json.dumps({
        "usuario_id": usuario_id,
        "evento_id": evento_id,
        "setor": setor_nome,
        "quantidade": quantidade,
        "preco_unitario": setor["preco"]
    })

    created = redis_client.set(reserva_key, reserva_data, nx=True, ex=600)
    if not created:
        raise HTTPException(
            status_code=409,
            detail="Já existe uma reserva ativa para este usuário/evento/setor"
        )

    ttl = redis_client.ttl(reserva_key)

    return {
        "mensagem": "Reserva criada com sucesso",
        "reserva_key": reserva_key,
        "ttl_segundos": ttl,
        "dados": {
            "usuario_id": usuario_id,
            "evento_id": evento_id,
            "setor": setor_nome,
            "quantidade": quantidade,
            "preco_unitario": setor["preco"]
        }
    }
