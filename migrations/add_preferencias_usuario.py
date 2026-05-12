#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Migração: Adicionar campo 'preferencias' na tabela 'usuario'
"""

import os
import sys
from sqlalchemy import create_engine, text, inspect

# Adicionar o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def add_preferencias_column():
    """Adiciona a coluna preferencias na tabela usuario"""
    
    # Obter DATABASE_URL do ambiente
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        print("❌ DATABASE_URL não configurado")
        return False
    
    try:
        engine = create_engine(database_url)
        inspector = inspect(engine)
        
        # Verificar se a coluna já existe
        columns = [col['name'] for col in inspector.get_columns('usuario')]
        
        if 'preferencias' in columns:
            print("✅ Coluna 'preferencias' já existe na tabela 'usuario'")
            return True
        
        print("📝 Adicionando coluna 'preferencias' na tabela 'usuario'...")
        
        # Detectar tipo de banco
        is_postgres = 'postgresql' in database_url or 'postgres' in database_url
        
        with engine.connect() as conn:
            if is_postgres:
                # PostgreSQL
                conn.execute(text("""
                    ALTER TABLE usuario 
                    ADD COLUMN preferencias TEXT NULL
                """))
                conn.commit()
            else:
                # SQLite
                conn.execute(text("""
                    ALTER TABLE usuario 
                    ADD COLUMN preferencias TEXT
                """))
                conn.commit()
        
        print("✅ Coluna 'preferencias' adicionada com sucesso!")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao adicionar coluna: {str(e)}")
        return False

if __name__ == '__main__':
    # Carregar variáveis de ambiente
    from dotenv import load_dotenv
    load_dotenv()
    
    success = add_preferencias_column()
    sys.exit(0 if success else 1)
