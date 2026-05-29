import time
import requests
from .configuracao import ConfiguracaoNotificacoes
from .logs import log_envio_whatsapp


def enviar_whatsapp(mensagem, destino=None, *, timeout=None, retries=None, enviar_para_todos=False):
    """
    Envia mensagem WhatsApp via Evolution API.
    
    Args:
        mensagem: Texto da mensagem
        destino: Número ou grupo específico. Se None, usa WHATSAPP_NUMEROS
        timeout: Timeout da requisição
        retries: Número de tentativas
        enviar_para_todos: Se True, envia para todos os números configurados
    """
    timeout = timeout or ConfiguracaoNotificacoes.WHATSAPP_TIMEOUT
    retries = ConfiguracaoNotificacoes.WHATSAPP_RETRIES if retries is None else retries

    if not ConfiguracaoNotificacoes.WHATSAPP_ATIVO:
        log_envio_whatsapp('sistema', mensagem, status='ignorado_whatsapp_desativado')
        return {'success': False, 'skipped': True, 'reason': 'WHATSAPP_ATIVO desativado'}

    if not all([
        ConfiguracaoNotificacoes.WHATSAPP_EVOLUTION_URL,
        ConfiguracaoNotificacoes.WHATSAPP_EVOLUTION_APIKEY,
        ConfiguracaoNotificacoes.WHATSAPP_EVOLUTION_INSTANCE,
    ]):
        log_envio_whatsapp('sistema', mensagem, status='ignorado_config_incompleta')
        return {'success': False, 'skipped': True, 'reason': 'configuracao incompleta'}
    
    # Determinar destinos
    if enviar_para_todos or destino is None:
        destinos = ConfiguracaoNotificacoes.WHATSAPP_NUMEROS or []
        if ConfiguracaoNotificacoes.WHATSAPP_GRUPO_PRODUCAO:
            destinos.append(ConfiguracaoNotificacoes.WHATSAPP_GRUPO_PRODUCAO)
        if not destinos:
            log_envio_whatsapp('sistema', mensagem, status='ignorado_sem_destinos')
            return {'success': False, 'skipped': True, 'reason': 'nenhum destino configurado'}
    else:
        destinos = [destino]
    
    # Enviar para todos os destinos
    resultados = []
    for dest in destinos:
        resultado = _enviar_whatsapp_unico(mensagem, dest, timeout, retries)
        resultados.append({'destino': dest, 'resultado': resultado})
    
    # Retornar sucesso se pelo menos um envio foi bem-sucedido
    sucesso = any(r['resultado'].get('success') for r in resultados)
    return {'success': sucesso, 'resultados': resultados}


def _enviar_whatsapp_unico(mensagem, destino, timeout, retries):
    """Envia mensagem para um único destino."""
    if not destino:
        return {'success': False, 'skipped': True, 'reason': 'destino vazio'}

    url = (
        f'{ConfiguracaoNotificacoes.WHATSAPP_EVOLUTION_URL}'
        f'/message/sendText/{ConfiguracaoNotificacoes.WHATSAPP_EVOLUTION_INSTANCE}'
    )
    headers = {
        'apikey': ConfiguracaoNotificacoes.WHATSAPP_EVOLUTION_APIKEY,
        'Content-Type': 'application/json',
    }
    payload = {
        'number': destino,
        'text': mensagem,
    }

    ultima_excecao = None
    for tentativa in range(1, retries + 2):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=timeout)
            if 200 <= response.status_code < 300:
                log_envio_whatsapp(destino, mensagem, status='enviado')
                return {'success': True, 'status_code': response.status_code, 'response': response.text}
            ultima_excecao = RuntimeError(f'HTTP {response.status_code}: {response.text[:300]}')
            log_envio_whatsapp(destino, mensagem, status=f'falha_tentativa_{tentativa}', erro=ultima_excecao)
        except Exception as exc:
            ultima_excecao = exc
            log_envio_whatsapp(destino, mensagem, status=f'erro_tentativa_{tentativa}', erro=exc)
        if tentativa <= retries:
            time.sleep(min(2 * tentativa, 5))

    return {'success': False, 'error': str(ultima_excecao)}
