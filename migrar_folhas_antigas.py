#!/usr/bin/env python3
"""
Script para migrar dados das folhas de processo antigas para o novo sistema
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

def migrar_folhas_antigas():
    """Migra dados das folhas antigas para o novo sistema"""
    
    database_url = os.getenv('DATABASE_URL', '')
    
    if database_url.startswith('postgresql://'):
        print("🔄 Migrando folhas antigas no PostgreSQL...")
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
            
            # Primeiro, vamos ver o que há na tabela antiga
            print("📋 Analisando folhas antigas...")
            cursor.execute("""
                SELECT id, item_id, maquina_id, categoria_maquina, titulo_servico, 
                       data_criacao, data_atualizacao, usuario_criacao_id, ativo
                FROM folha_processo 
                WHERE ativo = true
                ORDER BY data_criacao
            """)
            
            folhas_antigas = cursor.fetchall()
            print(f"📊 Encontradas {len(folhas_antigas)} folhas ativas para migrar")
            
            if len(folhas_antigas) == 0:
                print("✅ Nenhuma folha ativa para migrar!")
                cursor.close()
                conn.close()
                return
            
            # Verificar se já existem folhas no novo sistema
            cursor.execute("SELECT COUNT(*) FROM nova_folha_processo")
            count_novas = cursor.fetchone()[0]
            print(f"📊 Existem {count_novas} folhas no novo sistema")
            
            migradas = 0
            erros = 0
            
            for folha in folhas_antigas:
                try:
                    old_id, item_id, maquina_id, categoria_maquina, titulo_servico, data_criacao, data_atualizacao, usuario_criacao_id, ativo = folha
                    
                    # Verificar se já existe uma folha no novo sistema para este item/máquina/serviço
                    cursor.execute("""
                        SELECT id FROM nova_folha_processo 
                        WHERE item_id = %s AND maquina_id = %s AND titulo_servico = %s
                    """, (item_id, maquina_id, titulo_servico))
                    
                    existe = cursor.fetchone()
                    if existe:
                        print(f"⚠️  Folha já existe no novo sistema: Item {item_id}, Máquina {maquina_id}, Serviço '{titulo_servico}'")
                        continue
                    
                    # Inserir no novo sistema
                    cursor.execute("""
                        INSERT INTO nova_folha_processo 
                        (item_id, maquina_id, categoria_maquina, titulo_servico, 
                         data_criacao, data_atualizacao, usuario_criacao_id, ativo)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, (item_id, maquina_id, categoria_maquina, titulo_servico,
                          data_criacao, data_atualizacao, usuario_criacao_id, True))
                    
                    nova_id = cursor.fetchone()[0]
                    migradas += 1
                    
                    print(f"✅ Migrada folha {old_id} -> {nova_id}: Item {item_id}, '{titulo_servico}'")
                    
                except Exception as e:
                    erros += 1
                    print(f"❌ Erro ao migrar folha {old_id}: {e}")
            
            # Commit das mudanças
            conn.commit()
            
            print(f"\n📊 Resumo da migração:")
            print(f"   ✅ Migradas: {migradas}")
            print(f"   ❌ Erros: {erros}")
            print(f"   📋 Total processadas: {len(folhas_antigas)}")
            
            if migradas > 0:
                print(f"\n🎉 Migração concluída com sucesso!")
                print(f"💡 Agora você pode marcar as folhas antigas como inativas")
                
                # Perguntar se quer desativar as antigas
                resposta = input("\n❓ Deseja marcar as folhas antigas como inativas? (s/N): ").lower()
                if resposta in ['s', 'sim', 'y', 'yes']:
                    cursor.execute("UPDATE folha_processo SET ativo = false WHERE ativo = true")
                    conn.commit()
                    print("✅ Folhas antigas marcadas como inativas!")
                else:
                    print("ℹ️  Folhas antigas mantidas ativas")
            
            cursor.close()
            conn.close()
            
        except Exception as e:
            print(f"❌ Erro durante a migração: {e}")
            
    else:
        print("ℹ️  Migração disponível apenas para PostgreSQL")

if __name__ == '__main__':
    print("🔄 Iniciando migração de folhas antigas...")
    print("=" * 50)
    migrar_folhas_antigas()
    print("=" * 50)
    print("✅ Processo concluído!")
