#!/usr/bin/env python3
"""
Migração para adicionar o sistema de apontamento de produção
- Adiciona campo codigo_operador na tabela usuario
- Cria tabela apontamento_producao
- Cria tabela status_producao_os
"""

import os
import sys
import sqlite3
from datetime import datetime

def executar_migracao():
    """Executa a migração do banco de dados"""
    
    # Configurar caminho do banco
    db_dir = os.getenv('DB_DIR', os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(db_dir, 'database.db')
    
    if not os.path.exists(db_path):
        print(f"❌ Banco de dados não encontrado: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("🔄 Iniciando migração para sistema de apontamento...")
        
        # 1. Adicionar campo codigo_operador na tabela usuario
        print("📝 Adicionando campo codigo_operador na tabela usuario...")
        try:
            cursor.execute("ALTER TABLE usuario ADD COLUMN codigo_operador VARCHAR(4)")
            print("✅ Campo codigo_operador adicionado com sucesso")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print("⚠️ Campo codigo_operador já existe")
            else:
                raise e
        
        # 2. Criar tabela apontamento_producao
        print("📝 Criando tabela apontamento_producao...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS apontamento_producao (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ordem_servico_id INTEGER NOT NULL,
                usuario_id INTEGER NOT NULL,
                item_trabalho_id INTEGER NOT NULL,
                tipo_acao VARCHAR(20) NOT NULL,
                data_hora DATETIME DEFAULT CURRENT_TIMESTAMP,
                quantidade INTEGER,
                motivo_parada VARCHAR(100),
                tempo_decorrido INTEGER,
                lista_kanban VARCHAR(100),
                observacoes TEXT,
                FOREIGN KEY (ordem_servico_id) REFERENCES ordem_servico (id),
                FOREIGN KEY (usuario_id) REFERENCES usuario (id),
                FOREIGN KEY (item_trabalho_id) REFERENCES item_trabalho (id)
            )
        """)
        print("✅ Tabela apontamento_producao criada com sucesso")
        
        # 3. Criar tabela status_producao_os
        print("📝 Criando tabela status_producao_os...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS status_producao_os (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ordem_servico_id INTEGER UNIQUE NOT NULL,
                status_atual VARCHAR(50) DEFAULT 'Aguardando',
                operador_atual_id INTEGER,
                item_trabalho_atual_id INTEGER,
                inicio_acao DATETIME,
                quantidade_atual INTEGER DEFAULT 0,
                previsao_termino DATETIME,
                eficiencia_percentual REAL,
                motivo_pausa VARCHAR(100),
                data_atualizacao DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (ordem_servico_id) REFERENCES ordem_servico (id),
                FOREIGN KEY (operador_atual_id) REFERENCES usuario (id),
                FOREIGN KEY (item_trabalho_atual_id) REFERENCES item_trabalho (id)
            )
        """)
        print("✅ Tabela status_producao_os criada com sucesso")
        
        # 4. Criar índices para melhor performance
        print("📝 Criando índices...")
        indices = [
            "CREATE INDEX IF NOT EXISTS idx_apontamento_os ON apontamento_producao(ordem_servico_id)",
            "CREATE INDEX IF NOT EXISTS idx_apontamento_usuario ON apontamento_producao(usuario_id)",
            "CREATE INDEX IF NOT EXISTS idx_apontamento_data ON apontamento_producao(data_hora)",
            "CREATE INDEX IF NOT EXISTS idx_status_os ON status_producao_os(ordem_servico_id)",
            "CREATE INDEX IF NOT EXISTS idx_usuario_codigo ON usuario(codigo_operador)"
        ]
        
        for indice in indices:
            cursor.execute(indice)
        print("✅ Índices criados com sucesso")
        
        # 5. Inicializar status_producao_os para ordens de serviço existentes
        print("📝 Inicializando status para ordens de serviço existentes...")
        cursor.execute("""
            INSERT OR IGNORE INTO status_producao_os (ordem_servico_id, status_atual)
            SELECT id, 'Aguardando' FROM ordem_servico
            WHERE id NOT IN (SELECT ordem_servico_id FROM status_producao_os)
        """)
        
        linhas_inseridas = cursor.rowcount
        if linhas_inseridas > 0:
            print(f"✅ Status inicializado para {linhas_inseridas} ordens de serviço")
        else:
            print("ℹ️ Nenhuma ordem de serviço nova para inicializar")
        
        # Commit das alterações
        conn.commit()
        print("✅ Migração concluída com sucesso!")
        
        # Mostrar estatísticas
        cursor.execute("SELECT COUNT(*) FROM apontamento_producao")
        total_apontamentos = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM status_producao_os")
        total_status = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM usuario WHERE codigo_operador IS NOT NULL")
        usuarios_com_codigo = cursor.fetchone()[0]
        
        print(f"""
📊 ESTATÍSTICAS PÓS-MIGRAÇÃO:
   • Apontamentos: {total_apontamentos}
   • Status de OS: {total_status}
   • Usuários com código: {usuarios_com_codigo}
        """)
        
        return True
        
    except Exception as e:
        print(f"❌ Erro durante a migração: {e}")
        conn.rollback()
        return False
        
    finally:
        conn.close()

def verificar_migracao():
    """Verifica se a migração foi aplicada corretamente"""
    
    db_dir = os.getenv('DB_DIR', os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(db_dir, 'database.db')
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Verificar se as tabelas existem
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tabelas = [row[0] for row in cursor.fetchall()]
        
        tabelas_necessarias = ['apontamento_producao', 'status_producao_os']
        tabelas_existentes = [t for t in tabelas_necessarias if t in tabelas]
        
        # Verificar se o campo codigo_operador existe
        cursor.execute("PRAGMA table_info(usuario)")
        colunas_usuario = [col[1] for col in cursor.fetchall()]
        campo_codigo_existe = 'codigo_operador' in colunas_usuario
        
        print(f"""
🔍 VERIFICAÇÃO DA MIGRAÇÃO:
   • Tabelas criadas: {len(tabelas_existentes)}/{len(tabelas_necessarias)}
     - apontamento_producao: {'✅' if 'apontamento_producao' in tabelas else '❌'}
     - status_producao_os: {'✅' if 'status_producao_os' in tabelas else '❌'}
   • Campo codigo_operador: {'✅' if campo_codigo_existe else '❌'}
        """)
        
        return len(tabelas_existentes) == len(tabelas_necessarias) and campo_codigo_existe
        
    except Exception as e:
        print(f"❌ Erro na verificação: {e}")
        return False
        
    finally:
        conn.close()

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 MIGRAÇÃO: Sistema de Apontamento de Produção")
    print("=" * 60)
    
    if executar_migracao():
        print("\n" + "=" * 60)
        verificar_migracao()
        print("=" * 60)
        print("✅ Migração concluída! Sistema de apontamento pronto para uso.")
    else:
        print("❌ Falha na migração. Verifique os erros acima.")
        sys.exit(1)
