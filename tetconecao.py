from sqlalchemy import create_engine

DATABASE_URL = "postgresql+psycopg2://postgres.rxkuxdtpmrpfrufvnjxa:hsZQIE3QiOdprHB5@aws-0-sa-east-1.pooler.supabase.com:6543/postgres"

try:
    engine = create_engine(DATABASE_URL)
    conn = engine.connect()
    print("✅ Conexão bem-sucedida!")
except Exception as e:
    print("Erro de conexão:", e)
