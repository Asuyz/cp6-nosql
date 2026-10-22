from fastapi import APIRouter, HTTPException, Query
from bson import ObjectId
from bson.errors import InvalidId
from app.database import eventos_col, redis_client
from app.models.schemas import EventoCreate, EventoUpdate
import json

router = APIRouter(prefix="/eventos", tags=["Eventos"])


def serialize_doc(doc):
    """Converte ObjectId para string em um documento MongoDB."""
    if doc is None:
        return None
    doc["_id"] = str(doc["_id"])
    return doc


# ─── Req. 7 — Ranking dos mais vistos (Sorted Set) ─────────────────────────
@router.get("/ranking")
def ranking_eventos():
    """Retorna o top 5 eventos mais visualizados (Redis Sorted Set)."""
    top5 = redis_client.zrevrange("ranking:eventos", 0, 4, withscores=True)
    resultado = []
    for evento_id, score in top5:
        try:
            evento = eventos_col.find_one({"_id": ObjectId(evento_id)})
        except InvalidId:
            continue
        if evento:
            resultado.append({
                "evento": serialize_doc(evento),
                "visualizacoes": int(score)
            })
    return resultado


# ─── Req. 4 — Agregação: Faturamento por evento ────────────────────────────
@router.get("/relatorios/faturamento")
def relatorio_faturamento():
    """
    Soma de valorTotal dos pedidos confirmados, do maior para o menor,
    com nome do evento via $lookup.
    """
    pipeline = [
        {"$match": {"status": "confirmado"}},
        {"$group": {
            "_id": "$eventoId",
            "faturamento_total": {"$sum": "$valorTotal"}
        }},
        {"$lookup": {
            "from": "eventos",
            "localField": "_id",
            "foreignField": "_id",
            "as": "evento"
        }},
        {"$unwind": "$evento"},
        {"$project": {
            "_id": 0,
            "evento_id": {"$toString": "$_id"},
            "evento_nome": "$evento.nome",
            "faturamento_total": 1
        }},
        {"$sort": {"faturamento_total": -1}}
    ]
    from app.database import pedidos_col
    resultado = list(pedidos_col.aggregate(pipeline))
    return resultado


# ─── Req. 4 — Agregação: Ocupação por setor de um evento ───────────────────
@router.get("/relatorios/ocupacao/{evento_id}")
def relatorio_ocupacao(evento_id: str):
    """
    Percentual vendido de cada setor de um evento,
    usando $unwind e $project.
    """
    try:
        obj_id = ObjectId(evento_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="ID de evento inválido")

    pipeline = [
        {"$match": {"_id": obj_id}},
        {"$unwind": "$setores"},
        {"$project": {
            "_id": 0,
            "evento_id": {"$toString": "$_id"},
            "setor": "$setores.nome",
            "capacidade": "$setores.capacidade",
            "vendidos": "$setores.vendidos",
            "percentual_ocupacao": {
                "$round": [
                    {"$multiply": [
                        {"$cond": [
                            {"$eq": ["$setores.capacidade", 0]},
                            0,
                            {"$divide": ["$setores.vendidos", "$setores.capacidade"]}
                        ]},
                        100
                    ]},
                    2
                ]
            }
        }}
    ]
    resultado = list(eventos_col.aggregate(pipeline))
    if not resultado:
        raise HTTPException(status_code=404, detail="Evento não encontrado")
    return resultado


# ─── Req. 2 — Criar evento ─────────────────────────────────────────────────
@router.post("/", status_code=201)
def criar_evento(evento: EventoCreate):
    """Cria um novo evento no MongoDB."""
    doc = evento.model_dump()
    # Converter setores para dicts com campo 'vendidos'
    for setor in doc.get("setores", []):
        setor.setdefault("vendidos", 0)
    result = eventos_col.insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    return doc


# ─── Req. 2 — Listar eventos (filtro por categoria e cidade) ───────────────
@router.get("/")
def listar_eventos(
    categoria: str = Query(None, description="Filtrar por categoria"),
    cidade: str = Query(None, description="Filtrar por cidade")
):
    """Lista eventos com filtros opcionais por categoria e cidade."""
    filtro = {}
    if categoria:
        filtro["categoria"] = {"$regex": categoria, "$options": "i"}
    if cidade:
        filtro["local.cidade"] = {"$regex": cidade, "$options": "i"}
    eventos = [serialize_doc(e) for e in eventos_col.find(filtro)]
    return eventos


# ─── Req. 2 + Req. 5 — Buscar evento por ID (com cache-aside) ─────────────
@router.get("/{evento_id}")
def buscar_evento(evento_id: str):
    """
    Busca um evento por ID.
    - Req. 5: Consulta o Redis antes do MongoDB (cache-aside, TTL 60s).
    - Req. 7: Incrementa o contador no Sorted Set de ranking.
    A resposta inclui o campo 'origem' ("cache" ou "banco").
    """
    try:
        obj_id = ObjectId(evento_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="ID de evento inválido")

    cache_key = f"evento:{evento_id}"

    # 1) Tentar cache
    cached = redis_client.get(cache_key)
    if cached:
        evento = json.loads(cached)
        evento["origem"] = "cache"
        # Req. 7 — incrementar ranking
        redis_client.zincrby("ranking:eventos", 1, evento_id)
        return evento

    # 2) Cache miss → MongoDB
    evento = eventos_col.find_one({"_id": obj_id})
    if not evento:
        raise HTTPException(status_code=404, detail="Evento não encontrado")

    evento = serialize_doc(evento)

    # 3) Gravar no cache com TTL de 60s
    redis_client.setex(cache_key, 60, json.dumps(evento, default=str))

    # Req. 7 — incrementar ranking
    redis_client.zincrby("ranking:eventos", 1, evento_id)

    evento["origem"] = "banco"
    return evento


# ─── Req. 2 + Req. 9 — Atualizar evento (com invalidação de cache) ────────
@router.put("/{evento_id}")
def atualizar_evento(evento_id: str, evento: EventoUpdate):
    """
    Atualiza campos de um evento.
    Req. 9: invalida a chave evento:{id} no Redis após update.
    """
    try:
        obj_id = ObjectId(evento_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="ID de evento inválido")

    update_data = {k: v for k, v in evento.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="Nenhum campo para atualizar")

    # Converter subdocumentos Pydantic para dict
    if "local" in update_data and hasattr(update_data["local"], "model_dump"):
        update_data["local"] = update_data["local"].model_dump()
    if "setores" in update_data:
        update_data["setores"] = [
            s.model_dump() if hasattr(s, "model_dump") else s
            for s in update_data["setores"]
        ]

    result = eventos_col.update_one({"_id": obj_id}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Evento não encontrado")

    # Req. 9 — Invalidar cache
    redis_client.delete(f"evento:{evento_id}")

    evento_atualizado = eventos_col.find_one({"_id": obj_id})
    return serialize_doc(evento_atualizado)


# ─── Req. 2 + Req. 9 — Remover evento (com invalidação de cache) ──────────
@router.delete("/{evento_id}")
def remover_evento(evento_id: str):
    """
    Remove um evento do MongoDB.
    Req. 9: invalida a chave evento:{id} no Redis após delete.
    """
    try:
        obj_id = ObjectId(evento_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="ID de evento inválido")

    result = eventos_col.delete_one({"_id": obj_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Evento não encontrado")

    # Req. 9 — Invalidar cache
    redis_client.delete(f"evento:{evento_id}")

    return {"mensagem": "Evento removido com sucesso"}
