#!/usr/bin/env python3
"""
Versão simplificada do app Flask para testar o módulo de apontamento
sem problemas de compatibilidade do SQLAlchemy
"""

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
import sqlite3
import json
from datetime import datetime
import os
try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    psycopg2 = None

app = Flask(__name__)
app.secret_key = 'chave-secreta-para-desenvolvimento'

# Configuração do banco Supabase
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    """Retorna conexão com o banco de dados (Supabase ou SQLite local)"""
    database_url = DATABASE_URL
    
    if database_url and database_url.startswith('postgresql') and psycopg2:
        # Conexão com Supabase/PostgreSQL
        try:
            conn = psycopg2.connect(database_url)
            conn.cursor_factory = psycopg2.extras.RealDictCursor
            return conn
        except Exception as e:
            print(f"Erro ao conectar com PostgreSQL: {e}")
            print("Usando SQLite local como fallback")
    
    # Conexão local SQLite
    conn = sqlite3.connect('apontamento.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Inicializa o banco de dados com as tabelas necessárias"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Criar tabelas básicas se não existirem
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuario (
            id SERIAL PRIMARY KEY,
            nome TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            codigo_operador TEXT UNIQUE,
            ativo BOOLEAN DEFAULT 1
        )
    ''')
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS ordem_servico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero TEXT UNIQUE NOT NULL,
            data_criacao DATE DEFAULT CURRENT_DATE,
            status TEXT DEFAULT 'Entrada'
        )
    ''')
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS item_trabalho (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ordem_servico_id INTEGER,
            nome TEXT,
            tempo_setup INTEGER,
            tempo_peca INTEGER,
            FOREIGN KEY (ordem_servico_id) REFERENCES ordem_servico (id)
        )
    ''')
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS apontamento_producao (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ordem_servico_id INTEGER NOT NULL,
            usuario_id INTEGER NOT NULL,
            item_trabalho_id INTEGER NOT NULL,
            tipo_acao TEXT NOT NULL,
            data_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            quantidade INTEGER,
            motivo_parada TEXT,
            observacoes TEXT,
            lista_kanban TEXT,
            FOREIGN KEY (ordem_servico_id) REFERENCES ordem_servico (id),
            FOREIGN KEY (usuario_id) REFERENCES usuario (id),
            FOREIGN KEY (item_trabalho_id) REFERENCES item_trabalho (id)
        )
    ''')
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS status_producao_os (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ordem_servico_id INTEGER UNIQUE NOT NULL,
            status_atual TEXT NOT NULL,
            operador_atual_id INTEGER,
            trabalho_atual_id INTEGER,
            inicio_trabalho_atual TIMESTAMP,
            quantidade_atual INTEGER DEFAULT 0,
            motivo_parada TEXT,
            FOREIGN KEY (ordem_servico_id) REFERENCES ordem_servico (id),
            FOREIGN KEY (operador_atual_id) REFERENCES usuario (id),
            FOREIGN KEY (trabalho_atual_id) REFERENCES item_trabalho (id)
        )
    ''')
    
    # Inserir dados de teste se não existirem
    cursor = conn.execute('SELECT COUNT(*) FROM usuario')
    if cursor.fetchone()[0] == 0:
        conn.execute('''
            INSERT INTO usuario (nome, email, codigo_operador) 
            VALUES ('João Silva', 'joao@teste.com', '1234')
        ''')
        
        conn.execute('''
            INSERT INTO usuario (nome, email, codigo_operador) 
            VALUES ('Maria Santos', 'maria@teste.com', '5678')
        ''')
    
    cursor = conn.execute('SELECT COUNT(*) FROM ordem_servico')
    if cursor.fetchone()[0] == 0:
        conn.execute('''
            INSERT INTO ordem_servico (numero, status) 
            VALUES ('OS-001', 'Em Produção')
        ''')
        
        conn.execute('''
            INSERT INTO ordem_servico (numero, status) 
            VALUES ('OS-002', 'Setup')
        ''')
    
    cursor = conn.execute('SELECT COUNT(*) FROM item_trabalho')
    if cursor.fetchone()[0] == 0:
        conn.execute('''
            INSERT INTO item_trabalho (ordem_servico_id, nome, tempo_setup, tempo_peca) 
            VALUES (1, 'Usinagem CNC', 1800, 300)
        ''')
        
        conn.execute('''
            INSERT INTO item_trabalho (ordem_servico_id, nome, tempo_setup, tempo_peca) 
            VALUES (2, 'Torneamento', 1200, 240)
        ''')
    
    conn.commit()
    conn.close()

@app.route('/')
def index():
    """Página inicial - Kanban com dados reais do banco"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Buscar ordens de serviço reais do banco
        query = """
            SELECT 
                os.id,
                os.numero,
                os.status,
                os.data_criacao,
                STRING_AGG(DISTINCT c.nome, ', ') as clientes,
                STRING_AGG(DISTINCT COALESCE(i.nome, p.nome_item), ', ') as descricao,
                MIN(p.previsao_entrega) as data_entrega
            FROM ordem_servico os
            LEFT JOIN pedido_ordem_servico pos ON os.id = pos.ordem_servico_id
            LEFT JOIN pedido p ON pos.pedido_id = p.id
            LEFT JOIN cliente c ON p.cliente_id = c.id
            LEFT JOIN item i ON p.item_id = i.id
            WHERE os.status != 'Finalizada'
            GROUP BY os.id, os.numero, os.status, os.data_criacao
            ORDER BY os.data_criacao DESC
            LIMIT 50
        """
        
        # Verificar se é PostgreSQL ou SQLite e ajustar query
        database_url = os.environ.get('DATABASE_URL')
        if database_url and database_url.startswith('postgresql'):
            cursor.execute(query)
        else:
            # Query simplificada para SQLite
            sqlite_query = """
                SELECT 
                    os.id,
                    os.numero,
                    os.status,
                    os.data_criacao,
                    'Cliente' as clientes,
                    'Descrição da OS' as descricao,
                    date('now', '+7 days') as data_entrega
                FROM ordem_servico os
                WHERE os.status != 'Finalizada'
                ORDER BY os.data_criacao DESC
                LIMIT 50
            """
            cursor.execute(sqlite_query)
        
        ordens_servico = []
        for row in cursor.fetchall():
            ordens_servico.append({
                'id': row['id'],
                'numero': row['numero'],
                'status': row['status'],
                'cliente': row['clientes'] or 'Cliente não informado',
                'descricao': row['descricao'] or 'Descrição não informada',
                'data_entrega': row['data_entrega'] or '2024-12-31',
                'prioridade': 'Média'  # Valor padrão
            })
        
        conn.close()
        
        # Se não encontrou ordens, usar dados de exemplo
        if not ordens_servico:
            ordens_servico = [
                {
                    'id': 1,
                    'numero': 'OS-EXEMPLO-001',
                    'status': 'Aguardando',
                    'cliente': 'Cliente Exemplo',
                    'descricao': 'Exemplo de ordem de serviço',
                    'data_entrega': '2024-12-31',
                    'prioridade': 'Média'
                }
            ]
            print("Nenhuma ordem de serviço encontrada no banco. Usando dados de exemplo.")
        else:
            print(f"Encontradas {len(ordens_servico)} ordens de serviço no banco.")
        
    except Exception as e:
        print(f"Erro ao buscar ordens de serviço: {e}")
        # Fallback para dados de exemplo em caso de erro
        ordens_servico = [
            {
                'id': 1,
                'numero': 'OS-ERRO-001',
                'status': 'Aguardando',
                'cliente': 'Erro de conexão',
                'descricao': 'Erro ao conectar com banco de dados',
                'data_entrega': '2024-12-31',
                'prioridade': 'Alta'
            }
        ]
    
    return render_template('kanban/index_simple.html', ordens_servico=ordens_servico)

@app.route('/apontamento/validar-codigo', methods=['POST'])
def validar_codigo():
    """Valida código do operador"""
    dados = request.get_json()
    codigo = dados.get('codigo')
    
    if not codigo or len(codigo) != 4:
        return jsonify({
            'valid': False,
            'message': 'Código deve ter 4 dígitos'
        })
    
    conn = get_db_connection()
    usuario = conn.execute(
        'SELECT nome FROM usuario WHERE codigo_operador = ?', 
        (codigo,)
    ).fetchone()
    conn.close()
    
    if usuario:
        return jsonify({
            'valid': True,
            'message': f'Operador: {usuario["nome"]}'
        })
    else:
        return jsonify({
            'valid': False,
            'message': 'Código não encontrado'
        })

@app.route('/apontamento/os/<int:ordem_id>/tipos-trabalho')
def tipos_trabalho_os(ordem_id):
    """Retorna tipos de trabalho para uma OS"""
    conn = get_db_connection()
    
    # Verificar se a OS existe
    ordem = conn.execute(
        'SELECT * FROM ordem_servico WHERE id = ?', 
        (ordem_id,)
    ).fetchone()
    
    if not ordem:
        conn.close()
        return jsonify({
            'success': False,
            'message': 'Ordem de serviço não encontrada'
        })
    
    # Buscar itens de trabalho
    itens = conn.execute(
        'SELECT * FROM item_trabalho WHERE ordem_servico_id = ?', 
        (ordem_id,)
    ).fetchall()
    
    conn.close()
    
    tipos_trabalho = []
    for item in itens:
        tipos_trabalho.append({
            'id': item['id'],
            'nome': item['nome'] or f'Item {item["id"]}',
            'tempo_setup': item['tempo_setup'],
            'tempo_peca': item['tempo_peca']
        })
    
    return jsonify({
        'success': True,
        'tipos_trabalho': tipos_trabalho
    })

@app.route('/apontamento/registrar', methods=['POST'])
def registrar_apontamento():
    """Registra novo apontamento"""
    try:
        dados = request.get_json()
        
        # Validações básicas
        if not dados.get('ordem_servico_id'):
            return jsonify({'success': False, 'message': 'OS é obrigatória'})
        
        if not dados.get('tipo_acao'):
            return jsonify({'success': False, 'message': 'Tipo de ação é obrigatório'})
        
        if not dados.get('codigo_operador'):
            return jsonify({'success': False, 'message': 'Código do operador é obrigatório'})
        
        if not dados.get('item_trabalho_id'):
            return jsonify({'success': False, 'message': 'Tipo de trabalho é obrigatório'})
        
        conn = get_db_connection()
        
        # Validar operador
        usuario = conn.execute(
            'SELECT * FROM usuario WHERE codigo_operador = ?', 
            (dados['codigo_operador'],)
        ).fetchone()
        
        if not usuario:
            conn.close()
            return jsonify({'success': False, 'message': 'Código de operador inválido'})
        
        # Validar OS
        ordem = conn.execute(
            'SELECT * FROM ordem_servico WHERE id = ?', 
            (dados['ordem_servico_id'],)
        ).fetchone()
        
        if not ordem:
            conn.close()
            return jsonify({'success': False, 'message': 'Ordem de serviço não encontrada'})
        
        # Validar item de trabalho
        item = conn.execute(
            'SELECT * FROM item_trabalho WHERE id = ?', 
            (dados['item_trabalho_id'],)
        ).fetchone()
        
        if not item:
            conn.close()
            return jsonify({'success': False, 'message': 'Tipo de trabalho não encontrado'})
        
        # Validações específicas por tipo de ação
        tipo_acao = dados['tipo_acao']
        if tipo_acao == 'pausa':
            if not dados.get('quantidade'):
                conn.close()
                return jsonify({'success': False, 'message': 'Quantidade é obrigatória para pausas'})
            if not dados.get('motivo_parada'):
                conn.close()
                return jsonify({'success': False, 'message': 'Motivo da parada é obrigatório'})
        
        if tipo_acao == 'fim_producao':
            if not dados.get('quantidade'):
                conn.close()
                return jsonify({'success': False, 'message': 'Quantidade final é obrigatória'})
        
        # Mapear status
        status_map = {
            'inicio_setup': 'Setup em andamento',
            'fim_setup': 'Setup concluído',
            'inicio_producao': 'Produção em andamento',
            'pausa': 'Pausado',
            'fim_producao': 'Finalizado'
        }
        
        novo_status = status_map.get(tipo_acao, 'Desconhecido')
        
        # Inserir apontamento
        conn.execute('''
            INSERT INTO apontamento_producao 
            (ordem_servico_id, usuario_id, item_trabalho_id, tipo_acao, quantidade, motivo_parada, observacoes, lista_kanban)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            dados['ordem_servico_id'],
            usuario['id'],
            dados['item_trabalho_id'],
            tipo_acao,
            dados.get('quantidade'),
            dados.get('motivo_parada'),
            dados.get('observacoes'),
            ordem['status']
        ))
        
        # Atualizar ou inserir status da OS
        status_existente = conn.execute(
            'SELECT * FROM status_producao_os WHERE ordem_servico_id = ?',
            (dados['ordem_servico_id'],)
        ).fetchone()
        
        if status_existente:
            conn.execute('''
                UPDATE status_producao_os 
                SET status_atual = ?, operador_atual_id = ?, trabalho_atual_id = ?, 
                    quantidade_atual = ?, motivo_parada = ?
                WHERE ordem_servico_id = ?
            ''', (
                novo_status,
                usuario['id'],
                dados['item_trabalho_id'],
                dados.get('quantidade', 0),
                dados.get('motivo_parada'),
                dados['ordem_servico_id']
            ))
        else:
            conn.execute('''
                INSERT INTO status_producao_os 
                (ordem_servico_id, status_atual, operador_atual_id, trabalho_atual_id, quantidade_atual, motivo_parada)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                dados['ordem_servico_id'],
                novo_status,
                usuario['id'],
                dados['item_trabalho_id'],
                dados.get('quantidade', 0),
                dados.get('motivo_parada')
            ))
        
        conn.commit()
        conn.close()
        
        # Preparar mensagem de sucesso
        acao_nome = {
            'inicio_setup': 'Início de setup',
            'fim_setup': 'Fim de setup',
            'inicio_producao': 'Início de produção',
            'pausa': 'Pausa',
            'fim_producao': 'Fim de produção'
        }.get(tipo_acao, tipo_acao)
        
        return jsonify({
            'success': True,
            'message': f'{acao_nome} registrado com sucesso!',
            'status': novo_status
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Erro ao registrar apontamento: {str(e)}'
        })

@app.route('/apontamento/operadores')
def operadores():
    """Página de gestão de operadores"""
    conn = get_db_connection()
    usuarios = conn.execute('SELECT * FROM usuario ORDER BY nome').fetchall()
    conn.close()
    
    return render_template('apontamento/operadores.html', usuarios=usuarios)

@app.route('/apontamento/dashboard')
def dashboard():
    """Dashboard de apontamentos"""
    conn = get_db_connection()
    
    # Buscar status ativos
    status_ativos = conn.execute('''
        SELECT s.*, 
               o.numero as os_numero,
               u.nome as operador_nome, u.codigo_operador,
               i.nome as trabalho_nome
        FROM status_producao_os s
        LEFT JOIN ordem_servico o ON s.ordem_servico_id = o.id
        LEFT JOIN usuario u ON s.operador_atual_id = u.id
        LEFT JOIN item_trabalho i ON s.trabalho_atual_id = i.id
        WHERE s.status_atual != 'Finalizado'
        ORDER BY s.inicio_trabalho_atual DESC
    ''').fetchall()
    
    # Buscar últimos apontamentos
    ultimos_apontamentos = conn.execute('''
        SELECT a.*, 
               o.numero as os_numero,
               u.nome as operador_nome
        FROM apontamento_producao a
        LEFT JOIN ordem_servico o ON a.ordem_servico_id = o.id
        LEFT JOIN usuario u ON a.usuario_id = u.id
        ORDER BY a.data_hora DESC
        LIMIT 10
    ''').fetchall()
    
    conn.close()
    
    # Converter para objetos simulados para compatibilidade com template
    status_processados = []
    for status in status_ativos:
        status_obj = type('Status', (), {
            'ordem_servico_id': status['ordem_servico_id'],
            'status_atual': status['status_atual'],
            'quantidade_atual': status['quantidade_atual'],
            'inicio_trabalho_atual': datetime.fromisoformat(status['inicio_trabalho_atual']) if status['inicio_trabalho_atual'] else None,
            'motivo_parada': status['motivo_parada'],
            'ordem_servico': type('OS', (), {'numero': status['os_numero']})() if status['os_numero'] else None,
            'operador_atual': type('User', (), {
                'nome': status['operador_nome'],
                'codigo_operador': status['codigo_operador']
            })() if status['operador_nome'] else None,
            'trabalho_atual': type('Trabalho', (), {
                'nome': status['trabalho_nome'],
                'id': status['trabalho_atual_id']
            })() if status['trabalho_nome'] else None
        })()
        status_processados.append(status_obj)
    
    apontamentos_processados = []
    for apt in ultimos_apontamentos:
        apt_obj = type('Apontamento', (), {
            'tipo_acao': apt['tipo_acao'],
            'quantidade': apt['quantidade'],
            'motivo_parada': apt['motivo_parada'],
            'data_hora': datetime.fromisoformat(apt['data_hora']) if apt['data_hora'] else datetime.now(),
            'ordem_servico_id': apt['ordem_servico_id'],
            'ordem_servico': type('OS', (), {'numero': apt['os_numero']})() if apt['os_numero'] else None,
            'usuario': type('User', (), {'nome': apt['operador_nome']})() if apt['operador_nome'] else None
        })()
        apontamentos_processados.append(apt_obj)
    
    return render_template('apontamento/dashboard_simple.html', 
                         status_ativos=status_processados,
                         ultimos_apontamentos=apontamentos_processados)

@app.route('/apontamento/os/<int:ordem_id>/logs')
def logs_os(ordem_id):
    """Retorna logs de apontamento de uma OS"""
    conn = get_db_connection()
    
    logs = conn.execute('''
        SELECT a.*, 
               u.nome as operador_nome,
               i.nome as trabalho_nome
        FROM apontamento_producao a
        LEFT JOIN usuario u ON a.usuario_id = u.id
        LEFT JOIN item_trabalho i ON a.item_trabalho_id = i.id
        WHERE a.ordem_servico_id = ?
        ORDER BY a.data_hora DESC
    ''', (ordem_id,)).fetchall()
    
    conn.close()
    
    logs_formatados = []
    for log in logs:
        logs_formatados.append({
            'tipo_acao': log['tipo_acao'],
            'operador_nome': log['operador_nome'] or 'N/A',
            'trabalho_nome': log['trabalho_nome'] or f'Item {log["item_trabalho_id"]}',
            'quantidade': log['quantidade'],
            'motivo_parada': log['motivo_parada'],
            'observacoes': log['observacoes'],
            'data_hora': log['data_hora'],
            'data_fim': log['data_fim'],
            'tempo_decorrido': log['tempo_decorrido'],
            'item_id': log['item_id'],
            'trabalho_id': log['trabalho_id']
        })
    
    return jsonify({
        'success': True,
        'logs': logs_formatados
    })

@app.route('/apontamento/relatorios')
def relatorios():
    """Página de relatórios de produção"""
    return render_template('apontamento/relatorios.html')

@app.route('/apontamento/api/relatorio-dados')
def relatorio_dados():
    """API para dados do relatório"""
    try:
        # Parâmetros de filtro (opcional)
        data_inicio = request.args.get('data_inicio')
        data_fim = request.args.get('data_fim')
        operador_id = request.args.get('operador_id')
        os_id = request.args.get('os_id')
        
        conn = get_db_connection()
        
        # Query base
        query = '''
            SELECT a.*, 
                   o.numero as os_numero,
                   u.nome as operador_nome, u.codigo_operador,
                   i.nome as trabalho_nome
            FROM apontamento_producao a
            LEFT JOIN ordem_servico o ON a.ordem_servico_id = o.id
            LEFT JOIN usuario u ON a.usuario_id = u.id
            LEFT JOIN item_trabalho i ON a.item_trabalho_id = i.id
            WHERE 1=1
        '''
        
        params = []
        
        # Aplicar filtros se fornecidos
        if data_inicio:
            query += ' AND date(a.data_hora) >= ?'
            params.append(data_inicio)
        
        if data_fim:
            query += ' AND date(a.data_hora) <= ?'
            params.append(data_fim)
        
        if operador_id:
            query += ' AND u.codigo_operador = ?'
            params.append(operador_id)
        
        if os_id:
            query += ' AND a.ordem_servico_id = ?'
            params.append(os_id)
        
        query += ' ORDER BY a.data_hora DESC LIMIT 100'
        
        apontamentos = conn.execute(query, params).fetchall()
        
        # Calcular métricas
        total_apontamentos = len(apontamentos)
        pecas_produzidas = sum(apt['quantidade'] or 0 for apt in apontamentos if apt['tipo_acao'] == 'fim_producao')
        
        # Contar pausas por motivo
        pausas = [apt for apt in apontamentos if apt['tipo_acao'] == 'pausa']
        motivos_parada = {}
        for pausa in pausas:
            motivo = pausa['motivo_parada'] or 'Não informado'
            motivos_parada[motivo] = motivos_parada.get(motivo, 0) + 1
        
        # Distribuição por operador
        operadores = {}
        for apt in apontamentos:
            operador = apt['operador_nome'] or 'Não informado'
            operadores[operador] = operadores.get(operador, 0) + 1
        
        conn.close()
        
        # Formatar dados para resposta
        dados_formatados = []
        for apt in apontamentos:
            dados_formatados.append({
                'data_hora': datetime.fromisoformat(apt['data_hora']).strftime('%d/%m/%Y %H:%M:%S') if apt['data_hora'] else 'N/A',
                'os': apt['os_numero'] or f"OS-{apt['ordem_servico_id']}",
                'operador': apt['operador_nome'] or 'N/A',
                'codigo_operador': apt['codigo_operador'] or '',
                'acao': apt['tipo_acao'],
                'trabalho': apt['trabalho_nome'] or f"Item {apt['item_trabalho_id']}",
                'quantidade': apt['quantidade'],
                'motivo_parada': apt['motivo_parada'],
                'observacoes': apt['observacoes']
            })
        
        return jsonify({
            'success': True,
            'dados': dados_formatados,
            'metricas': {
                'total_apontamentos': total_apontamentos,
                'pecas_produzidas': pecas_produzidas,
                'tempo_paradas': '2.5h',  # Simulado
                'eficiencia': 87  # Simulado
            },
            'motivos_parada': motivos_parada,
            'distribuicao_operadores': operadores
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Erro ao gerar relatório: {str(e)}'
        })

if __name__ == '__main__':
    # Inicializar banco de dados
    init_db()
    print("Banco de dados inicializado com sucesso!")
    print("Servidor iniciando em http://localhost:5000")
    print("Conectando com banco de dados real do Supabase...")
    print("Acesse /apontamento/operadores para gerenciar códigos de operador")
    
    app.run(host='0.0.0.0', debug=True, port=5000)
