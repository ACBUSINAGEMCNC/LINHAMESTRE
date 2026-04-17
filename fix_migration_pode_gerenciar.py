"""
Script para adicionar coluna pode_gerenciar_apontamentos manualmente
Execute este script para corrigir o erro imediatamente
"""
import os
import sys
from sqlalchemy import create_engine, text

# Adicionar o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    # Importar configuração do banco
    from config import Config
    
    print("=" * 60)
    print("MIGRAÇÃO: Adicionar coluna pode_gerenciar_apontamentos")
    print("=" * 60)
    
    # Criar engine
    database_url = os.environ.get('DATABASE_URL') or Config.SQLALCHEMY_DATABASE_URI
    print(f"\nConectando ao banco de dados...")
    
    engine = create_engine(database_url)
    
    try:
        with engine.connect() as conn:
            # Verificar se a coluna já existe
            print("\n1. Verificando se coluna já existe...")
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='usuario' AND column_name='pode_gerenciar_apontamentos'
            """))
            
            if result.fetchone() is None:
                print("   ❌ Coluna NÃO existe. Adicionando...")
                
                # Adicionar coluna
                conn.execute(text("""
                    ALTER TABLE usuario 
                    ADD COLUMN pode_gerenciar_apontamentos BOOLEAN DEFAULT FALSE
                """))
                
                conn.commit()
                print("   ✅ Coluna adicionada com sucesso!")
                
                # Verificar novamente
                result2 = conn.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name='usuario' AND column_name='pode_gerenciar_apontamentos'
                """))
                
                if result2.fetchone():
                    print("\n2. Verificação final: ✅ Coluna existe no banco!")
                else:
                    print("\n2. Verificação final: ❌ ERRO - Coluna não foi criada!")
                    return False
                    
            else:
                print("   ✅ Coluna JÁ existe no banco!")
                
        print("\n" + "=" * 60)
        print("MIGRAÇÃO CONCLUÍDA COM SUCESSO!")
        print("=" * 60)
        print("\nAgora você pode executar o app normalmente.")
        return True
        
    except Exception as e:
        print(f"\n❌ ERRO ao executar migração: {e}")
        import traceback
        print("\nTraceback completo:")
        print(traceback.format_exc())
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
