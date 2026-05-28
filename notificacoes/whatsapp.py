import time
import requests
from .configuracao import ConfiguracaoNotificacoes
from .logs import log_envio_whatsapp


def enviar_whatsapp(mensagem, destino=None, *, timeout=None, retries=None):
    destino = destino or ConfiguracaoNotificacoes.WHATSAPP_GRUPO_PRODUCAO
    timeout = timeout or ConfiguracaoNotificacoes.WHATSAPP_TIMEOUT
    retries = ConfiguracaoNotificacoes.WHATSAPP_RETRIES if retries is None else retries

    if not ConfiguracaoNotificacoes.WHATSAPP_ATIVO:
        log_envio_whatsapp(destino, mensagem, status='ignorado_whatsapp_desativado')
        return {'success': False, 'skipped': True, 'reason': 'WHATSAPP_ATIVO desativado'}

    if not all([
        ConfiguracaoNotificacoes.WHATSAPP_EVOLUTION_URL,
        ConfiguracaoNotificacoes.WHATSAPP_EVOLUTION_APIKEY,
        ConfiguracaoNotificacoes.WHATSAPP_EVOLUTION_INSTANCE,
        destino,
    ]):
        log_envio_whatsapp(destino, mensagem, status='ignorado_config_incompleta')
        return {'success': False, 'skipped': True, 'reason': 'configuracao incompleta'}

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
