import os
import json
import uuid
import requests
from werkzeug.utils import secure_filename
from flask import flash, current_app, request
from urllib.parse import urlparse, quote

def allowed_file(filename, allowed_extensions):
    """Verifica se o arquivo tem uma extensão permitida"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

def save_file(file, folder):
    """Salva um arquivo enviado no diretório local ou Supabase Storage e retorna o caminho/URL"""
    if not file or not file.filename:
        return None
        
    # Verifica se estamos em ambiente de produção (Vercel/serverless)
    is_production = os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME") 
    use_supabase = os.environ.get('SUPABASE_URL') and os.environ.get('SUPABASE_KEY') and os.environ.get('SUPABASE_BUCKET')
    force_supabase = os.environ.get('FORCE_SUPABASE_STORAGE', '').lower() in ['true', '1', 'yes']
    
    # Se estamos em produção OU configuração do Supabase está completa OU forçado, usar Storage
    if is_production or use_supabase or force_supabase:
        return upload_to_supabase(file, folder)
    else:
        # Modo de desenvolvimento local - salvar em disco local
        filename = secure_filename(file.filename)
        
        # Usar a configuração correta baseada no tipo de pasta
        if folder == 'desenhos':
            upload_folder = current_app.config['UPLOAD_FOLDER_DESENHOS']
        elif folder == 'imagens':
            upload_folder = current_app.config['UPLOAD_FOLDER_IMAGENS']
        elif folder == 'instrucoes':
            upload_folder = current_app.config['UPLOAD_FOLDER_INSTRUCOES']
        else:
            # Fallback para uma pasta padrão
            upload_folder = os.path.join(current_app.config.get('UPLOAD_FOLDER_DESENHOS', 'uploads'), folder)
        
        # Garantir que a pasta existe
        os.makedirs(upload_folder, exist_ok=True)
        
        filepath = os.path.join(upload_folder, filename)
        file.save(filepath)
        return os.path.join(folder, filename)

def upload_to_supabase(file, folder):
    """Faz upload de um arquivo para o Supabase Storage usando a API Storage REST"""
    try:
        import requests
        import json
        from urllib.parse import quote
        
        # Obter configurações do Supabase do ambiente
        supabase_url = os.environ.get('SUPABASE_URL')
        supabase_key = os.environ.get('SUPABASE_KEY')
        bucket = os.environ.get('SUPABASE_BUCKET', 'uploads')
        
        print(f"[DEBUG] Iniciando upload para Supabase. Bucket: {bucket}, Folder: {folder}")
        print(f"[DEBUG] SUPABASE_URL: {'Definido' if supabase_url else 'Não definido'}")
        print(f"[DEBUG] SUPABASE_KEY: {'Definido' if supabase_key else 'Não definido (truncado)'}")
        print(f"[DEBUG] SUPABASE_KEY começa com: {supabase_key[:10]}... e termina com: ...{supabase_key[-10:]} (truncado)")
        
        if not all([supabase_url, supabase_key]):
            error_msg = 'Configuração do Supabase Storage incompleta. Verifique as variáveis de ambiente SUPABASE_URL e SUPABASE_KEY.'
            print(f"[ERROR] {error_msg}")
            flash(error_msg, 'danger')
            return None
            
        # Remover possível barra no final da URL
        if supabase_url.endswith('/'):
            supabase_url = supabase_url[:-1]
            
        # Primeiro, verificar se o bucket existe
        list_buckets_url = f"{supabase_url}/storage/v1/bucket"
        print(f"[DEBUG] Verificando buckets disponíveis: {list_buckets_url}")
        
        headers = {
            'Authorization': f'Bearer {supabase_key}',
            'apikey': f'{supabase_key}',
            'Content-Type': 'application/json'
        }
        
        try:
            bucket_response = requests.get(list_buckets_url, headers=headers)
            print(f"[DEBUG] Status da verificação de buckets: {bucket_response.status_code}")
            
            if bucket_response.status_code != 200:
                print(f"[ERROR] Falha ao listar buckets: {bucket_response.text}")
                # Se não conseguirmos listar buckets, tentamos criar um
                create_bucket_url = list_buckets_url
                bucket_data = {
                    'id': bucket,
                    'name': bucket,
                    'public': True
                }
                create_response = requests.post(
                    create_bucket_url, 
                    headers=headers, 
                    data=json.dumps(bucket_data)
                )
                print(f"[DEBUG] Tentativa de criar bucket: {create_response.status_code} - {create_response.text}")
        except Exception as e:
            print(f"[ERROR] Erro ao verificar/criar bucket: {str(e)}")
        
        # Gerar um nome de arquivo único para evitar colisões
        original_filename = secure_filename(file.filename)
        unique_id = str(uuid.uuid4())[:8]
        storage_path = f"{folder}/{unique_id}_{original_filename}"
        
        print(f"[DEBUG] Arquivo original: {file.filename}, Nome seguro: {original_filename}, Caminho no storage: {storage_path}")
        
        try:
            # Reset do arquivo para leitura (pode ter sido lido anteriormente)
            file.seek(0)
            
            # URL de upload do Supabase Storage REST API
            upload_url = f"{supabase_url}/storage/v1/object/{bucket}/{quote(storage_path)}"
            print(f"[DEBUG] URL de upload: {upload_url}")
            
            # Cabeçalhos para o upload
            upload_headers = {
                'Authorization': f'Bearer {supabase_key}',
                'apikey': f'{supabase_key}'
                # Não defina Content-Type aqui - o multipart/form-data será definido pelo requests
            }
            
            # Preparar arquivo para upload
            files = {
                'file': (original_filename, file, file.mimetype or 'application/octet-stream')
            }
            
            print(f"[DEBUG] Iniciando upload do arquivo para o bucket '{bucket}'...")
            
            # Fazer o upload via HTTP POST
            response = requests.post(upload_url, headers=upload_headers, files=files)
            
            # Verificar se o upload foi bem-sucedido
            print(f"[DEBUG] Resposta do upload: {response.status_code} {response.reason}")
            print(f"[DEBUG] Resposta completa: {response.text}")
            
            if response.status_code in [200, 201]:
                print(f"[DEBUG] Upload concluído com sucesso!")
                
                # Construir URL pública do arquivo
                public_url = f"{supabase_url}/storage/v1/object/public/{bucket}/{quote(storage_path)}"
                print(f"[DEBUG] URL pública do arquivo: {public_url}")
                
                # Retornar caminho do arquivo no formato supabase:// para referência futura
                return f"supabase://{storage_path}"
            else:
                error_msg = f"Erro ao fazer upload para o Supabase: {response.status_code} {response.reason} - {response.text}"
                print(f"[ERROR] {error_msg}")
                flash(f"Erro no upload: {response.status_code} {response.reason}", 'danger')
                return None
                
        except Exception as e:
            error_msg = f"Erro ao fazer upload para o Supabase: {str(e)}"
            print(f"[ERROR] {error_msg}")
            flash(error_msg, 'danger')
            return None
    except Exception as e:
        error_msg = f"Erro ao fazer upload para Supabase: {str(e)}"
        print(error_msg)
        flash(error_msg, 'danger')
        return None

def test_supabase_auth():
    """Testa a autenticação básica do Supabase com um endpoint simples"""
    import requests
    import os
    import json
    
    supabase_url = os.environ.get('SUPABASE_URL')
    supabase_key = os.environ.get('SUPABASE_KEY')
    
    print(f"[TESTE AUTH] URL: {supabase_url}")
    print(f"[TESTE AUTH] Key (primeiros 10 caracteres): {supabase_key[:10]}...")
    
    if not all([supabase_url, supabase_key]):
        return "Variáveis de ambiente não configuradas"
    
    # Cabeçalhos para autenticação
    headers = {
        'apikey': supabase_key,
        'Authorization': f'Bearer {supabase_key}'
    }
    
    # Tentar um endpoint básico que só requer autenticação
    # 1. Primeiro tente um SELECT de alguma tabela existente
    try:
        test_url = f"{supabase_url}/rest/v1/usuario?select=id&limit=1"
        print(f"[TESTE AUTH] Testando URL: {test_url}")
        resp = requests.get(test_url, headers=headers)
        print(f"[TESTE AUTH] Status: {resp.status_code}, Resposta: {resp.text}")
        
        if resp.status_code == 200:
            return f"Autenticação OK! Status: {resp.status_code}"
    except Exception as e:
        print(f"[TESTE AUTH] Erro no teste 1: {str(e)}")
    
    # 2. Se falhar, tente versão do PostgreSQL via RPC
    try:
        test_url2 = f"{supabase_url}/rest/v1/rpc/version"
        print(f"[TESTE AUTH] Testando URL alternativa: {test_url2}")
        resp2 = requests.post(test_url2, headers=headers, json={})
        print(f"[TESTE AUTH] Status: {resp2.status_code}, Resposta: {resp2.text}")
        
        if resp2.status_code == 200:
            return f"Autenticação OK no endpoint RPC! Status: {resp2.status_code}"
        else:
            return f"Falha na autenticação: {resp2.status_code} {resp2.text}"
    except Exception as e:
        return f"Erro em ambos testes: {str(e)}"

def get_file_url(file_path):
    """Converte um caminho de arquivo em URL, seja local ou do Supabase"""
    if not file_path:
        return None
        
    # Se for arquivo do Supabase Storage
    if file_path.startswith('supabase://'):
        bucket = os.environ.get('SUPABASE_BUCKET', 'uploads')
        supabase_url = os.environ.get('SUPABASE_URL')
        file_name = file_path.replace('supabase://', '')
        
        # Remover possível barra no final da URL
        if supabase_url and supabase_url.endswith('/'):
            supabase_url = supabase_url[:-1]
        
        # Retornar URL pública direta do Supabase
        public_url = f"{supabase_url}/storage/v1/object/public/{bucket}/{file_name}"
        print(f"[DEBUG] URL pública de arquivo: {public_url}")
        return public_url
    else:
        # Arquivo local - construir URL relativa
        return f"/uploads/{file_path}"

def generate_next_code(model, prefix, code_field, padding=5):
    """Gera o próximo código sequencial para um modelo"""
    last_item = model.query.order_by(getattr(model, 'id').desc()).first()
    if last_item:
        last_code = getattr(last_item, code_field)
        if last_code and last_code.startswith(prefix):
            try:
                last_number = int(last_code.split('-')[1])
                return f"{prefix}-{last_number + 1:0{padding}d}"
            except (IndexError, ValueError):
                pass
    return f"{prefix}-{'1'.zfill(padding)}"

def format_seconds_to_time(seconds):
    """Converte segundos em formato de horas e minutos"""
    if seconds is None:
        return "0h 0m"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return f"{hours}h {minutes}m"

def validate_form_data(form_data, required_fields):
    """Valida os dados do formulário, verificando campos obrigatórios"""
    errors = []
    for field in required_fields:
        if field not in form_data or not form_data[field]:
            errors.append(f"O campo '{field}' é obrigatório.")
    return errors

def parse_json_field(form_data, field_name, default=None):
    """Converte um campo JSON do formulário em um objeto Python"""
    try:
        value = form_data.get(field_name, '[]')
        return json.loads(value) if value else (default or [])
    except json.JSONDecodeError:
        flash(f"Erro ao processar dados do campo {field_name}", "danger")
        return default or []

def get_kanban_categories():
    """Retorna as categorias de trabalho para o Kanban baseadas nas listas do banco"""
    from models import KanbanLista
    
    # Obter listas ativas do banco
    listas = KanbanLista.query.filter_by(ativa=True).order_by(KanbanLista.ordem).all()
    
    # Se não houver listas no banco, usar as categorias padrão como fallback
    if not listas:
        return {
            'Serra': ['Serra'],
            'Torno CNC': ['Mazak', 'GLM240', 'Glory', 'Doosan', 'Tesla'],
            'Centro de Usinagem': ['D800 / D800 Plus', 'Glory1000'],
            'Manual': ['Torno Manual', 'Fresa Manual', 'Rebarbagem'],
            'Acabamento': ['Solda', 'Têmpera', 'Retífica']
        }
    
    # Agrupar listas por tipo de serviço
    categorias = {}
    for lista in listas:
        tipo = lista.tipo_servico or 'Outros'
        if tipo not in categorias:
            categorias[tipo] = []
        categorias[tipo].append(lista.nome)
    
    return categorias

def get_kanban_lists():
    """Retorna as listas ativas do Kanban garantindo que 'Entrada' seja a primeira e 'Expedição' a última."""
    from models import KanbanLista
    
    PROTECTED = ['Entrada', 'Expedição']
    
    # Obter listas ativas do banco ordenadas por campo "ordem"
    listas_db = KanbanLista.query.filter_by(ativa=True).order_by(KanbanLista.ordem).all()
    nomes = [l.nome for l in listas_db]
    
    # Inserir protegidas se não estiverem nos resultados
    if PROTECTED[0] not in nomes:
        nomes.insert(0, PROTECTED[0])
    if PROTECTED[1] not in nomes:
        nomes.append(PROTECTED[1])
    
    # Garantir posição correta mesmo se já existirem em lugares errados
    # Remove duplicatas mantendo ordem
    vistos = set()
    nomes = [n for n in nomes if not (n in vistos or vistos.add(n))]
    
    # Mover protegidas para extremidades
    if PROTECTED[0] in nomes:
        nomes.remove(PROTECTED[0])
        nomes.insert(0, PROTECTED[0])
    if PROTECTED[1] in nomes:
        nomes.remove(PROTECTED[1])
        nomes.append(PROTECTED[1])
    
    # Caso não haja listas no banco, retornar fallback padrão
    if not listas_db:
        return [
            'Entrada', 'Serra', 'Cortado a Distribuir', 'Mazak', 'GLM240', 'Glory',
            'Doosan', 'Tesla', 'Torno Manual', 'Fresa Manual', 'Rebarbagem',
            'Parada Próxima Etapa', 'D800 / D800 Plus', 'Glory1000', 'Montagem Modelo',
            'Serviço Terceiro', 'Solda', 'Têmpera', 'Retífica', 'Expedição'
        ]
    
    return nomes

from datetime import datetime

def context_processor():
    """Adiciona variáveis globais para todos os templates"""
    return {
        'datetime': datetime
    }

def generate_next_os_code():
    """Gera o próximo número sequencial de Ordem de Serviço no formato OS-YYYY-MM-XXX."""
    from models import OrdemServico
    hoje = datetime.now().date()
    prefixo = f"OS-{hoje.year}-{hoje.month:02d}"
    ultimas = OrdemServico.query.filter(OrdemServico.numero.startswith(prefixo)).all()
    max_seq = 0
    for os_item in ultimas:
        try:
            seq = int(os_item.numero.rsplit('-', 1)[1])
            if seq > max_seq:
                max_seq = seq
        except (IndexError, ValueError):
            continue
    proximo = max_seq + 1
    return f"{prefixo}-{proximo:03d}"
