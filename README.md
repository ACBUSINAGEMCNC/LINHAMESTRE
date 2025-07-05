# Sistema de Gestão ACB Usinagem

Este sistema foi desenvolvido para gerenciar os processos de produção, estoque e pedidos da ACB Usinagem CNC.

## Funcionalidades

- Gestão de clientes e unidades de entrega
- Controle de pedidos e ordens de serviço
- Gestão de estoque de materiais e peças
- Kanban para acompanhamento de produção
- Sistema de autenticação com diferentes níveis de acesso
- Backup e restauração do banco de dados

## Novidades na Versão Atual

- **Correção de inicialização do banco de dados**: O sistema agora verifica e inicializa automaticamente o banco de dados na primeira execução
- **Campos de prateleira e posição no estoque**: Organização do estoque por localização física
- **Sistema de autenticação com níveis de acesso**: Controle de permissões por usuário
- **Sistema de backup e restauração**: Proteção contra perda de dados

## Requisitos

- Python 3.10 ou superior
- Flask 2.3.3
- Flask-SQLAlchemy 3.1.1
- Werkzeug 2.3.7

## Instalação

1. Clone ou extraia este repositório para o seu computador
2. Instale as dependências:
   ```
   pip install -r requirements.txt
   ```
3. Execute a aplicação:
   ```
   python3 run.py
   ```
4. Acesse a aplicação em seu navegador:
   ```
   http://127.0.0.1:5000
   ```

## Primeiro Acesso

Ao iniciar pela primeira vez, um usuário administrador padrão será criado automaticamente:
- Email: admin@acbusinagem.com.br
- Senha: admin123

**Importante**: Altere esta senha após o primeiro acesso.

## Estrutura do Projeto

- `app.py`: Arquivo principal da aplicação Flask
- `models.py`: Definição dos modelos de dados (SQLAlchemy)
- `run.py`: Script para iniciar a aplicação
- `init_db.py`: Script para inicialização do banco de dados
- `routes/`: Diretório contendo as rotas da aplicação
- `templates/`: Diretório contendo os templates HTML
- `static/`: Diretório contendo arquivos estáticos (CSS, JS, imagens)
- `uploads/`: Diretório para armazenamento de arquivos enviados
- `backups/`: Diretório para armazenamento de backups

## Solução de Problemas

### Banco de Dados

O sistema agora verifica automaticamente se o banco de dados existe e se todas as tabelas necessárias estão presentes. Se houver algum problema, o banco de dados será inicializado automaticamente.

Se você precisar reinicializar manualmente o banco de dados:

1. Exclua o arquivo `database.db` (um backup será criado automaticamente)
2. Execute a aplicação novamente com `python3 run.py`

### Problemas com SQLAlchemy

Se você encontrar erros relacionados ao SQLAlchemy, consulte o arquivo `instrucoes_sqlalchemy.md` para soluções detalhadas.

## Suporte

Para suporte técnico, entre em contato com o desenvolvedor:
- Email: suporte@acbusinagem.com.br
