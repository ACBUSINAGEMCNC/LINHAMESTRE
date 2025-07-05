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
    
    def __repr__(self):
        return f'<Trabalho {self.nome}>'
    
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
