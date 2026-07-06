import os
import sys
import asyncpg
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def _log(msg: str) -> None:
    # stderr, not stdout: this module is also imported by the MCP stdio server,
    # where stdout carries the JSON-RPC protocol stream.
    print(msg, file=sys.stderr)

class Database:
    def __init__(self):
        self.pool = None

    async def connect(self):
        """Initialize the connection pool."""
        if not self.pool:
            try:
                self.pool = await asyncpg.create_pool(
                    DATABASE_URL,
                    min_size=1,
                    max_size=10
                )
                _log("Successfully connected to the Sovereign Vault via asyncpg.")
            except Exception as e:
                _log(f"Failed to connect to the database: {e}")
                raise

    async def disconnect(self):
        """Close the connection pool."""
        if self.pool:
            await self.pool.close()
            _log("Database connection pool closed.")

# Global database instance to be imported by FastAPI main application
db = Database()
