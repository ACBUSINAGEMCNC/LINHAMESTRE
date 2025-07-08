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
    
    # Se estamos em produção OU configuração do Supabase está completa, usar Storage
    if is_production or use_supabase:
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
    """Faz upload de um arquivo para o Supabase Storage"""
    try:
        # Obter configurações do Supabase do ambiente
        supabase_url = os.environ.get('SUPABASE_URL')
        supabase_key = os.environ.get('SUPABASE_KEY')
        bucket = os.environ.get('SUPABASE_BUCKET', 'uploads')
        
        if not all([supabase_url, supabase_key]):
            flash('Configuração do Supabase Storage incompleta. Upload não realizado.', 'danger')
            return None
        
        # Gerar um nome de arquivo único para evitar colisões
        original_filename = secure_filename(file.filename)
        file_ext = os.path.splitext(original_filename)[1]
        unique_id = str(uuid.uuid4())[:8]
        storage_path = f"{folder}/{unique_id}_{original_filename}"
        
        # Preparar a URL e cabeçalhos para a API do Supabase Storage
        # Formato correto da URL: {base_url}/storage/v1/object/{bucket_name}/{path}
        upload_url = f"{supabase_url}/storage/v1/object/{bucket}/{quote(storage_path)}"
        
        # Logs mais visíveis
        flash(f"[DEBUG] Tentando upload para: {upload_url}", 'info')
        flash(f"[DEBUG] Bucket: {bucket}, Path: {storage_path}", 'info')
        
        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": file.mimetype
        }
        
        # Fazer upload do arquivo
        file_content = file.read()
        flash(f"[DEBUG] Tamanho do arquivo: {len(file_content)} bytes", 'info')
        
        # Primeiro, verificar se o bucket existe
        bucket_url = f"{supabase_url}/storage/v1/bucket/{bucket}"
        bucket_response = requests.get(bucket_url, headers={"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}"})
        
        if bucket_response.status_code != 200:
            flash(f"[ERROR] Bucket '{bucket}' não existe ou sem acesso. Status: {bucket_response.status_code}", 'danger')
            return None
        
        # Enviar como multipart/form-data
        files = {'file': (storage_path, file_content, file.mimetype)}
        # Remover Content-Type do header, pois o requests vai definir corretamente para multipart
        headers_no_content = headers.copy()
        headers_no_content.pop('Content-Type', None)
        response = requests.post(upload_url, headers=headers_no_content, files=files)

        # Logs da resposta
        flash(f"[DEBUG] Status: {response.status_code}, Resposta: {response.text[:200]}", 'warning')
        
        response.raise_for_status()
        
        # Retornar URL pública do arquivo
        public_url = f"{supabase_url}/storage/v1/object/public/{bucket}/{storage_path}"
        
        # Guardar URL completa com prefixo para identificar que é um arquivo do Supabase
        return f"supabase://{storage_path}"
    except Exception as e:
        error_msg = f"Erro ao fazer upload para Supabase: {str(e)}"
        print(error_msg)
        flash(error_msg, 'danger')
        return None

def get_file_url(file_path):
    """Converte um caminho de arquivo em URL, seja local ou do Supabase"""
    if not file_path:
        return None
        
    # Se for arquivo do Supabase Storage
    if file_path.startswith('supabase://'):
        bucket = os.environ.get('SUPABASE_BUCKET', 'uploads')
        supabase_url = os.environ.get('SUPABASE_URL')
        file_name = file_path.replace('supabase://', '')
        
        # Retornar URL pública do Supabase
        return f"{supabase_url}/storage/v1/object/public/{bucket}/{file_name}"
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
