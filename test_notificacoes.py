"""
Script de teste para notificações WhatsApp
"""
import os
from dotenv import load_dotenv

# Carregar .env
load_dotenv()

# Importar após carregar .env
from notificacoes.whatsapp import enviar_whatsapp
from notificacoes.configuracao import ConfiguracaoNotificacoes

def testar_configuracao():
    print("\n" + "="*60)
    print("TESTE DE CONFIGURAÇÃO - NOTIFICAÇÕES WHATSAPP")
    print("="*60)
    
    print(f"\n✓ NOTIFICACOES_ATIVO: {ConfiguracaoNotificacoes.ATIVO}")
    print(f"✓ WHATSAPP_ATIVO: {ConfiguracaoNotificacoes.WHATSAPP_ATIVO}")
    print(f"✓ URL: {ConfiguracaoNotificacoes.WHATSAPP_EVOLUTION_URL}")
    print(f"✓ API Key: {ConfiguracaoNotificacoes.WHATSAPP_EVOLUTION_APIKEY[:20]}...")
    print(f"✓ Instância: {ConfiguracaoNotificacoes.WHATSAPP_EVOLUTION_INSTANCE}")
    print(f"✓ Números: {ConfiguracaoNotificacoes.WHATSAPP_NUMEROS}")
    print(f"✓ Grupo: {ConfiguracaoNotificacoes.WHATSAPP_GRUPO_PRODUCAO or '(vazio)'}")
    
    if not ConfiguracaoNotificacoes.WHATSAPP_ATIVO:
        print("\n❌ WHATSAPP_ATIVO está desativado!")
        return False
    
    if not ConfiguracaoNotificacoes.WHATSAPP_NUMEROS:
        print("\n❌ Nenhum número configurado em WHATSAPP_NUMEROS!")
        return False
    
    return True


def testar_envio_simples():
    print("\n" + "="*60)
    print("TESTE 1: Envio simples para todos os números")
    print("="*60)
    
    mensagem = "🤖 Teste de notificação ACB Usinagem\n\nSistema de notificações ativo!"
    
    print(f"\nEnviando: {mensagem}")
    resultado = enviar_whatsapp(mensagem)
    
    print(f"\n✓ Resultado: {resultado}")
    return resultado.get('success', False)


def testar_envio_apontamento():
    print("\n" + "="*60)
    print("TESTE 2: Simulação de notificação de apontamento")
    print("="*60)
    
    mensagem = """🔧 *Apontamento Iniciado*

👤 Operador: João Silva
📦 Item: ACB-12345
⚙️ Serviço: Torno CNC
📋 OS: 2024-001
🏷️ Lista: Em Produção

⏰ Início: 29/05/2026 18:15"""
    
    print(f"\nEnviando: {mensagem}")
    resultado = enviar_whatsapp(mensagem)
    
    print(f"\n✓ Resultado: {resultado}")
    return resultado.get('success', False)


def testar_envio_alerta():
    print("\n" + "="*60)
    print("TESTE 3: Simulação de alerta de setup longo")
    print("="*60)
    
    mensagem = """⚠️ *ALERTA: Setup Longo*

👤 Operador: Maria Santos
📦 Item: ACB-67890
⚙️ Serviço: Centro de Usinagem
📋 OS: 2024-002
🏷️ Lista: Setup

⏱️ Tempo: Setup em andamento há 35 minutos

⚡ Ação necessária!"""
    
    print(f"\nEnviando: {mensagem}")
    resultado = enviar_whatsapp(mensagem)
    
    print(f"\n✓ Resultado: {resultado}")
    return resultado.get('success', False)


def main():
    print("\n" + "="*60)
    print("TESTE DE NOTIFICAÇÕES WHATSAPP - ACB USINAGEM")
    print("="*60)
    
    # Verificar configuração
    if not testar_configuracao():
        print("\n❌ Configuração inválida. Verifique o .env")
        return
    
    # Aguardar confirmação
    input("\n⏸️  Pressione ENTER para iniciar os testes...")
    
    # Executar testes
    teste1 = testar_envio_simples()
    input("\n⏸️  Pressione ENTER para próximo teste...")
    
    teste2 = testar_envio_apontamento()
    input("\n⏸️  Pressione ENTER para próximo teste...")
    
    teste3 = testar_envio_alerta()
    
    # Resumo
    print("\n" + "="*60)
    print("RESUMO DOS TESTES")
    print("="*60)
    print(f"Teste 1 (Simples): {'✅ SUCESSO' if teste1 else '❌ FALHA'}")
    print(f"Teste 2 (Apontamento): {'✅ SUCESSO' if teste2 else '❌ FALHA'}")
    print(f"Teste 3 (Alerta): {'✅ SUCESSO' if teste3 else '❌ FALHA'}")
    
    total = sum([teste1, teste2, teste3])
    print(f"\n📊 Total: {total}/3 testes bem-sucedidos")
    print("="*60 + "\n")


if __name__ == '__main__':
    main()
