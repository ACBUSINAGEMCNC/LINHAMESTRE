# Configuração do Supabase para Backup

## Problema Identificado
O erro "Wrong password" no backup do Supabase indica que as credenciais de conexão não estão configuradas corretamente ou estão desatualizadas.

## Solução

### 1. Criar arquivo .env
Copie o arquivo `.env.example` para `.env`:
```bash
copy .env.example .env
```

### 2. Configurar DATABASE_URL no .env
Edite o arquivo `.env` e configure a `DATABASE_URL` com suas credenciais corretas do Supabase:

```env
# Substitua os valores entre [] pelas suas credenciais reais do Supabase
DATABASE_URL=postgresql://postgres.[SEU-PROJETO]:[SUA-SENHA-ESCAPADA]@aws-0-sa-east-1.pooler.supabase.com:6543/postgres
```

### 3. Como obter as credenciais corretas

1. **Acesse o painel do Supabase**: https://supabase.com/dashboard
2. **Selecione seu projeto**
3. **Vá em Settings > Database**
4. **Na seção "Connection string"**, copie a string de conexão
5. **IMPORTANTE**: Use a versão "Connection pooling" (porta 6543) para melhor performance

### 4. Escapar caracteres especiais na senha
Se sua senha contém caracteres especiais, você precisa escapá-los:
- `@` → `%40`
- `#` → `%23`
- `%` → `%25`
- `&` → `%26`
- `+` → `%2B`

Exemplo:
- Senha original: `MinhaSenh@123#`
- Senha escapada: `MinhaSenh%40123%23`

### 5. Exemplo completo de .env
```env
SECRET_KEY=sua_chave_secreta_aqui
DATABASE_URL=postgresql://postgres.abcdefghijklmnop:MinhaSenh%40123%23@aws-0-sa-east-1.pooler.supabase.com:6543/postgres
FLASK_ENV=production
```

### 6. Verificar a configuração
Após configurar o `.env`, reinicie a aplicação e tente criar um backup novamente. O sistema agora fornece mensagens de erro mais detalhadas para ajudar no diagnóstico.

## Melhorias Implementadas

1. **Validação de credenciais**: O sistema agora verifica se as credenciais estão configuradas antes de tentar conectar
2. **Mensagens de erro melhoradas**: Erros específicos para problemas de autenticação e conexão
3. **Detecção automática do Supabase**: O sistema detecta quando está usando Supabase e fornece instruções específicas
4. **Tratamento de erros robusto**: Diferentes tipos de erro recebem tratamento específico

## Notas Importantes

- O arquivo `.env` está no `.gitignore` por segurança - nunca faça commit das suas credenciais
- Use sempre a string de conexão com pooling (porta 6543) para melhor performance
- Mantenha suas credenciais atualizadas se você resetar a senha do banco no Supabase
