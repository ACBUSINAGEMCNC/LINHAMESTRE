import os
from datetime import datetime
from dotenv import load_dotenv

# Carrega variáveis do arquivo .env, se existir
load_dotenv()

# Configurações da aplicação Flask
class Config:
    # Chave secreta da aplicação; defina SECRET_KEY no ambiente ou .env
    SECRET_KEY = os.getenv("SECRET_KEY", "change_me")
    # URL do banco de dados; defina DATABASE_URL no ambiente ou .env
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///acb_usinagem.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = 'uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # Limite de 16MB para uploads
    
    # Diretórios de upload
    UPLOAD_DESENHOS = os.path.join(UPLOAD_FOLDER, 'desenhos')
    UPLOAD_IMAGENS = os.path.join(UPLOAD_FOLDER, 'imagens')
    UPLOAD_INSTRUCOES = os.path.join(UPLOAD_FOLDER, 'instrucoes')
    
    # Extensões permitidas para upload
    ALLOWED_EXTENSIONS = {
        'desenhos': {'pdf'},
        'imagens': {'png', 'jpg', 'jpeg', 'gif'},
        'instrucoes': {'pdf'}
    }
    
    @staticmethod
    def init_app(app):
        # Criar diretórios de upload se possível (ignorar erros em ambiente somente leitura)
        for path in [
            Config.UPLOAD_FOLDER,
            Config.UPLOAD_DESENHOS,
            Config.UPLOAD_IMAGENS,
            Config.UPLOAD_INSTRUCOES,
            'static'
        ]:
            try:
                os.makedirs(path, exist_ok=True)
            except PermissionError:
                # Em ambientes serverless (ex.: Vercel) o sistema de arquivos é somente leitura
                # exceto /tmp. Ignoramos a falha pois uploads não são persistentes lá.
                pass
        
        # Adicionar context processor para data atual
        @app.context_processor
        def utility_processor():
            def now():
                return datetime.now()
            return dict(now=now)

# Configurações para ambiente de desenvolvimento
class DevelopmentConfig(Config):
    DEBUG = True
    
# Configurações para ambiente de produção
class ProductionConfig(Config):
    DEBUG = False
    # Em produção, você pode querer usar um banco de dados diferente
    # SQLALCHEMY_DATABASE_URI = 'mysql://user:password@localhost/acb_usinagem'

# Configurações para testes
class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

# Dicionário de configurações disponíveis
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
