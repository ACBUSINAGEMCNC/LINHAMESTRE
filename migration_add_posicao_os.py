#!/usr/bin/env python3
"""
Migração para adicionar coluna 'posicao' à tabela ordem_servico e inicializar
as posições por lista (status).

- Adiciona a coluna posicao (INTEGER DEFAULT 0)
- Inicializa posicoes sequenciais (1..N) por lista, ordenando por id
- Cria índice (status, posicao) para ordenação eficiente no Kanban
"""
import os
import sys
import sqlite3
from datetime import datetime
from sqlalchemy import create_engine, text
from dotenv import load_dotenv


# Carregar variáveis de ambiente (incluindo DATABASE_URL) do .env, se existir
load_dotenv()

def get_db_path():
    """Resolve o caminho do banco de dados SQLite existente."""
    # Preferir variável de ambiente DATABASE_URL (sqlite:///arquivo.db)
    db_url = os.getenv('DATABASE_URL')
    if db_url and db_url.startswith('sqlite:///'):
        path = db_url.replace('sqlite:///', '')
        if os.path.exists(path) and os.path.getsize(path) > 1000:
            print(f"Usando banco de dados via DATABASE_URL: {path}")
            return path

    # Fallbacks conhecidos no repo
    possible = [
        'acb_usinagem.db',
        'database.db',
        'acb_usinagem.db.bak.20250804193341',
        'acb_usinagem.db.bak.20250707204629',
        'acb_usinagem.db.bak.20250707204627',
    ]
    for p in possible:
        if os.path.exists(p) and os.path.getsize(p) > 1000:
            print(f"Usando banco de dados: {p}")
            return p

    raise FileNotFoundError('Nenhum banco de dados válido encontrado.')


def column_exists(cursor, table, column):
    cursor.execute(f"PRAGMA table_info({table})")
    cols = [row[1] for row in cursor.fetchall()]
    return column in cols


def index_exists(cursor, name):
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name=?",(name,))
    return cursor.fetchone() is not None


def inicializar_posicoes(conn):
    cur = conn.cursor()
    # Obter listas (status) existentes
    cur.execute("SELECT DISTINCT status FROM ordem_servico WHERE status IS NOT NULL")
    listas = [row[0] for row in cur.fetchall()]

    for lista in listas:
        # Selecionar IDs desta lista, ordenados por posicao atual (se houver) e id
        cur.execute(
            """
            SELECT id FROM ordem_servico
            WHERE status = ?
            ORDER BY COALESCE(posicao, 0) ASC, id ASC
            """,
            (lista,),
        )
        ids = [row[0] for row in cur.fetchall()]
        for i, oid in enumerate(ids, start=1):
            cur.execute(
                "UPDATE ordem_servico SET posicao = ? WHERE id = ?",
                (i, oid),
            )
    conn.commit()


def executar_migracao_postgres(db_url: str) -> bool:
    """Executa migração para PostgreSQL usando SQLAlchemy."""
    print(f"Conectando ao PostgreSQL: {db_url}")
    engine = create_engine(db_url)
    try:
        with engine.begin() as conn:
            # Adicionar coluna posicao
            print("Garantindo coluna 'posicao' em 'ordem_servico'...")
            conn.execute(text("""
                ALTER TABLE ordem_servico
                ADD COLUMN IF NOT EXISTS posicao integer DEFAULT 0 NOT NULL
            """))

            # Inicializar posições sequenciais por lista (status)
            print("Inicializando posições por lista (PostgreSQL)...")
            conn.execute(text("""
                UPDATE ordem_servico AS os
                SET posicao = seq.seq
                FROM (
                    SELECT id,
                           ROW_NUMBER() OVER (
                               PARTITION BY status
                               ORDER BY COALESCE(posicao, 0) ASC, id ASC
                           ) AS seq
                    FROM ordem_servico
                ) AS seq
                WHERE os.id = seq.id
            """))

            # Criar índice
            print("Criando índice (se não existir) em (status, posicao)...")
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_ordem_servico_status_posicao ON ordem_servico(status, posicao)"
            ))

        print("✅ Migração PostgreSQL concluída com sucesso.")
        return True
    except Exception as e:
        print(f"❌ Erro na migração PostgreSQL: {e}")
        return False


