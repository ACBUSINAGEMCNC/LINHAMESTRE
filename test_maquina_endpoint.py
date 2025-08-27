#!/usr/bin/env python3
"""
Teste para verificar se as colunas categoria_trabalho e imagem foram adicionadas corretamente
na tabela maquina e se o endpoint /trabalhos/maquinas está funcionando.
"""

import os
import sys
import requests
import json
from dotenv import load_dotenv
import psycopg2

# Configurar logging simples
def log(message, error=False):
    prefix = "❌" if error else "✅"
    print(f"{prefix} {message}")

def test_database_column():
    """Testa se as colunas categoria_trabalho e imagem existem na tabela maquina."""
    try:
        load_dotenv()
        db_url = os.getenv('DATABASE_URL')
        if not db_url:
            log("Variável DATABASE_URL não encontrada!", error=True)
            return False
            
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()
        
        # Verificar se a coluna categoria_trabalho existe
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'maquina' AND column_name = 'categoria_trabalho'
            );
        """)
        
        categoria_exists = cursor.fetchone()[0]
        if categoria_exists:
            log("Coluna 'categoria_trabalho' existe na tabela 'maquina'")
        else:
            log("Coluna 'categoria_trabalho' NÃO existe na tabela 'maquina'!", error=True)
            
        # Verificar se a coluna imagem existe
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'maquina' AND column_name = 'imagem'
            );
        """)
        
        imagem_exists = cursor.fetchone()[0]
        if imagem_exists:
            log("Coluna 'imagem' existe na tabela 'maquina'")
        else:
            log("Coluna 'imagem' NÃO existe na tabela 'maquina'!", error=True)
            
        # Mostrar estrutura da tabela
        cursor.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'maquina'
            ORDER BY ordinal_position;
        """)
        
        print("\n📋 Estrutura da tabela 'maquina':")
        for col in cursor.fetchall():
            print(f"   {col[0]} - {col[1]}")
            
        return categoria_exists and imagem_exists

            
    except Exception as e:
        log(f"Erro ao verificar banco de dados: {str(e)}", error=True)
        return False
    finally:
        if 'conn' in locals() and conn:
            conn.close()

def test_endpoint():
    """Testa se o endpoint /trabalhos/maquinas está funcionando."""
    try:
        response = requests.get('http://127.0.0.1:5000/trabalhos/maquinas', timeout=10)
        
        if response.status_code == 200:
            log(f"Endpoint /trabalhos/maquinas respondeu com sucesso (HTTP 200)")
            return True
        else:
            log(f"Erro HTTP {response.status_code} ao acessar /trabalhos/maquinas: {response.text}", error=True)
            return False
            
    except Exception as e:
        log(f"Erro ao acessar endpoint: {str(e)}", error=True)
        return False

if __name__ == "__main__":
    print("=== TESTE DAS COLUNAS CATEGORIA_TRABALHO E IMAGEM ===\n")
    
    db_success = test_database_column()
    print("\n" + "-" * 50 + "\n")
    
    print("=== TESTE DO ENDPOINT /trabalhos/maquinas ===\n")
    endpoint_success = test_endpoint()
    
    print("\n" + "=" * 50)
    if db_success and endpoint_success:
        print("\n✅ TODOS OS TESTES PASSARAM COM SUCESSO!")
        sys.exit(0)
    else:
        print("\n❌ ALGUNS TESTES FALHARAM!")
        sys.exit(1)
