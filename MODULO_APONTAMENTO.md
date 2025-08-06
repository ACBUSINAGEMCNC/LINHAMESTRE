# Módulo de Apontamento de Produção - Especificação Técnica

## Visão Geral
Criação de um sistema de apontamento de produção integrado aos cartões (Ordens de Serviço) do Kanban, permitindo controle em tempo real da produção com rastreamento de operadores, tempos e quantidades.

## 1. Funcionalidades Principais

### 1.1 Códigos de Operador
- **Objetivo**: Identificação única de cada operador
- **Formato**: Código numérico de 4 dígitos (ex: 0001, 0002, 1234)
- **Implementação**: 
  - Adicionar campo `codigo_operador` na tabela `Usuario`
  - Geração automática sequencial ou manual pelo admin
  - Validação de unicidade

### 1.2 Botões de Apontamento no Cartão (Miniatura)
Botões visíveis na frente do cartão sem necessidade de abrir:

#### A) **Início Setup**
- Solicita: Código do operador + Tipo de trabalho
- Inicia cronômetro para setup
- Status: "Setup em andamento"

#### B) **Fim Setup** 
- Solicita: Código do operador + Confirmação do tipo de trabalho
- Para cronômetro de setup
- Calcula tempo real vs. tempo estimado

#### C) **Início Produção**
- Solicita: Código do operador + Tipo de trabalho + Quantidade inicial
- Inicia cronômetro de produção
- Status: "Produção em andamento"

#### D) **Pausa**
- Solicita: 
  - Código do operador
  - Quantidade atual de peças
  - Motivo da parada (dropdown):
    - Parada para café
    - Sem desenho
    - Sem ferramenta
    - Troca de ferramenta
    - Sem material
    - Falha na operação
    - Manutenção não programada
    - Banheiro
    - Outros (campo livre)
- Para cronômetro temporariamente
- Status: "Pausado - [Motivo]"

#### E) **Fim Produção**
- Solicita: Código do operador + Quantidade final
- Para cronômetro definitivamente
- Calcula eficiência vs. tempo estimado
- Status: "Concluído"

### 1.3 Sistema de Logs Detalhado
Dentro do cartão aberto, aba "Apontamentos" com histórico completo:

**Campos do Log:**
- Data/Hora da ação
- Nome do operador (buscar por código)
- Ação realizada (Início Setup, Fim Setup, etc.)
- Tipo de trabalho
- Quantidade (quando aplicável)
- Motivo (para pausas)
- Lista Kanban atual
- Tempo decorrido na ação

### 1.4 Previsão e Acompanhamento
- **Previsão de Término**: Baseada nos tempos cadastrados no item
- **Ajuste Dinâmico**: Recalcula conforme produção real
- **Status de Eficiência**: 
  - ✅ Dentro do prazo
  - ⚠️ Atrasado
  - 🚀 Adiantado

### 1.5 Dashboard Home
Novo painel no menu principal mostrando:
- **Cards Ativos**: Lista Kanban + Cartão em produção
- **Status Atual**: Rodando/Pausado/Setup
- **Operador Atual**: Nome do último operador
- **Última Quantidade**: Última quantidade apontada
- **Previsão**: Tempo estimado para conclusão

## 2. Alterações no Banco de Dados

### 2.1 Tabela `Usuario` - Adicionar Campos
```sql
ALTER TABLE usuario ADD COLUMN codigo_operador VARCHAR(4) UNIQUE;
```

### 2.2 Nova Tabela `ApontamentoProducao`
```sql
CREATE TABLE apontamento_producao (
    id INTEGER PRIMARY KEY,
    ordem_servico_id INTEGER NOT NULL,
    usuario_id INTEGER NOT NULL,
    item_trabalho_id INTEGER NOT NULL,
    tipo_acao VARCHAR(20) NOT NULL, -- 'inicio_setup', 'fim_setup', 'inicio_producao', 'pausa', 'fim_producao'
    data_hora DATETIME DEFAULT CURRENT_TIMESTAMP,
    quantidade INTEGER,
    motivo_parada VARCHAR(100),
    tempo_decorrido INTEGER, -- em segundos
    lista_kanban VARCHAR(100),
    observacoes TEXT,
    FOREIGN KEY (ordem_servico_id) REFERENCES ordem_servico (id),
    FOREIGN KEY (usuario_id) REFERENCES usuario (id),
    FOREIGN KEY (item_trabalho_id) REFERENCES item_trabalho (id)
);
```

