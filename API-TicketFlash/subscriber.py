"""
subscriber.py — Bônus: Assinante Pub/Sub do Redis

Escuta o canal 'pedidos:confirmados' e imprime cada mensagem
recebida no console.

Uso: python subscriber.py
"""

import os
import json
import redis

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
pubsub = r.pubsub()
pubsub.subscribe("pedidos:confirmados")

print("📡 Assinante Pub/Sub iniciado. Escutando canal 'pedidos:confirmados'...")
print("   (Pressione Ctrl+C para sair)\n")

try:
    for message in pubsub.listen():
        if message["type"] == "message":
            data = json.loads(message["data"])
            print("🎫 Novo pedido confirmado!")
            print(f"   Pedido ID:  {data.get('pedido_id')}")
            print(f"   Usuário ID: {data.get('usuario_id')}")
            print(f"   Evento ID:  {data.get('evento_id')}")
            print(f"   Setor:      {data.get('setor')}")
            print(f"   Quantidade: {data.get('quantidade')}")
            print(f"   Valor Total: R$ {data.get('valor_total', 0):.2f}")
            print("-" * 50)
except KeyboardInterrupt:
    print("\n👋 Assinante encerrado.")
finally:
    pubsub.unsubscribe()
