from motor.motor_asyncio import AsyncIOMotorClient
from .config import settings

client = AsyncIOMotorClient(settings.mongodb_uri)
database = client[settings.mongodb_database]


def get_database():
    return database


async def close_database():
    client.close()