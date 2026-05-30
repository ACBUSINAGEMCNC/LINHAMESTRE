from app import create_app
from utils import test_supabase_auth
import os

app = create_app()

if __name__ == '__main__':
    # Testar auteOKnticação Supabase antes de iniciar
    if os.environ.get('RUN_SUPABASE_AUTH_TEST', '').lower() in ('1', 'true', 'yes'):
        print("\n==== TESTE DE AUTENTICAÇÃO SUPABASE ====")
        resultado = test_supabase_auth()
        print(f"Resultado do teste: {resultado}")
        print("======================================\n")
    
    app.run(host='0.0.0.0', debug=True, port=5000, threaded=True)

