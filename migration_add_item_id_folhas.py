#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Migração: Adicionar campo item_id na tabela nova_folha_processo
para atrelar folhas de processo aos itens específicos
"""

import sqlite3
import os
from datetime import datetime

def main():
    # Caminho do banco de dados
    db_path = 'database.db'
    
    if not os.path.exists(db_path):
        print(f"❌ Banco de dados não encontrado: {db_path}")
        return
    
    try:
        # Conectar ao banco
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("🔧 Iniciando migração: Adicionar item_id às folhas de processo...")
        
        # Verificar se a coluna já existe
        cursor.execute("PRAGMA table_info(nova_folha_processo)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'item_id' in columns:
            print("✅ Coluna item_id já existe na tabela nova_folha_processo")
        else:
            # Adicionar a coluna item_id
            cursor.execute("""
                ALTER TABLE nova_folha_processo 
                ADD COLUMN item_id INTEGER REFERENCES item(id)
            """)
            print("✅ Coluna item_id adicionada à tabela nova_folha_processo")
        
        # Commit das alterações
        conn.commit()
        print("✅ Migração concluída com sucesso!")
        
        # Mostrar estatísticas
        cursor.execute("SELECT COUNT(*) FROM nova_folha_processo")
        total_folhas = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM nova_folha_processo WHERE item_id IS NOT NULL")
        folhas_com_item = cursor.fetchone()[0]
        
        print(f"\n📊 Estatísticas:")
        print(f"   • Total de folhas: {total_folhas}")
        print(f"   • Folhas com item: {folhas_com_item}")
        print(f"   • Folhas sem item: {total_folhas - folhas_com_item}")
        
        if total_folhas > folhas_com_item:
            print(f"\n💡 Dica: Você pode atrelar folhas existentes aos itens através da interface")
        
    except sqlite3.Error as e:
        print(f"❌ Erro na migração: {e}")
        conn.rollback()
    
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    main()
