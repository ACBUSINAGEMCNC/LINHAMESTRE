import os
import sys
import logging
import psycopg2
from dotenv import load_dotenv

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_database():
    """Verifica a estrutura do banco de dados."""
    conn = None
    try:
        load_dotenv()
        conn = psycopg2.connect(os.getenv('DATABASE_URL'))
        
        with conn.cursor() as cursor:
            # Verificar se a tabela maquina existe
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_name = 'maquina'
                );
            """)
            if not cursor.fetchone()[0]:
                logger.error("A tabela 'maquina' não existe no banco de dados!")
                return False
            
            # Verificar colunas da tabela maquina
            cursor.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'maquina'
                ORDER BY ordinal_position;
            """)
            
            logger.info("\nEstrutura da tabela 'maquina':")
            logger.info("-" * 80)
            logger.info(f"{'Nome da Coluna':<25} | {'Tipo de Dados':<20} | Pode ser Nulo?")
            logger.info("-" * 80)
            
            columns = cursor.fetchall()
            for col in columns:
                logger.info(f"{col[0]:<25} | {col[1]:<20} | {col[2]}")
            
            # Verificar se a coluna categoria_trabalho existe
            has_categoria = any(col[0] == 'categoria_trabalho' for col in columns)
            
            if has_categoria:
                logger.info("\n✅ A coluna 'categoria_trabalho' existe na tabela 'maquina'.")
            else:
                logger.error("\n❌ A coluna 'categoria_trabalho' NÃO foi encontrada na tabela 'maquina'!")
                
            # Verificar se a coluna imagem existe
            has_imagem = any(col[0] == 'imagem' for col in columns)
            
            if has_imagem:
                logger.info("\n✅ A coluna 'imagem' existe na tabela 'maquina'.")
            else:
                logger.error("\n❌ A coluna 'imagem' NÃO foi encontrada na tabela 'maquina'!")
                
            return has_categoria and has_imagem
                
    except Exception as e:
        logger.error(f"Erro ao verificar o banco de dados: {str(e)}")
        return False
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    logger.info("Verificando estrutura do banco de dados...")
    if check_database():
        logger.info("Verificação concluída com sucesso!")
    else:
        logger.error("Problemas encontrados durante a verificação.")
        sys.exit(1)
