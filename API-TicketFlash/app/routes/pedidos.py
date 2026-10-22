from fastapi import APIRouter, HTTPException
from bson import ObjectId
from bson.errors import InvalidId
from app.database import eventos_col, pedidos_col, redis_client
from app.models.schemas import PedidoConfirmar
from datetime import datetime, timezone
import json

router = APIRouter(prefix="/pedidos", tags=["Pedidos"])


def serialize_doc(doc):
    """Converte ObjectId e datetime para formatos serializáveis."""
    if doc is None:
        return None
    for key, value in doc.items():
        if isinstance(value, ObjectId):
            doc[key] = str(value)
        elif isinstance(value, datetime):
            doc[key] = value.isoformat()
    return doc


@router.post("/confirmar", status_code=201)
def confirmar_pedido(dados: PedidoConfirmar):
    """
    Confirma um pedido a partir de uma reserva existente no Redis.

    Fluxo (Req. 10):
      1. Verifica se a reserva ainda existe no Redis.
         - Se não existe → 410 Gone (reserva expirou).
      2. Incrementa 'vendidos' do setor com $inc atômico,
         usando condição no filtro para não ultrapassar a capacidade.
      3. Grava o pedido no MongoDB com status "confirmado".
      4. Apaga a reserva do Redis.
      5. Bônus: publica mensagem no canal pedidos:confirmados via Pub/Sub.
    """
    usuario_id = dados.usuario_id
    evento_id = dados.evento_id
    setor_nome = dados.setor

    # ── 1) Verificar reserva no Redis ────────────────────────────────────
    reserva_key = f"reserva:{usuario_id}:{evento_id}:{setor_nome}"
    reserva_data = redis_client.get(reserva_key)

    if not reserva_data:
        raise HTTPException(
            status_code=410,
            detail="Reserva expirada ou inexistente. Nenhum pedido foi gravado."
        )

    reserva = json.loads(reserva_data)
    quantidade = reserva["quantidade"]
    preco_unitario = reserva["preco_unitario"]
    valor_total = round(quantidade * preco_unitario, 2)

    # ── 2) Validar IDs ──────────────────────────────────────────────────
    try:
        evento_obj_id = ObjectId(evento_id)
        usuario_obj_id = ObjectId(usuario_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="IDs inválidos")

    # ── 3) Buscar capacidade atual do setor ──────────────────────────────
    evento = eventos_col.find_one(
        {"_id": evento_obj_id, "setores.nome": setor_nome},
        {"setores.$": 1}
    )
    if not evento or not evento.get("setores"):
        raise HTTPException(status_code=404, detail="Evento ou setor não encontrado")

    setor_info = evento["setores"][0]
    capacidade = setor_info["capacidade"]

    # ── 4) $inc atômico com condição de capacidade no filtro ─────────────
    max_vendidos_permitido = capacidade - quantidade

    result = eventos_col.update_one(
        {
            "_id": evento_obj_id,
            "setores": {
                "$elemMatch": {
                    "nome": setor_nome,
                    "vendidos": {"$lte": max_vendidos_permitido}
                }
            }
        },
        {"$inc": {"setores.$.vendidos": quantidade}}
    )

    if result.modified_count == 0:
        raise HTTPException(
            status_code=400,
            detail="Capacidade do setor esgotada. Não foi possível confirmar o pedido."
        )

    # ── 5) Gravar pedido no MongoDB ──────────────────────────────────────
    pedido = {
        "usuarioId": usuario_obj_id,
        "eventoId": evento_obj_id,
        "setor": setor_nome,
        "quantidade": quantidade,
        "valorTotal": valor_total,
        "status": "confirmado",
        "criadoEm": datetime.now(timezone.utc)
    }
    pedidos_col.insert_one(pedido)

    # ── 6) Apagar reserva do Redis ───────────────────────────────────────
    redis_client.delete(reserva_key)

    # ── 7) Bônus — Pub/Sub ───────────────────────────────────────────────
    redis_client.publish("pedidos:confirmados", json.dumps({
        "pedido_id": str(pedido["_id"]),
        "usuario_id": usuario_id,
        "evento_id": evento_id,
        "setor": setor_nome,
        "quantidade": quantidade,
        "valor_total": valor_total
    }))

    return {
        "mensagem": "Pedido confirmado com sucesso",
        "pedido": serialize_doc(pedido)
    }


@router.get("/")
def listar_pedidos():
    """Lista todos os pedidos."""
    pedidos = [serialize_doc(p) for p in pedidos_col.find()]
    return pedidos


@router.get("/{pedido_id}")
def buscar_pedido(pedido_id: str):
    """Busca um pedido por ID."""
    try:
        obj_id = ObjectId(pedido_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="ID de pedido inválido")

    pedido = pedidos_col.find_one({"_id": obj_id})
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    return serialize_doc(pedido)
