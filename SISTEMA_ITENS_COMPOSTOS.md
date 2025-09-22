# Sistema de Itens Compostos - ACB Usinagem CNC

## 📋 Visão Geral

O Sistema de Itens Compostos permite criar itens que são formados por outros itens já cadastrados no sistema. Quando um pedido de item composto é processado, o sistema automaticamente desmembra o item em seus componentes individuais, gerando ordens de serviço e pedidos de material separados para cada componente.

## 🎯 Funcionalidades Principais

### 1. **Cadastro de Item Composto**
- Interface dedicada para criação de itens compostos
- Seleção de componentes a partir de itens simples existentes
- Definição de quantidade de cada componente
- Suporte a tratamentos e acabamentos
- Upload de arquivos (desenho técnico, imagem, instruções)

### 2. **Desmembramento Automático**
- **Geração de OS**: Quando um pedido de item composto gera uma OS, o sistema cria automaticamente uma OS separada para cada componente
- **Pedido de Material**: Ao gerar pedido de material, o sistema calcula automaticamente os materiais necessários de todos os componentes

### 3. **Interface Intuitiva**
- Listagem diferenciada entre itens simples e compostos
- Visualização detalhada dos componentes
- Edição completa dos itens compostos
- Busca e filtros específicos

## 🗄️ Estrutura do Banco de Dados

### Tabelas Modificadas

#### `item`
```sql
-- Novas colunas adicionadas
eh_composto BOOLEAN DEFAULT 0        -- Identifica se é item composto
data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP
```

#### Nova Tabela: `item_composto`
```sql
CREATE TABLE item_composto (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_pai_id INTEGER NOT NULL,           -- ID do item composto
    item_componente_id INTEGER NOT NULL,    -- ID do item componente
    quantidade INTEGER NOT NULL DEFAULT 1,  -- Quantidade do componente
    observacoes TEXT,                       -- Observações específicas
    data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (item_pai_id) REFERENCES item (id),
    FOREIGN KEY (item_componente_id) REFERENCES item (id),
    UNIQUE(item_pai_id, item_componente_id)
);
```

## 🔧 Implementação Técnica

### Modelos (models.py)

#### Classe Item - Propriedades Adicionadas
```python
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
```

#### Classe ItemComposto
```python
class ItemComposto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_pai_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    item_componente_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False, default=1)
    observacoes = db.Column(db.Text)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
```

### Rotas (routes/itens.py)

#### Novas Rotas Implementadas
- `GET/POST /itens/composto/novo` - Cadastro de novo item composto
- `GET/POST /itens/composto/editar/<id>` - Edição de item composto
- `GET /itens/composto/visualizar/<id>` - Visualização de item composto
- `GET /api/itens/nao-compostos` - API para listar itens não compostos

### Lógica de Desmembramento (routes/pedidos.py)

#### Geração de OS para Itens Compostos
```python
def gerar_os_item_composto(pedidos_grupo, item_composto):
    """Gera múltiplas OS desmembrando um item composto"""
    os_geradas = []
    quantidade_total_composto = sum(pedido.quantidade for pedido in pedidos_grupo)
    
    # Para cada componente do item composto
    for componente_rel in item_composto.componentes:
        item_componente = componente_rel.item_componente
        quantidade_componente = componente_rel.quantidade * quantidade_total_composto
        
        # Criar OS individual para o componente
        # Criar pedido virtual para o componente
        # Associar pedido virtual à OS
```

#### Geração de Pedido de Material
- Desmembra automaticamente itens compostos
- Calcula materiais necessários de todos os componentes
- Agrupa materiais por tipo para otimizar compras

## 🎨 Interface do Usuário

### Listagem de Itens
- **Badge "Composto"**: Identifica visualmente itens compostos
- **Badge "Simples"**: Identifica itens normais
- **Coluna "Tipo"**: Diferenciação clara entre tipos
- **Ações Específicas**: Botões de edição/visualização específicos para cada tipo

### Cadastro/Edição de Item Composto
- **Painel Lateral**: Lista de itens disponíveis para usar como componentes
- **Busca Inteligente**: Filtro em tempo real dos itens disponíveis
- **Modal de Componente**: Interface para definir quantidade e observações
- **Validações**: Impede adicionar o próprio item como componente
- **Cálculos Automáticos**: Peso total, quantidade de materiais, etc.

### Visualização de Item Composto
- **Resumo Executivo**: Informações principais em destaque
- **Lista de Componentes**: Detalhamento completo de cada componente
- **Cálculos Totais**: Peso total, materiais totais, trabalhos totais
- **Links Rápidos**: Acesso direto aos detalhes de cada componente

