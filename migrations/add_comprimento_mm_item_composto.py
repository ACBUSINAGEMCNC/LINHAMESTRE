"""Migração para adicionar a coluna comprimento_mm à tabela item_composto.
Este script pode ser executado diretamente ou importado pelo app.py
para ser executado durante a inicialização da aplicação.
"""

import os
import logging
import sqlite3
from dotenv import load_dotenv

try:
	import psycopg2
except Exception:  # psycopg2 pode não estar instalado em ambiente SQLite local
	psycopg2 = None

try:
	import psycopg
except Exception:  # psycopg3 pode não estar instalado
	psycopg = None

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def migrate_postgres():
	"""Adiciona a coluna comprimento_mm à tabela item_composto no PostgreSQL."""
	conn = None
	try:
		load_dotenv()
		db_url = os.getenv('DATABASE_URL')
		if not db_url:
			logger.warning("DATABASE_URL não encontrada, pulando migração PostgreSQL")
			return False

		# Normalizar URLs SQLAlchemy (postgresql+psycopg://) para drivers nativos
		if db_url.startswith('postgresql+psycopg://'):
			db_url = 'postgresql://' + db_url[len('postgresql+psycopg://'):]
		elif db_url.startswith('postgres://'):
			db_url = 'postgresql://' + db_url[len('postgres://'):]

		close_cursor = False
		if psycopg is not None:
			conn = psycopg.connect(db_url)
			conn.autocommit = True
			cursor_ctx = conn.cursor()
			close_cursor = True
		elif psycopg2 is not None:
			conn = psycopg2.connect(db_url)
			conn.autocommit = True
			cursor_ctx = conn.cursor()
			close_cursor = True
		else:
			logger.warning("psycopg/psycopg2 não estão disponíveis, pulando migração PostgreSQL")
			return False

		try:
			cursor = cursor_ctx
			cursor.execute(
				"""
				SELECT column_name
				FROM information_schema.columns
				WHERE table_name = 'item_composto' AND column_name = 'comprimento_mm';
				"""
			)
			existing = {row[0] for row in cursor.fetchall()}

			if 'comprimento_mm' not in existing:
				cursor.execute(
					"""
					ALTER TABLE item_composto
					ADD COLUMN IF NOT EXISTS comprimento_mm DOUBLE PRECISION;
					"""
				)
				logger.info("Coluna 'comprimento_mm' adicionada com sucesso à tabela 'item_composto' (PostgreSQL)")

			return True
		finally:
			if close_cursor:
				cursor_ctx.close()

	except Exception as e:
		logger.error(f"Erro ao migrar PostgreSQL: {str(e)}")
		return False
	finally:
		if conn:
			conn.close()


def migrate_sqlite():
	"""Adiciona a coluna comprimento_mm à tabela item_composto no SQLite."""
	conn = None
	try:
		db_dir = os.getenv('DB_DIR', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
		db_path = os.path.join(db_dir, 'database.db')

		if not os.path.exists(db_path):
			logger.warning(f"Banco de dados SQLite não encontrado em {db_path}, pulando migração")
			return False

		conn = sqlite3.connect(db_path)
		cursor = conn.cursor()

		cursor.execute("PRAGMA table_info(item_composto)")
		columns = [column[1] for column in cursor.fetchall()]

		if 'comprimento_mm' not in columns:
			cursor.execute("ALTER TABLE item_composto ADD COLUMN comprimento_mm REAL")
			logger.info("Coluna 'comprimento_mm' adicionada com sucesso à tabela 'item_composto' (SQLite)")
			conn.commit()

		return True

	except Exception as e:
		logger.error(f"Erro ao migrar SQLite: {str(e)}")
		return False
	finally:
		if conn:
			conn.close()


def run_migration():
	logger.info("Iniciando migração para adicionar coluna 'comprimento_mm'...")

	pg_success = migrate_postgres()
	sqlite_success = migrate_sqlite()

	if pg_success or sqlite_success:
		logger.info("Migração concluída com sucesso!")
		return True

	logger.error("Falha na migração!")
	return False


if __name__ == "__main__":
	run_migration()
