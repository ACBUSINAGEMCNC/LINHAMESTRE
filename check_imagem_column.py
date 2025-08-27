#!/usr/bin/env python3
"""
Script simples para verificar se a coluna 'imagem' existe na tabela 'maquina'.
"""

import os
import sys
import psycopg2
from dotenv import load_dotenv

def check_imagem_column():
    """Verifica se a coluna 'imagem' existe na tabela 'maquina'."""
    try:
        # Carregar variáveis de ambiente
        load_dotenv()
        
        # Obter URL do banco de dados
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            print("❌ DATABASE_URL não configurada!")
            return False
            
        # Conectar ao banco de dados
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        
        # Verificar se a coluna existe
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'maquina' AND column_name = 'imagem'
            );
        """)
        
        if cursor.fetchone()[0]:
            print("✅ A coluna 'imagem' existe na tabela 'maquina'.")
            
            # Mostrar tipo da coluna
            cursor.execute("""
                SELECT data_type
                FROM information_schema.columns
                WHERE table_name = 'maquina' AND column_name = 'imagem';
            """)
            
            data_type = cursor.fetchone()[0]
            print(f"   Tipo de dados: {data_type}")
            return True
        else:
            print("❌ A coluna 'imagem' NÃO existe na tabela 'maquina'!")
            
            # Tentar executar a migração
            print("\nTentando executar a migração...")
            from migrations.add_columns_maquina import migrate_postgres
            if migrate_postgres():
                print("✅ Migração executada com sucesso!")
                
                # Verificar novamente
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT 1
                        FROM information_schema.columns
                        WHERE table_name = 'maquina' AND column_name = 'imagem'
                    );
                """)
                
                if cursor.fetchone()[0]:
                    print("✅ A coluna 'imagem' foi adicionada com sucesso!")
                    return True
                else:
                    print("❌ A coluna 'imagem' ainda não existe após a migração!")
                    return False
            else:
                print("❌ Falha ao executar a migração!")
                return False
                
    except Exception as e:
        print(f"❌ Erro ao verificar a coluna: {str(e)}")
        return False
    finally:
        if 'conn' in locals() and conn:
            conn.close()

if __name__ == "__main__":
    print("=== VERIFICAÇÃO DA COLUNA 'imagem' ===\n")
    
    if check_imagem_column():
        print("\n✅ VERIFICAÇÃO CONCLUÍDA COM SUCESSO!")
        sys.exit(0)
    else:
        print("\n❌ VERIFICAÇÃO FALHOU!")
        sys.exit(1)
