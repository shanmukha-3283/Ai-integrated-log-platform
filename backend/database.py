from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING, TEXT
from typing import Any, Optional
from models import LogDocument
from os import getenv
import asyncio

class Database:
    client: Optional[AsyncIOMotorClient] = None
    db: Any = None

    def __init__(self, uri: Optional[str] = None):
        # Fallback through common URI env vars
        self.uri = uri or getenv("MONGO_URI") or getenv("MONGODB_URL") or getenv("MONGODB_URI") or "mongodb://localhost:27017"
        self.client = AsyncIOMotorClient(self.uri)
        self.db = self.client.get_database("log_platform")

    async def create_indexes(self):
        """Create optimized indexes for common queries"""
        try:
            # Compound index for time-series filtering
            await self.db.logs.create_index(
                [
                    ("service", ASCENDING),
                    ("timestamp", DESCENDING),
                    ("level", ASCENDING)
                ],
                name="service_timestamp_level_idx"
            )
            
            # TTL index for automatic log expiration
            await self.db.logs.create_index(
                [
                    ("timestamp", ASCENDING)
                ],
                expireAfterSeconds=60*60*24*30,  # 30 days
                name="ttl_timestamp_idx"
            )
            
            # Text index for full-text search
            await self.db.logs.create_index(
                [
                    ("message", TEXT)
                ],
                name="text_message_idx"
            )
        except Exception as e:
            print(f"Warning: Index creation skipped or failed: {e}")

    async def get_db(self):
        """Get the database connection"""
        return self.db

    async def get_jobs_collection(self):
        """Get the jobs collection"""
        return self.db.jobs

# Initialize database connection
db = Database()
# Note: In production, indexes are usually created via a migration script or on startup
# We avoid top-level asyncio.run here to prevent issues with existing event loops
async def init_db():
    await db.create_indexes()