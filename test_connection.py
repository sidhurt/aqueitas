import psycopg2
from psycopg2.extras import RealDictCursor

def verify_vault():
    try:
        # Connect to the local sovereign vault with credentials from docker-compose.yml
        conn = psycopg2.connect(
            dbname="aqueitas_db",
            user="aqueitas_admin",
            password="sovereign_password_123",
            host="127.0.0.1",
            port="5433"
        )
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Verify pgvector extension
        cur.execute("SELECT extname FROM pg_extension WHERE extname = 'vector';")
        extension = cur.fetchone()
        
        # Verify tables
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")
        tables = [row['table_name'] for row in cur.fetchall()]
        
        print(f"--- Vault Status ---")
        print(f"pgvector Active: {bool(extension)}")
        print(f"Tables Found: {', '.join(tables)}")
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"CONNECTION FAILED: {e}")

if __name__ == "__main__":
    verify_vault()
