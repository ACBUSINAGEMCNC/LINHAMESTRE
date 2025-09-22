# 🔧 Configuração do Supabase Storage para Restauração

Para que a restauração completa funcione com o **Supabase Storage**, você precisa configurar as credenciais corretas.

## 📋 Passo a Passo

### 1. **Obter Credenciais do Supabase**

1. Acesse: https://app.supabase.com/
2. Entre no seu projeto
3. Vá em **Settings** → **API**
4. Copie as seguintes informações:
   - **Project URL** (ex: `https://abc123.supabase.co`)
   - **Service Role Key** (chave que começa com `eyJ...`)

### 2. **Configurar Arquivo .env**

Crie ou edite o arquivo `.env` na raiz do projeto:

```env
# Supabase Configuration
SUPABASE_URL=https://seu-projeto-id.supabase.co
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# Opcional: outras variáveis
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### 3. **Verificar Configuração**

Execute no terminal:

```bash
python -c "
import os
from dotenv import load_dotenv
load_dotenv()
print('SUPABASE_URL:', '✓' if os.getenv('SUPABASE_URL') else '✗')
print('SUPABASE_SERVICE_KEY:', '✓' if os.getenv('SUPABASE_SERVICE_KEY') else '✗')
"
```

## 🔑 Tipos de Chaves

| Chave | Uso | Necessária para Restauração |
|-------|-----|----------------------------|
| **anon key** | Frontend público | ❌ Não |
| **service_role key** | Backend/Admin | ✅ **SIM** |

⚠️ **IMPORTANTE**: Use sempre a **service_role key** para restauração, pois ela tem permissões administrativas.

## 🛡️ Segurança

- ✅ **Nunca** commite o arquivo `.env` no Git
- ✅ Adicione `.env` no `.gitignore`
- ✅ Use variáveis de ambiente no servidor de produção
- ✅ A service_role key é sensível - trate como senha

## 🧪 Teste de Conectividade

Após configurar, teste a conectividade:

```python
import os
import requests
from dotenv import load_dotenv

load_dotenv()

url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_SERVICE_KEY')

if url and key:
    headers = {'Authorization': f'Bearer {key}', 'apikey': key}
    response = requests.get(f'{url}/storage/v1/bucket', headers=headers)
    print(f'Status: {response.status_code}')
    print('✅ Conectado!' if response.status_code == 200 else '❌ Erro de conexão')
else:
    print('❌ Credenciais não configuradas')
```

## 🚀 Próximos Passos

1. Configure as credenciais no `.env`
2. Reinicie a aplicação Flask
3. Teste novamente a restauração completa
4. Verifique os logs para confirmar o upload dos arquivos

## 🆘 Problemas Comuns

### Erro 401 (Unauthorized)
- Verifique se a `SUPABASE_SERVICE_KEY` está correta
- Confirme se copiou a chave completa (muito longa)

### Erro 404 (Not Found)
- Verifique se a `SUPABASE_URL` está correta
- Confirme se o projeto existe e está ativo

### Erro de Timeout
- Verifique sua conexão com a internet
- O Supabase pode estar temporariamente indisponível

---

💡 **Dica**: Após configurar, a restauração mostrará logs detalhados como:
```
✅ Conectividade com Supabase Storage confirmada
📤 Iniciando upload de 25 arquivos...
📤 Progresso: 25/25 arquivos (100.0%)
📊 Restauração do Storage concluída:
   ✅ Enviados: 25/25 arquivos (100.0%)
```
