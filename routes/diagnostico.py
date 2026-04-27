from flask import Blueprint, render_template, jsonify, session
from functools import wraps
import time
import os
import requests
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

diagnostico_bp = Blueprint('diagnostico', __name__)

def require_login(f):
    """Decorator para exigir login (qualquer usuário autenticado)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Verificar se está autenticado
        if not session.get('usuario_id'):
            return jsonify({
                'error': 'Não autenticado',
                'tests': [],
                'timestamp': datetime.now().isoformat()
            }), 401
        
        # Qualquer usuário autenticado pode acessar
        return f(*args, **kwargs)
    return decorated_function


@diagnostico_bp.route('/diagnostico')
@require_login
def index():
    """Página principal de diagnóstico do sistema"""
    return render_template('diagnostico/index.html')


@diagnostico_bp.route('/diagnostico/test-ping')
@require_login
def test_ping():
    """Testa conectividade com serviços externos"""
    results = {
        'timestamp': datetime.now().isoformat(),
        'tests': []
    }
    
    # Lista de serviços para testar
    services = [
        {
            'name': 'Vercel (Deploy)',
            'url': 'https://vercel.com',
            'type': 'external'
        },
        {
            'name': 'Supabase API',
            'url': os.getenv('SUPABASE_URL', ''),
            'type': 'database'
        },
        {
            'name': 'GitHub',
            'url': 'https://github.com',
            'type': 'external'
        },
        {
            'name': 'Google DNS',
            'url': 'https://8.8.8.8',
            'type': 'network'
        }
    ]
    
    for service in services:
        if not service['url']:
            results['tests'].append({
                'name': service['name'],
                'status': 'skipped',
                'message': 'URL não configurada',
                'response_time': 0
            })
            continue
            
        try:
            start_time = time.time()
            response = requests.get(service['url'], timeout=5)
            response_time = (time.time() - start_time) * 1000  # em ms
            
            results['tests'].append({
                'name': service['name'],
                'status': 'success' if response.status_code < 400 else 'warning',
                'status_code': response.status_code,
                'response_time': round(response_time, 2),
                'message': f'OK ({response.status_code})'
            })
        except requests.exceptions.Timeout:
            results['tests'].append({
                'name': service['name'],
                'status': 'error',
                'response_time': 5000,
                'message': 'Timeout (>5s)'
            })
        except Exception as e:
            results['tests'].append({
                'name': service['name'],
                'status': 'error',
                'response_time': 0,
                'message': str(e)
            })
    
    return jsonify(results)


@diagnostico_bp.route('/diagnostico/test-database')
@require_login
def test_database():
    """Testa performance do banco de dados"""
    results = {
        'timestamp': datetime.now().isoformat(),
        'tests': []
    }
    
    try:
        from models import db, Item, Pedido, OrdemServico
    except Exception as e:
        logger.error(f"Erro ao importar models: {e}")
        results['tests'].append({
            'name': 'Importação de Models',
            'status': 'error',
            'response_time': 0,
            'message': f'Erro ao importar models: {str(e)}'
        })
        return jsonify(results)
    
    # Teste 1: Query simples
    try:
        start_time = time.time()
        count = db.session.query(Item).count()
        query_time = (time.time() - start_time) * 1000
        
        results['tests'].append({
            'name': 'Contagem de Itens',
            'status': 'success',
            'response_time': round(query_time, 2),
            'result': f'{count} itens',
            'message': 'OK'
        })
    except Exception as e:
        results['tests'].append({
            'name': 'Contagem de Itens',
            'status': 'error',
            'response_time': 0,
            'message': str(e)
        })
    
    # Teste 2: Query com JOIN
    try:
        start_time = time.time()
        pedidos = db.session.query(Pedido).join(Item).limit(10).all()
        query_time = (time.time() - start_time) * 1000
        
        results['tests'].append({
            'name': 'Query com JOIN (Pedidos + Itens)',
            'status': 'success',
            'response_time': round(query_time, 2),
            'result': f'{len(pedidos)} registros',
            'message': 'OK'
        })
    except Exception as e:
        results['tests'].append({
            'name': 'Query com JOIN',
            'status': 'error',
            'response_time': 0,
            'message': str(e)
        })
    
    # Teste 3: Query complexa (Ordens de Serviço com relacionamentos)
    try:
        start_time = time.time()
        ordens = db.session.query(OrdemServico).limit(5).all()
        # Forçar carregamento dos relacionamentos
        for ordem in ordens:
            _ = ordem.pedidos
            _ = ordem.trabalhos
        query_time = (time.time() - start_time) * 1000
        
        results['tests'].append({
            'name': 'Query Complexa (Ordens + Relacionamentos)',
            'status': 'success',
            'response_time': round(query_time, 2),
            'result': f'{len(ordens)} ordens',
            'message': 'OK'
        })
    except Exception as e:
        results['tests'].append({
            'name': 'Query Complexa',
            'status': 'error',
            'response_time': 0,
            'message': str(e)
        })
    
    return jsonify(results)


@diagnostico_bp.route('/diagnostico/test-storage')
@require_login
def test_storage():
    """Testa acesso ao Supabase Storage"""
    results = {
        'timestamp': datetime.now().isoformat(),
        'tests': []
    }
    
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_KEY') or os.getenv('SUPABASE_ANON_KEY')
    bucket = os.getenv('SUPABASE_BUCKET', 'uploads')
    
    # Teste 1: Verificar configuração
    if not supabase_url or not supabase_key:
        results['tests'].append({
            'name': 'Configuração do Supabase',
            'status': 'error',
            'response_time': 0,
            'message': 'Variáveis de ambiente não configuradas'
        })
        return jsonify(results)
    
    results['tests'].append({
        'name': 'Configuração do Supabase',
        'status': 'success',
        'response_time': 0,
        'message': 'Variáveis configuradas'
    })
    
    # Teste 2: Listar arquivos do bucket
    try:
        start_time = time.time()
        storage_url = f"{supabase_url}/storage/v1/object/list/{bucket}"
        headers = {
            'Authorization': f'Bearer {supabase_key}',
            'apikey': supabase_key
        }
        
        response = requests.post(
            storage_url,
            headers=headers,
            json={
                'limit': 10, 
                'offset': 0, 
                'prefix': '',  # Parâmetro obrigatório
                'sortBy': {'column': 'name', 'order': 'asc'}
            },
            timeout=10
        )
        response_time = (time.time() - start_time) * 1000
        
        if response.status_code == 200:
            files = response.json()
            results['tests'].append({
                'name': 'Listar Arquivos do Storage',
                'status': 'success',
                'response_time': round(response_time, 2),
                'result': f'{len(files)} arquivos',
                'message': 'OK'
            })
        else:
            results['tests'].append({
                'name': 'Listar Arquivos do Storage',
                'status': 'error',
                'response_time': round(response_time, 2),
                'message': f'HTTP {response.status_code}: {response.text[:100]}'
            })
    except Exception as e:
        results['tests'].append({
            'name': 'Listar Arquivos do Storage',
            'status': 'error',
            'response_time': 0,
            'message': str(e)
        })
    
    return jsonify(results)


@diagnostico_bp.route('/diagnostico/test-kanban-performance')
@require_login
def test_kanban_performance():
    """Testa performance específica do Kanban (cartões, OS, PDF)"""
    results = {
        'timestamp': datetime.now().isoformat(),
        'tests': [],
        'warnings': []
    }
    
    try:
        from models import db, OrdemServico, Pedido, Item, Trabalho
    except Exception as e:
        logger.error(f"Erro ao importar models: {e}")
        results['tests'].append({
            'name': 'Importação de Models',
            'status': 'error',
            'response_time': 0,
            'message': f'Erro ao importar models: {str(e)}'
        })
        return jsonify(results)
    
    # Teste 1: Carregar dados do Kanban (simulação)
    try:
        start_time = time.time()
        
        # Simular query do Kanban
        ordens = db.session.query(OrdemServico).filter(
            OrdemServico.status.in_(['em_andamento', 'pausada', 'aguardando'])
        ).limit(20).all()
        
        query_time = (time.time() - start_time) * 1000
        
        results['tests'].append({
            'name': 'Carregar Ordens do Kanban',
            'status': 'success',
            'response_time': round(query_time, 2),
            'result': f'{len(ordens)} ordens',
            'message': 'OK'
        })
        
        if query_time > 1000:
            results['warnings'].append('Query de ordens está lenta (>1s)')
            
    except Exception as e:
        results['tests'].append({
            'name': 'Carregar Ordens do Kanban',
            'status': 'error',
            'response_time': 0,
            'message': str(e)
        })
    
    # Teste 2: Carregar detalhes de uma OS (com todos os relacionamentos)
    try:
        start_time = time.time()
        
        ordem = db.session.query(OrdemServico).first()
        if ordem:
            # Forçar carregamento de todos os relacionamentos
            _ = ordem.pedidos
            for pedido in ordem.pedidos:
                _ = pedido.item
                _ = pedido.item.imagem_path if pedido.item else None
            _ = ordem.trabalhos
            for trabalho in ordem.trabalhos:
                _ = trabalho.maquina
                _ = trabalho.tipo_trabalho
            
        query_time = (time.time() - start_time) * 1000
        
        results['tests'].append({
            'name': 'Carregar Detalhes Completos de OS',
            'status': 'success',
            'response_time': round(query_time, 2),
            'message': 'OK'
        })
        
        if query_time > 500:
            results['warnings'].append('Carregamento de detalhes da OS está lento (>500ms)')
            
    except Exception as e:
        results['tests'].append({
            'name': 'Carregar Detalhes de OS',
            'status': 'error',
            'response_time': 0,
            'message': str(e)
        })
    
    # Teste 3: Simular geração de PDF (tempo de processamento)
    try:
        start_time = time.time()
        
        # Simular processamento pesado (sem gerar PDF de verdade)
        import io
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        
        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=A4)
        p.drawString(100, 750, "Teste de Performance")
        for i in range(50):  # Simular 50 linhas
            p.drawString(100, 700 - (i * 10), f"Linha {i}")
        p.showPage()
        p.save()
        
        pdf_time = (time.time() - start_time) * 1000
        
        results['tests'].append({
            'name': 'Geração de PDF (Simulação)',
            'status': 'success',
            'response_time': round(pdf_time, 2),
            'result': f'{len(buffer.getvalue())} bytes',
            'message': 'OK'
        })
        
        if pdf_time > 1000:
            results['warnings'].append('Geração de PDF está lenta (>1s)')
            
    except Exception as e:
        results['tests'].append({
            'name': 'Geração de PDF',
            'status': 'error',
            'response_time': 0,
            'message': str(e)
        })
    
    return jsonify(results)


@diagnostico_bp.route('/diagnostico/system-info')
@require_login
def system_info():
    """Retorna informações do sistema"""
    import platform
    import sys
    
    info = {
        'timestamp': datetime.now().isoformat(),
        'python_version': sys.version,
        'platform': platform.platform(),
        'environment': 'production' if os.getenv('VERCEL') else 'development',
        'database_url': 'Configurado' if os.getenv('DATABASE_URL') else 'Não configurado',
        'supabase_url': 'Configurado' if os.getenv('SUPABASE_URL') else 'Não configurado',
        'vercel': bool(os.getenv('VERCEL')),
    }
    
    return jsonify(info)
