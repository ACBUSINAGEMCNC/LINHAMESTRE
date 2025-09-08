import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from urllib.parse import urlparse

# Carregar .env
load_dotenv()

db_url = os.getenv('DATABASE_URL')
print('DATABASE_URL encontrada:', bool(db_url))

if db_url:
    print('Tipo:', 'PostgreSQL' if 'postgresql' in db_url else 'SQLite')
    if 'postgresql' in db_url:
        parsed = urlparse(db_url)
        print('Host:', parsed.hostname)
        print('Port:', parsed.port)
        print('Username:', parsed.username)

        # Tentar conectar
        try:
            engine = create_engine(db_url)
            with engine.connect() as conn:
                result = conn.execute("SELECT 1")
                print('Conexão OK!')
        except Exception as e:
            print('Erro na conexão:', str(e))
    else:
        print('Usando SQLite - backup não usa Supabase')
else:
    print('DATABASE_URL não definida')
