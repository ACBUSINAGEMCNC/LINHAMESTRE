from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from datetime import datetime, timezone, timedelta
import math

# Timezone helpers (preferir America/Sao_Paulo)
try:
    from zoneinfo import ZoneInfo  # Python 3.9+
    LOCAL_TZ = ZoneInfo("America/Sao_Paulo")
except Exception:
    # Fallback to fixed -03:00 (Brazil currently no DST)
    LOCAL_TZ = timezone(timedelta(hours=-3))

def local_now_naive():
    """Retorna agora no fuso America/Sao_Paulo como datetime naive.
    Isso evita diferença de horário quando o servidor está em UTC.
    """
    return datetime.now(LOCAL_TZ).replace(tzinfo=None)

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
            # Usar conversor unificado de URL (local ou Supabase)
            from utils import get_file_url
            return get_file_url(self.imagem)
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
            from utils import get_file_url
            return get_file_url(self.imagem)
        return None

class GabaritoCentroUsinagem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(20), unique=True)  # Código automático
    nome = db.Column(db.String(100), nullable=False)
    categoria_trabalho = db.Column(db.String(50))  # Categoria/Tipo de serviço (ex: Centro de Usinagem)
    funcao = db.Column(db.Text)  # Função do gabarito
    imagem = db.Column(db.String(255))  # Caminho para a imagem do gabarito
    local_armazenamento = db.Column(db.String(100))  # Estante/linha/posição
    data_cadastro = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<GabaritoCentroUsinagem {self.nome}>'
    
    @property
    def imagem_path(self):
        if self.imagem:
            from utils import get_file_url
            return get_file_url(self.imagem)
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
            from utils import get_file_url
            return get_file_url(self.imagem)
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


class Fornecedor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False, unique=True)

    def __repr__(self):
        return f'<Fornecedor {self.nome}>'


