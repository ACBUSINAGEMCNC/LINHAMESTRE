#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de teste para verificar acesso ao Supabase Storage
"""

import os
import requests
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

def test_supabase_storage():
    """Testa o acesso ao Supabase Storage"""
    print("=== TESTE DO SUPABASE STORAGE ===")
    
    # Configurações - tentar diferentes nomes de variáveis
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = (
        os.getenv('SUPABASE_SERVICE_KEY') or 
        os.getenv('SUPABASE_ANON_KEY') or 
        os.getenv('SUPABASE_KEY')
    )
    bucket_name = os.getenv('SUPABASE_BUCKET', 'uploads')
    
    print(f"URL: {supabase_url[:50] + '...' if supabase_url else 'Não configurado'}")
    print(f"KEY: {'Configurado' if supabase_key else 'Não configurado'}")
    print(f"BUCKET: {bucket_name}")
    print()
    
    auth_key = supabase_key
    
    if not all([supabase_url, auth_key]):
        print("❌ ERRO: Credenciais não configuradas!")
        print("Configure SUPABASE_URL e SUPABASE_ANON_KEY no arquivo .env")
        return False
    
    # Headers para autenticação
    headers = {
        'Authorization': f'Bearer {auth_key}',
        'apikey': auth_key
    }
    
    # Testar listagem de arquivos
    list_url = f"{supabase_url}/storage/v1/object/list/{bucket_name}"
    print(f"Testando: {list_url}")
    
    try:
        # Tentar com prefix vazio (requerido pela API)
        response = requests.post(list_url, headers=headers, json={'prefix': ''}, timeout=10)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            files = response.json()
            print(f"✅ SUCESSO: Encontrados {len(files)} arquivos no bucket '{bucket_name}'")
            
            # Mostrar alguns arquivos como exemplo
            if files:
                print("\nPrimeiros arquivos encontrados:")
                for i, file_info in enumerate(files[:5]):
                    if file_info.get('name'):
                        print(f"  {i+1}. {file_info['name']}")
                        
                # Testar download de um arquivo
                if files and files[0].get('name'):
                    test_file = files[0]['name']
                    download_url = f"{supabase_url}/storage/v1/object/public/{bucket_name}/{test_file}"
                    print(f"\nTestando download: {test_file}")
                    
                    try:
                        download_response = requests.get(download_url, timeout=10)
                        if download_response.status_code == 200:
                            print(f"✅ Download OK: {len(download_response.content)} bytes")
                        else:
                            print(f"❌ Erro no download: {download_response.status_code}")
                    except Exception as e:
                        print(f"❌ Erro no download: {str(e)}")
            else:
                print("ℹ️  Bucket vazio (nenhum arquivo encontrado)")
            
            return True
        else:
            print(f"❌ ERRO: {response.status_code}")
            print(f"Resposta: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"❌ ERRO na requisição: {str(e)}")
        return False

if __name__ == '__main__':
    success = test_supabase_storage()
    print(f"\nResultado: {'✅ SUCESSO' if success else '❌ FALHA'}")
