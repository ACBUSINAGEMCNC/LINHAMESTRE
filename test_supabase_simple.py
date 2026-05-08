#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script simples para testar Supabase Storage
"""

import os
import sys
import requests

def test_supabase():
    print("=== TESTE SUPABASE STORAGE ===\n")
    
    # Ler variáveis de ambiente
    supabase_url = os.environ.get('SUPABASE_URL')
    supabase_key = (
        os.environ.get('SUPABASE_SERVICE_KEY') or 
        os.environ.get('SUPABASE_ANON_KEY') or 
        os.environ.get('SUPABASE_KEY')
    )
    bucket = os.environ.get('SUPABASE_BUCKET', 'uploads')
    
    print(f"URL: {supabase_url if supabase_url else '❌ NÃO CONFIGURADO'}")
    print(f"KEY: {'✅ Configurada' if supabase_key else '❌ NÃO CONFIGURADA'}")
    print(f"BUCKET: {bucket}\n")
    
    if not supabase_url or not supabase_key:
        print("❌ PROBLEMA: Variáveis de ambiente não configuradas!")
        print("\nPara configurar, adicione no arquivo .env:")
        print("SUPABASE_URL=https://seu-projeto.supabase.co")
        print("SUPABASE_SERVICE_KEY=sua_service_key_aqui")
        print("SUPABASE_BUCKET=uploads")
        return False
    
    # Testar conexão
    headers = {
        'Authorization': f'Bearer {supabase_key}',
        'apikey': supabase_key
    }
    
    list_url = f"{supabase_url}/storage/v1/object/list/{bucket}"
    print(f"Testando URL: {list_url}\n")
    
    try:
        response = requests.post(list_url, headers=headers, json={'prefix': ''}, timeout=10)
        print(f"Status HTTP: {response.status_code}")
        
        if response.status_code == 200:
            files = response.json()
            print(f"✅ SUCESSO! Encontrados {len(files)} itens no bucket\n")
            
            if files:
                print("Arquivos encontrados:")
                for i, item in enumerate(files[:10], 1):
                    name = item.get('name', 'sem nome')
                    size = item.get('metadata', {}).get('size', 0)
                    print(f"  {i}. {name} ({size} bytes)")
                
                if len(files) > 10:
                    print(f"  ... e mais {len(files) - 10} arquivos")
            else:
                print("ℹ️  Bucket está vazio")
            
            return True
        else:
            print(f"❌ ERRO: Status {response.status_code}")
            print(f"Resposta: {response.text[:300]}")
            
            if response.status_code == 400:
                print("\n💡 Dica: Verifique se o bucket existe no Supabase")
            elif response.status_code == 401:
                print("\n💡 Dica: Verifique se a SUPABASE_SERVICE_KEY está correta")
            elif response.status_code == 404:
                print("\n💡 Dica: Verifique se a URL do Supabase está correta")
            
            return False
            
    except requests.exceptions.Timeout:
        print("❌ ERRO: Timeout na conexão")
        return False
    except requests.exceptions.ConnectionError:
        print("❌ ERRO: Falha na conexão com o Supabase")
        return False
    except Exception as e:
        print(f"❌ ERRO: {str(e)}")
        return False

if __name__ == '__main__':
    success = test_supabase()
    print(f"\n{'='*50}")
    print(f"Resultado: {'✅ CONFIGURADO E FUNCIONANDO' if success else '❌ PROBLEMA NA CONFIGURAÇÃO'}")
    sys.exit(0 if success else 1)
