import logging
from datetime import datetime

logger = logging.getLogger('notificacoes')


def log_evento(tipo, payload=None, status='registrado', erro=None):
    payload = payload or {}
    extra = {
        'tipo': tipo,
        'status': status,
        'erro': str(erro) if erro else None,
        'timestamp': datetime.now().isoformat(timespec='seconds'),
    }
    if erro:
        logger.warning('[NOTIFICACOES] %s | %s | erro=%s | payload=%s', tipo, status, erro, payload)
    else:
        logger.info('[NOTIFICACOES] %s | %s | payload=%s', tipo, status, payload)
    return extra


def log_envio_whatsapp(destino, mensagem, status='enviado', erro=None):
    resumo = (mensagem or '')[:120].replace('\n', ' ')
    if erro:
        logger.warning('[WHATSAPP] destino=%s | %s | erro=%s | msg=%s', destino, status, erro, resumo)
    else:
        logger.info('[WHATSAPP] destino=%s | %s | msg=%s', destino, status, resumo)
