"""
Migration para criar tabelas do módulo de Orçamentos
"""
from sqlalchemy import text


def migrate_postgres():
    """Cria tabelas de orçamento para PostgreSQL/Supabase"""
    from app import create_app
    from models import db
    
    app = create_app()
    with app.app_context():
        # Tabela orcamento
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS orcamento (
                id SERIAL PRIMARY KEY,
                numero VARCHAR(20) UNIQUE NOT NULL,
                
                -- Cliente (pode ser cadastrado ou não)
                cliente_id INTEGER REFERENCES cliente(id),
                cliente_nome VARCHAR(200),
                cliente_email VARCHAR(200),
                cliente_telefone VARCHAR(50),
                cliente_cnpj_cpf VARCHAR(20),
                cliente_endereco TEXT,
                
                -- Status e validade
                status VARCHAR(20) DEFAULT 'rascunho',
                validade_dias INTEGER DEFAULT 30,
                data_validade TIMESTAMP,
                
                -- Informações comerciais
                observacoes TEXT,
                condicoes_pagamento TEXT,
                prazo_entrega VARCHAR(200),
                
                -- Totais
                total_itens NUMERIC(10, 2) DEFAULT 0,
                desconto_percentual NUMERIC(5, 2) DEFAULT 0,
                desconto_valor NUMERIC(10, 2) DEFAULT 0,
                total_final NUMERIC(10, 2) DEFAULT 0,
                
                -- Auditoria
                criado_por_id INTEGER REFERENCES usuario(id),
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                aprovado_em TIMESTAMP,
                aprovado_por_id INTEGER REFERENCES usuario(id)
            )
        """))
        
        # Tabela orcamento_item
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS orcamento_item (
                id SERIAL PRIMARY KEY,
                orcamento_id INTEGER NOT NULL REFERENCES orcamento(id) ON DELETE CASCADE,
                item_id INTEGER NOT NULL REFERENCES item(id),
                
                -- Descrição pode ser customizada
                descricao_customizada TEXT,
                
                -- Quantidades e valores
                quantidade NUMERIC(10, 3) NOT NULL DEFAULT 1,
                valor_unitario NUMERIC(10, 2) NOT NULL,
                desconto_percentual NUMERIC(5, 2) DEFAULT 0,
                valor_total NUMERIC(10, 2),
                
                -- Informações de estoque (calculadas)
                tem_estoque BOOLEAN DEFAULT FALSE,
                quantidade_estoque NUMERIC(10, 3) DEFAULT 0,
                
                -- Observação e ordem
                observacao TEXT,
                ordem INTEGER DEFAULT 0
            )
        """))
        
        # Índices
        db.session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_orcamento_numero ON orcamento(numero)
        """))
        
        db.session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_orcamento_status ON orcamento(status)
        """))
        
        db.session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_orcamento_cliente ON orcamento(cliente_id)
        """))
        
        db.session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_orcamento_item_orcamento ON orcamento_item(orcamento_id)
        """))
        
        db.session.commit()
        print("✅ Tabelas de orçamento criadas (PostgreSQL)")


def migrate_sqlite():
    """Cria tabelas de orçamento para SQLite"""
    from app import create_app
    from models import db
    
    app = create_app()
    with app.app_context():
        # Tabela orcamento
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS orcamento (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                numero VARCHAR(20) UNIQUE NOT NULL,
                
                -- Cliente (pode ser cadastrado ou não)
                cliente_id INTEGER REFERENCES cliente(id),
                cliente_nome VARCHAR(200),
                cliente_email VARCHAR(200),
                cliente_telefone VARCHAR(50),
                cliente_cnpj_cpf VARCHAR(20),
                cliente_endereco TEXT,
                
                -- Status e validade
                status VARCHAR(20) DEFAULT 'rascunho',
                validade_dias INTEGER DEFAULT 30,
                data_validade TIMESTAMP,
                
                -- Informações comerciais
                observacoes TEXT,
                condicoes_pagamento TEXT,
                prazo_entrega VARCHAR(200),
                
                -- Totais
                total_itens NUMERIC(10, 2) DEFAULT 0,
                desconto_percentual NUMERIC(5, 2) DEFAULT 0,
                desconto_valor NUMERIC(10, 2) DEFAULT 0,
                total_final NUMERIC(10, 2) DEFAULT 0,
                
                -- Auditoria
                criado_por_id INTEGER REFERENCES usuario(id),
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                aprovado_em TIMESTAMP,
                aprovado_por_id INTEGER REFERENCES usuario(id)
            )
        """))
        
        # Tabela orcamento_item
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS orcamento_item (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                orcamento_id INTEGER NOT NULL REFERENCES orcamento(id) ON DELETE CASCADE,
                item_id INTEGER NOT NULL REFERENCES item(id),
                
                -- Descrição pode ser customizada
                descricao_customizada TEXT,
                
                -- Quantidades e valores
                quantidade NUMERIC(10, 3) NOT NULL DEFAULT 1,
                valor_unitario NUMERIC(10, 2) NOT NULL,
                desconto_percentual NUMERIC(5, 2) DEFAULT 0,
                valor_total NUMERIC(10, 2),
                
                -- Informações de estoque (calculadas)
                tem_estoque BOOLEAN DEFAULT 0,
                quantidade_estoque NUMERIC(10, 3) DEFAULT 0,
                
                -- Observação e ordem
                observacao TEXT,
                ordem INTEGER DEFAULT 0
            )
        """))
        
        # Índices
        db.session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_orcamento_numero ON orcamento(numero)
        """))
        
        db.session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_orcamento_status ON orcamento(status)
        """))
        
        db.session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_orcamento_cliente ON orcamento(cliente_id)
        """))
        
        db.session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_orcamento_item_orcamento ON orcamento_item(orcamento_id)
        """))
        
        db.session.commit()
        print("✅ Tabelas de orçamento criadas (SQLite)")


if __name__ == '__main__':
    import os
    if os.getenv('FORCE_SQLITE') == '1':
        migrate_sqlite()
    else:
        migrate_postgres()
