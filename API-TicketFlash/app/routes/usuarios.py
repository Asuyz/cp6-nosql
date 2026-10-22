from fastapi import APIRouter, HTTPException
from bson import ObjectId
from bson.errors import InvalidId
from app.database import usuarios_col
from app.models.schemas import UsuarioCreate, UsuarioUpdate
from datetime import datetime, timezone

router = APIRouter(prefix="/usuarios", tags=["Usuários"])


def serialize_doc(doc):
    """Converte ObjectId e datetime para formatos serializáveis."""
    if doc is None:
        return None
    doc["_id"] = str(doc["_id"])
    if "dataCadastro" in doc and isinstance(doc["dataCadastro"], datetime):
        doc["dataCadastro"] = doc["dataCadastro"].isoformat()
    return doc


@router.post("/", status_code=201)
def criar_usuario(usuario: UsuarioCreate):
    """Cria um novo usuário. O email deve ser único (índice único)."""
    # Verificar email duplicado
    if usuarios_col.find_one({"email": usuario.email}):
        raise HTTPException(status_code=409, detail="Email já cadastrado")

    doc = usuario.model_dump()
    doc["dataCadastro"] = datetime.now(timezone.utc)
    result = usuarios_col.insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    doc["dataCadastro"] = doc["dataCadastro"].isoformat()
    return doc


@router.get("/")
def listar_usuarios():
    """Lista todos os usuários."""
    usuarios = [serialize_doc(u) for u in usuarios_col.find()]
    return usuarios


@router.get("/{usuario_id}")
def buscar_usuario(usuario_id: str):
    """Busca um usuário por ID."""
    try:
        obj_id = ObjectId(usuario_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="ID de usuário inválido")

    usuario = usuarios_col.find_one({"_id": obj_id})
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return serialize_doc(usuario)


@router.put("/{usuario_id}")
def atualizar_usuario(usuario_id: str, usuario: UsuarioUpdate):
    """Atualiza dados de um usuário."""
    try:
        obj_id = ObjectId(usuario_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="ID de usuário inválido")

    update_data = {k: v for k, v in usuario.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="Nenhum campo para atualizar")

    # Se estiver atualizando email, verificar duplicidade
    if "email" in update_data:
        existing = usuarios_col.find_one({
            "email": update_data["email"],
            "_id": {"$ne": obj_id}
        })
        if existing:
            raise HTTPException(status_code=409, detail="Email já cadastrado")

    result = usuarios_col.update_one({"_id": obj_id}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    usuario_atualizado = usuarios_col.find_one({"_id": obj_id})
    return serialize_doc(usuario_atualizado)


@router.delete("/{usuario_id}")
def remover_usuario(usuario_id: str):
    """Remove um usuário."""
    try:
        obj_id = ObjectId(usuario_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="ID de usuário inválido")

    result = usuarios_col.delete_one({"_id": obj_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    return {"mensagem": "Usuário removido com sucesso"}
