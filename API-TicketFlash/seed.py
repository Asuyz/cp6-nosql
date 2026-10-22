"""
seed.py — Popula o MongoDB com dados iniciais para a plataforma TicketFlash.

Gera no mínimo:
  • 10 eventos (com setores embutidos)
  • 20 usuários
  • 50 pedidos

Uso: python seed.py
"""

import os
import random
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient
from bson import ObjectId

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
client = MongoClient(MONGO_URI)
db = client["ticketflash"]

# ─── Limpar coleções existentes ─────────────────────────────────────────────
db.eventos.drop()
db.usuarios.drop()
db.pedidos.drop()
print("🗑️  Coleções limpas.")

# ─── Dados auxiliares ───────────────────────────────────────────────────────
categorias = ["Show", "Festival", "Teatro", "Stand-up", "Esporte"]
cidades = [
    {"cidade": "São Paulo", "endereco": "Av. Paulista, 1000"},
    {"cidade": "Rio de Janeiro", "endereco": "Rua da Lapa, 200"},
    {"cidade": "Belo Horizonte", "endereco": "Praça da Liberdade, 50"},
    {"cidade": "Curitiba", "endereco": "Rua XV de Novembro, 300"},
    {"cidade": "Porto Alegre", "endereco": "Av. Borges de Medeiros, 500"},
    {"cidade": "Salvador", "endereco": "Pelourinho, s/n"},
    {"cidade": "Brasília", "endereco": "Esplanada dos Ministérios, 10"},
    {"cidade": "Recife", "endereco": "Av. Boa Viagem, 800"},
    {"cidade": "Fortaleza", "endereco": "Av. Beira Mar, 400"},
    {"cidade": "Manaus", "endereco": "Av. Eduardo Ribeiro, 150"},
]

nomes_eventos = [
    "Rock in Rio 2025",
    "Lollapalooza Brasil",
    "Festival de Jazz de SP",
    "Stand-up Comedy Night",
    "Clássicos do Teatro Nacional",
    "Sertanejo Universitário Fest",
    "Eletrônica Sunset",
    "MPB ao Vivo",
    "Copa e-Sports Brasil",
    "Cirque du Soleil — Amaluna",
    "Pagode na Praia",
    "Festival de Inverno",
]

atracoes_pool = [
    "Banda Alpha", "DJ Beta", "Grupo Gamma", "Cantor Delta",
    "Comediante Epsilon", "Orquestra Zeta", "Dupla Eta", "MC Theta",
    "Ator Iota", "Bailarina Kappa", "Rapper Lambda", "Violinista Mu",
    "Pianista Nu", "Banda Omicron", "DJ Pi", "Cantor Rho",
]

nomes_usuarios = [
    "Ana Silva", "Bruno Costa", "Carla Oliveira", "Daniel Santos",
    "Elena Ferreira", "Felipe Almeida", "Gabriela Lima", "Henrique Souza",
    "Isabela Pereira", "João Rodrigues", "Karen Martins", "Lucas Araújo",
    "Mariana Gomes", "Nicolas Barbosa", "Olívia Ribeiro", "Paulo Cardoso",
    "Rafaela Nunes", "Samuel Correia", "Tatiana Mendes", "Vinícius Rocha",
    "Yasmin Teixeira", "Wesley Carvalho",
]


