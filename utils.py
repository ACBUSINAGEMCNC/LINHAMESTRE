import os
from werkzeug.utils import secure_filename
from flask import flash, current_app
import json

def allowed_file(filename, allowed_extensions):
    """Verifica se o arquivo tem uma extensão permitida"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

def save_file(file, folder):
    """Salva um arquivo enviado no diretório especificado e retorna o caminho relativo"""
    if file and file.filename:
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
    return None

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
