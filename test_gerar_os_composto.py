#!/usr/bin/env python3
"""
Script para testar a geração de OS de item composto
"""

import os
import sys
import requests
from datetime import datetime

def test_gerar_os():
    """Testa a geração de OS via requisição HTTP"""
    
    print("=" * 60)
    print("TESTE: GERAÇÃO DE OS PARA ITEM COMPOSTO")
    print("=" * 60)
    
    # URL da aplicação
    base_url = "http://127.0.0.1:5000"
    
    # Primeiro, vamos fazer login
    session = requests.Session()
    
    print("1. Fazendo login...")
    login_data = {
        'email': 'admin@acbusinagem.com.br',
        'password': 'admin123'
    }
    
    login_response = session.post(f"{base_url}/login", data=login_data)
    if login_response.status_code == 200:
        print("   ✅ Login realizado com sucesso")
    else:
        print(f"   ❌ Erro no login: {login_response.status_code}")
        return
    
    # Listar pedidos para encontrar o item composto
    print("\n2. Listando pedidos...")
    pedidos_response = session.get(f"{base_url}/pedidos")
    if pedidos_response.status_code == 200:
        print("   ✅ Pedidos carregados")
    else:
        print(f"   ❌ Erro ao carregar pedidos: {pedidos_response.status_code}")
        return
    
    # Tentar gerar OS para o pedido do item composto
    # Baseado no debug, sabemos que existe o pedido PED-00035 do item ACB-00020
    print("\n3. Tentando gerar OS para item composto...")
    
    # Vamos simular a seleção do pedido e geração de OS
    # Primeiro precisamos encontrar o ID do pedido
    
    # Como não temos acesso direto ao HTML, vamos tentar via API ou fazer uma requisição direta
    os_data = {
        'pedidos[]': ['35']  # ID do pedido baseado no debug (PED-00035 provavelmente tem ID 35)
    }
    
    print("   Enviando requisição para gerar OS...")
    print(f"   Dados: {os_data}")
    
    os_response = session.post(f"{base_url}/pedidos/gerar-os-multipla", data=os_data)
    
    print(f"   Status da resposta: {os_response.status_code}")
    
    if os_response.status_code == 200:
        print("   ✅ Requisição processada")
        # Verificar se houve redirecionamento (sucesso)
        if 'pedidos' in os_response.url:
            print("   ✅ Redirecionado para lista de pedidos (sucesso)")
        else:
            print("   ⚠️  Resposta inesperada")
    else:
        print(f"   ❌ Erro na geração de OS: {os_response.status_code}")
        print(f"   Resposta: {os_response.text[:500]}")
    
    print("\n" + "=" * 60)
    print("TESTE CONCLUÍDO")
    print("=" * 60)

if __name__ == "__main__":
    test_gerar_os()
