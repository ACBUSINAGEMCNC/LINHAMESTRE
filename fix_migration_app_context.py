"""
Script para adicionar coluna pode_gerenciar_apontamentos usando app context
"""
import os
import sys

# Adicionar o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    from app import create_app, db
    from sqlalchemy import text
    
    print("=" * 60)
    print("MIGRAÇÃO: Adicionar coluna pode_gerenciar_apontamentos")
    print("=" * 60)
    
    # Criar app sem executar migrações automáticas
    os.environ['SKIP_MIGRATIONS'] = '1'
    app = create_app()
    
    with app.app_context():
        try:
            print("\n1. Verificando se coluna já existe...")
            
            result = db.session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='usuario' AND column_name='pode_gerenciar_apontamentos'
            """))
            
            if result.fetchone() is None:
                print("   ❌ Coluna NÃO existe. Adicionando...")
                
                # Adicionar coluna
                db.session.execute(text("""
                    ALTER TABLE usuario 
                    ADD COLUMN pode_gerenciar_apontamentos BOOLEAN DEFAULT FALSE
                """))
                
                db.session.commit()
                print("   ✅ Coluna adicionada com sucesso!")
                
                # Verificar novamente
                result2 = db.session.execute(text("""
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
            db.session.rollback()
            return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
