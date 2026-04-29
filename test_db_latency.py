import psycopg2
import time

# Conexão direta (sem pooler)
DATABASE_URL = "postgresql://postgres.rxkuxdtpmrpfrufvnjxa:hsZQIE3QiOdprHB5@aws-0-sa-east-1.supabase.com:5432/postgres"

print("Testando conexão direta com Supabase (port 5432)...")
print(f"URL: {DATABASE_URL}")

start = time.time()
try:
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=10)
    end = time.time()
    latency = (end - start) * 1000
    print(f"✅ Conexão bem-sucedida! Latência: {latency:.2f}ms")
    
    # Test query simples
    start_query = time.time()
    cursor = conn.cursor()
    cursor.execute("SELECT 1")
    cursor.fetchone()
    end_query = time.time()
    query_time = (end_query - start_query) * 1000
    print(f"✅ Query SELECT 1: {query_time:.2f}ms")
    
    cursor.close()
    conn.close()
except Exception as e:
    end = time.time()
    latency = (end - start) * 1000
    print(f"❌ Erro após {latency:.2f}ms: {e}")
