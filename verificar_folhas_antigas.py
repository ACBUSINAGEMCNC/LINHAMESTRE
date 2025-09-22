#!/usr/bin/env python3
"""
Script para verificar se há dados nas tabelas antigas de folhas de processo
antes de removê-las definitivamente.
"""

import os
import sys
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

def verificar_folhas_antigas():
    """Verifica se há dados nas tabelas antigas de folhas de processo"""
    
    database_url = os.getenv('DATABASE_URL', '')
    
    if database_url.startswith('postgresql://'):
        print("🔍 Verificando tabelas antigas no PostgreSQL...")
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
            
            # Verificar tabelas antigas que podem existir
            tabelas_antigas = [
                'folha_processo',
                'folha_processo_centro_usinagem', 
                'folha_processo_corte_serra',
                'folha_processo_servicos_gerais',
                'folha_processo_torno_cnc'
            ]
            
            dados_encontrados = False
            
            for tabela in tabelas_antigas:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {tabela}")
                    count = cursor.fetchone()[0]
                    if count > 0:
                        print(f"⚠️  Tabela '{tabela}' contém {count} registros")
                        dados_encontrados = True
                    else:
                        print(f"✅ Tabela '{tabela}' está vazia")
                except Exception as e:
                    print(f"ℹ️  Tabela '{tabela}' não existe ou erro: {e}")
            
            cursor.close()
            conn.close()
            
            if not dados_encontrados:
                print("\n✅ Nenhum dado encontrado nas tabelas antigas!")
                print("🗑️  É seguro remover os templates antigos.")
            else:
                print("\n⚠️  ATENÇÃO: Dados encontrados nas tabelas antigas!")
                print("📋 Considere migrar os dados antes de remover os templates.")
                
        except Exception as e:
            print(f"❌ Erro ao conectar com PostgreSQL: {e}")
            
    else:
        print("🔍 Verificando tabelas antigas no SQLite...")
        import sqlite3
        
        try:
            db_path = os.path.join(os.path.dirname(__file__), 'database.db')
            if not os.path.exists(db_path):
                print("ℹ️  Banco SQLite não encontrado - provavelmente usando PostgreSQL")
                return
                
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Verificar tabelas antigas
            tabelas_antigas = [
                'folha_processo',
                'folha_processo_centro_usinagem', 
                'folha_processo_corte_serra',
                'folha_processo_servicos_gerais',
                'folha_processo_torno_cnc'
            ]
            
            dados_encontrados = False
            
            for tabela in tabelas_antigas:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {tabela}")
                    count = cursor.fetchone()[0]
                    if count > 0:
                        print(f"⚠️  Tabela '{tabela}' contém {count} registros")
                        dados_encontrados = True
                    else:
                        print(f"✅ Tabela '{tabela}' está vazia")
                except Exception as e:
                    print(f"ℹ️  Tabela '{tabela}' não existe: {e}")
            
            conn.close()
            
            if not dados_encontrados:
                print("\n✅ Nenhum dado encontrado nas tabelas antigas!")
                print("🗑️  É seguro remover os templates antigos.")
            else:
                print("\n⚠️  ATENÇÃO: Dados encontrados nas tabelas antigas!")
                print("📋 Considere migrar os dados antes de remover os templates.")
                
        except Exception as e:
            print(f"❌ Erro ao verificar SQLite: {e}")

if __name__ == '__main__':
    print("🔍 Verificando folhas de processo antigas...")
    print("=" * 50)
    verificar_folhas_antigas()
    print("=" * 50)
    print("✅ Verificação concluída!")
