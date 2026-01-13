#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Script para remover os botões Pedidos e Itens do header do Kanban"""

import os

file_path = r'c:\Users\ARTCOMPANY\Desktop\git\13 12 2025\LINHAMESTRE\templates\kanban\index.html'

# Ler o arquivo
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Substituir a seção com os botões por apenas o título
old_section = '''    <div class="container-fluid py-3">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <h1 class="mb-0">Kanban ACB</h1>
            <div class="kanban-shortcuts">
                <a href="/pedidos" class="btn btn-outline-primary btn-sm me-2">
                    <i class="fas fa-clipboard-list me-1"></i>Pedidos
                </a>
                <a href="/itens" class="btn btn-outline-success btn-sm">
                    <i class="fas fa-boxes me-1"></i>Itens
                </a>
            </div>
        </div>
        
        <div class="kanban-container">'''

new_section = '''    <div class="container-fluid py-3">
        <h1 class="mb-4">Kanban ACB</h1>
        
        <div class="kanban-container">'''

# Adicionar links na navbar
old_navbar = '''                    <li class="nav-item">
                        <a class="nav-link" href="/registros-mensais"><i class="fas fa-archive"></i> Registros Mensais</a>
                    </li>
                </ul>'''

new_navbar = '''                    <li class="nav-item">
                        <a class="nav-link" href="/registros-mensais"><i class="fas fa-archive"></i> Registros Mensais</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="/pedidos"><i class="fas fa-clipboard-list"></i> Pedidos</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="/itens"><i class="fas fa-boxes"></i> Itens</a>
                    </li>
                </ul>'''

# Fazer as substituições
if old_section in content:
    content = content.replace(old_section, new_section)
    print("✓ Botões removidos do header")
else:
    print("✗ Seção dos botões não encontrada")

if old_navbar in content and 'href="/pedidos"' not in content[:content.index(old_navbar)]:
    content = content.replace(old_navbar, new_navbar)
    print("✓ Links adicionados na navbar")
else:
    print("✓ Links já existem na navbar")

# Salvar o arquivo
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("\n✅ Arquivo atualizado com sucesso!")
print(f"📁 {file_path}")