### 2.3 Nova Tabela `StatusProducaoOS`
```sql
CREATE TABLE status_producao_os (
    id INTEGER PRIMARY KEY,
    ordem_servico_id INTEGER UNIQUE NOT NULL,
    status_atual VARCHAR(50) DEFAULT 'Aguardando', -- 'Aguardando', 'Setup', 'Produzindo', 'Pausado', 'Concluido'
    operador_atual_id INTEGER,
    item_trabalho_atual_id INTEGER,
    inicio_acao DATETIME,
    quantidade_atual INTEGER DEFAULT 0,
    previsao_termino DATETIME,
    eficiencia_percentual DECIMAL(5,2),
    FOREIGN KEY (ordem_servico_id) REFERENCES ordem_servico (id),
    FOREIGN KEY (operador_atual_id) REFERENCES usuario (id),
    FOREIGN KEY (item_trabalho_atual_id) REFERENCES item_trabalho (id)
);
```

## 3. Alterações na Interface

### 3.1 Cartão Kanban (Miniatura)
- **Área de Botões**: Nova seção com 5 botões compactos
- **Indicador de Status**: Badge colorido com status atual
- **Info Rápida**: Operador atual e última quantidade

### 3.2 Modal de Apontamento
- **Campos Dinâmicos**: Baseados no tipo de ação
- **Validação**: Código de operador obrigatório
- **Dropdown**: Tipos de trabalho do item
- **Seleção**: Motivos de parada pré-definidos

### 3.3 Cartão Aberto - Aba Apontamentos
- **Timeline**: Histórico cronológico de ações
- **Filtros**: Por operador, tipo de ação, data
- **Métricas**: Tempo total, eficiência, pausas

### 3.4 Dashboard Home
- **Grid de Cards Ativos**: 3-4 colunas responsivas
- **Indicadores Visuais**: Cores para status
- **Atualização**: Tempo real ou refresh automático

## 4. Lógica de Negócio

### 4.1 Validações
- Operador deve existir e estar ativo
- Não permitir ações duplicadas (ex: dois "início setup")
- Sequência lógica: Setup → Produção → Fim
- Quantidade não pode ser negativa

### 4.2 Cálculos Automáticos
- **Tempo Real**: Diferença entre início e fim de cada ação
- **Eficiência**: (Tempo estimado / Tempo real) × 100
- **Previsão**: Baseada na velocidade atual de produção

### 4.3 Regras de Status
- **Aguardando**: Cartão criado, sem apontamentos
- **Setup**: Entre início e fim de setup
- **Produzindo**: Entre início e fim de produção
- **Pausado**: Após botão pausa, antes de retomar
- **Concluído**: Após fim de produção

## 5. Implementação Sugerida

### Fase 1: Estrutura Base
1. Criar modelos de banco de dados
2. Migração para adicionar campos
3. Interface básica de códigos de operador

### Fase 2: Apontamentos
1. Botões nos cartões
2. Modais de apontamento
3. Sistema de logs

### Fase 3: Dashboard e Relatórios
1. Dashboard home
2. Métricas e eficiência
3. Relatórios de produção

### Fase 4: Otimizações
1. Atualização em tempo real
2. Notificações
3. Relatórios avançados

## 6. Considerações Técnicas

### 6.1 Performance
- Índices nas tabelas de apontamento
- Cache para dashboard
- Paginação nos logs

### 6.2 Segurança
- Validação de códigos de operador
- Log de alterações
- Controle de acesso por nível

### 6.3 Usabilidade
- Interface intuitiva e rápida
- Feedback visual imediato
- Responsividade mobile

---

**Próximos Passos:**
1. Revisar e aprovar especificação
2. Criar branch para desenvolvimento
3. Implementar fase 1
4. Testes e validação com usuários
5. Deploy incremental por fases
