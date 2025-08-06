import sqlite3
import os

# Connect to the database
conn = sqlite3.connect('database.db')
cursor = conn.cursor()

# Check if the table exists
try:
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='status_producao_os'")
    table_exists = cursor.fetchone()
    if not table_exists:
        print("Table status_producao_os does not exist")
        conn.close()
        exit()
        
    # Count active apontamentos
    cursor.execute("SELECT COUNT(*) FROM status_producao_os WHERE status_atual != 'Finalizado'")
    count = cursor.fetchone()[0]
    print(f'Active apontamentos: {count}')
    
    # Get details of active apontamentos
    cursor.execute("SELECT ordem_servico_id, status_atual FROM status_producao_os WHERE status_atual != 'Finalizado' LIMIT 5")
    rows = cursor.fetchall()
    print('Active apontamentos details:')
    for row in rows:
        print(row)
        
    # Check all status values
    cursor.execute("SELECT DISTINCT status_atual FROM status_producao_os")
    statuses = cursor.fetchall()
    print('All status values in database:')
    for status in statuses:
        print(f"  - {status[0]}")
        
    conn.close()
except Exception as e:
    print(f"Error: {e}")
    conn.close()
