from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ---------- Evento ----------
class LocalModel(BaseModel):
    cidade: str
    endereco: str


class SetorModel(BaseModel):
    nome: str
    preco: float
    capacidade: int
    vendidos: int = 0


class EventoCreate(BaseModel):
    nome: str
    categoria: str
    data: str
    local: LocalModel
    atracoes: List[str]
    setores: List[SetorModel]


class EventoUpdate(BaseModel):
    nome: Optional[str] = None
    categoria: Optional[str] = None
    data: Optional[str] = None
    local: Optional[LocalModel] = None
    atracoes: Optional[List[str]] = None
    setores: Optional[List[SetorModel]] = None


# ---------- Usuário ----------
class UsuarioCreate(BaseModel):
    nome: str
    email: str
    cidade: str


class UsuarioUpdate(BaseModel):
    nome: Optional[str] = None
    email: Optional[str] = None
    cidade: Optional[str] = None


# ---------- Reserva ----------
class ReservaCreate(BaseModel):
    usuario_id: str
    evento_id: str
    setor: str
    quantidade: int = Field(ge=1)


# ---------- Pedido ----------
class PedidoConfirmar(BaseModel):
    usuario_id: str
    evento_id: str
    setor: str