class CotacaoPedidoMaterial(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pedido_material_id = db.Column(db.Integer, db.ForeignKey('pedido_material.id'), nullable=False)
    fornecedor_id = db.Column(db.Integer, db.ForeignKey('fornecedor.id'), nullable=False)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    observacoes = db.Column(db.Text)

    pedido_material = relationship('PedidoMaterial', backref='cotacoes_fornecedores', lazy=True)
    fornecedor = relationship('Fornecedor', backref='cotacoes', lazy=True)
    itens = db.relationship('CotacaoItemPedidoMaterial', backref='cotacao', lazy=True, cascade="all, delete-orphan")

    __table_args__ = (
        db.UniqueConstraint('pedido_material_id', 'fornecedor_id', name='uq_cotacao_pedido_fornecedor'),
    )

    def __repr__(self):
        return f'<CotacaoPedidoMaterial {self.id}>'


class CotacaoItemPedidoMaterial(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cotacao_id = db.Column(db.Integer, db.ForeignKey('cotacao_pedido_material.id'), nullable=False)
    item_pedido_material_id = db.Column(db.Integer, db.ForeignKey('item_pedido_material.id'), nullable=False)

    preco_total = db.Column(db.Float)
    preco_por_kg = db.Column(db.Float)
    preco_unitario = db.Column(db.Float)
    ipi_percent = db.Column(db.Float)
    prazo_entrega_dias = db.Column(db.Integer)
    prazo_pagamento_dias = db.Column(db.Integer)

    # Rateio (opcional): quanto deste item será comprado deste fornecedor
    quantidade_escolhida = db.Column(db.Integer)
    metros_escolhidos = db.Column(db.Float)

    item_pedido_material = relationship('ItemPedidoMaterial', backref='cotacoes_itens', lazy=True)

    __table_args__ = (
        db.UniqueConstraint('cotacao_id', 'item_pedido_material_id', name='uq_cotacao_item'),
    )

    def __repr__(self):
        return f'<CotacaoItemPedidoMaterial {self.id}>'


class CotacaoPedidoMontagem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pedido_montagem_id = db.Column(db.Integer, db.ForeignKey('pedido_montagem.id'), nullable=False)
    fornecedor_id = db.Column(db.Integer, db.ForeignKey('fornecedor.id'), nullable=False)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    observacoes = db.Column(db.Text)

    pedido_montagem = relationship('PedidoMontagem', backref='cotacoes_fornecedores', lazy=True)
    fornecedor = relationship('Fornecedor', backref='cotacoes_montagem', lazy=True)
    itens = db.relationship('CotacaoItemPedidoMontagem', backref='cotacao', lazy=True, cascade="all, delete-orphan")

    __table_args__ = (
        db.UniqueConstraint('pedido_montagem_id', 'fornecedor_id', name='uq_cotacao_pedido_montagem_fornecedor'),
    )

    def __repr__(self):
        return f'<CotacaoPedidoMontagem {self.id}>'


class CotacaoItemPedidoMontagem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cotacao_id = db.Column(db.Integer, db.ForeignKey('cotacao_pedido_montagem.id'), nullable=False)
    item_pedido_montagem_id = db.Column(db.Integer, db.ForeignKey('item_pedido_montagem.id'), nullable=False)

    preco_total = db.Column(db.Float)
    preco_por_kg = db.Column(db.Float)
    preco_unitario = db.Column(db.Float)
    ipi_percent = db.Column(db.Float)
    prazo_entrega_dias = db.Column(db.Integer)
    prazo_pagamento_dias = db.Column(db.Integer)

    # Rateio (opcional): quanto deste item será comprado deste fornecedor
    quantidade_escolhida = db.Column(db.Integer)
    metros_escolhidos = db.Column(db.Float)

    item_pedido_montagem = relationship('ItemPedidoMontagem', backref='cotacoes_itens', lazy=True)

    __table_args__ = (
        db.UniqueConstraint('cotacao_id', 'item_pedido_montagem_id', name='uq_cotacao_item_pedido_montagem'),
    )

    def __repr__(self):
        return f'<CotacaoItemPedidoMontagem {self.id}>'
    
class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False, unique=True)
    codigo_acb = db.Column(db.String(20), unique=True)
    criado_via_importacao_estoque = db.Column(db.Boolean, default=False)
    desenho_tecnico = db.Column(db.String(255))
    desenho_aprovado_em = db.Column(db.DateTime, nullable=True)
    desenho_aprovado_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    desenho_aprovado_por_nome = db.Column(db.String(120), nullable=True)
    imagem = db.Column(db.String(255))
    instrucoes_trabalho = db.Column(db.String(255))
    tipo_item = db.Column(db.String(20), default='producao')
    categoria_montagem = db.Column(db.String(50))
    tamanho_peca = db.Column(db.String(100))
    tempera = db.Column(db.Boolean, default=False)
    tipo_tempera = db.Column(db.String(50))
    retifica = db.Column(db.Boolean, default=False)
    pintura = db.Column(db.Boolean, default=False)
    tipo_pintura = db.Column(db.String(50))
    cor_pintura = db.Column(db.String(50))
    oleo_protetivo = db.Column(db.Boolean, default=False)
    zincagem = db.Column(db.Boolean, default=False)
    tipo_zincagem = db.Column(db.String(50))
    tipo_bruto = db.Column(db.String(50))
    tipo_embalagem = db.Column(db.String(50))
    peso = db.Column(db.Float)
    # Novo campo para identificar se é item composto
    eh_composto = db.Column(db.Boolean, default=False)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    materiais = relationship('ItemMaterial', backref='item', lazy=True, cascade="all, delete-orphan")
    trabalhos = relationship('ItemTrabalho', backref='item', lazy=True, cascade="all, delete-orphan")
    pedidos = relationship('Pedido', backref='item', lazy=True)
    arquivos_cnc = relationship('ArquivoCNC', backref='item', lazy=True, cascade="all, delete-orphan")
    # Relacionamentos para item composto
    componentes = relationship('ItemComposto', foreign_keys='ItemComposto.item_pai_id', backref='item_pai', lazy=True, cascade="all, delete-orphan")
    usado_em = relationship('ItemComposto', foreign_keys='ItemComposto.item_componente_id', backref='item_componente', lazy=True)
    
    def __repr__(self):
        return f'<Item {self.nome}>'
    
    @property
    def desenho_tecnico_path(self):
        if self.desenho_tecnico:
            from utils import get_file_url
            return get_file_url(self.desenho_tecnico)
        return None
    
    @property
    def imagem_path(self):
        if self.imagem:
            from utils import get_file_url
            return get_file_url(self.imagem)
        return None
    
    @property
    def instrucoes_trabalho_path(self):
        if self.instrucoes_trabalho:
            from utils import get_file_url
            return get_file_url(self.instrucoes_trabalho)
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
    
    @property
    def total_componentes(self):
        """Retorna o número total de componentes se for item composto"""
        if self.eh_composto:
            return len(self.componentes)
        return 0
    
    @property
    def peso_total_composto(self):
        """Calcula o peso total considerando todos os componentes"""
        if not self.eh_composto:
            return self.peso or 0
        
        peso_total = 0
        for componente in self.componentes:
            peso_componente = componente.item_componente.peso or 0
            peso_total += peso_componente * componente.quantidade
        
        return peso_total

# Modelo para relacionamento entre item pai e seus componentes
class ItemComposto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_pai_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    item_componente_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False, default=1)
    comprimento_mm = db.Column(db.Float, nullable=True)
    observacoes = db.Column(db.Text)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<ItemComposto {self.item_pai_id}->{self.item_componente_id}>'
    
    @property
    def peso_total_componente(self):
        """Calcula o peso total deste componente considerando a quantidade"""
        peso_unitario = self.item_componente.peso or 0
        return peso_unitario * self.quantidade

    @property
    def comprimento_total_m(self):
        """Retorna o comprimento total (m) baseado no comprimento_mm e na quantidade."""
        if not self.comprimento_mm:
            return 0
        return (self.comprimento_mm * (self.quantidade or 0)) / 1000.0
    
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
    nome_item = db.Column(db.String(255), nullable=True)
    descricao = db.Column(db.Text)
    quantidade = db.Column(db.Integer, nullable=False)
    data_entrada = db.Column(db.Date, nullable=False, default=datetime.now().date())
    numero_pedido = db.Column(db.String(50))  # Número interno do sistema (PED-00077 ou AUTO-*)
    numero_pedido_cliente = db.Column(db.String(100))  # Número do pedido do cliente
    previsao_entrega = db.Column(db.Date)
    numero_oc = db.Column(db.String(20), nullable=True)
    numero_pedido_material = db.Column(db.String(50))
    numero_pedido_montagem = db.Column(db.String(50))
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
    aprovado_em = db.Column(db.DateTime, nullable=True)
    aprovado_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    aprovado_por_nome = db.Column(db.String(120), nullable=True)
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
    quantidade_snapshot = db.Column(db.Integer, nullable=True)
    
    def __repr__(self):
        return f'<PedidoOrdemServico {self.id}>'
    
    @property
    def quantidade_alterada(self):
        """Verifica se a quantidade do pedido foi alterada desde a vinculação"""
        if self.quantidade_snapshot is None:
            return False
        
        # Para pedidos virtuais de componentes (AUTO-*), verificar se o pedido original mudou
        if self.pedido and self.pedido.numero_pedido and self.pedido.numero_pedido.startswith('AUTO-'):
            # Extrair ID do pedido original do formato AUTO-OS-XXX-{pedido_original_id}
            import re
            match = re.search(r'-(\d+)$', self.pedido.numero_pedido)
            if match:
                pedido_original_id = int(match.group(1))
                pedido_original = Pedido.query.get(pedido_original_id)
                if pedido_original and pedido_original.item_id:
                    # Buscar o item composto
                    item_composto = pedido_original.item
                    if item_composto and item_composto.eh_composto:
                        # Verificar se a quantidade do pedido original mudou
                        # A quantidade esperada do componente seria: quantidade_original * fator_componente
                        # Se a quantidade atual do pedido virtual não bate, houve mudança
                        for comp_rel in item_composto.componentes:
                            if comp_rel.item_componente_id == self.pedido.item_id:
                                quantidade_esperada = comp_rel.quantidade * pedido_original.quantidade
                                if self.pedido.quantidade != quantidade_esperada:
                                    return True
        
        # Verificação padrão para pedidos normais
        return self.pedido.quantidade != self.quantidade_snapshot
    
