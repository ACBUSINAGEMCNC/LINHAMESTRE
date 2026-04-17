"""
Script para executar migração usando conexão local do .env
"""
import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

# Importar após carregar .env
from migrations.add_pode_gerenciar_apontamentos import migrate_postgresql_engine
from sqlalchemy import create_engine

# Forçar uso do psycopg (versão 3) ao invés de psycopg2
os.environ.setdefault('SQLALCHEMY_WARN_20', '1')

def main():
    print("=" * 70)
    print("EXECUTANDO MIGRAÇÃO: pode_gerenciar_apontamentos")
    print("=" * 70)
    
    # Obter URL do banco de dados do .env
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        print("\n❌ ERRO: DATABASE_URL não encontrada no .env")
        return False
    
    # Converter URL para usar psycopg (versão 3) ao invés de psycopg2
    if database_url.startswith('postgresql://'):
        database_url = database_url.replace('postgresql://', 'postgresql+psycopg://', 1)
    elif database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql+psycopg://', 1)
    
    print(f"\n✓ DATABASE_URL encontrada")
    print(f"  Conectando ao banco...")
    
    try:
        # Criar engine
        engine = create_engine(database_url)
        
        # Executar migração
        print("\n→ Executando migração...")
        resultado = migrate_postgresql_engine(engine)
        
        if resultado:
            print("\n" + "=" * 70)
            print("✅ MIGRAÇÃO CONCLUÍDA COM SUCESSO!")
            print("=" * 70)
            print("\nAgora você pode executar o app normalmente:")
            print("  python run.py")
            return True
        else:
            print("\n" + "=" * 70)
            print("❌ MIGRAÇÃO FALHOU")
            print("=" * 70)
            return False
            
    except Exception as e:
        print(f"\n❌ ERRO ao executar migração: {e}")
        import traceback
        print("\nTraceback:")
        print(traceback.format_exc())
        return False

if __name__ == '__main__':
    import sys
    success = main()
    sys.exit(0 if success else 1)