def executar_migracao():
    db_url = os.getenv('DATABASE_URL', '')

    # Se for Postgres, usar caminho específico
    if db_url.startswith('postgres://') or db_url.startswith('postgresql://'):
        return executar_migracao_postgres(db_url)

    # Caso contrário, assumir SQLite
    db_path = get_db_path()

    # Backup preventivo (apenas SQLite)
    backup_path = f"{db_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    try:
        import shutil
        shutil.copy2(db_path, backup_path)
        print(f"Backup criado: {backup_path}")
    except Exception as e:
        print(f"Aviso: não foi possível criar backup: {e}")

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    try:
        # Garantir existência da tabela
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ordem_servico'")
        if cur.fetchone() is None:
            raise RuntimeError("Tabela 'ordem_servico' não encontrada.")

        # Adicionar coluna posicao, se necessário
        if not column_exists(cur, 'ordem_servico', 'posicao'):
            print("Adicionando coluna 'posicao' à tabela 'ordem_servico'...")
            cur.execute("ALTER TABLE ordem_servico ADD COLUMN posicao INTEGER DEFAULT 0")
            conn.commit()
        else:
            print("Coluna 'posicao' já existe em 'ordem_servico'.")

        # Inicializar/normalizar posicoes sequenciais por lista
        print("Inicializando posições por lista...")
        inicializar_posicoes(conn)

        # Criar índice combinado para ordenar por lista e posição
        if not index_exists(cur, 'idx_ordem_servico_status_posicao'):
            print("Criando índice idx_ordem_servico_status_posicao...")
            cur.execute(
                "CREATE INDEX idx_ordem_servico_status_posicao ON ordem_servico(status, posicao)"
            )
            conn.commit()
        else:
            print("Índice idx_ordem_servico_status_posicao já existe.")

        print("✅ Migração (SQLite) concluída com sucesso.")
        return True
    except Exception as e:
        conn.rollback()
        print(f"❌ Erro na migração SQLite: {e}")
        return False
    finally:
        conn.close()


def verificar():
    try:
        db_url = os.getenv('DATABASE_URL', '')
        if db_url.startswith('postgres://') or db_url.startswith('postgresql://'):
            engine = create_engine(db_url)
            with engine.connect() as conn:
                print("Estrutura de ordem_servico (PostgreSQL):")
                cols = conn.execute(text(
                    """
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_name = 'ordem_servico'
                    ORDER BY ordinal_position
                    """
                )).fetchall()
                for name, dtype in cols:
                    print(f" - {name} ({dtype})")

                print("Resumo por lista:")
                rows = conn.execute(text(
                    "SELECT status, COUNT(*), MIN(posicao), MAX(posicao) FROM ordem_servico GROUP BY status ORDER BY status"
                )).fetchall()
                for row in rows:
                    print(f" - {row[0]}: {row[1]} cards, posicao {row[2]}..{row[3]}")
            return True
        else:
            db_path = get_db_path()
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(ordem_servico)")
            print("Estrutura de ordem_servico:")
            for col in cur.fetchall():
                print(f" - {col[1]} ({col[2]})")
            cur.execute("SELECT status, COUNT(*), MIN(posicao), MAX(posicao) FROM ordem_servico GROUP BY status")
            print("Resumo por lista:")
            for row in cur.fetchall():
                print(f" - {row[0]}: {row[1]} cards, posicao {row[2]}..{row[3]}")
            return True
    except Exception as e:
        print(f"Erro na verificação: {e}")
        return False


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'verify':
        verificar()
    else:
        if executar_migracao():
            print("\nVerificando...")
            verificar()
        else:
            sys.exit(1)