class PedidoMaterial(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(20), unique=True)
    data_criacao = db.Column(db.Date, default=datetime.now().date())
    aprovado_em = db.Column(db.DateTime, nullable=True)
    aprovado_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    aprovado_por_nome = db.Column(db.String(120), nullable=True)
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

class PedidoMontagem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(20), unique=True)
    data_criacao = db.Column(db.Date, default=datetime.now().date())
    aprovado_em = db.Column(db.DateTime, nullable=True)
    aprovado_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    aprovado_por_nome = db.Column(db.String(120), nullable=True)
    itens = db.relationship('ItemPedidoMontagem', backref='pedido_montagem', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<PedidoMontagem {self.numero}>'

class ItemPedidoMontagem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pedido_montagem_id = db.Column(db.Integer, db.ForeignKey('pedido_montagem.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False, default=1)
    item = relationship('Item', backref='pedidos_montagem', lazy=True)

    def __repr__(self):
        return f'<ItemPedidoMontagem {self.id}>'

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
    estante = db.Column(db.Integer)        # 1..8
    secao = db.Column(db.Integer)          # 1..4
    linha = db.Column(db.Integer)          # 1..2
    coluna = db.Column(db.Integer)         # 1..10
    linha_fim = db.Column(db.Integer)      # 1..2 (opcional, para ocupar múltiplos slots atravessando linhas na mesma seção)
    coluna_fim = db.Column(db.Integer)     # 1..10 (opcional, para ocupar múltiplos slots na mesma linha)
    slots_json = db.Column(db.Text)        # JSON com slots arbitrários selecionados no mapa
    permitir_compartilhado = db.Column(db.Boolean, default=False)  # permite múltiplos itens no mesmo slot
    slot_temp_id = db.Column(db.Integer, db.ForeignKey('estoque_pecas_slot_temp.id'), nullable=True)
    observacao = db.Column(db.Text)
    item = relationship('Item', backref='estoque_pecas', lazy=True)
    slot_temp = relationship('EstoquePecasSlotTemp', backref='itens', lazy=True)
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


class EstoquePecasSlotTemp(db.Model):
    __tablename__ = 'estoque_pecas_slot_temp'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), nullable=True)
    estante = db.Column(db.Integer, nullable=False)       # 1..8
    secao = db.Column(db.Integer, nullable=False)         # 1..4
    linha = db.Column(db.Integer, nullable=False)         # 1..2
    coluna = db.Column(db.Integer, nullable=False)        # 1..6
    linha_fim = db.Column(db.Integer, nullable=True)      # 1..2 (opcional)
    coluna_fim = db.Column(db.Integer, nullable=True)     # 1..6 (opcional)
    slots_json = db.Column(db.Text, nullable=True)        # JSON com slots arbitrários do temporário
    permitir_compartilhado = db.Column(db.Boolean, default=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<EstoquePecasSlotTemp {self.id}>'

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
    storage_url = db.Column(db.String(500))  # URL do backup no Supabase Storage
    storage_type = db.Column(db.String(50), default='local')  # 'local' ou 'supabase'
    
    usuario = relationship('Usuario', backref='backups')
    
    def __repr__(self):
        return f'<Backup {self.nome_arquivo}>'


class AuditLog(db.Model):
    __tablename__ = 'audit_log'

    id = db.Column(db.Integer, primary_key=True)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    usuario_nome = db.Column(db.String(100), nullable=True)

    acao = db.Column(db.String(20), nullable=False)
    entidade_tipo = db.Column(db.String(100), nullable=False)
    entidade_id = db.Column(db.String(64), nullable=True)
    mudancas_json = db.Column(db.Text, nullable=True)

    endpoint = db.Column(db.String(200), nullable=True)
    metodo = db.Column(db.String(10), nullable=True)
    ip = db.Column(db.String(64), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)

    usuario = relationship('Usuario', backref='audit_logs', lazy=True)

    def __repr__(self):
        return f'<AuditLog {self.id} {self.acao} {self.entidade_tipo}:{self.entidade_id}>'

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
    data_atualizacao = db.Column(db.DateTime, default=local_now_naive, onupdate=local_now_naive)
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
    data_hora = db.Column(db.DateTime, default=local_now_naive)
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
    data_atualizacao = db.Column(db.DateTime, default=local_now_naive, onupdate=local_now_naive)
    
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
            return int((local_now_naive() - self.inicio_acao).total_seconds())
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

# ================= NOVOS MODELOS PARA FOLHAS DE PROCESSO REFORMULADAS =================

class NovaFolhaProcesso(db.Model):
    """Modelo principal para as novas folhas de processo personalizadas por categoria"""
    __tablename__ = 'nova_folha_processo'
    
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=True)  # Atrelar folha ao item específico
    maquina_id = db.Column(db.Integer, db.ForeignKey('maquina.id'), nullable=False)
    categoria_maquina = db.Column(db.String(50), nullable=False)  # serra, torno_cnc, centro_usinagem, manual, acabamento, outros
    titulo_servico = db.Column(db.String(200), nullable=False)  # Tipo de serviço informado pelo usuário
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    data_atualizacao = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    usuario_criacao_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    ativo = db.Column(db.Boolean, default=True)
    
    # Relacionamentos
    item = db.relationship('Item', backref='novas_folhas_processo_item')
    maquina = db.relationship('Maquina', backref='novas_folhas_processo')
    usuario_criacao = db.relationship('Usuario', backref='novas_folhas_criadas')
    
    @property
    def titulo_completo(self):
        """Retorna o título completo: Nome da Máquina + Tipo de Serviço"""
        return f"{self.maquina.nome} - {self.titulo_servico}"
    
    def __repr__(self):
        return f'<NovaFolhaProcesso {self.titulo_completo}>'

class FolhaProcessoSerra(db.Model):
    """Folha de processo específica para categoria Serra"""
    __tablename__ = 'folha_processo_serra'
    
    id = db.Column(db.Integer, primary_key=True)
    nova_folha_id = db.Column(db.Integer, db.ForeignKey('nova_folha_processo.id'), nullable=False)
    
    # Informações sobre o corte
    tamanho_corte = db.Column(db.String(100))
    diametro_material = db.Column(db.Float)
    tipo_material = db.Column(db.String(100))
    como_cortar = db.Column(db.Text)
    observacoes = db.Column(db.Text)
    
    # Imagens
    imagem_peca_bruta = db.Column(db.String(255))  # Path para imagem da peça bruta
    
    # Relacionamento
    nova_folha = db.relationship('NovaFolhaProcesso', backref=db.backref('folha_serra', uselist=False))

class FolhaProcessoTornoCNC(db.Model):
    """Folha de processo específica para categoria Torno CNC"""
    __tablename__ = 'folha_processo_torno_cnc'
    
    id = db.Column(db.Integer, primary_key=True)
    nova_folha_id = db.Column(db.Integer, db.ForeignKey('nova_folha_processo.id'), nullable=False)
    
    # Castanha utilizada
    castanha_id = db.Column(db.Integer, db.ForeignKey('castanha.id'))
    
    # Gabarito de rosca (opcional)
    gabarito_rosca_id = db.Column(db.Integer, db.ForeignKey('gabarito_rosca.id'))
    
    # Programa CNC
    programa_cnc = db.Column(db.Text)  # Conteúdo do programa
    nome_programa = db.Column(db.String(200))
    
    # Bucha guia e encosto
    jogo_bucha_guia = db.Column(db.String(200))
    local_armazenagem_bucha = db.Column(db.String(200))
    encosto = db.Column(db.String(200))
    local_armazenagem_encosto = db.Column(db.String(200))

    # BT e AR
    bt = db.Column(db.String(50))
    ar = db.Column(db.String(50))
    
    # Observações
    observacoes = db.Column(db.Text)
    
    # Imagens
    imagem_torre_montada = db.Column(db.String(255))
    imagem_peca_fixa = db.Column(db.String(255))
    imagem_bucha_guia = db.Column(db.String(255))
    imagem_encosto = db.Column(db.String(255))
    
    # Relacionamentos
    nova_folha = db.relationship('NovaFolhaProcesso', backref=db.backref('folha_torno_cnc', uselist=False))
    castanha = db.relationship('Castanha', backref='folhas_processo_torno')
    gabarito_rosca = db.relationship('GabaritoRosca', backref='folhas_processo_torno')

class FolhaProcessoCentroUsinagem(db.Model):
    """Folha de processo específica para categoria Centro de Usinagem"""
    __tablename__ = 'folha_processo_centro_usinagem'
    
    id = db.Column(db.Integer, primary_key=True)
    nova_folha_id = db.Column(db.Integer, db.ForeignKey('nova_folha_processo.id'), nullable=False)
    
    # Gabarito (opcional)
    gabarito_centro_id = db.Column(db.Integer, db.ForeignKey('gabarito_centro_usinagem.id'))
    
    # Zeramento
    como_zeramento = db.Column(db.Text)
    
    # Observações
    observacoes = db.Column(db.Text)
    
    # Imagens
    imagem_gabarito_montado = db.Column(db.String(255))
    imagem_zeramento = db.Column(db.String(255))
    
    # Relacionamentos
    nova_folha = db.relationship('NovaFolhaProcesso', backref=db.backref('folha_centro_usinagem', uselist=False))
    gabarito_centro = db.relationship('GabaritoCentroUsinagem', backref='folhas_processo_centro')

class FolhaProcessoManualAcabamento(db.Model):
    """Folha de processo específica para categorias Manual, Acabamento e Outros"""
    __tablename__ = 'folha_processo_manual_acabamento'
    
    id = db.Column(db.Integer, primary_key=True)
    nova_folha_id = db.Column(db.Integer, db.ForeignKey('nova_folha_processo.id'), nullable=False)
    
    # Têmpera
    possui_tempera = db.Column(db.Boolean, default=False)
    tipo_tempera = db.Column(db.String(20))  # 'forno' ou 'inducao'
    
    # Têmpera por Indução
    programa_inducao = db.Column(db.String(200))
    indutor_utilizado = db.Column(db.String(200))
    local_armazenagem_gabarito_inducao = db.Column(db.String(200))
    dureza_inducao = db.Column(db.String(100))
    
    # Têmpera por Forno
    dureza_forno = db.Column(db.String(100))
    
    # Observações
    observacoes = db.Column(db.Text)
    
    # Imagens gerais
    imagem_gabarito_inducao = db.Column(db.String(255))
    imagem_indutor = db.Column(db.String(255))
    imagem_montagem_inducao = db.Column(db.String(255))
    imagem_dureza_inducao = db.Column(db.String(255))
    imagem_peca_temperada_forno = db.Column(db.String(255))
    imagem_dureza_forno = db.Column(db.String(255))
    
    # Relacionamento
    nova_folha = db.relationship('NovaFolhaProcesso', backref=db.backref('folha_manual_acabamento', uselist=False))

# Tabelas auxiliares para múltiplas entradas

class FerramentaTorno(db.Model):
    """Ferramentas utilizadas no Torno CNC"""
    __tablename__ = 'ferramenta_torno'
    
    id = db.Column(db.Integer, primary_key=True)
    folha_torno_id = db.Column(db.Integer, db.ForeignKey('folha_processo_torno_cnc.id'), nullable=False)
    posicao = db.Column(db.String(10))  # Ex: T01, T02, etc
    descricao = db.Column(db.String(200))  # Ex: TNMEG R01 9
    configuracao = db.Column(db.String(200))
    suporte_bt = db.Column(db.String(100))
    comprimento_fora = db.Column(db.String(50))
    imagem = db.Column(db.String(255))
    
    # Relacionamento
    folha_torno = db.relationship('FolhaProcessoTornoCNC', backref='ferramentas')

class FerramentaCentro(db.Model):
    """Ferramentas utilizadas no Centro de Usinagem"""
    __tablename__ = 'ferramenta_centro'
    
    id = db.Column(db.Integer, primary_key=True)
    folha_centro_id = db.Column(db.Integer, db.ForeignKey('folha_processo_centro_usinagem.id'), nullable=False)
    posicao = db.Column(db.String(10))  # Ex: T01, T02, etc
    descricao = db.Column(db.String(200))
    configuracao = db.Column(db.String(200))
    suporte_bt = db.Column(db.String(100))
    comprimento_fora = db.Column(db.String(50))
    imagem = db.Column(db.String(255))
    
    # Relacionamento
    folha_centro = db.relationship('FolhaProcessoCentroUsinagem', backref='ferramentas')

class MedidaCritica(db.Model):
    """Medidas críticas para Torno e Centro de Usinagem"""
    __tablename__ = 'medida_critica'
    
    id = db.Column(db.Integer, primary_key=True)
    folha_tipo = db.Column(db.String(20))  # 'torno' ou 'centro'
    folha_id = db.Column(db.Integer)  # ID da folha específica
    descricao = db.Column(db.String(200))  # Ex: "Diâmetro externo"
    valor = db.Column(db.String(100))  # Ex: "50mm"
    tolerancia = db.Column(db.String(100))  # Ex: "+0.1/-0.05"

class ImagemPecaProcesso(db.Model):
    """Imagens de peças com observações para Torno e Centro"""
    __tablename__ = 'imagem_peca_processo'
    
    id = db.Column(db.Integer, primary_key=True)
    folha_tipo = db.Column(db.String(20))  # 'torno' ou 'centro'
    folha_id = db.Column(db.Integer)  # ID da folha específica
    imagem = db.Column(db.String(255))
    observacao = db.Column(db.Text)  # Ex: "Cuidar acabamento nessa área"

class ImagemProcessoGeral(db.Model):
    """Imagens gerais para Manual/Acabamento/Outros"""
    __tablename__ = 'imagem_processo_geral'
    
    id = db.Column(db.Integer, primary_key=True)
    folha_manual_id = db.Column(db.Integer, db.ForeignKey('folha_processo_manual_acabamento.id'), nullable=False)
    imagem = db.Column(db.String(255))
    observacao = db.Column(db.Text)
    
    # Relacionamento
    folha_manual = db.relationship('FolhaProcessoManualAcabamento', backref='imagens_processo')
