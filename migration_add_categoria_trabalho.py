import os
import sqlite3
import logging
from dotenv import load_dotenv

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Carregar variáveis de ambiente
load_dotenv()

def add_categoria_trabalho_column():
    """Adiciona a coluna categoria_trabalho à tabela maquina se ela não existir."""
    try:
        # Obter caminho do banco de dados
        db_dir = os.getenv('DB_DIR', os.path.dirname(os.path.abspath(__file__)))
        db_path = os.path.join(db_dir, 'database.db')
        
        logger.info(f"Conectando ao banco de dados: {db_path}")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Verificar se a coluna já existe
        cursor.execute("PRAGMA table_info(maquina)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'categoria_trabalho' not in columns:
            logger.info("Coluna 'categoria_trabalho' não encontrada. Adicionando à tabela 'maquina'...")
            cursor.execute("ALTER TABLE maquina ADD COLUMN categoria_trabalho VARCHAR(50)")
            conn.commit()
            logger.info("Coluna 'categoria_trabalho' adicionada com sucesso!")
        else:
            logger.info("Coluna 'categoria_trabalho' já existe na tabela 'maquina'.")
        
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Erro ao adicionar coluna 'categoria_trabalho': {str(e)}")
        return False

if __name__ == "__main__":
    logger.info("Iniciando migração para adicionar coluna 'categoria_trabalho' à tabela 'maquina'...")
    success = add_categoria_trabalho_column()
    if success:
        logger.info("Migração concluída com sucesso!")
    else:
        logger.error("Falha na migração!")
