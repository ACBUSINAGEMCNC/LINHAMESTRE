# Instruções para Resolver o Problema do SQLAlchemy

Este documento contém instruções para resolver o problema persistente com o SQLAlchemy que pode ocorrer ao executar o projeto.

## Problema

Ao iniciar a aplicação, você pode encontrar o seguinte erro:

```
RuntimeError: The current Flask app is not registered with this 'SQLAlchemy' instance. Did you forget to call 'init_app', or did you create multiple 'SQLAlchemy' instances?
```

Este erro ocorre devido a problemas de importação circular entre os módulos da aplicação e a inicialização do SQLAlchemy.

## Solução

Para resolver este problema, siga um dos métodos abaixo:

### Método 1: Reconstruir o banco de dados

1. Pare a aplicação se estiver em execução
2. Exclua o arquivo `database.db` existente
3. Execute o script de inicialização para criar um novo banco de dados:

```bash
cd /caminho/para/projeto_melhorado
rm database.db
python init_db.py
```

### Método 2: Modificar a estrutura de importação

Se o Método 1 não funcionar, você pode modificar a estrutura de importação do projeto:

1. Crie um arquivo chamado `init_db.py` na raiz do projeto com o seguinte conteúdo:

```python
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash

# Configuração do banco de dados
basedir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Importar modelos
from models import Usuario, Cliente, UnidadeEntrega, Material, Trabalho, Item, Pedido, OrdemServico, PedidoMaterial, Estoque, EstoquePecas, PedidoOrdemServico, MovimentacaoEstoque, MovimentacaoEstoquePecas

# Criar tabelas
db.create_all()

# Adicionar colunas à tabela estoque_pecas
import sqlite3
try:
    conn = sqlite3.connect(os.path.join(basedir, 'database.db'))
    cursor = conn.cursor()
    
    # Verificar se as colunas existem
    cursor.execute("PRAGMA table_info(estoque_pecas)")
    colunas = [coluna[1] for coluna in cursor.fetchall()]
    
    # Adicionar coluna prateleira se não existir
    if 'prateleira' not in colunas:
        cursor.execute("ALTER TABLE estoque_pecas ADD COLUMN prateleira TEXT")
    
    # Adicionar coluna posicao se não existir
    if 'posicao' not in colunas:
        cursor.execute("ALTER TABLE estoque_pecas ADD COLUMN posicao TEXT")
    
    conn.commit()
    conn.close()
except sqlite3.OperationalError as e:
    print(f"Nota: {e}")

# Criar usuário administrador padrão
admin = Usuario.query.filter_by(email='admin@acbusinagem.com.br').first()
if not admin:
    novo_admin = Usuario(
        nome='Administrador',
        email='admin@acbusinagem.com.br',
        senha=generate_password_hash('admin123'),
        nivel='admin',
        acesso_pedidos=True,
        acesso_kanban=True,
        acesso_estoque=True,
        acesso_cadastros=True,
        acesso_finalizar_os=True
    )
    db.session.add(novo_admin)
    db.session.commit()
    print("Usuário administrador padrão criado com sucesso!")

print("Banco de dados inicializado com sucesso!")
```

2. Execute este script para inicializar o banco de dados:

```bash
python init_db.py
```

3. Modifique o arquivo `app.py` para usar a instância de SQLAlchemy já inicializada:

```python
# No início do arquivo app.py, substitua:
db = SQLAlchemy()

# Por:
from init_db import db
```

### Método 3: Usar uma versão específica do Flask-SQLAlchemy

Algumas versões do Flask-SQLAlchemy podem ter problemas de compatibilidade. Tente instalar uma versão específica:

```bash
pip uninstall flask-sqlalchemy
pip install flask-sqlalchemy==2.5.1
```

## Observações Importantes

- Estas modificações podem afetar a estrutura do projeto, mas preservarão sua funcionalidade
- Após aplicar qualquer uma destas soluções, reinicie a aplicação
- Se você tiver dados importantes no banco de dados atual, faça um backup antes de excluí-lo
