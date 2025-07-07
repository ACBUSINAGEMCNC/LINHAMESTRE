"""Entry point para Vercel Serverless Function

Vercel detecta o runtime Python (@vercel/python). Basta exportar um objeto WSGI chamado
``app`` que será usado como handler. Aqui simplesmente importamos o ``create_app``
do projeto Flask e o expomos.

Executar localmente:
    python run.py  # (continua funcionando normalmente)

Em produção (Vercel):
    Todas as rotas serão encaminhadas para este módulo, que responderá via Flask.
"""

from app import create_app

# Cria instância da aplicação Flask
app = create_app()
