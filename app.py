import os
import sys
import datetime
import subprocess
import sqlite3
import logging
import json
from types import SimpleNamespace
from flask import Flask, render_template, redirect, url_for, flash, request, session, send_file, g, has_request_context
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event, inspect
from sqlalchemy.pool import NullPool
from sqlalchemy.exc import OperationalError
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# Carregar variáveis de ambiente do arquivo .env
load_dotenv()

# Configuração do banco de dados
basedir = os.path.abspath(os.path.dirname(__file__))
# Diretório gravável em ambientes serverless (Vercel). Somente /tmp é permitido.
WRITABLE_DIR = '/tmp' if os.getenv('VERCEL') else basedir

# Logger do módulo
logger = logging.getLogger(__name__)


def _env_flag(name: str) -> bool:
    val = os.getenv(name, '').strip().lower()
    return val in ('1', 'true', 'yes', 'on')


def _is_max_connections_error(exc: Exception) -> bool:
    msg = str(exc or '')
    return 'Max client connections reached' in msg or 'max client connections reached' in msg


def _get_database_url_from_env() -> str:
    url = (
        os.getenv('DATABASE_URL', '')
        or os.getenv('URL_DO_BANCO_DE_DADOS', '')
        or os.getenv('URL_BANCO_DE_DADOS', '')
    )
    if not url:
        return ''

    url_lower = url.lower()
    if url_lower.startswith('postgres://'):
        url = 'postgresql://' + url[len('postgres://'):]
        url_lower = url.lower()

    # Preferir psycopg3 quando URL for postgresql genérica
    if url_lower.startswith('postgresql://') and '+psycopg' not in url_lower and '+psycopg2' not in url_lower:
        try:
            import psycopg  # noqa: F401
            url = 'postgresql+psycopg://' + url[len('postgresql://'):]
        except Exception:
            pass

    return url

