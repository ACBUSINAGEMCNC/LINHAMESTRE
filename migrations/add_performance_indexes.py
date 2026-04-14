"""
Adiciona índices para melhorar performance do Kanban e Apontamentos
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from models import db
from sqlalchemy import text, inspect
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = create_app()

def index_exists(inspector, table_name, index_name):
    """Verifica se um índice existe"""
    try:
        indexes = inspector.get_indexes(table_name)
        return any(idx['name'] == index_name for idx in indexes)
    except Exception:
        return False

def add_indexes():
    """Adiciona índices de performance"""
    with app.app_context():
        inspector = inspect(db.engine)
        
        indexes_to_create = [
            # Índices para OrdemServico (Kanban)
            {
                'table': 'ordem_servico',
                'name': 'idx_ordem_servico_status_posicao',
                'sql': 'CREATE INDEX IF NOT EXISTS idx_ordem_servico_status_posicao ON ordem_servico(status, posicao, id)'
            },
            # Índices para ApontamentoProducao
            {
                'table': 'apontamento_producao',
                'name': 'idx_apontamento_ordem_trabalho',
                'sql': 'CREATE INDEX IF NOT EXISTS idx_apontamento_ordem_trabalho ON apontamento_producao(ordem_servico_id, trabalho_id)'
            },
            {
                'table': 'apontamento_producao',
                'name': 'idx_apontamento_data_fim',
                'sql': 'CREATE INDEX IF NOT EXISTS idx_apontamento_data_fim ON apontamento_producao(data_fim) WHERE data_fim IS NULL'
            },
            {
                'table': 'apontamento_producao',
                'name': 'idx_apontamento_usuario_data_fim',
                'sql': 'CREATE INDEX IF NOT EXISTS idx_apontamento_usuario_data_fim ON apontamento_producao(usuario_id, data_fim)'
            },
            # Índices para CartaoFantasma
            {
                'table': 'cartao_fantasma',
                'name': 'idx_cartao_fantasma_lista_ativo',
                'sql': 'CREATE INDEX IF NOT EXISTS idx_cartao_fantasma_lista_ativo ON cartao_fantasma(lista_kanban, ativo, posicao_fila)'
            },
            # Índices para ItemTrabalho (usado em cálculos de tempo)
            {
                'table': 'item_trabalho',
                'name': 'idx_item_trabalho_item_id',
                'sql': 'CREATE INDEX IF NOT EXISTS idx_item_trabalho_item_id ON item_trabalho(item_id)'
            },
            # Índices para PedidoOrdemServico
            {
                'table': 'pedido_ordem_servico',
                'name': 'idx_pedido_os_ordem_id',
                'sql': 'CREATE INDEX IF NOT EXISTS idx_pedido_os_ordem_id ON pedido_ordem_servico(ordem_servico_id)'
            },
            # Índice para Usuario (validação de código operador)
            {
                'table': 'usuario',
                'name': 'idx_usuario_codigo_operador',
                'sql': 'CREATE INDEX IF NOT EXISTS idx_usuario_codigo_operador ON usuario(codigo_operador) WHERE codigo_operador IS NOT NULL'
            }
        ]
        
        created_count = 0
        skipped_count = 0
        
        for idx_info in indexes_to_create:
            table = idx_info['table']
            name = idx_info['name']
            sql = idx_info['sql']
            
            if index_exists(inspector, table, name):
                logger.info(f"✓ Índice {name} já existe em {table}")
                skipped_count += 1
                continue
            
            try:
                db.session.execute(text(sql))
                db.session.commit()
                logger.info(f"✓ Criado índice {name} em {table}")
                created_count += 1
            except Exception as e:
                db.session.rollback()
                logger.error(f"✗ Erro ao criar índice {name}: {e}")
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Índices criados: {created_count}")
        logger.info(f"Índices já existentes: {skipped_count}")
        logger.info(f"{'='*60}")

if __name__ == '__main__':
    add_indexes()
