#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Adicionar coluna preferencias na tabela usuario (SQLite)
"""

import sqlite3
import os

# Caminho do banco SQLite
db_path = os.path.join(os.path.dirname(__file__), 'database.db')

if not os.path.exists(db_path):
    print(f"❌ Banco de dados não encontrado: {db_path}")
    exit(1)

print(f"📂 Conectando ao banco: {db_path}")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Verificar se a coluna já existe
cursor.execute("PRAGMA table_info(usuario)")
columns = [row[1] for row in cursor.fetchall()]

if 'preferencias' in columns:
    print("✅ Coluna 'preferencias' já existe!")
else:
    print("📝 Adicionando coluna 'preferencias'...")
    cursor.execute("ALTER TABLE usuario ADD COLUMN preferencias TEXT")
    conn.commit()
    print("✅ Coluna adicionada com sucesso!")

conn.close()
print("✨ Migração concluída!")
