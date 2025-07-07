#!/usr/bin/env python3
"""
Script de migração para adicionar as tabelas das Folhas de Processo
Executar: python migration_add_folhas_processo.py
"""

import sqlite3
from datetime import datetime

def executar_migracao():
    try:
        # Conectar ao banco de dados
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        
        print("=== MIGRAÇÃO: FOLHAS DE PROCESSO ===")
        print(f"Iniciando migração em {datetime.now()}")
        
        # 1. Criar tabela FolhaProcesso (tabela base)
        print("\n1. Criando tabela folha_processo...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS folha_processo (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                tipo_processo VARCHAR(30) NOT NULL,
                versao INTEGER DEFAULT 1,
                data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP,
                data_atualizacao DATETIME DEFAULT CURRENT_TIMESTAMP,
                criado_por VARCHAR(100),
                responsavel VARCHAR(100),
                ativo BOOLEAN DEFAULT 1,
                observacoes TEXT,
                FOREIGN KEY (item_id) REFERENCES item (id)
            )
        ''')
        
        # 2. Criar tabela FolhaTornoCNC
        print("2. Criando tabela folha_torno_cnc...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS folha_torno_cnc (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                folha_processo_id INTEGER NOT NULL,
                codigo_item VARCHAR(50),
                nome_peca VARCHAR(200),
                quantidade INTEGER,
                maquina_torno VARCHAR(100),
                tipo_fixacao VARCHAR(100),
                tipo_material VARCHAR(100),
                programa_cnc VARCHAR(255),
                ferramentas_utilizadas TEXT,
                operacoes_previstas TEXT,
                diametros_criticos TEXT,
                comprimentos_criticos TEXT,
                rpm_sugerido VARCHAR(50),
                avanco_sugerido VARCHAR(50),
                ponto_controle_dimensional TEXT,
                observacoes_tecnicas TEXT,
                responsavel_preenchimento VARCHAR(100),
                FOREIGN KEY (folha_processo_id) REFERENCES folha_processo (id)
            )
        ''')
        
        # 3. Criar tabela FolhaCentroUsinagem
        print("3. Criando tabela folha_centro_usinagem...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS folha_centro_usinagem (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                folha_processo_id INTEGER NOT NULL,
                codigo_item VARCHAR(50),
                nome_peca VARCHAR(200),
                quantidade INTEGER,
                maquina_centro VARCHAR(100),
                sistema_fixacao VARCHAR(100),
                z_zero_origem VARCHAR(100),
                lista_ferramentas TEXT,
                operacoes TEXT,
                caminho_programa_cnc VARCHAR(255),
                ponto_critico_colisao TEXT,
                limitacoes TEXT,
                tolerancias_especificas TEXT,
                observacoes_engenharia TEXT,
                responsavel_tecnico VARCHAR(100),
                FOREIGN KEY (folha_processo_id) REFERENCES folha_processo (id)
            )
        ''')
        
        # 4. Criar tabela FolhaCorteSerraria
        print("4. Criando tabela folha_corte_serraria...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS folha_corte_serraria (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                folha_processo_id INTEGER NOT NULL,
                codigo_item VARCHAR(50),
                nome_peca VARCHAR(200),
                quantidade_cortar INTEGER,
                tipo_material VARCHAR(100),
                tipo_serra VARCHAR(100),
                tamanho_bruto VARCHAR(100),
                tamanho_final_corte VARCHAR(100),
                perda_esperada VARCHAR(50),
                tolerancia_permitida VARCHAR(50),
                operador_responsavel VARCHAR(100),
                data_corte DATE,
                observacoes_corte TEXT,
                FOREIGN KEY (folha_processo_id) REFERENCES folha_processo (id)
            )
        ''')
        
        # 5. Criar tabela FolhaServicosGerais
        print("5. Criando tabela folha_servicos_gerais...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS folha_servicos_gerais (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                folha_processo_id INTEGER NOT NULL,
                codigo_item VARCHAR(50),
                nome_peca VARCHAR(200),
                processo_rebarba BOOLEAN DEFAULT 0,
                processo_lavagem BOOLEAN DEFAULT 0,
                processo_inspecao BOOLEAN DEFAULT 0,
                ferramentas_utilizadas TEXT,
                padrao_qualidade TEXT,
                itens_inspecionar TEXT,
                resultado_inspecao VARCHAR(20),
                motivo_reprovacao TEXT,
                operador_responsavel VARCHAR(100),
                observacoes_gerais TEXT,
                FOREIGN KEY (folha_processo_id) REFERENCES folha_processo (id)
            )
        ''')
        
        # 6. Criar índices para melhor performance
        print("6. Criando índices...")
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_folha_processo_item_id ON folha_processo (item_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_folha_processo_tipo ON folha_processo (tipo_processo)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_folha_torno_cnc_folha_id ON folha_torno_cnc (folha_processo_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_folha_centro_usinagem_folha_id ON folha_centro_usinagem (folha_processo_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_folha_corte_serraria_folha_id ON folha_corte_serraria (folha_processo_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_folha_servicos_gerais_folha_id ON folha_servicos_gerais (folha_processo_id)')
        
        # Confirmar todas as alterações
        conn.commit()
        
        print("\n✅ MIGRAÇÃO CONCLUÍDA COM SUCESSO!")
        print("Tabelas criadas:")
        print("  - folha_processo")
        print("  - folha_torno_cnc")
        print("  - folha_centro_usinagem")
        print("  - folha_corte_serraria")
        print("  - folha_servicos_gerais")
        print("  - Índices de performance criados")
        
        # Verificar se as tabelas foram criadas
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'folha_%'")
        tabelas = cursor.fetchall()
        print(f"\nTabelas verificadas: {len(tabelas)} tabelas de folhas encontradas")
        
    except Exception as e:
        print(f"❌ ERRO na migração: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    executar_migracao()
