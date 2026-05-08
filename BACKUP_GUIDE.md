# 📦 Guia Completo de Backup e Restauração - ACB Usinagem CNC

## 🎯 Visão Geral

O sistema de backup da ACB Usinagem CNC é **COMPLETO** e garante que você possa restaurar **TUDO** em caso de problemas:

### ✅ O que é incluído no backup:

1. **Banco de Dados Completo**
   - Todas as tabelas (usuários, itens, pedidos, apontamentos, etc.)
   - Histórico completo de apontamentos
   - Configurações do sistema

2. **Arquivos de Upload Locais**
   - Imagens de itens
   - PDFs de desenhos técnicos
   - Programas CNC
   - Documentos anexados

3. **Arquivos do Supabase Storage** (se configurado)
   - Todos os arquivos armazenados na nuvem
   - Estrutura de pastas preservada
   - Metadados dos arquivos

4. **Script de Restauração Automática**
   - Restaura banco de dados
   - Restaura uploads locais
   - Restaura Supabase Storage
   - Instruções detalhadas

---

## 🚀 Como Criar um Backup

### Método 1: Interface Web (Recomendado)

1. Acesse **Administração → Gerenciar Backups**
2. Clique em **"Criar Backup"**
3. Adicione uma descrição (opcional): Ex: "Backup antes da atualização"
4. Clique em **"Criar"**
5. Aguarde a conclusão (pode levar alguns minutos dependendo do tamanho)

### Método 2: Automático (Agendado)

O sistema pode criar backups automáticos periodicamente (se configurado).

---

## 📥 Como Restaurar um Backup

### ⚠️ IMPORTANTE: Antes de Restaurar

**A restauração irá SUBSTITUIR todos os dados atuais!**

- Faça um backup atual antes de restaurar
- Certifique-se de que está restaurando o backup correto
- Todos os usuários devem sair do sistema

### Método 1: Restauração pela Interface (Mais Simples)

1. Acesse **Administração → Gerenciar Backups**
2. Localize o backup desejado na lista
3. Clique no botão **"Restaurar"** (ícone de seta circular)
4. Confirme a restauração
5. **Reinicie a aplicação** após a conclusão

### Método 2: Restauração Manual com Script (Mais Seguro)

1. **Baixe o backup:**
   - Clique no botão **"Download"** (ícone de download)
   - Salve o arquivo ZIP em um local seguro

2. **Extraia o ZIP:**
   ```bash
   unzip backup_20250508_143000.zip -d backup_restore
   cd backup_restore
   ```

3. **Configure as variáveis de ambiente** (se usar Supabase):
   ```bash
   # No arquivo .env
   SUPABASE_URL=https://seu-projeto.supabase.co
   SUPABASE_SERVICE_KEY=sua_service_key_aqui
   ```

4. **Execute o script de restauração:**
   ```bash
   python restore.py
   ```

5. **Reinicie a aplicação:**
   ```bash
   # Se estiver usando run.py
   python run.py
   ```

### Método 3: Upload de Backup Externo

Se você tem um arquivo de backup de outro servidor:

1. Acesse **Administração → Gerenciar Backups**
2. Clique em **"Restaurar ZIP"**
3. Selecione o arquivo ZIP do backup
4. Clique em **"Upload e Restaurar"**
5. Aguarde a conclusão
6. **Reinicie a aplicação**

---

## 🔧 Configuração do Supabase (Para Backup de Arquivos na Nuvem)

### Passo 1: Obter Credenciais

