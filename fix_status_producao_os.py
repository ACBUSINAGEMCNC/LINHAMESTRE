#!/usr/bin/env python3
"""
Script para corrigir a estrutura das tabelas status_producao_os e apontamento_producao no PostgreSQL/Supabase
Remove as tabelas antigas e recria com a estrutura atualizada
"""

import os
import psycopg2
import time
from psycopg2.extras import RealDictCursor

def fix_tables():
    """Corrige a estrutura das tabelas status_producao_os e apontamento_producao"""
    
    # Configurar conexão com PostgreSQL/Supabase
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("❌ Erro: DATABASE_URL não encontrada")
        return False
    
    try:
        # Conectar ao banco
        print("🔗 Conectando ao PostgreSQL/Supabase...")
        conn = psycopg2.connect(database_url)
        conn.autocommit = True  # Para evitar problemas com DROP/CREATE
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        print("✅ Conectado com sucesso!")
        
        # ======== CORRIGIR TABELA APONTAMENTO_PRODUCAO ========
        print("\n1️⃣ CORRIGINDO TABELA APONTAMENTO_PRODUCAO...")
        
        # 1. Fazer backup dos dados existentes (se houver)
        print("📦 Fazendo backup dos dados de apontamento_producao...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS apontamento_producao_backup AS 
            SELECT * FROM apontamento_producao;
        """)
        
        # 2. Remover a tabela antiga
        print("🗑️ Removendo tabela apontamento_producao antiga...")
        cursor.execute("DROP TABLE IF EXISTS apontamento_producao CASCADE;")
        
        # 3. Recriar a tabela com a estrutura correta
        print("🔨 Recriando tabela apontamento_producao com estrutura atualizada...")
        cursor.execute("""
            CREATE TABLE apontamento_producao (
                id SERIAL PRIMARY KEY,
                ordem_servico_id INTEGER NOT NULL,
                usuario_id INTEGER NOT NULL,
                item_id INTEGER,
                trabalho_id INTEGER,
                tipo_acao TEXT NOT NULL,
                data_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                quantidade INTEGER,
                motivo_parada TEXT,
                tempo_decorrido INTEGER,
                lista_kanban TEXT,
                observacoes TEXT,
                CONSTRAINT fk_apontamento_os FOREIGN KEY (ordem_servico_id) REFERENCES ordem_servico (id),
                CONSTRAINT fk_apontamento_usuario FOREIGN KEY (usuario_id) REFERENCES usuario (id),
                CONSTRAINT fk_apontamento_item FOREIGN KEY (item_id) REFERENCES item (id),
                CONSTRAINT fk_apontamento_trabalho FOREIGN KEY (trabalho_id) REFERENCES trabalho (id)
            );
        """)
        
        # Criar índices para apontamento_producao
        print("📊 Criando índices para apontamento_producao...")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_apontamento_os ON apontamento_producao(ordem_servico_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_apontamento_item ON apontamento_producao(item_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_apontamento_data ON apontamento_producao(data_hora);")
        
        print("✅ Tabela apontamento_producao recriada com sucesso!")
        
        # ======== CORRIGIR TABELA STATUS_PRODUCAO_OS ========
        print("\n2️⃣ CORRIGINDO TABELA STATUS_PRODUCAO_OS...")
        
        # 1. Fazer backup dos dados existentes (se houver)
        print("📦 Fazendo backup dos dados de status_producao_os...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS status_producao_os_backup AS 
            SELECT * FROM status_producao_os;
        """)
        
        # 2. Remover a tabela antiga
        print("🗑️ Removendo tabela status_producao_os antiga...")
        cursor.execute("DROP TABLE IF EXISTS status_producao_os CASCADE;")
        
        # 3. Recriar a tabela com a estrutura correta
        print("🔨 Recriando tabela status_producao_os com estrutura atualizada...")
        cursor.execute("""
            CREATE TABLE status_producao_os (
                id SERIAL PRIMARY KEY,
                ordem_servico_id INTEGER UNIQUE NOT NULL,
                status_atual TEXT NOT NULL DEFAULT 'Aguardando',
                operador_atual_id INTEGER,
                item_atual_id INTEGER,
                trabalho_atual_id INTEGER,
                inicio_acao TIMESTAMP,
                quantidade_atual INTEGER DEFAULT 0,
                previsao_termino TIMESTAMP,
                eficiencia_percentual FLOAT,
                motivo_pausa TEXT,
                data_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT fk_status_os FOREIGN KEY (ordem_servico_id) REFERENCES ordem_servico (id),
                CONSTRAINT fk_status_operador FOREIGN KEY (operador_atual_id) REFERENCES usuario (id),
                CONSTRAINT fk_status_item FOREIGN KEY (item_atual_id) REFERENCES item (id),
                CONSTRAINT fk_status_trabalho FOREIGN KEY (trabalho_atual_id) REFERENCES trabalho (id)
            );
        """)
        
        # 4. Criar índices para status_producao_os
        print("📊 Criando índices para status_producao_os...")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_status_os ON status_producao_os(ordem_servico_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_status_operador ON status_producao_os(operador_atual_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_status_item ON status_producao_os(item_atual_id);")
        
        # 5. Inicializar registros para ordens de serviço existentes
        print("🔄 Inicializando registros para ordens de serviço existentes...")
        cursor.execute("""
            INSERT INTO status_producao_os (ordem_servico_id, status_atual)
            SELECT id, 'Aguardando'
            FROM ordem_servico
            WHERE id NOT IN (SELECT ordem_servico_id FROM status_producao_os);
        """)
        
        # 6. Verificar resultado
        cursor.execute("SELECT COUNT(*) FROM status_producao_os")
        count = cursor.fetchone()['count']
        print(f"✅ Tabela status_producao_os recriada com sucesso! {count} registros inicializados.")
        
        # 7. Limpar tabelas de backup (opcional - manter para segurança)
        # cursor.execute("DROP TABLE IF EXISTS apontamento_producao_backup;")
        # cursor.execute("DROP TABLE IF EXISTS status_producao_os_backup;")
        print("📝 Backups mantidos como apontamento_producao_backup e status_producao_os_backup")
        
        print("\n🎉 Correção das tabelas concluída com sucesso!")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao corrigir tabelas: {e}")
        if 'conn' in locals():
            conn.rollback()
        return False
        
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()
        print("🔌 Conexão fechada.")

if __name__ == "__main__":
    # Definir DATABASE_URL se não estiver definida
    if not os.environ.get('DATABASE_URL'):
        os.environ['DATABASE_URL'] = "postgresql://postgres.rxkuxdtpmrpfrufvnjxa:PIRULLITTO12@aws-0-sa-east-1.pooler.supabase.com:6543/postgres"
    
    print("==== CORREÇÃO DAS TABELAS DO MÓDULO DE APONTAMENTO ====")
    time.sleep(1)
    
    print("\n⚠️ ATENÇÃO: Este script vai recriar as tabelas apontamento_producao")
    print("e status_producao_os do zero. Os dados existentes serão perdidos,")
    print("mas backups serão criados automaticamente.")
    time.sleep(1)
    
    confirmacao = input("\n🔴 Digite 'SIM' para continuar: ")
    if confirmacao.upper() != "SIM":
        print("Operação cancelada pelo usuário.")
        exit()
    
    print("\nIniciando correção das tabelas...")
    success = fix_tables()
    
    if success:
        print("\n✅ Correção concluída! Reinicie o servidor Flask para aplicar as mudanças.")
    else:
        print("\n❌ Correção falhou. Verifique os logs de erro acima.")
