from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from datetime import datetime
import math

# Inicializar SQLAlchemy
db = SQLAlchemy()

# Models
class Cliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    unidades = relationship('UnidadeEntrega', backref='cliente', lazy=True)
    pedidos = relationship('Pedido', backref='cliente', lazy=True)
    
    def __repr__(self):
        return f'<Cliente {self.nome}>'
    
class UnidadeEntrega(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'), nullable=False)
    pedidos = relationship('Pedido', backref='unidade_entrega', lazy=True)
    
    def __repr__(self):
        return f'<UnidadeEntrega {self.nome}>'

class Material(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    tipo = db.Column(db.String(50))  # chapa, fundido, blank, redondo, quadrado, etc.
    material = db.Column(db.String(50))  # aço mecânico, inox, etc.
    liga = db.Column(db.String(50))  # 1045, etc.
    diametro = db.Column(db.Float)  # para redondo
    lado = db.Column(db.Float)  # para quadrado
    largura = db.Column(db.Float)  # para retângulo
    altura = db.Column(db.Float)  # para retângulo
    especifico = db.Column(db.Boolean, default=False)  # material específico ou comum
    
    def __repr__(self):
        return f'<Material {self.nome}>'
    
    @property
    def comprimento_em_metros(self):
        """Retorna o comprimento em metros, arredondado para cima"""
        if hasattr(self, 'comprimento') and self.comprimento:
            return math.ceil(self.comprimento / 1000)
        return 0
    
class Trabalho(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False, unique=True)
    categoria = db.Column(db.String(50))  # Serra, Torno CNC, Centro de Usinagem, etc.
    descricao = db.Column(db.Text)  # Descrição detalhada do tipo de trabalho
    
    def __repr__(self):
        return f'<Trabalho {self.nome}>'

class Maquina(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(20), unique=True)  # Código automático
    nome = db.Column(db.String(100), nullable=False)
    categoria_trabalho = db.Column(db.String(50))  # Categoria de trabalho
    imagem = db.Column(db.String(255))  # Caminho para a imagem da máquina
    data_cadastro = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Maquina {self.nome}>'
    
    @property
    def imagem_path(self):
        if self.imagem:
            return f'/uploads/{self.imagem}'
        return None

class Castanha(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(20), unique=True)  # Código automático
    diametro = db.Column(db.Float, nullable=True)  # Diâmetro da castanha
    comprimento = db.Column(db.Float, nullable=True)  # Comprimento da castanha
    castanha_livre = db.Column(db.Boolean, default=False)  # Se é castanha livre
    imagem = db.Column(db.String(255))  # Caminho para a imagem da castanha
    maquina_id = db.Column(db.Integer, db.ForeignKey('maquina.id'), nullable=True)
    local_armazenamento = db.Column(db.String(100))  # Bloco/posição
    data_cadastro = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamento
    maquina = relationship('Maquina', backref='castanhas', lazy=True)
    
    def __repr__(self):
        return f'<Castanha {self.codigo}>'
    
    @property
    def imagem_path(self):
        if self.imagem:
            return f'/uploads/{self.imagem}'
        return None

class GabaritoCentroUsinagem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(20), unique=True)  # Código automático
    nome = db.Column(db.String(100), nullable=False)
    funcao = db.Column(db.Text)  # Função do gabarito
    imagem = db.Column(db.String(255))  # Caminho para a imagem do gabarito
    local_armazenamento = db.Column(db.String(100))  # Estante/linha/posição
    data_cadastro = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<GabaritoCentroUsinagem {self.nome}>'
    
    @property
    def imagem_path(self):
        if self.imagem:
            return f'/uploads/{self.imagem}'
        return None

class GabaritoRosca(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(20), unique=True)  # Código automático
    tipo_rosca = db.Column(db.String(100), nullable=False)  # Qual rosca é
    imagem = db.Column(db.String(255))  # Caminho para a imagem do gabarito
    local_armazenamento = db.Column(db.String(100))  # Bloco/posição
    data_cadastro = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<GabaritoRosca {self.tipo_rosca}>'
    
    @property
    def imagem_path(self):
        if self.imagem:
            return f'/uploads/{self.imagem}'
        return None
    
class ItemTrabalho(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    trabalho_id = db.Column(db.Integer, db.ForeignKey('trabalho.id'), nullable=False)
    tempo_setup = db.Column(db.Integer)  # em segundos
    tempo_peca = db.Column(db.Integer)  # em segundos
    tempo_real = db.Column(db.Integer, nullable=True)  # tempo real registrado na produção
    trabalho = relationship('Trabalho', backref='itens_trabalho', lazy=True)
    
    def __repr__(self):
        return f'<ItemTrabalho {self.id}>'
    
    @property
    def tempo_setup_formatado(self):
        """Retorna o tempo de setup formatado como MM:SS"""
        if self.tempo_setup:
            minutos = self.tempo_setup // 60
            segundos = self.tempo_setup % 60
            return f"{minutos}:{segundos:02d}"
        return "0:00"
    
    @property
    def tempo_peca_formatado(self):
        """Retorna o tempo por peça formatado como MM:SS"""
        if self.tempo_peca:
            minutos = self.tempo_peca // 60
            segundos = self.tempo_peca % 60
            return f"{minutos}:{segundos:02d}"
        return "0:00"
    
    @property
    def tempo_real_formatado(self):
        """Retorna o tempo real formatado como MM:SS"""
        if self.tempo_real:
            minutos = self.tempo_real // 60
            segundos = self.tempo_real % 60
            return f"{minutos}:{segundos:02d}"
        return "0:00"
    
class ItemMaterial(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    material_id = db.Column(db.Integer, db.ForeignKey('material.id'), nullable=False)
    comprimento = db.Column(db.Float)
    quantidade = db.Column(db.Integer, default=1)
    material = relationship('Material', backref='item_materiais', lazy=True)
    
    def __repr__(self):
        return f'<ItemMaterial {self.id}>'
    
    @property
    def comprimento_em_metros(self):
        """Retorna o comprimento em metros, arredondado para cima"""
        if self.comprimento:
            return math.ceil(self.comprimento / 1000)
        return 0
    
class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False, unique=True)
    codigo_acb = db.Column(db.String(20), unique=True)
    desenho_tecnico = db.Column(db.String(255))
    imagem = db.Column(db.String(255))
    instrucoes_trabalho = db.Column(db.String(255))
    tempera = db.Column(db.Boolean, default=False)
    tipo_tempera = db.Column(db.String(50))
    retifica = db.Column(db.Boolean, default=False)
    pintura = db.Column(db.Boolean, default=False)
    tipo_pintura = db.Column(db.String(50))
    cor_pintura = db.Column(db.String(50))
    oleo_protetivo = db.Column(db.Boolean, default=False)
    zincagem = db.Column(db.Boolean, default=False)
    tipo_zincagem = db.Column(db.String(50))
    tipo_embalagem = db.Column(db.String(50))
    peso = db.Column(db.Float)
    materiais = relationship('ItemMaterial', backref='item', lazy=True, cascade="all, delete-orphan")
    trabalhos = relationship('ItemTrabalho', backref='item', lazy=True, cascade="all, delete-orphan")
    pedidos = relationship('Pedido', backref='item', lazy=True)
    arquivos_cnc = relationship('ArquivoCNC', backref='item', lazy=True, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<Item {self.nome}>'
    
    @property
    def desenho_tecnico_path(self):
        if self.desenho_tecnico:
            return f'/uploads/{self.desenho_tecnico}'
        return None
    
    @property
    def imagem_path(self):
        if self.imagem:
            return f'/uploads/{self.imagem}'
        return None
    
    @property
    def instrucoes_trabalho_path(self):
        if self.instrucoes_trabalho:
            return f'/uploads/{self.instrucoes_trabalho}'
        return None
    
    @property
    def tempo_total_producao(self):
        """Calcula o tempo total de produção para uma unidade do item"""
        tempo_total = 0
        for trabalho in self.trabalhos:
            # Usar tempo real se disponível, senão usar tempo estimado
            tempo_peca = trabalho.tempo_real or trabalho.tempo_peca
            tempo_total += tempo_peca + trabalho.tempo_setup
        
        # Formatar como MM:SS
        minutos = tempo_total // 60
        segundos = tempo_total % 60
        return f"{minutos}:{segundos:02d}"
    
class ArquivoCNC(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    nome_arquivo = db.Column(db.String(255), nullable=False)
    caminho_arquivo = db.Column(db.String(255), nullable=False)
    maquina = db.Column(db.String(100), nullable=False)
    criador_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    criador = relationship('Usuario', foreign_keys=[criador_id], lazy=True)
    
    def __repr__(self):
        return f'<ArquivoCNC {self.nome_arquivo}>'
    
class Pedido(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'), nullable=False)
    unidade_entrega_id = db.Column(db.Integer, db.ForeignKey('unidade_entrega.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=True)
    nome_item = db.Column(db.String(100), nullable=True)
    descricao = db.Column(db.Text)
    quantidade = db.Column(db.Integer, nullable=False)
    data_entrada = db.Column(db.Date, nullable=False, default=datetime.now().date())
    numero_pedido = db.Column(db.String(50))
    previsao_entrega = db.Column(db.Date)
    numero_oc = db.Column(db.String(20), nullable=True)
    numero_pedido_material = db.Column(db.String(50))
    data_entrega = db.Column(db.Date)
    material_comprado = db.Column(db.Boolean, default=False)  # Novo campo para status de compra
    ordens_servico = relationship('PedidoOrdemServico', backref='pedido', lazy=True, cascade="all, delete-orphan")

    # Campos de cancelamento
    cancelado = db.Column(db.Boolean, default=False)
    motivo_cancelamento = db.Column(db.Text, nullable=True)
    cancelado_por = db.Column(db.String(100), nullable=True)
    data_cancelamento = db.Column(db.DateTime, nullable=True)
    
    def __repr__(self):
        return f'<Pedido {self.id}>'
    
    @property
    def status(self):
        if self.cancelado:
            return "cancelado"
        if self.data_entrega:
            return "entregue"
        elif self.previsao_entrega and self.previsao_entrega < datetime.now().date():
            return "atrasado"
        else:
            return "pendente"
    
class OrdemServico(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(20), unique=True)
    data_criacao = db.Column(db.Date, default=datetime.now().date())
    status = db.Column(db.String(50), default='Entrada')
    posicao = db.Column(db.Integer, nullable=False, default=0)
    pedidos = db.relationship('PedidoOrdemServico', backref='ordem_servico', lazy=True, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<OrdemServico {self.numero}>'
    
    @property
    def tempo_total_producao(self):
        """Calcula o tempo total de produção para todos os itens da ordem de serviço"""
        tempo_total = 0
        for pedido_os in self.pedidos:
            pedido = pedido_os.pedido
            if pedido.item_id:
                item = Item.query.get(pedido.item_id)
                for trabalho in item.trabalhos:
                    # Usar tempo real se disponível, senão usar tempo estimado
                    tempo_peca = trabalho.tempo_real or trabalho.tempo_peca
                    tempo_total += (tempo_peca * pedido.quantidade) + trabalho.tempo_setup
        
        # Formatar como MM:SS
        minutos = tempo_total // 60
        segundos = tempo_total % 60
        return f"{minutos}:{segundos:02d}"
    
class PedidoOrdemServico(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey('pedido.id'), nullable=False)
    ordem_servico_id = db.Column(db.Integer, db.ForeignKey('ordem_servico.id'), nullable=False)
    
    def __repr__(self):
        return f'<PedidoOrdemServico {self.id}>'
    
class PedidoMaterial(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(20), unique=True)
    data_criacao = db.Column(db.Date, default=datetime.now().date())
    itens = db.relationship('ItemPedidoMaterial', backref='pedido_material', lazy=True, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<PedidoMaterial {self.numero}>'
    
class ItemPedidoMaterial(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pedido_material_id = db.Column(db.Integer, db.ForeignKey('pedido_material.id'), nullable=False)
    material_id = db.Column(db.Integer, db.ForeignKey('material.id'), nullable=False)
    comprimento = db.Column(db.Float)
    quantidade = db.Column(db.Integer)
    sufixo = db.Column(db.String(10), default='')
    material = relationship('Material', backref='pedidos_material', lazy=True)
    
    def __repr__(self):
        return f'<ItemPedidoMaterial {self.id}>'
    
    @property
    def comprimento_em_metros(self):
        """Retorna o comprimento em metros, arredondado para cima"""
        if self.comprimento:
            return math.ceil(self.comprimento / 1000)
        return 0

# Estoque models
class Estoque(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    material_id = db.Column(db.Integer, db.ForeignKey('material.id'), nullable=False)
    quantidade = db.Column(db.Integer, default=0)
    comprimento_total = db.Column(db.Float, default=0)
    material = relationship('Material', backref='estoque', lazy=True)
    movimentacoes = relationship('MovimentacaoEstoque', backref='estoque', lazy=True, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<Estoque {self.id}>'
    
    @property
    def comprimento_total_em_metros(self):
        """Retorna o comprimento total em metros, arredondado para cima"""
        if self.comprimento_total:
            return math.ceil(self.comprimento_total / 1000)
        return 0

class MovimentacaoEstoque(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    estoque_id = db.Column(db.Integer, db.ForeignKey('estoque.id'), nullable=False)
    tipo = db.Column(db.String(10), nullable=False)  # 'entrada' ou 'saida'
    quantidade = db.Column(db.Integer, nullable=False)
    comprimento = db.Column(db.Float)
    data = db.Column(db.Date, default=datetime.now().date())
    referencia = db.Column(db.String(50))  # Nota fiscal ou OS
    observacao = db.Column(db.Text)
    
    def __repr__(self):
        return f'<MovimentacaoEstoque {self.id}>'
    
    @property
    def comprimento_em_metros(self):
        """Retorna o comprimento em metros, arredondado para cima"""
        if self.comprimento:
            return math.ceil(self.comprimento / 1000)
        return 0

# Modelo para estoque de peças com campos adicionais para prateleira e posição
class EstoquePecas(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    quantidade = db.Column(db.Integer, default=0)
    data_entrada = db.Column(db.Date, default=datetime.now().date())
    prateleira = db.Column(db.String(10))  # Novo campo para armazenar a prateleira
    posicao = db.Column(db.String(10))     # Novo campo para armazenar a posição
    observacao = db.Column(db.Text)
    item = relationship('Item', backref='estoque_pecas', lazy=True)
    movimentacoes = relationship('MovimentacaoEstoquePecas', backref='estoque_pecas', lazy=True, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<EstoquePecas {self.id}>'

class MovimentacaoEstoquePecas(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    estoque_pecas_id = db.Column(db.Integer, db.ForeignKey('estoque_pecas.id'), nullable=False)
    tipo = db.Column(db.String(10), nullable=False)  # 'entrada' ou 'saida'
    quantidade = db.Column(db.Integer, nullable=False)
    data = db.Column(db.Date, default=datetime.now().date())
    referencia = db.Column(db.String(50))  # Pedido ou OS
    observacao = db.Column(db.Text)
    
    def __repr__(self):
        return f'<MovimentacaoEstoquePecas {self.id}>'

# Novo modelo para registro mensal de cartões finalizados
class RegistroMensal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ordem_servico_id = db.Column(db.Integer, db.ForeignKey('ordem_servico.id'), nullable=False)
    data_finalizacao = db.Column(db.Date, default=datetime.now().date())
    mes_referencia = db.Column(db.String(7))  # Formato: YYYY-MM
    ordem_servico = relationship('OrdemServico', backref='registro_mensal', lazy=True)
    
    def __repr__(self):
        return f'<RegistroMensal {self.id}>'

# Modelo para usuários e autenticação
class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False, unique=True)
    senha_hash = db.Column(db.String(255), nullable=False)
    nivel_acesso = db.Column(db.String(20), nullable=False, default='usuario')  # admin, usuario, kanban, estoque
    acesso_kanban = db.Column(db.Boolean, default=False)
    acesso_estoque = db.Column(db.Boolean, default=False)
    acesso_pedidos = db.Column(db.Boolean, default=False)
    acesso_cadastros = db.Column(db.Boolean, default=False)
    pode_finalizar_os = db.Column(db.Boolean, default=False)
    codigo_operador = db.Column(db.String(4), unique=True, nullable=True)  # Código de 4 dígitos para apontamentos
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    ultimo_acesso = db.Column(db.DateTime)
    # Relação removida para evitar conflito
    
    def __repr__(self):
        return f'<Usuario {self.nome}>'

# Modelo para backups do sistema
class Backup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome_arquivo = db.Column(db.String(255), nullable=False)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    tamanho = db.Column(db.Integer)  # Tamanho em bytes
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    descricao = db.Column(db.Text)
    automatico = db.Column(db.Boolean, default=False)
    
    usuario = relationship('Usuario', backref='backups')
    
    def __repr__(self):
        return f'<Backup {self.nome_arquivo}>'

# ====================
# FOLHAS DE PROCESSO
# ====================

# Folha base para todos os tipos de processo
class FolhaProcesso(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    tipo_processo = db.Column(db.String(30), nullable=False)  # 'torno_cnc', 'centro_usinagem', 'corte_serra', 'servicos_gerais'
    versao = db.Column(db.Integer, default=1)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    data_atualizacao = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    criado_por = db.Column(db.String(100))
    responsavel = db.Column(db.String(100))
    ativo = db.Column(db.Boolean, default=True)
    observacoes = db.Column(db.Text)
    
    # Relacionamento com Item
    item = relationship('Item', backref='folhas_processo')
    
    def __repr__(self):
        return f'<FolhaProcesso {self.item_id}-{self.tipo_processo} v{self.versao}>'

# Folha específica para Torno CNC
class FolhaTornoCNC(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    folha_processo_id = db.Column(db.Integer, db.ForeignKey('folha_processo.id'), nullable=False)
    
    # Campos específicos do Torno CNC
    codigo_item = db.Column(db.String(50))
    nome_peca = db.Column(db.String(200))
    quantidade = db.Column(db.Integer)
    maquina_torno = db.Column(db.String(100))  # Máquina/torno designado
    tipo_fixacao = db.Column(db.String(100))  # castanhas, luneta, flange
    tipo_material = db.Column(db.String(100))
    programa_cnc = db.Column(db.String(255))  # código ou caminho
    ferramentas_utilizadas = db.Column(db.Text)
    operacoes_previstas = db.Column(db.Text)  # desbaste, acabamento, furo, rosca, canal
    diametros_criticos = db.Column(db.Text)
    comprimentos_criticos = db.Column(db.Text)
    rpm_sugerido = db.Column(db.String(50))
    avanco_sugerido = db.Column(db.String(50))
    ponto_controle_dimensional = db.Column(db.Text)
    observacoes_tecnicas = db.Column(db.Text)
    responsavel_preenchimento = db.Column(db.String(100))
    
    # Relacionamento
    folha_processo = relationship('FolhaProcesso', backref='folha_torno_cnc')
    
    def __repr__(self):
        return f'<FolhaTornoCNC {self.id}>'

# Folha específica para Centro de Usinagem
class FolhaCentroUsinagem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    folha_processo_id = db.Column(db.Integer, db.ForeignKey('folha_processo.id'), nullable=False)
    
    # Campos específicos do Centro de Usinagem
    codigo_item = db.Column(db.String(50))
    nome_peca = db.Column(db.String(200))
    quantidade = db.Column(db.Integer)
    maquina_centro = db.Column(db.String(100))  # Máquina/centro designado
    sistema_fixacao = db.Column(db.String(100))  # morsa, dispositivo, vácuo
    z_zero_origem = db.Column(db.String(100))
    lista_ferramentas = db.Column(db.Text)  # com posição no magazine
    operacoes = db.Column(db.Text)  # faceamento, furação, rasgo, interpolação
    caminho_programa_cnc = db.Column(db.String(255))
    ponto_critico_colisao = db.Column(db.Text)
    limitacoes = db.Column(db.Text)
    tolerancias_especificas = db.Column(db.Text)
    observacoes_engenharia = db.Column(db.Text)
    responsavel_tecnico = db.Column(db.String(100))
    
    # Relacionamento
    folha_processo = relationship('FolhaProcesso', backref='folha_centro_usinagem')
    
    def __repr__(self):
        return f'<FolhaCentroUsinagem {self.id}>'

# Folha específica para Corte e Serra
class FolhaCorteSerraria(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    folha_processo_id = db.Column(db.Integer, db.ForeignKey('folha_processo.id'), nullable=False)
    
    # Campos específicos do Corte e Serra
    codigo_item = db.Column(db.String(50))
    nome_peca = db.Column(db.String(200))
    quantidade_cortar = db.Column(db.Integer)
    tipo_material = db.Column(db.String(100))
    tipo_serra = db.Column(db.String(100))  # manual, fita, disco, automática
    tamanho_bruto = db.Column(db.String(100))
    tamanho_final_corte = db.Column(db.String(100))
    perda_esperada = db.Column(db.String(50))
    tolerancia_permitida = db.Column(db.String(50))
    operador_responsavel = db.Column(db.String(100))
    data_corte = db.Column(db.Date)
    observacoes_corte = db.Column(db.Text)
    
    # Relacionamento
    folha_processo = relationship('FolhaProcesso', backref='folha_corte_serraria')
    
    def __repr__(self):
        return f'<FolhaCorteSerraria {self.id}>'

# Folha específica para Serviços Gerais
class FolhaServicosGerais(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    folha_processo_id = db.Column(db.Integer, db.ForeignKey('folha_processo.id'), nullable=False)
    
    # Campos específicos dos Serviços Gerais
    codigo_item = db.Column(db.String(50))
    nome_peca = db.Column(db.String(200))
    processo_rebarba = db.Column(db.Boolean, default=False)
    processo_lavagem = db.Column(db.Boolean, default=False)
    processo_inspecao = db.Column(db.Boolean, default=False)
    ferramentas_utilizadas = db.Column(db.Text)  # lima, esmeril, soprador
    padrao_qualidade = db.Column(db.Text)  # sem rebarbas, sem arranhões, limpo
    itens_inspecionar = db.Column(db.Text)
    resultado_inspecao = db.Column(db.String(20))  # Aprovado/Reprovado
    motivo_reprovacao = db.Column(db.Text)
    operador_responsavel = db.Column(db.String(100))
    observacoes_gerais = db.Column(db.Text)
    
    # Relacionamento
    folha_processo = relationship('FolhaProcesso', backref='folha_servicos_gerais')
    
    def __repr__(self):
        return f'<FolhaServicosGerais {self.id}>'

# Modelo para listas Kanban configuráveis
class KanbanLista(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False, unique=True)
    ordem = db.Column(db.Integer, nullable=False, default=0)
    tipo_servico = db.Column(db.String(50))  # Serra, Torno CNC, Centro de Usinagem, Manual, Acabamento, etc.
    ativa = db.Column(db.Boolean, default=True)
    cor = db.Column(db.String(7), default='#6c757d')  # cor hexadecimal para a lista
    tempo_medio_fila = db.Column(db.Integer, default=0)  # tempo médio em segundos
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    data_atualizacao = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<KanbanLista {self.nome}>'


# ====================
# SISTEMA DE APONTAMENTO
# ====================

# Modelo para apontamentos de produção
class ApontamentoProducao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ordem_servico_id = db.Column(db.Integer, db.ForeignKey('ordem_servico.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    trabalho_id = db.Column(db.Integer, db.ForeignKey('trabalho.id'), nullable=False)
    tipo_acao = db.Column(db.String(20), nullable=False)  # 'inicio_setup', 'fim_setup', 'inicio_producao', 'pausa', 'fim_producao'
    data_hora = db.Column(db.DateTime, default=datetime.utcnow)
    data_fim = db.Column(db.DateTime, nullable=True)  # Data/hora de finalização (para cálculo de duração)
    quantidade = db.Column(db.Integer, nullable=True)  # Quantidade de peças no momento do apontamento
    motivo_parada = db.Column(db.String(100), nullable=True)  # Motivo da pausa
    tempo_decorrido = db.Column(db.Integer, nullable=True)  # Tempo decorrido em segundos
    lista_kanban = db.Column(db.String(100), nullable=True)  # Nome da lista Kanban atual
    observacoes = db.Column(db.Text, nullable=True)
    operador_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)  # Operador que realizou o apontamento
    
    # Relacionamentos
    ordem_servico = relationship('OrdemServico', backref='apontamentos', lazy=True)
    usuario = relationship('Usuario', foreign_keys=[usuario_id], backref='apontamentos', lazy=True)
    operador = relationship('Usuario', foreign_keys=[operador_id], backref='apontamentos_como_operador', lazy=True)
    item = relationship('Item', backref='apontamentos', lazy=True)
    trabalho = relationship('Trabalho', backref='apontamentos', lazy=True)
    
    def __repr__(self):
        return f'<ApontamentoProducao OS:{self.ordem_servico_id} - {self.tipo_acao}>'
    
    @property
    def tempo_decorrido_formatado(self):
        """Retorna o tempo decorrido formatado como HH:MM:SS"""
        if self.tempo_decorrido:
            horas = self.tempo_decorrido // 3600
            minutos = (self.tempo_decorrido % 3600) // 60
            segundos = self.tempo_decorrido % 60
            return f"{horas:02d}:{minutos:02d}:{segundos:02d}"
        return "00:00:00"
    
    @property
    def data_hora_formatada(self):
        """Retorna a data/hora formatada"""
        if self.data_hora:
            return self.data_hora.strftime('%d/%m/%Y %H:%M:%S')
        return ""


# Modelo para cartões fantasma - permite uma OS em múltiplas listas
class CartaoFantasma(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ordem_servico_id = db.Column(db.Integer, db.ForeignKey('ordem_servico.id'), nullable=False)
    lista_kanban = db.Column(db.String(100), nullable=False)  # Nome da lista onde aparece
    posicao_fila = db.Column(db.Integer, default=1)  # Posição na fila (1=primeiro, 2=segundo, etc.)
    ativo = db.Column(db.Boolean, default=True)  # Se o cartão fantasma está ativo
    trabalho_id = db.Column(db.Integer, db.ForeignKey('trabalho.id'), nullable=True)  # Trabalho específico para este fantasma
    observacoes = db.Column(db.Text, nullable=True)  # Observações específicas
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    data_atualizacao = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    criado_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    
    # Relacionamentos
    ordem_servico = relationship('OrdemServico', backref='cartoes_fantasma', lazy=True)
    trabalho = relationship('Trabalho', lazy=True)
    criado_por = relationship('Usuario', foreign_keys=[criado_por_id], lazy=True)
    
    def __repr__(self):
        return f'<CartaoFantasma OS:{self.ordem_servico_id} Lista:{self.lista_kanban}>'
    
    @property
    def is_fantasma(self):
        """Sempre retorna True para identificar como cartão fantasma"""
        return True
    
    @property
    def lista_cor(self):
        """Retorna a cor da lista Kanban correspondente"""
        lista = KanbanLista.query.filter_by(nome=self.lista_kanban).first()
        return lista.cor if lista else '#6c757d'

# Modelo para controle do status atual de produção de cada OS
class StatusProducaoOS(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ordem_servico_id = db.Column(db.Integer, db.ForeignKey('ordem_servico.id'), unique=True, nullable=False)
    status_atual = db.Column(db.String(50), default='Aguardando')  # 'Aguardando', 'Setup', 'Produzindo', 'Pausado', 'Concluido'
    operador_atual_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    item_atual_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=True)
    trabalho_atual_id = db.Column(db.Integer, db.ForeignKey('trabalho.id'), nullable=True)
    inicio_acao = db.Column(db.DateTime, nullable=True)  # Início da ação atual
    quantidade_atual = db.Column(db.Integer, default=0)  # Última quantidade apontada
    previsao_termino = db.Column(db.DateTime, nullable=True)  # Previsão de término baseada na produção
    eficiencia_percentual = db.Column(db.Float, nullable=True)  # Eficiência em relação ao tempo estimado
    motivo_pausa = db.Column(db.String(100), nullable=True)  # Último motivo de pausa
    data_atualizacao = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    ordem_servico = relationship('OrdemServico', backref='status_producao', uselist=False, lazy=True)
    operador_atual = relationship('Usuario', foreign_keys=[operador_atual_id], lazy=True)
    item_atual = relationship('Item', foreign_keys=[item_atual_id], lazy=True)
    trabalho_atual = relationship('Trabalho', foreign_keys=[trabalho_atual_id], lazy=True)
    
    def __repr__(self):
        return f'<StatusProducaoOS OS:{self.ordem_servico_id} - {self.status_atual}>'
    
    @property
    def tempo_acao_atual(self):
        """Calcula o tempo decorrido da ação atual em segundos"""
        if self.inicio_acao:
            return int((datetime.utcnow() - self.inicio_acao).total_seconds())
        return 0
    
    @property
    def tempo_acao_atual_formatado(self):
        """Retorna o tempo da ação atual formatado como HH:MM:SS"""
        tempo = self.tempo_acao_atual
        horas = tempo // 3600
        minutos = (tempo % 3600) // 60
        segundos = tempo % 60
        return f"{horas:02d}:{minutos:02d}:{segundos:02d}"
    
    def calcular_previsao_termino(self):
        """Calcula a previsão de término baseada na produção atual"""
        if not self.item_trabalho_atual or not self.quantidade_atual:
            return None
            
        # Buscar o pedido relacionado à OS para obter quantidade total
        pedido_os = self.ordem_servico.pedidos[0] if self.ordem_servico.pedidos else None
        if not pedido_os:
            return None
            
        quantidade_total = pedido_os.pedido.quantidade
        quantidade_restante = quantidade_total - self.quantidade_atual
        
        if quantidade_restante <= 0:
            return datetime.utcnow()  # Já concluído
            
        # Calcular tempo médio por peça baseado na produção atual
        tempo_producao_atual = self.tempo_acao_atual
        if self.quantidade_atual > 0 and tempo_producao_atual > 0:
            tempo_medio_peca = tempo_producao_atual / self.quantidade_atual
            tempo_restante = quantidade_restante * tempo_medio_peca
            return datetime.utcnow() + datetime.timedelta(seconds=tempo_restante)
        
        # Fallback: usar tempo estimado do item
        tempo_estimado_restante = quantidade_restante * (self.item_trabalho_atual.tempo_peca or 0)
        return datetime.utcnow() + datetime.timedelta(seconds=tempo_estimado_restante)
