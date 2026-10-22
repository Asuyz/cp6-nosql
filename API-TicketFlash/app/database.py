import os
from pymongo import MongoClient
import redis

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

# MongoDB
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["ticketflash"]

# Coleções
eventos_col = db["eventos"]
usuarios_col = db["usuarios"]
pedidos_col = db["pedidos"]

# Redis
redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=0,
    decode_responses=True
)
