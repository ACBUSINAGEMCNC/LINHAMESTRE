import os
import logging
import sqlite3
from dotenv import load_dotenv

try:
	import psycopg2
	from psycopg2 import sql
except Exception:
	psycopg2 = None
	sql = None

try:
	import psycopg
except Exception:
	psycopg = None

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def migrate_postgres():
	conn = None
	try:
		load_dotenv()
		db_url = os.getenv('DATABASE_URL')
		if not db_url:
			logger.warning("DATABASE_URL não encontrada, pulando migração PostgreSQL")
			return False

		# psycopg2 não entende drivers no scheme (postgresql+psycopg:// / postgresql+psycopg2://)
		db_url = db_url.replace('postgresql+psycopg://', 'postgresql://')
		db_url = db_url.replace('postgresql+psycopg2://', 'postgresql://')
		if db_url.startswith('postgres://'):
			db_url = 'postgresql://' + db_url[len('postgres://'):]

		if psycopg2 is not None:
			conn = psycopg2.connect(db_url)
			conn.autocommit = True

			with conn.cursor() as cursor:
				cursor.execute(
					"""
					SELECT character_maximum_length
					FROM information_schema.columns
					WHERE table_name = 'pedido' AND column_name = 'nome_item';
					"""
				)
				row = cursor.fetchone()
				if not row:
					logger.warning("Coluna 'nome_item' não encontrada na tabela 'pedido' (PostgreSQL)")
					return False

				max_len = row[0]
				if max_len is None:
					logger.info("Coluna 'nome_item' já é tipo sem limite definido (PostgreSQL)")
					return True
				if int(max_len) >= 255:
					logger.info("Coluna 'nome_item' já possui tamanho >= 255 (PostgreSQL)")
					return True

				cursor.execute("ALTER TABLE pedido ALTER COLUMN nome_item TYPE VARCHAR(255);")
				logger.info("Coluna 'nome_item' alterada para VARCHAR(255) na tabela 'pedido' (PostgreSQL)")
				return True

		if psycopg is not None:
			with psycopg.connect(db_url, autocommit=True) as conn3:
				with conn3.cursor() as cursor:
					cursor.execute(
						"""
						SELECT character_maximum_length
						FROM information_schema.columns
						WHERE table_name = 'pedido' AND column_name = 'nome_item';
						"""
					)
					row = cursor.fetchone()
					if not row:
						logger.warning("Coluna 'nome_item' não encontrada na tabela 'pedido' (PostgreSQL)")
						return False

					max_len = row[0]
					if max_len is None:
						logger.info("Coluna 'nome_item' já é tipo sem limite definido (PostgreSQL)")
						return True
					if int(max_len) >= 255:
						logger.info("Coluna 'nome_item' já possui tamanho >= 255 (PostgreSQL)")
						return True

					cursor.execute("ALTER TABLE pedido ALTER COLUMN nome_item TYPE VARCHAR(255);")
					logger.info("Coluna 'nome_item' alterada para VARCHAR(255) na tabela 'pedido' (PostgreSQL)")
					return True

		logger.warning("Nem psycopg2 nem psycopg (v3) estão disponíveis, pulando migração PostgreSQL")
		return False

	except Exception as e:
		logger.error(f"Erro ao migrar PostgreSQL: {str(e)}")
		return False
	finally:
		if conn:
			conn.close()


def migrate_sqlite():
	conn = None
	try:
		db_dir = os.getenv('DB_DIR', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
		db_path = os.path.join(db_dir, 'database.db')

		if not os.path.exists(db_path):
			logger.warning(f"Banco de dados SQLite não encontrado em {db_path}, pulando migração")
			return False

		conn = sqlite3.connect(db_path)
		cursor = conn.cursor()
		cursor.execute("PRAGMA table_info(pedido)")
		columns = [column[1] for column in cursor.fetchall()]
		if 'nome_item' not in columns:
			logger.warning("Coluna 'nome_item' não encontrada na tabela 'pedido' (SQLite)")
			return False

		logger.info("SQLite não aplica limite de VARCHAR(100) de forma restritiva. Nenhuma ação necessária.")
		return True

	except Exception as e:
		logger.error(f"Erro ao migrar SQLite: {str(e)}")
		return False
	finally:
		if conn:
			conn.close()


def run_migration():
	logger.info("Iniciando migração para ajustar tamanho da coluna 'pedido.nome_item'...")
	pg_success = migrate_postgres()
	sqlite_success = migrate_sqlite()
	if pg_success or sqlite_success:
		logger.info("Migração concluída com sucesso!")
		return True
	logger.error("Falha na migração!")
	return False


if __name__ == "__main__":
	run_migration()
