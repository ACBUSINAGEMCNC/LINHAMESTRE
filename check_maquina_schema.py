import os
import logging
import psycopg2
from dotenv import load_dotenv

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_maquina_table():
    """Verifica a estrutura da tabela maquina."""
    conn = None
    try:
        load_dotenv()
        conn = psycopg2.connect(os.getenv('DATABASE_URL'))
        
        with conn.cursor() as cursor:
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
            
            for col in cursor.fetchall():
                logger.info(f"{col[0]:<25} | {col[1]:<20} | {col[2]}")
            
            # Verificar se a coluna categoria_trabalho existe
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = 'maquina' AND column_name = 'categoria_trabalho'
                );
            """)
            
            if cursor.fetchone()[0]:
                logger.info("\n✅ A coluna 'categoria_trabalho' existe na tabela 'maquina'.")
            else:
                logger.error("\n❌ A coluna 'categoria_trabalho' NÃO foi encontrada na tabela 'maquina'!")
                
            # Verificar se a coluna imagem existe
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = 'maquina' AND column_name = 'imagem'
                );
            """)
            
            if cursor.fetchone()[0]:
                logger.info("\n✅ A coluna 'imagem' existe na tabela 'maquina'.")
            else:
                logger.error("\n❌ A coluna 'imagem' NÃO foi encontrada na tabela 'maquina'!")
                
    except Exception as e:
        logger.error(f"Erro ao verificar a estrutura da tabela: {str(e)}")
        return False
    finally:
        if conn:
            conn.close()
    return True

if __name__ == "__main__":
    logger.info("Verificando estrutura da tabela 'maquina'...")
    check_maquina_table()
