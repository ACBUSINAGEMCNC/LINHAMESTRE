"""
Teste direto de notificação de apontamento
"""
from dotenv import load_dotenv
load_dotenv()

from notificacoes.eventos import registrar_evento_apontamento
from notificacoes.configuracao import ConfiguracaoNotificacoes

print("\n" + "="*60)
print("TESTE DE NOTIFICAÇÃO DE APONTAMENTO")
print("="*60)

print(f"\n✓ NOTIFICACOES_ATIVO: {ConfiguracaoNotificacoes.ATIVO}")
print(f"✓ WHATSAPP_ATIVO: {ConfiguracaoNotificacoes.WHATSAPP_ATIVO}")
print(f"✓ FILA_ATIVA: {ConfiguracaoNotificacoes.FILA_ATIVA}")
print(f"✓ SCHEDULER_ATIVO: {ConfiguracaoNotificacoes.SCHEDULER_ATIVO}")

if not ConfiguracaoNotificacoes.ATIVO:
    print("\n❌ NOTIFICACOES_ATIVO está desativado!")
    print("Configure NOTIFICACOES_ATIVO=1 no .env")
    exit(1)

if not ConfiguracaoNotificacoes.WHATSAPP_ATIVO:
    print("\n❌ WHATSAPP_ATIVO está desativado!")
    print("Configure WHATSAPP_ATIVO=1 no .env")
    exit(1)

# Criar objetos mock para teste
class MockUsuario:
    nome = "João Silva"
    codigo_operador = "OP001"

class MockItem:
    codigo_acb = "ACB-12345"
    nome = "Peça Teste"

class MockTrabalho:
    nome = "Torno CNC"

class MockOrdem:
    numero = "OS-2024-001"
    status = "Em Produção"

print("\n" + "="*60)
print("TESTE 1: Início de Setup")
print("="*60)

resultado = registrar_evento_apontamento(
    'inicio_setup',
    usuario=MockUsuario(),
    item=MockItem(),
    trabalho=MockTrabalho(),
    ordem=MockOrdem(),
    lista="Setup",
    quantidade=None,
    motivo=None
)

print(f"Resultado: {resultado}")

print("\n" + "="*60)
print("TESTE 2: Início de Produção")
print("="*60)

resultado = registrar_evento_apontamento(
    'inicio_producao',
    usuario=MockUsuario(),
    item=MockItem(),
    trabalho=MockTrabalho(),
    ordem=MockOrdem(),
    lista="Em Produção",
    quantidade=10,
    motivo=None
)

print(f"Resultado: {resultado}")

print("\n" + "="*60)
print("TESTE 3: Pausa")
print("="*60)

resultado = registrar_evento_apontamento(
    'pausa',
    usuario=MockUsuario(),
    item=MockItem(),
    trabalho=MockTrabalho(),
    ordem=MockOrdem(),
    lista="Pausado",
    quantidade=5,
    motivo="Troca de ferramenta"
)

print(f"Resultado: {resultado}")

print("\n" + "="*60)
print("TESTE 4: Stop")
print("="*60)

resultado = registrar_evento_apontamento(
    'stop',
    usuario=MockUsuario(),
    item=MockItem(),
    trabalho=MockTrabalho(),
    ordem=MockOrdem(),
    lista="Pausado",
    quantidade=8,
    motivo="Fim do turno"
)

print(f"Resultado: {resultado}")

print("\n" + "="*60)
print("✅ Testes concluídos!")
print("="*60)
print("\nVerifique se as mensagens chegaram nos WhatsApp:")
print("- 5545999434981")
print("- 5545991369209")
print("="*60 + "\n")
