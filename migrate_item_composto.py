#!/usr/bin/env python3
"""
Script de migração para adicionar suporte a Itens Compostos
Adiciona:
- Coluna 'eh_composto' na tabela 'item'
- Coluna 'data_criacao' na tabela 'item'
- Nova tabela 'item_composto' para relacionamentos
"""

import sqlite3
import os
from datetime import datetime

def migrate_database():
    """Executa a migração do banco de dados"""
    
    # Caminho do banco de dados
    db_path = 'acb_usinagem.db'
    
    if not os.path.exists(db_path):
        print(f"❌ Banco de dados não encontrado: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("🔄 Iniciando migração para Itens Compostos...")
        
        # 1. Adicionar coluna eh_composto na tabela item
        try:
            cursor.execute("ALTER TABLE item ADD COLUMN eh_composto BOOLEAN DEFAULT 0")
            print("✅ Coluna 'eh_composto' adicionada à tabela 'item'")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print("⚠️  Coluna 'eh_composto' já existe na tabela 'item'")
            else:
                raise e
        
        # 2. Adicionar coluna data_criacao na tabela item
        try:
            cursor.execute("ALTER TABLE item ADD COLUMN data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP")
            print("✅ Coluna 'data_criacao' adicionada à tabela 'item'")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print("⚠️  Coluna 'data_criacao' já existe na tabela 'item'")
            else:
                raise e
        
        # 3. Criar tabela item_composto
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS item_composto (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_pai_id INTEGER NOT NULL,
                item_componente_id INTEGER NOT NULL,
                quantidade INTEGER NOT NULL DEFAULT 1,
                observacoes TEXT,
                data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (item_pai_id) REFERENCES item (id),
                FOREIGN KEY (item_componente_id) REFERENCES item (id),
                UNIQUE(item_pai_id, item_componente_id)
            )
        """)
        print("✅ Tabela 'item_composto' criada")
        
        # 4. Atualizar itens existentes sem data_criacao
        cursor.execute("""
            UPDATE item 
            SET data_criacao = CURRENT_TIMESTAMP 
            WHERE data_criacao IS NULL
        """)
        
        # Commit das alterações
        conn.commit()
        
        # 5. Verificar se as alterações foram aplicadas
        cursor.execute("PRAGMA table_info(item)")
        colunas_item = [col[1] for col in cursor.fetchall()]
        
        cursor.execute("PRAGMA table_info(item_composto)")
        colunas_item_composto = [col[1] for col in cursor.fetchall()]
        
        print("\n📊 Verificação das alterações:")
        print(f"   Colunas na tabela 'item': {', '.join(colunas_item)}")
        print(f"   Colunas na tabela 'item_composto': {', '.join(colunas_item_composto)}")
        
        # Verificar se as colunas necessárias existem
        required_item_columns = ['eh_composto', 'data_criacao']
        required_composto_columns = ['item_pai_id', 'item_componente_id', 'quantidade']
        
        missing_item = [col for col in required_item_columns if col not in colunas_item]
        missing_composto = [col for col in required_composto_columns if col not in colunas_item_composto]
        
        if missing_item:
            print(f"❌ Colunas faltantes na tabela 'item': {', '.join(missing_item)}")
            return False
        
        if missing_composto:
            print(f"❌ Colunas faltantes na tabela 'item_composto': {', '.join(missing_composto)}")
            return False
        
        print("\n✅ Migração concluída com sucesso!")
        print("   - Suporte a Itens Compostos adicionado")
        print("   - Banco de dados atualizado")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro durante a migração: {str(e)}")
        return False
    
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    print("=" * 60)
    print("MIGRAÇÃO: SUPORTE A ITENS COMPOSTOS")
    print("=" * 60)
    
    success = migrate_database()
    
    if success:
        print("\n🎉 Migração executada com sucesso!")
        print("   Agora você pode:")
        print("   1. Cadastrar itens compostos")
        print("   2. Gerar OS que desmembram automaticamente")
        print("   3. Usar o sistema Kanban com itens compostos")
    else:
        print("\n💥 Falha na migração!")
        print("   Verifique os erros acima e tente novamente")
    
    print("=" * 60)
