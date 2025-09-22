#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Migração PostgreSQL: Adicionar campo item_id na tabela nova_folha_processo
para atrelar folhas de processo aos itens específicos
"""

import psycopg2
import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

def main():
    # Configurações do banco PostgreSQL (Supabase)
    DATABASE_URL = os.getenv('DATABASE_URL')
    
    if not DATABASE_URL:
        print("❌ DATABASE_URL não encontrada nas variáveis de ambiente")
        return
    
    try:
        # Conectar ao banco PostgreSQL
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        print("🔧 Iniciando migração PostgreSQL: Adicionar item_id às folhas de processo...")
        
        # Verificar se a coluna já existe
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'nova_folha_processo' 
            AND column_name = 'item_id'
        """)
        
        if cursor.fetchone():
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
        print("✅ Migração PostgreSQL concluída com sucesso!")
        
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
    
    except psycopg2.Error as e:
        print(f"❌ Erro na migração PostgreSQL: {e}")
        if conn:
            conn.rollback()
    
    except Exception as e:
        print(f"❌ Erro geral: {e}")
    
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

if __name__ == '__main__':
    main()