1. Acesse seu projeto no [Supabase](https://supabase.com)
2. Vá em **Settings → API**
3. Copie:
   - **Project URL** (SUPABASE_URL)
   - **Service Role Key** (SUPABASE_SERVICE_KEY)

### Passo 2: Configurar no .env

Adicione no arquivo `.env`:

```env
# Supabase Storage
SUPABASE_URL=https://xxxxxxxxxxxxx.supabase.co
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_BUCKET=uploads
```

### Passo 3: Criar Bucket no Supabase

1. No painel do Supabase, vá em **Storage**
2. Crie um bucket chamado `uploads`
3. Configure as permissões conforme necessário

---

## 📋 Estrutura do Arquivo de Backup

Quando você extrai um backup ZIP, encontrará:

```
backup_20250508_143000/
├── acb_usinagem.db          # Banco de dados SQLite
├── uploads/                  # Arquivos locais
│   ├── imagens/
│   ├── desenhos/
│   └── programas_cnc/
├── supabase_storage/         # Arquivos do Supabase
│   ├── file_mapping.json     # Mapeamento de arquivos
│   └── [arquivos...]
├── restore.py                # Script de restauração automática
└── README.md                 # Instruções de restauração
```

---

## 🔍 Verificação de Integridade

### Verificar se o Backup Contém Tudo:

1. **Baixe o backup**
2. **Extraia o ZIP**
3. **Verifique:**
   - ✅ Arquivo `.db` existe
   - ✅ Pasta `uploads/` existe e contém arquivos
   - ✅ Pasta `supabase_storage/` existe (se usar Supabase)
   - ✅ Arquivo `restore.py` existe
   - ✅ Arquivo `README.md` existe

### Testar Restauração em Ambiente de Teste:

**SEMPRE** teste a restauração em um ambiente separado antes de usar em produção!

---

## 🆘 Solução de Problemas

### Problema: "Erro ao criar backup"

**Soluções:**
1. Verifique se há espaço em disco suficiente
2. Verifique permissões de escrita na pasta `backups/`
3. Se usar Supabase, verifique as credenciais no `.env`

### Problema: "Backup não inclui imagens/PDFs"

**Soluções:**
1. Verifique se a pasta `uploads/` existe
2. Verifique se há arquivos na pasta `uploads/`
3. Se usar Supabase, verifique as credenciais
4. Verifique os logs do sistema durante a criação do backup

### Problema: "Erro ao restaurar backup"

**Soluções:**
1. Certifique-se de que o arquivo ZIP não está corrompido
2. Verifique se tem permissões de escrita
3. Use o script `restore.py` ao invés da interface web
4. Verifique os logs de erro para detalhes

### Problema: "Supabase Storage não está sendo incluído"

**Soluções:**
1. Verifique se `SUPABASE_URL` está configurado no `.env`
2. Verifique se `SUPABASE_SERVICE_KEY` está configurado
3. Verifique se o bucket existe no Supabase
4. Teste a conexão com o Supabase manualmente

---

## 📅 Boas Práticas de Backup

### Frequência Recomendada:

- **Diário**: Para sistemas em produção ativa
- **Semanal**: Para sistemas com baixa movimentação
- **Antes de atualizações**: SEMPRE faça backup antes de atualizar o sistema
- **Antes de mudanças importantes**: Backup antes de alterações no banco

### Armazenamento:

1. **Local**: Mantenha backups na pasta `backups/` (automático)
2. **Nuvem**: Exporte backups para Google Drive/OneDrive
3. **Externo**: Baixe backups importantes para HD externo
4. **Múltiplas cópias**: Regra 3-2-1
   - 3 cópias dos dados
   - 2 tipos de mídia diferentes
   - 1 cópia off-site (fora do local)

### Retenção:

- **Diários**: Manter últimos 7 dias
- **Semanais**: Manter últimas 4 semanas
- **Mensais**: Manter últimos 12 meses
- **Anuais**: Manter indefinidamente

---

## 🔐 Segurança

### Proteção dos Backups:

1. **Não compartilhe** arquivos de backup publicamente
2. **Criptografe** backups sensíveis antes de enviar para nuvem
3. **Proteja** as credenciais do Supabase (nunca commite no Git)
4. **Limite** acesso à pasta de backups apenas para administradores

### Dados Incluídos nos Backups:

⚠️ **ATENÇÃO**: Os backups contêm dados sensíveis:
- Senhas de usuários (hash)
- Informações de clientes
- Valores de itens
- Histórico de produção
- Arquivos confidenciais

**Trate os backups com o mesmo nível de segurança que o sistema em produção!**

---

## 📞 Suporte

Em caso de problemas com backup/restauração:

1. Verifique os logs do sistema
2. Consulte este guia
3. Teste em ambiente de desenvolvimento primeiro
4. Entre em contato com o suporte técnico

---

## ✅ Checklist de Backup Mensal

- [ ] Criar backup manual
- [ ] Baixar backup para local seguro
- [ ] Verificar integridade do backup (extrair e verificar arquivos)
- [ ] Testar restauração em ambiente de teste
- [ ] Exportar para nuvem (Google Drive/OneDrive)
- [ ] Remover backups antigos (manter apenas necessários)
- [ ] Documentar qualquer problema encontrado

---

**Última atualização:** 08/05/2026
**Versão do Sistema:** ACB Usinagem CNC v2.0
