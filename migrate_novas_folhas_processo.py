#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script de migração para criar as tabelas das novas folhas de processo reformuladas
"""

import sys
import os

# Adicionar o diretório raiz ao PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import db
from models import (NovaFolhaProcesso, FolhaProcessoSerra, FolhaProcessoTornoCNC, 
                   FolhaProcessoCentroUsinagem, FolhaProcessoManualAcabamento,
                   FerramentaTorno, FerramentaCentro, MedidaCritica, 
                   ImagemPecaProcesso, ImagemProcessoGeral)
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def criar_tabelas_novas_folhas():
    """Cria as tabelas para o novo sistema de folhas de processo"""
    
    app = create_app()
    
    with app.app_context():
        try:
            logger.info("🚀 Iniciando migração das novas folhas de processo...")
            
            # Lista de todas as novas tabelas
            novas_tabelas = [
                NovaFolhaProcesso,
                FolhaProcessoSerra,
                FolhaProcessoTornoCNC,
                FolhaProcessoCentroUsinagem,
                FolhaProcessoManualAcabamento,
                FerramentaTorno,
                FerramentaCentro,
                MedidaCritica,
                ImagemPecaProcesso,
                ImagemProcessoGeral
            ]
            
            # Verificar quais tabelas já existem
            inspector = db.inspect(db.engine)
            tabelas_existentes = inspector.get_table_names()
            
            tabelas_criadas = []
            tabelas_ja_existentes = []
            
            for modelo in novas_tabelas:
                nome_tabela = modelo.__tablename__
                
                if nome_tabela not in tabelas_existentes:
                    logger.info(f"📋 Criando tabela: {nome_tabela}")
                    modelo.__table__.create(db.engine, checkfirst=True)
                    tabelas_criadas.append(nome_tabela)
                else:
                    logger.info(f"✅ Tabela já existe: {nome_tabela}")
                    tabelas_ja_existentes.append(nome_tabela)
            
            # Confirmar alterações
            db.session.commit()
            
            # Relatório final
            logger.info("\n" + "="*60)
            logger.info("📊 RELATÓRIO DA MIGRAÇÃO")
            logger.info("="*60)
            
            if tabelas_criadas:
                logger.info(f"✅ Tabelas CRIADAS ({len(tabelas_criadas)}):")
                for tabela in tabelas_criadas:
                    logger.info(f"   • {tabela}")
            
            if tabelas_ja_existentes:
                logger.info(f"ℹ️  Tabelas JÁ EXISTIAM ({len(tabelas_ja_existentes)}):")
                for tabela in tabelas_ja_existentes:
                    logger.info(f"   • {tabela}")
            
            logger.info("\n🎉 Migração concluída com sucesso!")
            logger.info("🔧 O novo sistema de folhas de processo está pronto para uso.")
            logger.info("\n📋 PRÓXIMOS PASSOS:")
            logger.info("1. Acesse: /folhas-processo-novas")
            logger.info("2. Teste criando uma nova folha de processo")
            logger.info("3. Verifique se todas as funcionalidades estão operacionais")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro durante a migração: {str(e)}")
            db.session.rollback()
            return False

def verificar_estrutura_banco():
    """Verifica se a estrutura do banco está correta"""
    
    app = create_app()
    
    with app.app_context():
        try:
            logger.info("🔍 Verificando estrutura do banco...")
            
            inspector = db.inspect(db.engine)
            tabelas_existentes = inspector.get_table_names()
            
            tabelas_necessarias = [
                'nova_folha_processo',
                'folha_processo_serra', 
                'folha_processo_torno_cnc',
                'folha_processo_centro_usinagem',
                'folha_processo_manual_acabamento',
                'ferramenta_torno',
                'ferramenta_centro',
                'medida_critica',
                'imagem_peca_processo',
                'imagem_processo_geral'
            ]
            
            tabelas_faltando = []
            for tabela in tabelas_necessarias:
                if tabela not in tabelas_existentes:
                    tabelas_faltando.append(tabela)
            
            if not tabelas_faltando:
                logger.info("✅ Todas as tabelas estão presentes!")
                
                # Verificar algumas colunas importantes
                logger.info("🔍 Verificando estrutura das colunas...")
                
                # Verificar tabela principal
                colunas_principal = [col['name'] for col in inspector.get_columns('nova_folha_processo')]
                colunas_esperadas = ['maquina_id', 'categoria_maquina', 'titulo_servico']
                
                for coluna in colunas_esperadas:
                    if coluna in colunas_principal:
                        logger.info(f"✅ Coluna '{coluna}' encontrada na tabela principal")
                    else:
                        logger.warning(f"⚠️  Coluna '{coluna}' NOT encontrada na tabela principal")
                
                logger.info("🎉 Estrutura do banco verificada com sucesso!")
                return True
            else:
                logger.warning(f"⚠️  Tabelas faltando: {tabelas_faltando}")
                logger.info("💡 Execute: python migrate_novas_folhas_processo.py")
                return False
                
        except Exception as e:
            logger.error(f"❌ Erro ao verificar estrutura: {str(e)}")
            return False

if __name__ == "__main__":
    print("🔧 MIGRAÇÃO - NOVAS FOLHAS DE PROCESSO")
    print("="*50)
    
    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        # Apenas verificar
        verificar_estrutura_banco()
    else:
        # Executar migração
        sucesso = criar_tabelas_novas_folhas()
        
        if sucesso:
            print("\n✅ Migração executada com sucesso!")
            print("🚀 Sistema pronto para uso!")
        else:
            print("\n❌ Falha na migração!")
            sys.exit(1)