def verificar_inicializar_banco():
    """Verifica se o banco de dados existe e o inicializa se necessário."""
    if _env_flag('SKIP_DB_CHECKS'):
        logger.info("SKIP_DB_CHECKS ativo - pulando verificações/migrações de banco")
        return

    force_sqlite = os.getenv('FORCE_SQLITE', '').strip().lower() in ('1', 'true', 'yes')
    database_url = '' if force_sqlite else _get_database_url_from_env()
    
    # Se for PostgreSQL (Supabase), usar script de migração rápido
    if database_url.startswith('postgresql://') or database_url.startswith('postgresql+psycopg://') or database_url.startswith('postgresql+psycopg2://'):
        is_serverless = bool(os.getenv('VERCEL') or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
        run_startup_migrations = _env_flag('RUN_STARTUP_MIGRATIONS')
        if is_serverless and not run_startup_migrations:
            logger.info("Ambiente serverless detectado: rodando apenas migrações críticas (defina RUN_STARTUP_MIGRATIONS=1 para habilitar todas)")

            # Migrações críticas para evitar 500 por colunas/tabelas faltantes
            try:
                from migrations.add_estoque_pecas_localizacao_grid import migrate_postgres as migrate_estoque_grid_pg
                migrate_estoque_grid_pg()
            except Exception as col_err:
                if _is_max_connections_error(col_err):
                    logger.warning("Supabase sem conexões disponíveis (Max client connections reached). Pulando migrações críticas do estoque.")
                    return
                logger.warning(f"Erro ao migrar estoque_pecas (localizacao grid): {str(col_err)}")

            try:
                from migrations.add_estoque_pecas_merge_compartilhado import migrate_postgres as migrate_estoque_merge_pg
                migrate_estoque_merge_pg()
            except Exception as col_err:
                if _is_max_connections_error(col_err):
                    logger.warning("Supabase sem conexões disponíveis (Max client connections reached). Pulando migrações críticas do estoque.")
                    return
                logger.warning(f"Erro ao migrar estoque_pecas (merge/compartilhado): {str(col_err)}")

            try:
                from migrations.add_estoque_pecas_slot_temporario import migrate_postgres as migrate_estoque_temp_pg
                migrate_estoque_temp_pg()
            except Exception as col_err:
                if _is_max_connections_error(col_err):
                    logger.warning("Supabase sem conexões disponíveis (Max client connections reached). Pulando migrações críticas do estoque.")
                    return
                logger.warning(f"Erro ao migrar estoque_pecas (slot temporário): {str(col_err)}")

            return

        logger.info("Usando PostgreSQL (Supabase) - verificando tabelas de apontamento...")
        try:
            # Usar script rápido com timeout
            result = subprocess.run(
                [sys.executable, 'migrate_apontamento_supabase_fast.py'], 
                timeout=15,  # Timeout de 15 segundos
                capture_output=True, 
                text=True
            )
            
            if result.returncode == 0:
                logger.info("Tabelas PostgreSQL verificadas/criadas com sucesso.")
            else:
                logger.warning(f"Script de migração retornou código {result.returncode}")
                if result.stderr:
                    logger.warning(f"Stderr: {result.stderr[:200]}")
                    
        except subprocess.TimeoutExpired:
            logger.warning("Timeout na migração PostgreSQL - continuando sem migração")
                
        except subprocess.CalledProcessError as e:
            logger.warning(f"Migração retornou código {e.returncode}, mas pode estar OK")
        except Exception as e:
            logger.warning(f"Erro na migração PostgreSQL: {str(e)[:100]} - continuando")

        # Migrações do Estoque de Peças (críticas para evitar 500 por coluna/tabela faltante)
        try:
            from migrations.add_estoque_pecas_localizacao_grid import migrate_postgres as migrate_estoque_grid_pg
            migrate_estoque_grid_pg()
            logger.info("Colunas de localização do estoque_pecas verificadas/adicionadas (Supabase).")
        except Exception as col_err:
            if _is_max_connections_error(col_err):
                logger.warning("Supabase sem conexões disponíveis (Max client connections reached). Pulando migrações de estoque_pecas.")
                return
            logger.warning(f"Erro ao migrar estoque_pecas (localizacao grid): {str(col_err)}")

        try:
            from migrations.add_estoque_pecas_merge_compartilhado import migrate_postgres as migrate_estoque_merge_pg
            migrate_estoque_merge_pg()
            logger.info("Colunas de mescla/compartilhado do estoque_pecas verificadas/adicionadas (Supabase).")
        except Exception as col_err:
            if _is_max_connections_error(col_err):
                logger.warning("Supabase sem conexões disponíveis (Max client connections reached). Pulando migrações de estoque_pecas.")
                return
            logger.warning(f"Erro ao migrar estoque_pecas (merge/compartilhado): {str(col_err)}")

        try:
            from migrations.add_estoque_pecas_slot_temporario import migrate_postgres as migrate_estoque_temp_pg
            migrate_estoque_temp_pg()
            logger.info("Tabela/coluna de slot temporário do estoque_pecas verificadas/criadas (Supabase).")
        except Exception as col_err:
            if _is_max_connections_error(col_err):
                logger.warning("Supabase sem conexões disponíveis (Max client connections reached). Pulando migrações de estoque_pecas.")
                return
            logger.warning(f"Erro ao migrar estoque_pecas (slot temporário): {str(col_err)}")

        try:
            from migrations.add_estoque_pecas_linha_fim import migrate_postgres as migrate_estoque_linha_fim_pg
            migrate_estoque_linha_fim_pg()
            logger.info("Colunas linha_fim do estoque_pecas/slot_temp verificadas/adicionadas (Supabase).")
        except Exception as col_err:
            if _is_max_connections_error(col_err):
                logger.warning("Supabase sem conexões disponíveis (Max client connections reached). Pulando migrações de estoque_pecas.")
                return
            logger.warning(f"Erro ao migrar estoque_pecas (linha_fim): {str(col_err)}")

        try:
            from migrations.add_estoque_pecas_slots_json import migrate_postgres as migrate_estoque_slots_json_pg
            migrate_estoque_slots_json_pg()
            logger.info("Colunas slots_json do estoque_pecas/slot_temp verificadas/adicionadas (Supabase).")
        except Exception as col_err:
            if _is_max_connections_error(col_err):
                logger.warning("Supabase sem conexões disponíveis (Max client connections reached). Pulando migrações de estoque_pecas.")
                return
            logger.warning(f"Erro ao migrar estoque_pecas (slots_json): {str(col_err)}")

        try:
            from migrations.add_item_importacao_estoque_flag import migrate_postgres as migrate_item_importacao_estoque_flag_pg
            migrate_item_importacao_estoque_flag_pg()
            logger.info("Campo criado_via_importacao_estoque do item verificado/adicionado (Supabase).")
        except Exception as col_err:
            if _is_max_connections_error(col_err):
                logger.warning("Supabase sem conexões disponíveis (Max client connections reached). Pulando migrações de item.")
                return
            logger.warning(f"Erro ao migrar item (criado_via_importacao_estoque): {str(col_err)}")

        try:
            from migrations.add_item_valor_usuario_acesso_valores import migrate_postgres as migrate_item_valor_usuario_acesso_valores_pg
            migrate_item_valor_usuario_acesso_valores_pg()
            logger.info("Campos valor_item/acesso_valores_itens verificados/adicionados (Supabase).")
        except Exception as col_err:
            if _is_max_connections_error(col_err):
                logger.warning("Supabase sem conexões disponíveis (Max client connections reached). Pulando migrações de valores.")
                return
            logger.warning(f"Erro ao migrar valores de itens/permissões: {str(col_err)}")
        
        # Habilitar RLS nas tabelas temporárias (segurança Supabase)
        try:
            from migrations.enable_rls_temp_tables import migrate_postgres as migrate_rls_temp_tables_pg
            migrate_rls_temp_tables_pg()
            logger.info("RLS habilitado nas tabelas temporárias (Supabase).")
        except Exception as col_err:
            if _is_max_connections_error(col_err):
                logger.warning("Supabase sem conexões disponíveis (Max client connections reached). Pulando migração RLS.")
                return
            logger.warning(f"Erro ao habilitar RLS nas tabelas temporárias: {str(col_err)}")
        
        # Criar tabelas de lista de retirada
        try:
            from migrations.add_lista_retirada_tables import migrate_postgres as migrate_lista_retirada_pg
            migrate_lista_retirada_pg()
            logger.info("Tabelas lista_retirada criadas/verificadas (Supabase).")
        except Exception as col_err:
            if _is_max_connections_error(col_err):
                logger.warning("Supabase sem conexões disponíveis (Max client connections reached). Pulando migração lista_retirada.")
                return
            logger.warning(f"Erro ao criar tabelas lista_retirada: {str(col_err)}")
            
        # Executar migrações adicionais para PostgreSQL
        try:
            from migrations.add_categoria_trabalho import migrate_postgres
            if migrate_postgres():
                logger.info("Coluna categoria_trabalho verificada/adicionada com sucesso.")
            else:
                logger.warning("Falha ao verificar/adicionar coluna categoria_trabalho.")
        except Exception as col_err:
            if _is_max_connections_error(col_err):
                logger.warning("Supabase sem conexões disponíveis (Max client connections reached). Pulando demais migrações de startup.")
                return
            logger.warning(f"Erro ao migrar coluna categoria_trabalho: {str(col_err)}")

        try:
            from migrations.add_quantidade_snapshot import migrate_postgres as migrate_snapshot_pg
            if migrate_snapshot_pg():
                logger.info("Coluna quantidade_snapshot verificada/adicionada com sucesso.")
            else:
                logger.warning("Falha ao verificar/adicionar coluna quantidade_snapshot.")
        except Exception as col_err:
            if _is_max_connections_error(col_err):
                logger.warning("Supabase sem conexões disponíveis (Max client connections reached). Pulando demais migrações de startup.")
                return
            logger.warning(f"Erro ao migrar coluna quantidade_snapshot: {str(col_err)}")

        try:
            from migrations.add_pode_gerenciar_apontamentos import migrate_postgresql_engine
            if migrate_postgresql_engine(db.engine):
                logger.info("Coluna pode_gerenciar_apontamentos verificada/adicionada com sucesso.")
            else:
                logger.warning("Falha ao verificar/adicionar coluna pode_gerenciar_apontamentos.")
        except Exception as col_err:
            if _is_max_connections_error(col_err):
                logger.warning("Supabase sem conexões disponíveis. Pulando migração pode_gerenciar_apontamentos.")
                return
            logger.warning(f"Erro ao migrar coluna pode_gerenciar_apontamentos: {str(col_err)}")

        try:
            from migrations.alter_pedido_nome_item_length import migrate_postgres as migrate_pedido_nome_item_len
            if migrate_pedido_nome_item_len():
                logger.info("Coluna pedido.nome_item verificada/alterada para VARCHAR(255) (Supabase).")
            else:
                logger.warning("Falha ao verificar/alterar coluna pedido.nome_item (Supabase).")
        except Exception as col_err:
            if _is_max_connections_error(col_err):
                logger.warning("Supabase sem conexões disponíveis (Max client connections reached). Pulando demais migrações de startup.")
                return
            logger.warning(f"Erro ao migrar coluna pedido.nome_item: {str(col_err)}")

        try:
            from migrations.enable_rls_public_tables import migrate_postgres as migrate_rls_public
            if migrate_rls_public():
                logger.info("RLS verificado/habilitado nas tabelas public (Supabase).")
            else:
                logger.warning("Falha ao verificar/habilitar RLS nas tabelas public.")
        except Exception as col_err:
            if _is_max_connections_error(col_err):
                logger.warning("Supabase sem conexões disponíveis (Max client connections reached). Pulando demais migrações de startup.")
                return
            logger.warning(f"Erro ao migrar RLS public tables: {str(col_err)}")

        try:
            from migrations.add_indexes_and_pk_postgres import migrate_postgres as migrate_indexes_pk
            if migrate_indexes_pk():
                logger.info("Índices de FKs e PKs de tabelas backup verificados/criados (Supabase).")
            else:
                logger.warning("Falha ao verificar/criar índices de FKs e PKs de tabelas backup (Supabase).")
        except Exception as col_err:
            if _is_max_connections_error(col_err):
                logger.warning("Supabase sem conexões disponíveis (Max client connections reached). Pulando demais migrações de startup.")
                return
            logger.warning(f"Erro ao migrar índices/PKs Postgres: {str(col_err)}")
            
        # Executar migração para adicionar coluna tipo_bruto em Item
        try:
            from migrations.add_tipo_bruto_item import migrate_postgres as migrate_tipo_bruto_postgres
            if migrate_tipo_bruto_postgres():
                logger.info("Coluna tipo_bruto verificada/adicionada com sucesso.")
            else:
                logger.warning("Falha ao verificar/adicionar coluna tipo_bruto.")
        except Exception as col_err:
            if _is_max_connections_error(col_err):
                logger.warning("Supabase sem conexões disponíveis (Max client connections reached). Pulando demais migrações de startup.")
                return
            logger.warning(f"Erro ao migrar coluna tipo_bruto: {str(col_err)}")

        try:
            from migrations.add_blank_laser_item import migrate_postgres as migrate_blank_laser_postgres
            if migrate_blank_laser_postgres():
                logger.info("Coluna blank_laser verificada/adicionada com sucesso.")
            else:
                logger.warning("Falha ao verificar/adicionar coluna blank_laser.")
        except Exception as col_err:
            if _is_max_connections_error(col_err):
                logger.warning("Supabase sem conexões disponíveis (Max client connections reached). Pulando demais migrações de startup.")
                return
            logger.warning(f"Erro ao migrar coluna blank_laser: {str(col_err)}")

        try:
            from migrations.add_laser_material_fields_item import migrate_postgres as migrate_laser_material_fields_postgres
            if migrate_laser_material_fields_postgres():
                logger.info("Colunas material_laser/espessura_laser verificadas/adicionadas com sucesso.")
            else:
                logger.warning("Falha ao verificar/adicionar colunas material_laser/espessura_laser.")
        except Exception as col_err:
            if _is_max_connections_error(col_err):
                logger.warning("Supabase sem conexões disponíveis (Max client connections reached). Pulando demais migrações de startup.")
                return
            logger.warning(f"Erro ao migrar colunas material_laser/espessura_laser: {str(col_err)}")

        try:
            from migrations.add_laser_fields_item_pedido_material import migrate_postgres as migrate_item_pedido_material_laser_postgres
            if migrate_item_pedido_material_laser_postgres():
                logger.info("Estrutura de item_pedido_material para laser verificada/adicionada com sucesso.")
            else:
                logger.warning("Falha ao verificar/adicionar estrutura de item_pedido_material para laser.")
        except Exception as col_err:
            if _is_max_connections_error(col_err):
                logger.warning("Supabase sem conexões disponíveis (Max client connections reached). Pulando demais migrações de startup.")
                return
            logger.warning(f"Erro ao migrar estrutura de item_pedido_material para laser: {str(col_err)}")
            
        # Executar migração para adicionar coluna tamanho_peca em Item
        try:
            from migrations.add_tamanho_peca_item import migrate_postgres as migrate_tamanho_peca_postgres
            if migrate_tamanho_peca_postgres():
                logger.info("Coluna tamanho_peca verificada/adicionada com sucesso.")
            else:
                logger.warning("Falha ao verificar/adicionar coluna tamanho_peca.")
        except Exception as col_err:
            if _is_max_connections_error(col_err):
                logger.warning("Supabase sem conexões disponíveis (Max client connections reached). Pulando demais migrações de startup.")
                return
            logger.warning(f"Erro ao migrar coluna tamanho_peca: {str(col_err)}")

        # Executar migração para adicionar colunas tipo_item e categoria_montagem em Item
        try:
            from migrations.add_tipo_item_categoria_montagem_item import migrate_postgres as migrate_tipo_item_postgres
            if migrate_tipo_item_postgres():
                logger.info("Colunas tipo_item/categoria_montagem verificadas/adicionadas com sucesso.")
            else:
                logger.warning("Falha ao verificar/adicionar colunas tipo_item/categoria_montagem.")
        except Exception as col_err:
            if _is_max_connections_error(col_err):
                logger.warning("Supabase sem conexões disponíveis (Max client connections reached). Pulando demais migrações de startup.")
                return
            logger.warning(f"Erro ao migrar colunas tipo_item/categoria_montagem: {str(col_err)}")

        # Executar migração para adicionar coluna comprimento_mm em item_composto
        try:
            from migrations.add_comprimento_mm_item_composto import migrate_postgres as migrate_composto_mm_postgres
            if migrate_composto_mm_postgres():
                logger.info("Coluna comprimento_mm verificada/adicionada com sucesso em item_composto.")
            else:
                logger.warning("Falha ao verificar/adicionar coluna comprimento_mm em item_composto.")
        except Exception as col_err:
            if _is_max_connections_error(col_err):
                logger.warning("Supabase sem conexões disponíveis (Max client connections reached). Pulando demais migrações de startup.")
                return
            logger.warning(f"Erro ao migrar coluna comprimento_mm em item_composto: {str(col_err)}")

        # Executar migração para criar tabelas de Pedido de Montagem
        try:
            from migrations.add_pedido_montagem_tables import migrate_postgres as migrate_pedido_montagem_postgres
            if migrate_pedido_montagem_postgres():
                logger.info("Tabelas/colunas de Pedido de Montagem verificadas/criadas com sucesso.")
            else:
                logger.warning("Falha ao verificar/criar tabelas/colunas de Pedido de Montagem.")
        except Exception as col_err:
            if _is_max_connections_error(col_err):
                logger.warning("Supabase sem conexões disponíveis (Max client connections reached). Pulando demais migrações de startup.")
                return
            logger.warning(f"Erro ao migrar tabelas/colunas de Pedido de Montagem: {str(col_err)}")

        # Executar migração para criar tabelas de cotação/comparativo de Pedido de Montagem
        try:
            from migrations.add_cotacao_pedido_montagem_tables import migrate_postgres as migrate_cotacao_pedido_montagem_postgres
            if migrate_cotacao_pedido_montagem_postgres():
                logger.info("Tabelas de cotação/comparativo de Pedido de Montagem verificadas/criadas com sucesso.")
            else:
                logger.warning("Falha ao verificar/criar tabelas de cotação/comparativo de Pedido de Montagem.")
        except Exception as col_err:
            if _is_max_connections_error(col_err):
                logger.warning("Supabase sem conexões disponíveis (Max client connections reached). Pulando demais migrações de startup.")
                return
            logger.warning(f"Erro ao migrar tabelas de cotação/comparativo de Pedido de Montagem: {str(col_err)}")

        try:
            from migrations.add_aprovacao_campos import migrate_postgres as migrate_aprovacao_postgres
            if migrate_aprovacao_postgres():
                logger.info("Campos de aprovação verificados/adicionados com sucesso.")
            else:
                logger.warning("Falha ao verificar/adicionar campos de aprovação.")
        except Exception as col_err:
            if _is_max_connections_error(col_err):
                logger.warning("Supabase sem conexões disponíveis (Max client connections reached). Pulando demais migrações de startup.")
                return
            logger.warning(f"Erro ao migrar campos de aprovação: {str(col_err)}")
            
        # Executar migração para adicionar colunas imagem e data_cadastro
        try:
            from migrations.add_columns_maquina import migrate_postgres as migrate_colunas_postgres
            if migrate_colunas_postgres():
                logger.info("Colunas imagem e data_cadastro verificadas/adicionadas com sucesso.")
            else:
                logger.warning("Falha ao verificar/adicionar colunas imagem e data_cadastro.")
        except Exception as cols_err:
            if _is_max_connections_error(cols_err):
                logger.warning("Supabase sem conexões disponíveis (Max client connections reached). Pulando demais migrações de startup.")
                return
            logger.warning(f"Erro ao migrar colunas imagem e data_cadastro: {str(cols_err)}")
            
        return
    
    # Para SQLite, verificar se arquivo existe
    logger.info("Usando SQLite local...")
    db_dir = os.getenv('DB_DIR', os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(db_dir, 'database.db')
    
    if not os.path.exists(db_path):
        logger.info(f"Banco de dados SQLite não encontrado em {db_path}. Inicializando...")
        subprocess.run([sys.executable, 'init_db_local.py'], check=True)
        logger.info("Banco de dados SQLite inicializado com sucesso.")
    else:
        logger.info(f"Banco de dados SQLite verificado: {db_path}")
        
        # Verificar se tabelas de apontamento existem
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Verificar se tabela apontamento_producao existe
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='apontamento_producao';")
            if not cursor.fetchone():
                logger.info("Tabelas de apontamento não encontradas. Executando migração...")
                subprocess.run([sys.executable, 'migrate_apontamento.py'], check=True)
                logger.info("Migração de apontamento concluída.")
            
            # Verificar se tabela maquina tem a coluna categoria_trabalho
            try:
                cursor.execute("PRAGMA table_info(maquina)")
                columns = [column[1] for column in cursor.fetchall()]
                if 'categoria_trabalho' not in columns:
                    logger.info("Coluna categoria_trabalho não encontrada na tabela maquina. Executando migração...")
                    from migrations.add_categoria_trabalho import migrate_sqlite
                    if migrate_sqlite():
                        logger.info("Coluna categoria_trabalho adicionada com sucesso à tabela maquina.")
                    else:
                        logger.warning("Falha ao adicionar coluna categoria_trabalho à tabela maquina.")
                        
                # Verificar se tabela usuario tem a coluna pode_gerenciar_apontamentos
                cursor.execute("PRAGMA table_info(usuario)")
                usuario_columns = [column[1] for column in cursor.fetchall()]
                if 'pode_gerenciar_apontamentos' not in usuario_columns:
                    logger.info("Coluna pode_gerenciar_apontamentos não encontrada na tabela usuario. Executando migração...")
                    from migrations.add_pode_gerenciar_apontamentos import migrate_sqlite as migrate_pode_gerenciar
                    if migrate_pode_gerenciar(conn):
                        logger.info("Coluna pode_gerenciar_apontamentos adicionada com sucesso à tabela usuario.")
                    else:
                        logger.warning("Falha ao adicionar coluna pode_gerenciar_apontamentos à tabela usuario.")
                
                # Verificar se tabela maquina tem as colunas imagem e data_cadastro
                if 'imagem' not in columns or 'data_cadastro' not in columns:
                    logger.info("Colunas imagem ou data_cadastro não encontradas na tabela maquina. Executando migração...")
                    from migrations.add_columns_maquina import migrate_sqlite
                    if migrate_sqlite():
                        logger.info("Colunas imagem e data_cadastro adicionadas com sucesso à tabela maquina.")
                    else:
                        logger.warning("Falha ao adicionar colunas imagem e data_cadastro à tabela maquina.")
                
                # Verificar se tabela pedido_ordem_servico tem a coluna quantidade_snapshot
                cursor.execute("PRAGMA table_info(pedido_ordem_servico)")
                pos_columns = [column[1] for column in cursor.fetchall()]
                if 'quantidade_snapshot' not in pos_columns:
                    logger.info("Coluna quantidade_snapshot não encontrada na tabela pedido_ordem_servico. Executando migração...")
                    from migrations.add_quantidade_snapshot import migrate_sqlite as migrate_snapshot_sqlite
                    if migrate_snapshot_sqlite():
                        logger.info("Coluna quantidade_snapshot adicionada com sucesso à tabela pedido_ordem_servico.")
                    else:
                        logger.warning("Falha ao adicionar coluna quantidade_snapshot à tabela pedido_ordem_servico.")

                # Verificar se tabela item_composto tem a coluna comprimento_mm
                try:
                    cursor.execute("PRAGMA table_info(item_composto)")
                    composto_columns = [column[1] for column in cursor.fetchall()]
                    if 'comprimento_mm' not in composto_columns:
                        logger.info("Coluna comprimento_mm não encontrada na tabela item_composto. Executando migração...")
                        from migrations.add_comprimento_mm_item_composto import migrate_sqlite as migrate_composto_mm_sqlite
                        if migrate_composto_mm_sqlite():
                            logger.info("Coluna comprimento_mm adicionada com sucesso à tabela item_composto.")
                        else:
                            logger.warning("Falha ao adicionar coluna comprimento_mm à tabela item_composto.")
                except Exception as e:
                    logger.warning(f"Erro ao verificar/migrar coluna comprimento_mm em item_composto: {str(e)}")
                        
                # Verificar se tabela item tem a coluna tipo_bruto
                try:
                    cursor.execute("PRAGMA table_info(item)")
                    item_columns = [column[1] for column in cursor.fetchall()]
                    if 'tipo_bruto' not in item_columns:
                        logger.info("Coluna tipo_bruto não encontrada na tabela item. Executando migração...")
                        from migrations.add_tipo_bruto_item import migrate_sqlite as migrate_tipo_bruto_sqlite
                        if migrate_tipo_bruto_sqlite():
                            logger.info("Coluna tipo_bruto adicionada com sucesso à tabela item.")
                        else:
                            logger.warning("Falha ao adicionar coluna tipo_bruto à tabela item.")
                    if 'blank_laser' not in item_columns:
                        logger.info("Coluna blank_laser não encontrada na tabela item. Executando migração...")
                        from migrations.add_blank_laser_item import migrate_sqlite as migrate_blank_laser_sqlite
                        if migrate_blank_laser_sqlite():
                            logger.info("Coluna blank_laser adicionada com sucesso à tabela item.")
                        else:
                            logger.warning("Falha ao adicionar coluna blank_laser à tabela item.")
                    if 'material_laser' not in item_columns or 'espessura_laser' not in item_columns:
                        logger.info("Colunas material_laser/espessura_laser não encontradas na tabela item. Executando migração...")
                        from migrations.add_laser_material_fields_item import migrate_sqlite as migrate_laser_material_fields_sqlite
                        if migrate_laser_material_fields_sqlite():
                            logger.info("Colunas material_laser/espessura_laser adicionadas com sucesso à tabela item.")
                        else:
                            logger.warning("Falha ao adicionar colunas material_laser/espessura_laser à tabela item.")

                    cursor.execute("PRAGMA table_info(item_pedido_material)")
                    item_pedido_material_columns = [column[1] for column in cursor.fetchall()]
                    item_pedido_material_material_col = next((column for column in cursor.execute("PRAGMA table_info(item_pedido_material)").fetchall() if column[1] == 'material_id'), None)
                    item_pedido_material_material_notnull = bool(item_pedido_material_material_col and item_pedido_material_material_col[3] == 1)
                    if 'descricao_material' not in item_pedido_material_columns or 'item_origem_id' not in item_pedido_material_columns or item_pedido_material_material_notnull:
                        logger.info("Estrutura de item_pedido_material para laser não encontrada/completa. Executando migração...")
                        from migrations.add_laser_fields_item_pedido_material import migrate_sqlite as migrate_item_pedido_material_laser_sqlite
                        if migrate_item_pedido_material_laser_sqlite():
                            logger.info("Estrutura de item_pedido_material para laser ajustada com sucesso.")
                        else:
                            logger.warning("Falha ao ajustar estrutura de item_pedido_material para laser.")
                    if 'tamanho_peca' not in item_columns:
                        logger.info("Coluna tamanho_peca não encontrada na tabela item. Executando migração...")
                        from migrations.add_tamanho_peca_item import migrate_sqlite as migrate_tamanho_peca_sqlite
                        if migrate_tamanho_peca_sqlite():
                            logger.info("Coluna tamanho_peca adicionada com sucesso à tabela item.")
                        else:
                            logger.warning("Falha ao adicionar coluna tamanho_peca à tabela item.")

                    if 'tipo_item' not in item_columns or 'categoria_montagem' not in item_columns:
                        logger.info("Colunas tipo_item/categoria_montagem não encontradas na tabela item. Executando migração...")
                        from migrations.add_tipo_item_categoria_montagem_item import migrate_sqlite as migrate_tipo_item_sqlite
                        if migrate_tipo_item_sqlite():
                            logger.info("Colunas tipo_item/categoria_montagem adicionadas com sucesso à tabela item.")
                        else:
                            logger.warning("Falha ao adicionar colunas tipo_item/categoria_montagem à tabela item.")

                    # Tabelas/coluna de pedido de montagem
                    cursor.execute("PRAGMA table_info(pedido)")
                    pedido_columns = [column[1] for column in cursor.fetchall()]
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pedido_montagem';")
                    has_pedido_montagem_table = cursor.fetchone() is not None
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='item_pedido_montagem';")
                    has_item_pedido_montagem_table = cursor.fetchone() is not None
                    if 'numero_pedido_montagem' not in pedido_columns or (not has_pedido_montagem_table) or (not has_item_pedido_montagem_table):
                        logger.info("Estruturas de Pedido de Montagem não encontradas. Executando migração...")
                        from migrations.add_pedido_montagem_tables import migrate_sqlite as migrate_pedido_montagem_sqlite
                        if migrate_pedido_montagem_sqlite():
                            logger.info("Estruturas de Pedido de Montagem criadas com sucesso.")
                        else:
                            logger.warning("Falha ao criar estruturas de Pedido de Montagem.")

                    # Tabelas de cotação/comparativo de pedido de montagem
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cotacao_pedido_montagem';")
                    has_cotacao_pm = cursor.fetchone() is not None
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cotacao_item_pedido_montagem';")
                    has_cotacao_item_pm = cursor.fetchone() is not None
                    if (not has_cotacao_pm) or (not has_cotacao_item_pm):
                        logger.info("Estruturas de comparativo (Pedido de Montagem) não encontradas. Executando migração...")
                        from migrations.add_cotacao_pedido_montagem_tables import migrate_sqlite as migrate_cotacao_pm_sqlite
                        if migrate_cotacao_pm_sqlite():
                            logger.info("Estruturas de comparativo (Pedido de Montagem) criadas com sucesso.")
                        else:
                            logger.warning("Falha ao criar estruturas de comparativo (Pedido de Montagem).")

                    try:
                        from migrations.add_aprovacao_campos import migrate_sqlite as migrate_aprovacao_sqlite
                        if migrate_aprovacao_sqlite():
                            logger.info("Campos de aprovação verificados/adicionados com sucesso.")
                        else:
                            logger.warning("Falha ao verificar/adicionar campos de aprovação.")
                    except Exception as e:
                        logger.warning(f"Erro ao verificar/migrar campos de aprovação: {str(e)}")

                    try:
                        from migrations.add_item_desenho_aprovacao_campos import migrate_sqlite as migrate_item_desenho_aprovacao_sqlite
                        if migrate_item_desenho_aprovacao_sqlite():
                            logger.info("Campos de aprovação de desenho do Item verificados/adicionados com sucesso.")
                        else:
                            logger.warning("Falha ao verificar/adicionar campos de aprovação de desenho do Item.")
                    except Exception as e:
                        logger.warning(f"Erro ao verificar/migrar campos de aprovação de desenho do Item: {str(e)}")

                    try:
                        from migrations.add_estoque_pecas_localizacao_grid import migrate_sqlite as migrate_estoque_pecas_localizacao_sqlite
                        if migrate_estoque_pecas_localizacao_sqlite():
                            logger.info("Campos de localização (grid) do Estoque de Peças verificados/adicionados com sucesso.")
                        else:
                            logger.warning("Falha ao verificar/adicionar campos de localização (grid) do Estoque de Peças.")
                    except Exception as e:
                        logger.warning(f"Erro ao verificar/migrar campos de localização (grid) do Estoque de Peças: {str(e)}")

                    try:
                        from migrations.add_estoque_pecas_linha_fim import migrate_sqlite as migrate_estoque_pecas_linha_fim_sqlite
                        if migrate_estoque_pecas_linha_fim_sqlite():
                            logger.info("Campos linha_fim do Estoque de Peças verificados/adicionados com sucesso.")
                        else:
                            logger.warning("Falha ao verificar/adicionar campos linha_fim do Estoque de Peças.")
                    except Exception as e:
                        logger.warning(f"Erro ao verificar/migrar campos linha_fim do Estoque de Peças: {str(e)}")

                    try:
                        from migrations.add_estoque_pecas_slots_json import migrate_sqlite as migrate_estoque_pecas_slots_json_sqlite
                        if migrate_estoque_pecas_slots_json_sqlite():
                            logger.info("Campos slots_json do Estoque de Peças verificados/adicionados com sucesso.")
                        else:
                            logger.warning("Falha ao verificar/adicionar campos slots_json do Estoque de Peças.")
                    except Exception as e:
                        logger.warning(f"Erro ao verificar/migrar campos slots_json do Estoque de Peças: {str(e)}")

                    try:
                        from migrations.add_item_importacao_estoque_flag import migrate_sqlite as migrate_item_importacao_estoque_flag_sqlite
                        if migrate_item_importacao_estoque_flag_sqlite():
                            logger.info("Campo criado_via_importacao_estoque do item verificado/adicionado com sucesso.")
                        else:
                            logger.warning("Falha ao verificar/adicionar campo criado_via_importacao_estoque do item.")
                    except Exception as e:
                        logger.warning(f"Erro ao verificar/migrar campo criado_via_importacao_estoque do item: {str(e)}")

                    try:
                        from migrations.add_item_valor_usuario_acesso_valores import migrate_sqlite as migrate_item_valor_usuario_acesso_valores_sqlite
                        if migrate_item_valor_usuario_acesso_valores_sqlite():
                            logger.info("Campos valor_item/acesso_valores_itens verificados/adicionados com sucesso.")
                        else:
                            logger.warning("Falha ao verificar/adicionar campos valor_item/acesso_valores_itens.")
                    except Exception as e:
                        logger.warning(f"Erro ao verificar/migrar campos valor_item/acesso_valores_itens: {str(e)}")
                except Exception as col_err:
                    logger.warning(f"Erro ao verificar/adicionar coluna tipo_bruto na tabela item: {str(col_err)}")
            except Exception as col_err:
                logger.warning(f"Erro ao verificar/adicionar colunas na tabela maquina: {str(col_err)}")
                
            conn.close()
            
        except Exception as e:
            logger.exception("Erro ao verificar tabelas")
            # Se houver erro, tentar migração
            try:
                subprocess.run([sys.executable, 'migrate_apontamento.py'], check=True)
                logger.info("Migração de apontamento concluída.")
            except Exception as migrate_error:
                logger.exception("Erro na migração")

def create_app():
    # Definir diretório de banco gravável para init_db.py
    os.environ['DB_DIR'] = WRITABLE_DIR
    # Verificar e inicializar o banco de dados antes de criar a aplicação (a menos que pulado)
    is_serverless = bool(os.getenv('VERCEL') or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
    run_startup_migrations = _env_flag('RUN_STARTUP_MIGRATIONS')
    skip_db_checks = _env_flag('SKIP_DB_CHECKS') or (is_serverless and not run_startup_migrations)

    if not skip_db_checks:
        verificar_inicializar_banco()
    else:
        if is_serverless and not run_startup_migrations and not _env_flag('SKIP_DB_CHECKS'):
            logger.info("Ambiente serverless detectado: pulando verificar_inicializar_banco() (defina RUN_STARTUP_MIGRATIONS=1 para habilitar)")
        else:
            logger.info("SKIP_DB_CHECKS habilitado: pulando verificar_inicializar_banco()")
    
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'acbusinagem2023')
    # Configurar DATABASE_URL: PostgreSQL (produção) ou SQLite (desenvolvimento/temporário)
    # FORCE_SQLITE: força SQLite mesmo que DATABASE_URL esteja configurada (útil para testes locais)
    force_sqlite = os.getenv('FORCE_SQLITE', '').strip().lower() in ('1', 'true', 'yes')
    database_url = None if force_sqlite else _get_database_url_from_env()
    if not database_url:
        # Usar SQLite local como fallback ou quando FORCE_SQLITE está ativo
        db_path = os.path.join(WRITABLE_DIR, 'database.db')
        database_url = f'sqlite:///{db_path}'

    # Preferir psycopg3 (psycopg) no Python 3.13+ quando URL for PostgreSQL genérica
    # Isso evita dependência de psycopg2 que pode não ter wheel no Windows/Py3.13
    if database_url:
        db_url_lower = database_url.lower()
        if db_url_lower.startswith('postgres://'):
            database_url = 'postgresql://' + database_url[len('postgres://'):]
            db_url_lower = database_url.lower()
        if db_url_lower.startswith('postgresql://') and '+psycopg' not in db_url_lower and '+psycopg2' not in db_url_lower:
            try:
                import psycopg  # noqa: F401
                database_url = 'postgresql+psycopg://' + database_url[len('postgresql://'):]
            except Exception:
                pass
    
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.logger.info(
        "Usando banco: %s",
        'PostgreSQL (Supabase)'
        if (database_url.startswith('postgresql://') or database_url.startswith('postgresql+'))
        else 'SQLite'
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    if database_url and database_url.lower().startswith('postgresql'):
        engine_options = {
            'pool_pre_ping': True,
        }

        # Em ambiente serverless, evitar pool de conexões para reduzir "Max client connections reached".
        if is_serverless:
            engine_options['poolclass'] = NullPool
            engine_options['pool_recycle'] = 60
        else:
            engine_options['pool_recycle'] = 180
            engine_options['pool_size'] = int(os.getenv('DB_POOL_SIZE', '5') or 5)
            engine_options['max_overflow'] = int(os.getenv('DB_MAX_OVERFLOW', '5') or 5)
            engine_options['pool_timeout'] = int(os.getenv('DB_POOL_TIMEOUT', '30') or 30)
        # Supabase / poolers podem causar "DuplicatePreparedStatement" no psycopg3.
        # Desativar prepared statements evita esse erro.
        if database_url.lower().startswith('postgresql+psycopg://'):
            engine_options['connect_args'] = {
                'prepare_threshold': None,
            }
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = engine_options
    app.config['UPLOAD_FOLDER_DESENHOS'] = os.path.join(basedir, 'uploads/desenhos')
    app.config['UPLOAD_FOLDER_INSTRUCOES'] = os.path.join(basedir, 'uploads/instrucoes')
    app.config['UPLOAD_FOLDER_IMAGENS'] = os.path.join(basedir, 'uploads/imagens')
    app.config['BACKUP_FOLDER'] = os.path.join(basedir, 'backups')
    
    # Garantir que as pastas de upload existam
    # Tentar criar pastas de upload se possível; ignorar em ambiente somente leitura
    for path in [
        app.config['UPLOAD_FOLDER_DESENHOS'],
        app.config['UPLOAD_FOLDER_INSTRUCOES'],
        app.config['UPLOAD_FOLDER_IMAGENS']
    ]:
        try:
            os.makedirs(path, exist_ok=True)
        except (PermissionError, OSError):
            pass  # Ignorar erros de permissão ou sistema de arquivos somente leitura
    try:
        os.makedirs(app.config['BACKUP_FOLDER'], exist_ok=True)
    except (PermissionError, OSError):
        pass  # Ignorar erros de permissão ou sistema de arquivos somente leitura
    
    # Inicializar SQLAlchemy
    from models import db
    db.init_app(app)

    def _register_audit_logging(_app):
        if _app.extensions.get('audit_log_registered'):
            return

        from models import AuditLog

        def _get_actor():
            usuario = getattr(g, 'usuario', None)
            if usuario is not None:
                return usuario.id, getattr(usuario, 'nome', None)
            if 'usuario_id' in session:
                return session.get('usuario_id'), session.get('usuario_nome')
            return None, None

        def _get_request_meta():
            if not has_request_context():
                return None, None, None, None
            try:
                endpoint = request.endpoint
            except Exception:
                endpoint = None
            try:
                metodo = request.method
            except Exception:
                metodo = None
            try:
                ip = request.headers.get('X-Forwarded-For', request.remote_addr)
            except Exception:
                ip = None
            try:
                ua = request.headers.get('User-Agent')
            except Exception:
                ua = None
            return endpoint, metodo, ip, ua

        def _row_identity(obj):
            try:
                mapper = inspect(obj).mapper
                pks = [col.key for col in mapper.primary_key]
                if not pks:
                    return None
                if len(pks) == 1:
                    return str(getattr(obj, pks[0], None))
                return json.dumps({k: getattr(obj, k, None) for k in pks}, ensure_ascii=False, default=str)
            except Exception:
                return None

        def _collect_changes(obj, action):
            try:
                state = inspect(obj)
                mapper = state.mapper
                changes = {}

                for attr in mapper.column_attrs:
                    key = attr.key
                    if key == 'id':
                        continue
                    hist = state.attrs[key].history

                    if action == 'create':
                        val = getattr(obj, key, None)
                        if val is not None:
                            changes[key] = {'old': None, 'new': val}
                        continue

                    if action == 'delete':
                        val = getattr(obj, key, None)
                        if val is not None:
                            changes[key] = {'old': val, 'new': None}
                        continue

                    if action == 'update':
                        if not hist.has_changes():
                            continue
                        old = hist.deleted[0] if hist.deleted else None
                        new = hist.added[0] if hist.added else getattr(obj, key, None)
                        changes[key] = {'old': old, 'new': new}

                if not changes:
                    return None
                return changes
            except Exception:
                return None

        @event.listens_for(db.session.__class__, 'before_flush')
        def _audit_before_flush(session_, flush_context, instances):
            if session_.info.get('_audit_logging_disabled'):
                return

            usuario_id, usuario_nome = _get_actor()
            endpoint, metodo, ip, ua = _get_request_meta()

            def _add_log(acao, obj, changes):
                if isinstance(obj, AuditLog):
                    return

                entidade_tipo = obj.__class__.__name__
                entidade_id = _row_identity(obj)
                mudancas_json = None
                if changes is not None:
                    try:
                        mudancas_json = json.dumps(changes, ensure_ascii=False, default=str)
                    except Exception:
                        mudancas_json = None

                session_.add(
                    AuditLog(
                        usuario_id=usuario_id,
                        usuario_nome=usuario_nome,
                        acao=acao,
                        entidade_tipo=entidade_tipo,
                        entidade_id=entidade_id,
                        mudancas_json=mudancas_json,
                        endpoint=endpoint,
                        metodo=metodo,
                        ip=ip,
                        user_agent=ua,
                    )
                )

            for obj in list(session_.new):
                if isinstance(obj, AuditLog):
                    continue
                changes = _collect_changes(obj, 'create')
                _add_log('create', obj, changes)

            for obj in list(session_.dirty):
                if isinstance(obj, AuditLog):
                    continue
                if not session_.is_modified(obj, include_collections=False):
                    continue
                changes = _collect_changes(obj, 'update')
                if changes:
                    _add_log('update', obj, changes)

            for obj in list(session_.deleted):
                if isinstance(obj, AuditLog):
                    continue
                changes = _collect_changes(obj, 'delete')
                _add_log('delete', obj, changes)

        _app.extensions['audit_log_registered'] = True

    _register_audit_logging(app)
    
    if not skip_db_checks:
        with app.app_context():
            try:
                db.create_all()
            except OperationalError as e:
                if _is_max_connections_error(e):
                    app.logger.warning("Supabase sem conexões disponíveis (Max client connections reached). Pulando db.create_all()/seed nesta inicialização.")
                    # Deixar o app subir; requisições que dependem do DB serão tratadas com 503.
                    return app
                raise

            uri = app.config.get('SQLALCHEMY_DATABASE_URI') or ''
            db_type = 'PostgreSQL (Supabase)' if (uri.startswith('postgresql://') or uri.startswith('postgresql+')) else 'SQLite'
            app.logger.info("Tabelas %s criadas/verificadas com sucesso.", db_type)
            
            # Executar migração para adicionar numero_pedido_cliente
            try:
                from migrations.add_numero_pedido_cliente import upgrade
                upgrade(db.engine)
            except Exception as e:
                app.logger.warning(f"Migração numero_pedido_cliente: {str(e)}")

            # Executar migração para adicionar categoria_trabalho em gabarito_centro_usinagem
            try:
                from migrations.add_categoria_trabalho_gabarito_centro import upgrade
                upgrade(db.engine)
            except Exception as e:
                app.logger.warning(f"Migração categoria_trabalho (gabarito_centro_usinagem): {str(e)}")

            # Executar migração para adicionar bt/ar em folha_processo_torno_cnc
            try:
                from migrations.add_bt_ar_folha_torno_cnc import upgrade
                upgrade(db.engine)
            except Exception as e:
                app.logger.warning(f"Migração bt/ar (folha_processo_torno_cnc): {str(e)}")

            # Executar migração para adicionar campos suporte_bt/comprimento_fora em ferramentas
            try:
                from migrations.add_campos_ferramenta_suporte_comprimento import upgrade
                upgrade(db.engine)
            except Exception as e:
                app.logger.warning(f"Migração suporte_bt/comprimento_fora (ferramentas): {str(e)}")

            try:
                from migrations.add_item_desenho_aprovacao_campos import migrate_postgres as migrate_item_desenho_aprovacao_postgres
                if migrate_item_desenho_aprovacao_postgres():
                    app.logger.info("Campos de aprovação de desenho do Item verificados/adicionados com sucesso.")
                else:
                    app.logger.warning("Falha ao verificar/adicionar campos de aprovação de desenho do Item.")
            except Exception as e:
                app.logger.warning(f"Migração aprovação desenho do Item: {str(e)}")

            try:
                from migrations.add_estoque_pecas_localizacao_grid import migrate_postgres as migrate_estoque_pecas_localizacao_postgres
                if migrate_estoque_pecas_localizacao_postgres():
                    app.logger.info("Campos de localização (grid) do Estoque de Peças verificados/adicionados com sucesso.")
                else:
                    app.logger.warning("Falha ao verificar/adicionar campos de localização (grid) do Estoque de Peças.")
            except Exception as e:
                app.logger.warning(f"Migração localização (grid) Estoque de Peças: {str(e)}")
            
            # Garantir que o usuário admin existe (especialmente importante no Vercel)
            from models import Usuario
            from werkzeug.security import generate_password_hash
            
            admin_user = Usuario.query.filter_by(email='admin@acbusinagem.com.br').first()
            if not admin_user:
                admin_user = Usuario(
                    nome='Administrador',
                    email='admin@acbusinagem.com.br',
                    senha_hash=generate_password_hash('admin123'),
                    nivel_acesso='admin',
                    acesso_pedidos=True,
                    acesso_kanban=True,
                    acesso_estoque=True,
                    acesso_cadastros=True,
                    pode_finalizar_os=True
                )
                db.session.add(admin_user)
                db.session.commit()
                app.logger.info("Usuário admin criado no banco %s.", db_type)
            else:
                app.logger.info("Usuário admin já existe no banco %s.", db_type)
    else:
        if is_serverless and not run_startup_migrations and not _env_flag('SKIP_DB_CHECKS'):
            app.logger.info("Ambiente serverless detectado: pulando db.create_all()/seed (defina RUN_STARTUP_MIGRATIONS=1 para habilitar)")
        else:
            app.logger.info("SKIP_DB_CHECKS habilitado: pulando db.create_all() e seed do usuário admin")
    
    # Registrar blueprints
    from routes.clientes import clientes
    from routes.materiais import materiais
    from routes.trabalhos import trabalhos
    from routes.itens import itens
    from routes.pedidos import pedidos
    from routes.ordens import ordens
    from routes.pedidos_material import pedidos_material
    from routes.pedidos_montagem import pedidos_montagem
    from routes.estoque import estoque
    from routes.kanban import kanban
    from routes.arquivos import arquivos
    from routes.estoque_pecas import estoque_pecas
    from routes.auth import auth
    from routes.backup import backup
    from routes.main import main
    from routes.folhas_processo import folhas_processo
    from routes.apontamento import apontamento_bp
    from routes.maquinas import maquinas
    from routes.castanhas import castanhas
    from routes.gabaritos_centro import gabaritos_centro
    from routes.gabaritos_rosca import gabaritos_rosca
    from routes.novas_folhas_processo import novas_folhas_processo
    from routes.auditoria import auditoria
    from routes.lista_retirada import lista_retirada_bp
    
    app.register_blueprint(clientes)
    app.register_blueprint(materiais)
    app.register_blueprint(trabalhos)
    app.register_blueprint(itens)
    app.register_blueprint(pedidos)
    app.register_blueprint(ordens)
    app.register_blueprint(pedidos_material)
    app.register_blueprint(pedidos_montagem)
    app.register_blueprint(estoque)
    app.register_blueprint(kanban)
    app.register_blueprint(arquivos)
    app.register_blueprint(estoque_pecas)
    app.register_blueprint(lista_retirada_bp)
    app.register_blueprint(auth)
    app.register_blueprint(backup)
    app.register_blueprint(main)
    app.register_blueprint(apontamento_bp, url_prefix='/apontamento')
    app.register_blueprint(maquinas)
    app.register_blueprint(castanhas)
    app.register_blueprint(gabaritos_centro)
    app.register_blueprint(gabaritos_rosca)
    app.register_blueprint(novas_folhas_processo)
    app.register_blueprint(auditoria)

    # Guard global de autenticação/autorização
    @app.before_request
    def _global_auth_guard():
        # Permitir preflight CORS/OPTIONS sem login
        if request.method == 'OPTIONS':
            return

        endpoint = request.endpoint or ''
        blueprint = request.blueprint

        # Endpoints públicos
        if endpoint.startswith('static'):
            return
        if endpoint in ('auth.login', 'auth.logout'):
            return
        if endpoint.startswith('arquivos.uploaded_'):
            return
        if endpoint == 'supabase_redirect':
            return

        # Qualquer outra rota exige usuário logado
        if 'usuario_id' not in session:
            flash('Por favor, faça login para acessar esta página', 'warning')
            return redirect(url_for('auth.login', next=request.url))

        usuario_id = session.get('usuario_id')
        usuario_nivel = session.get('usuario_nivel')
        if not usuario_id or not usuario_nivel:
            session.clear()
            flash('Sessão inválida. Faça login novamente.', 'warning')
            return redirect(url_for('auth.login'))

        usuario = SimpleNamespace(
            id=usuario_id,
            nome=session.get('usuario_nome'),
            nivel_acesso=usuario_nivel,
            acesso_pedidos=bool(session.get('acesso_pedidos', False)),
            acesso_kanban=bool(session.get('acesso_kanban', False)),
            acesso_estoque=bool(session.get('acesso_estoque', False)),
            acesso_cadastros=bool(session.get('acesso_cadastros', False)),
            acesso_valores_itens=bool(session.get('acesso_valores_itens', False)),
            pode_finalizar_os=bool(session.get('pode_finalizar_os', False)),
            email=session.get('usuario_email'),
        )
        g.usuario = usuario

        # Admin possui acesso total
        if usuario.nivel_acesso == 'admin':
            return

        # Blueprints que já têm verificação interna (evitar duplicar regras finas)
        if blueprint in ('kanban', 'estoque', 'folhas_processo', 'backup', 'auth'):
            return

        # Permissões por módulo
        if blueprint in ('pedidos', 'ordens', 'pedidos_material', 'pedidos_montagem', 'clientes'):
            if not usuario.acesso_pedidos:
                flash('Você não tem permissão para acessar esta área', 'danger')
                return redirect(url_for('main.index'))

        if blueprint in ('apontamento',):
            if not usuario.acesso_kanban:
                flash('Você não tem permissão para acessar esta área', 'danger')
                return redirect(url_for('main.index'))

        if blueprint in (
            'itens',
            'materiais',
            'trabalhos',
            'maquinas',
            'castanhas',
            'gabaritos_centro',
            'gabaritos_rosca',
            'novas_folhas_processo',
        ):
            if endpoint in (
                'itens.listar_valores_itens',
                'itens.exportar_planilha_valores_itens',
                'itens.importar_planilha_valores_itens',
                'itens.confirmar_importacao_valores_itens',
            ):
                if not bool(getattr(usuario, 'acesso_valores_itens', False)) and not session.get('usuario_admin_master', False):
                    flash('Você não tem permissão para acessar esta área', 'danger')
                    return redirect(url_for('main.index'))
                return
            if not usuario.acesso_cadastros:
                flash('Você não tem permissão para acessar esta área', 'danger')
                return redirect(url_for('main.index'))

        if blueprint in ('estoque_pecas',):
            if not usuario.acesso_estoque:
                flash('Você não tem permissão para acessar esta área', 'danger')
                return redirect(url_for('main.index'))

    @app.context_processor
    def _inject_audit_footer():
        try:
            usuario = getattr(g, 'usuario', None)
            if not usuario or getattr(usuario, 'nivel_acesso', None) != 'admin':
                return {}

            if not has_request_context():
                return {}

            return {}
        except Exception:
            return {}
    
    # Rota para redirecionar URLs Supabase
    @app.route('/uploads/supabase:/<path:file_path>')
    def supabase_redirect(file_path):
        import os
        from urllib.parse import quote
        from flask import current_app as _current_app
        
        # Construir URL pública direta sem usar get_file_url para evitar loop
        bucket_env = os.environ.get('SUPABASE_BUCKET', 'uploads')
        supabase_url = os.environ.get('SUPABASE_URL', '').rstrip('/')
        
        # Log da tentativa de redirecionamento
        _current_app.logger.info("Tentativa de redirecionamento Supabase para: %s", file_path)
        _current_app.logger.debug("SUPABASE_URL configurado: %s", 'Sim' if supabase_url else 'Não')
        _current_app.logger.debug("SUPABASE_BUCKET: %s", bucket_env)
        
        if supabase_url:
            # Remover qualquer '/' inicial para evitar '//'
            path_clean = file_path.lstrip('/')
            
            # Detectar se o caminho já inclui o bucket como primeiro segmento.
            # Mantém compatibilidade com caminhos antigos: 'imagens/arquivo.jpg'
            # e novos: '<bucket>/imagens/arquivo.jpg'
            KNOWN_FOLDERS = {'imagens', 'desenhos', 'instrucoes', 'cnc_files', 'maquinas', 'castanhas', 'gabaritos', 'folhas_processo', 'blank_laser'}
            parts = path_clean.split('/', 1)
            if len(parts) > 1 and parts[0] not in KNOWN_FOLDERS:
                bucket = parts[0]
                rel_path = parts[1]
            else:
                bucket = bucket_env
                rel_path = path_clean

            # Não codificar as barras do caminho
            rel_encoded = quote(rel_path, safe='/')
            public_url = f"{supabase_url}/storage/v1/object/public/{bucket}/{rel_encoded}"
            _current_app.logger.info("Redirecionando para URL Supabase: %s", public_url)
            return redirect(public_url, code=302)
        else:
            # Log do erro de configuração
            _current_app.logger.error("SUPABASE_URL não configurado! Não é possível redirecionar para: %s", file_path)
            _current_app.logger.error("Configure a variável de ambiente SUPABASE_URL para usar o Supabase Storage")
            
            # Em vez de retornar 404, tentar servir arquivo local como fallback
            _current_app.logger.info("Tentando fallback para arquivo local...")
            
            # Extrair apenas o nome do arquivo e pasta
            path_clean = file_path.lstrip('/')
            parts = path_clean.split('/', 1)
            
            if len(parts) >= 2:
                folder = parts[0]  # ex: 'imagens'
                filename = parts[1]  # ex: 'df879b3c_POLIA_TENSORA.jpg'
                
                # Tentar servir arquivo local
                if folder == 'imagens':
                    local_path = os.path.join(_current_app.config['UPLOAD_FOLDER_IMAGENS'], filename)
                elif folder == 'desenhos':
                    local_path = os.path.join(_current_app.config['UPLOAD_FOLDER_DESENHOS'], filename)
                elif folder == 'instrucoes':
                    local_path = os.path.join(_current_app.config['UPLOAD_FOLDER_INSTRUCOES'], filename)
                else:
                    local_path = None
                
                if local_path and os.path.exists(local_path):
                    _current_app.logger.info("Arquivo local encontrado, servindo: %s", local_path)
                    return send_file(local_path)
                else:
                    _current_app.logger.warning("Arquivo local não encontrado: %s", local_path if local_path else 'caminho inválido')
            
            from flask import abort
            _current_app.logger.error("Retornando 404 para: %s", file_path)
            abort(404)
    
    app.register_blueprint(folhas_processo)
    
    # Adicionar contexto global para templates
    @app.context_processor
    def inject_user():
        from utils import get_file_url
        user_data = {
            'usuario_nome': session.get('usuario_nome', 'Visitante'),
            'usuario_nivel': session.get('usuario_nivel', None),
            'acesso_pedidos': session.get('acesso_pedidos', False),
            'acesso_kanban': session.get('acesso_kanban', False),
            'acesso_estoque': session.get('acesso_estoque', False),
            'acesso_cadastros': session.get('acesso_cadastros', False),
            'acesso_valores_itens': session.get('acesso_valores_itens', False),
            'usuario_admin_master': session.get('usuario_admin_master', False),
            'pode_finalizar_os': session.get('pode_finalizar_os', False),
            'acesso_finalizar_os': session.get('pode_finalizar_os', False),
            'get_file_url': get_file_url  # Adicionar função para templates
        }
        return user_data

    @app.context_processor
    def inject_app_version():
        try:
            from version import APP_VERSION
            return {'app_version': APP_VERSION}
        except Exception:
            return {'app_version': ''}

    @app.context_processor
    def inject_release_banner():
        try:
            import time
            if not session.get('usuario_id'):
                return {'release_2_0_show_banner': False}
            seen_at = session.get('release_2_0_seen_at')
            if not seen_at:
                return {'release_2_0_show_banner': False}
            try:
                seen_at = int(seen_at)
            except Exception:
                return {'release_2_0_show_banner': False}

            prazo_seg = 5 * 24 * 60 * 60
            show = (time.time() - seen_at) < prazo_seg
            return {
                'release_2_0_show_banner': bool(show),
                'release_2_0_items': [
                    'Desenho do Item: aprovação com carimbo APROVADO dentro do PDF (nome e data).',
                    'Kanban: links do desenho agora abrem o PDF carimbado quando aprovado.',
                    'Editar Item: tempos de setup e por peça em minutos/segundos com cálculo automático.',
                    'Estoque de Peças: endereçamento por Estante/Seção/Linha/Coluna e mapa interativo.',
                    'Estoque de Peças: busca com imagem + PDF do desenho e pesquisa global no mapa.',
                ]
            }
        except Exception:
            return {'release_2_0_show_banner': False}

    # Adicionar função now() para os templates
    @app.context_processor
    def utility_processor():
        def now():
            return datetime.datetime.now()
        return dict(now=now)

    # Adicionar filtros customizados
    @app.template_filter('nl2br')
    def nl2br_filter(s):
        """Converte quebras de linha em tags <br>"""
        if s is None:
            return ''
        from markupsafe import Markup, escape
        # Escapar HTML primeiro, depois converter quebras de linha
        escaped = escape(str(s))
        return Markup(str(escaped).replace('\n', '<br>\n'))
    
    @app.template_filter('safe')
    def safe_filter(s):
        """Marca string como segura para HTML"""
        if s is None:
            return ''
        from markupsafe import Markup
        return Markup(str(s))
    
    # Adicionar manipuladores de erro
    @app.errorhandler(404)
    def pagina_nao_encontrada(e):
        return render_template('404.html'), 404
    
    @app.errorhandler(500)
    def erro_servidor(e):
        return render_template('500.html'), 500
    
    return app
