#!/usr/bin/env python3
"""
Migração para adicionar tabela CartaoFantasma
Data: 15/08/2025
Descrição: Adiciona a tabela CartaoFantasma para suporte a cartões fantasma no Kanban
"""

import sqlite3
import os
import sys
from datetime import datetime

def get_db_path():
    """Retorna o caminho do banco de dados"""
    # Procurar pelo banco de dados na pasta atual
    possible_paths = [
        'database.db',
        'acb_usinagem.db',
        'acb_usinagem.db.bak.20250804193341',
        'acb_usinagem.db.bak.20250707204629',
        'acb_usinagem.db.bak.20250707204627'
    ]
    
    for path in possible_paths:
        if os.path.exists(path) and os.path.getsize(path) > 1000:  # Verificar se não está vazio
            print(f"Usando banco de dados: {path}")
            return path
    
    raise FileNotFoundError("Nenhum banco de dados válido encontrado!")

def executar_migracao():
    """Executa a migração para adicionar tabela CartaoFantasma"""
    db_path = get_db_path()
    
    # Fazer backup antes da migração
    backup_path = f"{db_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    if os.path.exists(db_path):
        import shutil
        shutil.copy2(db_path, backup_path)
        print(f"Backup criado: {backup_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Verificar se a tabela já existe
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='cartao_fantasma'
        """)
        
        if cursor.fetchone():
            print("❌ Tabela 'cartao_fantasma' já existe! Migração cancelada.")
            return False
        
        # Criar tabela CartaoFantasma
        print("🔄 Criando tabela cartao_fantasma...")
        cursor.execute("""
            CREATE TABLE cartao_fantasma (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ordem_servico_id INTEGER NOT NULL,
                lista_kanban TEXT NOT NULL,
                posicao_fila INTEGER DEFAULT 1,
                ativo BOOLEAN DEFAULT 1,
                trabalho_id INTEGER,
                observacoes TEXT,
                data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                data_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                criado_por_id INTEGER,
                
                FOREIGN KEY (ordem_servico_id) REFERENCES ordem_servico(id),
                FOREIGN KEY (trabalho_id) REFERENCES trabalho(id),
                FOREIGN KEY (criado_por_id) REFERENCES usuario(id)
            )
        """)
        
        # Criar índices para melhor performance
        print("🔄 Criando índices...")
        
        cursor.execute("""
            CREATE INDEX idx_cartao_fantasma_ordem_lista 
            ON cartao_fantasma(ordem_servico_id, lista_kanban)
        """)
        
        cursor.execute("""
            CREATE INDEX idx_cartao_fantasma_lista_ativo 
            ON cartao_fantasma(lista_kanban, ativo)
        """)
        
        cursor.execute("""
            CREATE INDEX idx_cartao_fantasma_posicao 
            ON cartao_fantasma(lista_kanban, posicao_fila)
        """)
        
        # Criar trigger para atualizar data_atualizacao automaticamente
        print("🔄 Criando trigger para data_atualizacao...")
        cursor.execute("""
            CREATE TRIGGER trigger_cartao_fantasma_update_timestamp 
            AFTER UPDATE ON cartao_fantasma
            BEGIN
                UPDATE cartao_fantasma 
                SET data_atualizacao = CURRENT_TIMESTAMP 
                WHERE id = NEW.id;
            END
        """)
        
        # Verificar se as tabelas de referência existem
        print("🔄 Verificando integridade das referências...")
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ordem_servico'")
        if not cursor.fetchone():
            raise Exception("Tabela ordem_servico não encontrada!")
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trabalho'")
        if not cursor.fetchone():
            raise Exception("Tabela trabalho não encontrada!")
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='usuario'")
        if not cursor.fetchone():
            raise Exception("Tabela usuario não encontrada!")
        
        # Commit das mudanças
        conn.commit()
        
        print("✅ Migração executada com sucesso!")
        print("📋 Resumo das mudanças:")
        print("   - Tabela 'cartao_fantasma' criada")
        print("   - 3 índices criados para performance")
        print("   - Trigger para data_atualizacao criado")
        print("   - Referências de integridade verificadas")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro durante a migração: {e}")
        conn.rollback()
        return False
    
    finally:
        conn.close()

def verificar_migracao():
    """Verifica se a migração foi aplicada corretamente"""
    try:
        db_path = get_db_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Verificar estrutura da tabela
        cursor.execute("PRAGMA table_info(cartao_fantasma)")
        colunas = cursor.fetchall()
        
        if not colunas:
            print("❌ Tabela cartao_fantasma não encontrada!")
            return False
        
        print("✅ Verificação da migração:")
        print("📋 Estrutura da tabela cartao_fantasma:")
        for coluna in colunas:
            print(f"   - {coluna[1]} ({coluna[2]})")
        
        # Verificar índices
        cursor.execute("PRAGMA index_list(cartao_fantasma)")
        indices = cursor.fetchall()
        print(f"📋 Índices criados: {len(indices)}")
        
        # Verificar triggers
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='trigger' AND tbl_name='cartao_fantasma'
        """)
        triggers = cursor.fetchall()
        print(f"📋 Triggers criados: {len(triggers)}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Erro na verificação: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Iniciando migração CartaoFantasma...")
    print("="*50)
    
    if len(sys.argv) > 1 and sys.argv[1] == "verify":
        verificar_migracao()
    else:
        sucesso = executar_migracao()
        if sucesso:
            print("\n🔍 Verificando migração...")
            verificar_migracao()
        else:
            print("❌ Migração falhou!")
            sys.exit(1)
    
    print("="*50)
    print("✅ Processo concluído!")
