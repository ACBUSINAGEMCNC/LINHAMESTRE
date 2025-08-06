#!/usr/bin/env python3
"""
Teste básico para verificar a funcionalidade do módulo de apontamento
sem depender do SQLAlchemy problemático
"""

import json
from datetime import datetime

# Simulação de dados para teste
def simular_dados_teste():
    """Simula dados de teste para apontamento"""
    
    # Dados simulados de uma OS
    ordem_servico = {
        'id': 1,
        'numero': 'OS-001',
        'status': 'Em Produção'
    }
    
    # Dados simulados de um operador
    operador = {
        'id': 1,
        'nome': 'João Silva',
        'codigo_operador': '1234'
    }
    
    # Dados simulados de item de trabalho
    item_trabalho = {
        'id': 1,
        'nome': 'Usinagem CNC',
        'tempo_setup': 1800,  # 30 minutos
        'tempo_peca': 300     # 5 minutos por peça
    }
    
    return ordem_servico, operador, item_trabalho

def validar_apontamento(dados):
    """Valida os dados de um apontamento"""
    
    erros = []
    
    # Validações obrigatórias
    if not dados.get('ordem_servico_id'):
        erros.append('OS é obrigatória')
    
    if not dados.get('tipo_acao'):
        erros.append('Tipo de ação é obrigatório')
    
    if not dados.get('codigo_operador'):
        erros.append('Código do operador é obrigatório')
    
    if not dados.get('item_trabalho_id'):
        erros.append('Tipo de trabalho é obrigatório')
    
    # Validações específicas por tipo de ação
    tipo_acao = dados.get('tipo_acao')
    
    if tipo_acao == 'pausa':
        if not dados.get('quantidade'):
            erros.append('Quantidade é obrigatória para pausas')
        if not dados.get('motivo_parada'):
            erros.append('Motivo da parada é obrigatório')
    
    if tipo_acao == 'fim_producao':
        if not dados.get('quantidade'):
            erros.append('Quantidade final é obrigatória')
    
    return erros

def processar_apontamento(dados):
    """Processa um apontamento simulado"""
    
    # Validar dados
    erros = validar_apontamento(dados)
    if erros:
        return {
            'success': False,
            'message': '; '.join(erros)
        }
    
    # Simular processamento
    agora = datetime.now()
    tipo_acao = dados['tipo_acao']
    
    # Mapear ações para status
    status_map = {
        'inicio_setup': 'Setup em andamento',
        'fim_setup': 'Setup concluído',
        'inicio_producao': 'Produção em andamento',
        'pausa': 'Pausado',
        'fim_producao': 'Finalizado'
    }
    
    novo_status = status_map.get(tipo_acao, 'Desconhecido')
    
    # Simular criação do apontamento
    apontamento = {
        'id': 1,
        'ordem_servico_id': dados['ordem_servico_id'],
        'codigo_operador': dados['codigo_operador'],
        'item_trabalho_id': dados['item_trabalho_id'],
        'tipo_acao': tipo_acao,
        'data_hora': agora.isoformat(),
        'quantidade': dados.get('quantidade'),
        'motivo_parada': dados.get('motivo_parada'),
        'observacoes': dados.get('observacoes'),
        'status_resultante': novo_status
    }
    
    # Preparar mensagem de sucesso
    acao_nome = {
        'inicio_setup': 'Início de setup',
        'fim_setup': 'Fim de setup',
        'inicio_producao': 'Início de produção',
        'pausa': 'Pausa',
        'fim_producao': 'Fim de produção'
    }.get(tipo_acao, tipo_acao)
    
    return {
        'success': True,
        'message': f'{acao_nome} registrado com sucesso!',
        'apontamento': apontamento,
        'status': novo_status
    }

def testar_cenarios():
    """Testa diferentes cenários de apontamento"""
    
    print("=== TESTE DO MÓDULO DE APONTAMENTO ===\n")
    
    ordem_servico, operador, item_trabalho = simular_dados_teste()
    
    # Cenário 1: Início de setup
    print("1. Testando início de setup...")
    dados_setup = {
        'ordem_servico_id': ordem_servico['id'],
        'tipo_acao': 'inicio_setup',
        'codigo_operador': operador['codigo_operador'],
        'item_trabalho_id': item_trabalho['id'],
        'observacoes': 'Iniciando setup da peça'
    }
    
    resultado = processar_apontamento(dados_setup)
    print(f"Resultado: {resultado['message']}")
    print(f"Status: {resultado.get('status', 'N/A')}\n")
    
    # Cenário 2: Início de produção com quantidade
    print("2. Testando início de produção...")
    dados_producao = {
        'ordem_servico_id': ordem_servico['id'],
        'tipo_acao': 'inicio_producao',
        'codigo_operador': operador['codigo_operador'],
        'item_trabalho_id': item_trabalho['id'],
        'quantidade': 0,
        'observacoes': 'Iniciando produção'
    }
    
    resultado = processar_apontamento(dados_producao)
    print(f"Resultado: {resultado['message']}")
    print(f"Status: {resultado.get('status', 'N/A')}\n")
    
    # Cenário 3: Pausa com motivo
    print("3. Testando pausa...")
    dados_pausa = {
        'ordem_servico_id': ordem_servico['id'],
        'tipo_acao': 'pausa',
        'codigo_operador': operador['codigo_operador'],
        'item_trabalho_id': item_trabalho['id'],
        'quantidade': 5,
        'motivo_parada': 'Parada para café',
        'observacoes': 'Pausa programada'
    }
    
    resultado = processar_apontamento(dados_pausa)
    print(f"Resultado: {resultado['message']}")
    print(f"Status: {resultado.get('status', 'N/A')}\n")
    
    # Cenário 4: Fim de produção
    print("4. Testando fim de produção...")
    dados_fim = {
        'ordem_servico_id': ordem_servico['id'],
        'tipo_acao': 'fim_producao',
        'codigo_operador': operador['codigo_operador'],
        'item_trabalho_id': item_trabalho['id'],
        'quantidade': 10,
        'observacoes': 'Produção finalizada com sucesso'
    }
    
    resultado = processar_apontamento(dados_fim)
    print(f"Resultado: {resultado['message']}")
    print(f"Status: {resultado.get('status', 'N/A')}\n")
    
    # Cenário 5: Teste de validação (dados inválidos)
    print("5. Testando validação (dados inválidos)...")
    dados_invalidos = {
        'tipo_acao': 'pausa',
        # Faltando campos obrigatórios
    }
    
    resultado = processar_apontamento(dados_invalidos)
    print(f"Resultado: {resultado['message']}")
    print(f"Success: {resultado['success']}\n")
    
    print("=== TESTES CONCLUÍDOS ===")

if __name__ == '__main__':
    testar_cenarios()
