#!/usr/bin/env python3
"""
Migração SQLAlchemy para adicionar o sistema de apontamento de produção
- Usa SQLAlchemy para garantir compatibilidade com PostgreSQL (Supabase) e SQLite
- Adiciona campo codigo_operador na tabela usuario
- Cria tabelas apontamento_producao e status_producao_os
"""

import os
import sys
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from config import Config

# Importar modelos para garantir que estejam registrados
from models import db, Usuario, ApontamentoProducao, StatusProducaoOS, OrdemServico

def criar_app_temporario():
    """Cria uma instância temporária do Flask para migração"""
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Inicializar SQLAlchemy
    db.init_app(app)
    
    return app

def executar_migracao():
    """Executa a migração usando SQLAlchemy"""
    
    app = criar_app_temporario()
    
    with app.app_context():
        try:
            print("🔄 Iniciando migração SQLAlchemy para sistema de apontamento...")
            print(f"📊 Banco configurado: {app.config['SQLALCHEMY_DATABASE_URI']}")
            
            # 1. Verificar se as tabelas já existem
            inspector = db.inspect(db.engine)
            tabelas_existentes = inspector.get_table_names()
            
            print(f"📋 Tabelas existentes: {len(tabelas_existentes)}")
            
            # 2. Criar todas as tabelas (incluindo as novas)
            print("📝 Criando/atualizando tabelas...")
            db.create_all()
            print("✅ Tabelas criadas/atualizadas com sucesso")
            
            # 3. Para SQLite, adicionar campo codigo_operador se não existir
            if 'sqlite' in app.config['SQLALCHEMY_DATABASE_URI'].lower():
                print("📝 Verificando campo codigo_operador (SQLite)...")
                try:
                    # Tentar adicionar a coluna (falhará se já existir)
                    db.engine.execute(text("ALTER TABLE usuario ADD COLUMN codigo_operador VARCHAR(4)"))
                    print("✅ Campo codigo_operador adicionado")
                except Exception as e:
                    if "duplicate column name" in str(e).lower():
                        print("ℹ️ Campo codigo_operador já existe")
                    else:
                        print(f"⚠️ Aviso ao adicionar campo: {e}")
            
            # 4. Para PostgreSQL, usar ALTER TABLE se necessário
            elif 'postgresql' in app.config['SQLALCHEMY_DATABASE_URI'].lower():
                print("📝 Verificando campo codigo_operador (PostgreSQL)...")
                try:
                    # Verificar se a coluna existe
                    result = db.engine.execute(text("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name='usuario' AND column_name='codigo_operador'
                    """))
                    
                    if not result.fetchone():
                        db.engine.execute(text("ALTER TABLE usuario ADD COLUMN codigo_operador VARCHAR(4)"))
                        print("✅ Campo codigo_operador adicionado")
                    else:
                        print("ℹ️ Campo codigo_operador já existe")
                        
                except Exception as e:
                    print(f"⚠️ Aviso ao verificar/adicionar campo: {e}")
            
            # 5. Inicializar status para ordens de serviço existentes
            print("📝 Inicializando status para ordens de serviço existentes...")
            
            # Buscar ordens de serviço sem status
            ordens_sem_status = db.session.query(OrdemServico).filter(
                ~OrdemServico.id.in_(
                    db.session.query(StatusProducaoOS.ordem_servico_id)
                )
            ).all()
            
            for ordem in ordens_sem_status:
                status = StatusProducaoOS(
                    ordem_servico_id=ordem.id,
                    status_atual='Aguardando'
                )
                db.session.add(status)
            
            db.session.commit()
            
            if ordens_sem_status:
                print(f"✅ Status inicializado para {len(ordens_sem_status)} ordens de serviço")
            else:
                print("ℹ️ Todas as ordens de serviço já possuem status")
            
            # 6. Mostrar estatísticas
            print("\n📊 ESTATÍSTICAS PÓS-MIGRAÇÃO:")
            
            total_usuarios = db.session.query(Usuario).count()
            usuarios_com_codigo = db.session.query(Usuario).filter(
                Usuario.codigo_operador.isnot(None)
            ).count()
            
            total_apontamentos = db.session.query(ApontamentoProducao).count()
            total_status = db.session.query(StatusProducaoOS).count()
            total_ordens = db.session.query(OrdemServico).count()
            
            print(f"   • Total de usuários: {total_usuarios}")
            print(f"   • Usuários com código: {usuarios_com_codigo}")
            print(f"   • Total de apontamentos: {total_apontamentos}")
            print(f"   • Status de OS: {total_status}")
            print(f"   • Total de OS: {total_ordens}")
            
            print("\n✅ Migração SQLAlchemy concluída com sucesso!")
            return True
            
        except Exception as e:
            print(f"❌ Erro durante a migração: {e}")
            db.session.rollback()
            return False

def verificar_migracao():
    """Verifica se a migração foi aplicada corretamente"""
    
    app = criar_app_temporario()
    
    with app.app_context():
        try:
            inspector = db.inspect(db.engine)
            tabelas_existentes = inspector.get_table_names()
            
            # Verificar tabelas necessárias
            tabelas_necessarias = ['apontamento_producao', 'status_producao_os']
            tabelas_encontradas = [t for t in tabelas_necessarias if t in tabelas_existentes]
            
            # Verificar campo codigo_operador
            colunas_usuario = [col['name'] for col in inspector.get_columns('usuario')]
            campo_codigo_existe = 'codigo_operador' in colunas_usuario
            
            print(f"""
🔍 VERIFICAÇÃO DA MIGRAÇÃO:
   • Tabelas criadas: {len(tabelas_encontradas)}/{len(tabelas_necessarias)}
     - apontamento_producao: {'✅' if 'apontamento_producao' in tabelas_existentes else '❌'}
     - status_producao_os: {'✅' if 'status_producao_os' in tabelas_existentes else '❌'}
   • Campo codigo_operador: {'✅' if campo_codigo_existe else '❌'}
   • Banco: {app.config['SQLALCHEMY_DATABASE_URI'].split('://')[0].upper()}
            """)
            
            return len(tabelas_encontradas) == len(tabelas_necessarias) and campo_codigo_existe
            
        except Exception as e:
            print(f"❌ Erro na verificação: {e}")
            return False

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 MIGRAÇÃO SQLAlchemy: Sistema de Apontamento")
    print("=" * 60)
    
    if executar_migracao():
        print("\n" + "=" * 60)
        verificar_migracao()
        print("=" * 60)
        print("✅ Sistema de apontamento pronto para uso!")
    else:
        print("❌ Falha na migração. Verifique os erros acima.")
        sys.exit(1)
