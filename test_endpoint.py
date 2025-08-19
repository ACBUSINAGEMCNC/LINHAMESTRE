#!/usr/bin/env python3
"""
Teste rápido do endpoint /apontamento/status-ativos para verificar se OS-2025-08-002 ainda aparece
"""

import requests
import json

try:
    response = requests.get('http://127.0.0.1:5000/apontamento/status-ativos', timeout=10)
    
    if response.status_code == 200:
        data = response.json()
        status_ativos = data.get('status_ativos', [])
        
        print(f"=== TESTE ENDPOINT STATUS-ATIVOS ===")
        print(f"Total de status ativos: {len(status_ativos)}")
        
        # Verificar se OS-2025-08-002 está na lista
        os_002_encontrada = False
        for item in status_ativos:
            os_numero = item.get('os_numero', '')
            if 'OS-2025-08-002' in os_numero:
                os_002_encontrada = True
                print(f"❌ OS-2025-08-002 AINDA APARECE:")
                print(f"   OS: {os_numero}")
                print(f"   Status: {item.get('status_atual', 'N/A')}")
                print(f"   Lista Kanban: {item.get('lista_kanban', 'N/A')}")
                break
        
        if not os_002_encontrada:
            print("✅ OS-2025-08-002 NÃO APARECE MAIS - Correção funcionou!")
        
        # Mostrar todas as OS encontradas
        print(f"\n📋 Todas as OS ativas:")
        for item in status_ativos:
            os_numero = item.get('os_numero', 'N/A')
            status = item.get('status_atual', 'N/A')
            lista = item.get('lista_kanban', 'N/A')
            print(f"   {os_numero} - {status} - {lista}")
            
    else:
        print(f"❌ Erro HTTP {response.status_code}: {response.text}")
        
except Exception as e:
    print(f"❌ Erro na requisição: {e}")