## 📊 Fluxo de Trabalho

### 1. Cadastro de Item Composto
```
1. Usuário acessa "Itens" → "Item Composto"
2. Preenche informações básicas
3. Seleciona componentes da lista lateral
4. Define quantidade de cada componente
5. Adiciona observações se necessário
6. Salva o item composto
```

### 2. Pedido de Item Composto
```
1. Cliente faz pedido de item composto (ex: 10 unidades)
2. Pedido é cadastrado normalmente no sistema
3. Ao gerar OS, sistema detecta que é item composto
4. Sistema desmembra automaticamente:
   - Componente A: 20 unidades (2 por item composto × 10)
   - Componente B: 10 unidades (1 por item composto × 10)
   - Componente C: 30 unidades (3 por item composto × 10)
5. Cria OS separada para cada componente
6. Atualiza pedido original com referência às OS geradas
```

### 3. Pedido de Material
```
1. Usuário seleciona pedidos (incluindo compostos)
2. Sistema analisa cada pedido:
   - Item simples: calcula materiais diretamente
   - Item composto: desmembra e calcula materiais dos componentes
3. Agrupa todos os materiais necessários
4. Gera pedido de material consolidado
```

## 🔍 Exemplos Práticos

### Exemplo 1: Conjunto de Engrenagens
```
Item Composto: "Conjunto Engrenagem Redutora"
├── Engrenagem Principal (1 unidade)
├── Engrenagem Secundária (2 unidades)  
├── Eixo Principal (1 unidade)
└── Parafusos M8 (8 unidades)

Pedido: 5 conjuntos
Resultado: 
├── OS001: 5 Engrenagens Principais
├── OS002: 10 Engrenagens Secundárias
├── OS003: 5 Eixos Principais
└── OS004: 40 Parafusos M8
```

### Exemplo 2: Kit de Montagem
```
Item Composto: "Kit Montagem Bomba"
├── Corpo da Bomba (1 unidade)
├── Rotor (1 unidade)
├── Tampa (2 unidades)
└── Vedações (4 unidades)

Materiais Calculados Automaticamente:
├── Aço 1045 Ø50mm: 200mm (corpo) + 100mm (rotor) = 300mm
├── Aço 1020 Ø30mm: 400mm (tampas: 2×200mm)
└── Borracha NBR: 40mm (vedações: 4×10mm)
```

## 🚀 Benefícios do Sistema

### Para a Produção
- **Organização**: Cada componente tem sua própria OS
- **Rastreabilidade**: Controle individual de cada peça
- **Planejamento**: Visão clara do que produzir
- **Kanban**: Cada componente segue seu fluxo no Kanban

### Para Compras
- **Automação**: Cálculo automático de materiais
- **Precisão**: Quantidades exatas considerando todos os componentes
- **Otimização**: Agrupamento inteligente de materiais

### Para Gestão
- **Controle**: Visão completa dos itens compostos
- **Flexibilidade**: Fácil modificação dos componentes
- **Relatórios**: Análise detalhada de custos e tempos

## 🔧 Instalação e Configuração

### 1. Executar Migração do Banco
```bash
python migrate_item_composto.py
```

### 2. Verificar Importações
Certifique-se de que as rotas estão importando o novo modelo:
```python
from models import ItemComposto
```

### 3. Registrar Blueprint
O blueprint `itens` já está registrado e inclui as novas rotas.

## 🎯 Próximos Passos

### Melhorias Futuras
1. **Níveis Múltiplos**: Suporte a itens compostos dentro de outros itens compostos
2. **Templates**: Criação de templates de itens compostos
3. **Relatórios**: Relatórios específicos para análise de itens compostos
4. **API REST**: Endpoints para integração com outros sistemas
5. **Importação/Exportação**: Funcionalidades para backup e migração

### Integrações Planejadas
1. **Sistema de Custos**: Cálculo automático de custos dos itens compostos
2. **Estoque**: Controle de estoque considerando componentes
3. **Produção**: Integração com sistema de apontamento de produção

## 📞 Suporte

Para dúvidas ou problemas com o sistema de itens compostos:
1. Verifique se a migração foi executada corretamente
2. Confirme se todos os templates foram criados
3. Teste o fluxo completo: cadastro → pedido → OS → material

---

**Desenvolvido para ACB Usinagem CNC**  
*Sistema de Gestão Industrial Completo*