def gerar_setores():
    """Gera de 2 a 4 setores com preços e capacidades variados."""
    setores_base = [
        {"nome": "Pista", "preco": round(random.uniform(80, 200), 2), "capacidade": random.randint(200, 500)},
        {"nome": "VIP", "preco": round(random.uniform(250, 600), 2), "capacidade": random.randint(50, 150)},
        {"nome": "Camarote", "preco": round(random.uniform(500, 1200), 2), "capacidade": random.randint(20, 80)},
        {"nome": "Arquibancada", "preco": round(random.uniform(50, 120), 2), "capacidade": random.randint(300, 800)},
    ]
    qtd = random.randint(2, 4)
    escolhidos = random.sample(setores_base, qtd)
    for s in escolhidos:
        s["vendidos"] = random.randint(0, s["capacidade"] // 2)
    return escolhidos


# ─── Criar Eventos (mínimo 10) ─────────────────────────────────────────────
eventos = []
for i in range(12):
    local = random.choice(cidades)
    evento = {
        "nome": nomes_eventos[i] if i < len(nomes_eventos) else f"Evento Extra {i}",
        "categoria": random.choice(categorias),
        "data": (datetime.now(timezone.utc) + timedelta(days=random.randint(5, 120))).isoformat(),
        "local": {
            "cidade": local["cidade"],
            "endereco": local["endereco"],
        },
        "atracoes": random.sample(atracoes_pool, k=random.randint(2, 5)),
        "setores": gerar_setores(),
    }
    eventos.append(evento)

result_eventos = db.eventos.insert_many(eventos)
evento_ids = result_eventos.inserted_ids
print(f"✅ {len(evento_ids)} eventos inseridos.")

# ─── Criar Usuários (mínimo 20) ────────────────────────────────────────────
usuarios = []
for i, nome in enumerate(nomes_usuarios):
    usuario = {
        "nome": nome,
        "email": f"{nome.lower().replace(' ', '.')}@email.com",
        "cidade": random.choice(cidades)["cidade"],
        "dataCadastro": (datetime.now(timezone.utc) - timedelta(days=random.randint(1, 365))).isoformat(),
    }
    usuarios.append(usuario)

result_usuarios = db.usuarios.insert_many(usuarios)
usuario_ids = result_usuarios.inserted_ids
print(f"✅ {len(usuario_ids)} usuários inseridos.")

# ─── Criar Pedidos (mínimo 50) ─────────────────────────────────────────────
pedidos = []
status_opcoes = ["confirmado", "confirmado", "confirmado", "cancelado", "pendente"]

for _ in range(55):
    evento_id = random.choice(evento_ids)
    evento_doc = db.eventos.find_one({"_id": evento_id})
    setor = random.choice(evento_doc["setores"])
    quantidade = random.randint(1, 4)
    valor_total = round(quantidade * setor["preco"], 2)

    pedido = {
        "usuarioId": random.choice(usuario_ids),
        "eventoId": evento_id,
        "setor": setor["nome"],
        "quantidade": quantidade,
        "valorTotal": valor_total,
        "status": random.choice(status_opcoes),
        "criadoEm": (datetime.now(timezone.utc) - timedelta(days=random.randint(0, 30))).isoformat(),
    }
    pedidos.append(pedido)

result_pedidos = db.pedidos.insert_many(pedidos)
print(f"✅ {len(result_pedidos.inserted_ids)} pedidos inseridos.")

# ─── Criar Índices (Req. 3) ────────────────────────────────────────────────
db.usuarios.create_index("email", unique=True)
print("📇 Índice único criado: usuarios.email")

db.eventos.create_index([("categoria", 1), ("data", 1)])
print("📇 Índice composto criado: eventos(categoria, data)")

db.pedidos.create_index("usuarioId")
print("📇 Índice criado: pedidos.usuarioId")

# ─── Explain do índice composto (Req. 3) ────────────────────────────────────
explain_result = db.eventos.find(
    {"categoria": "Show", "data": {"$gte": datetime.now(timezone.utc).isoformat()}}
).explain()

import json
print("\n📊 explain() — Consulta usando índice composto (categoria + data):")
winning_plan = explain_result.get("queryPlanner", {}).get("winningPlan", {})
print(json.dumps(winning_plan, indent=2, default=str))

print("\n🎉 Seed concluído com sucesso!")
print(f"   Eventos: {len(evento_ids)}")
print(f"   Usuários: {len(usuario_ids)}")
print(f"   Pedidos: {len(result_pedidos.inserted_ids)}")
