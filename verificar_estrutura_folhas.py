#!/usr/bin/env python3
"""
Script para verificar a estrutura das tabelas de folhas de processo
"""

import os
import sys
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

def verificar_estrutura():
    """Verifica a estrutura das tabelas de folhas de processo"""
    
    database_url = os.getenv('DATABASE_URL', '')
    
    if database_url.startswith('postgresql://'):
        print("🔍 Verificando estrutura no PostgreSQL...")
        import psycopg2
        from urllib.parse import urlparse
        
        try:
            # Parse da URL do PostgreSQL
            result = urlparse(database_url)
            conn = psycopg2.connect(
                database=result.path[1:],
                user=result.username,
                password=result.password,
                host=result.hostname,
                port=result.port
            )
            
            cursor = conn.cursor()
            
            # Verificar estrutura da tabela antiga
            print("📋 Estrutura da tabela 'folha_processo':")
            cursor.execute("""
                SELECT column_name, data_type, is_nullable 
                FROM information_schema.columns 
                WHERE table_name = 'folha_processo'
                ORDER BY ordinal_position
            """)
            
            colunas_antigas = cursor.fetchall()
            for coluna in colunas_antigas:
                print(f"   - {coluna[0]} ({coluna[1]}) {'NULL' if coluna[2] == 'YES' else 'NOT NULL'}")
            
            print("\n📋 Estrutura da tabela 'nova_folha_processo':")
            cursor.execute("""
                SELECT column_name, data_type, is_nullable 
                FROM information_schema.columns 
                WHERE table_name = 'nova_folha_processo'
                ORDER BY ordinal_position
            """)
            
            colunas_novas = cursor.fetchall()
            for coluna in colunas_novas:
                print(f"   - {coluna[0]} ({coluna[1]}) {'NULL' if coluna[2] == 'YES' else 'NOT NULL'}")
            
            # Verificar dados da tabela antiga
            print(f"\n📊 Dados da tabela 'folha_processo':")
            cursor.execute("SELECT * FROM folha_processo LIMIT 3")
            dados = cursor.fetchall()
            
            if dados:
                # Pegar nomes das colunas
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'folha_processo'
                    ORDER BY ordinal_position
                """)
                nomes_colunas = [row[0] for row in cursor.fetchall()]
                
                print(f"   Colunas: {', '.join(nomes_colunas)}")
                for i, linha in enumerate(dados):
                    print(f"   Linha {i+1}: {linha}")
            else:
                print("   Nenhum dado encontrado")
            
            cursor.close()
            conn.close()
            
        except Exception as e:
            print(f"❌ Erro: {e}")

if __name__ == '__main__':
    print("🔍 Verificando estrutura das tabelas...")
    print("=" * 60)
    verificar_estrutura()
    print("=" * 60)
    print("✅ Verificação concluída!")
