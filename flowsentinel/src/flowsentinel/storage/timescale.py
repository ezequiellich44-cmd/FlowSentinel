import logging
import os
from typing import Optional, List, Any
import asyncpg

logger = logging.getLogger(__name__)

class TimescaleClient:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self) -> None:
        if not self.pool:
            self.pool = await asyncpg.create_pool(self.database_url)
            logger.info("Connected to TimescaleDB connection pool")

    async def close(self) -> None:
        if self.pool:
            await self.pool.close()
            logger.info("Closed TimescaleDB connection pool")
            self.pool = None

    async def execute(self, query: str, *args: Any) -> str:
        if not self.pool:
            raise RuntimeError("Database connection pool not initialized. Call connect() first.")
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetch(self, query: str, *args: Any) -> List[asyncpg.Record]:
        if not self.pool:
            raise RuntimeError("Database connection pool not initialized. Call connect() first.")
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def run_migrations(self, migration_file_path: str) -> None:
        """
        Loads and executes SQL migrations from a file path.
        """
        if not os.path.exists(migration_file_path):
            raise FileNotFoundError(f"Migration file not found at {migration_file_path}")
        
        with open(migration_file_path, "r", encoding="utf-8") as f:
            migration_sql = f.read()

        logger.info("Running database migrations from %s", migration_file_path)
        await self.execute(migration_sql)
        logger.info("Database migrations executed successfully")
