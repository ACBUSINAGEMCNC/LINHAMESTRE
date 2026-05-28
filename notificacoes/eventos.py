from datetime import datetime
from .configuracao import ConfiguracaoNotificacoes
from .logs import log_evento
from .templates import mensagem_evento
from .whatsapp import enviar_whatsapp

EVENTOS_WHATSAPP = {
    'producao_iniciada',
    'producao_finalizada',
    'pausa_iniciada',
    'pausa_finalizada',
    'setup_iniciado',
    'setup_finalizado',
    'kanban_movido',
    'atraso_detectado',
    'maquina_parada',
    'servico_parado',
}

TIPO_ACAO_EVENTO = {
    'inicio_setup': 'setup_iniciado',
    'fim_setup': 'setup_finalizado',
    'inicio_producao': 'producao_iniciada',
    'fim_producao': 'producao_finalizada',
    'pausa': 'pausa_iniciada',
    'stop': 'pausa_finalizada',
}


def registrar_evento(tipo, **dados):
    evento = {
        'tipo': tipo,
        'dados': dados,
        'criado_em': datetime.now().isoformat(timespec='seconds'),
    }
    log_evento(tipo, dados, status='registrado')

    if not ConfiguracaoNotificacoes.ATIVO:
        log_evento(tipo, dados, status='ignorado_notificacoes_desativadas')
        return {'success': False, 'skipped': True, 'reason': 'NOTIFICACOES_ATIVO desativado'}

    from .fila import enfileirar_evento
    return enfileirar_evento(evento)


def processar_evento(evento):
    tipo = evento.get('tipo')
    dados = evento.get('dados') or {}
    dados.setdefault('tipo', tipo)
    log_evento(tipo, dados, status='processando')

    resultado = {'success': True, 'actions': []}
    if tipo in EVENTOS_WHATSAPP:
        mensagem = mensagem_evento(tipo, dados)
        envio = enviar_whatsapp(mensagem)
        resultado['actions'].append({'whatsapp': envio})

    log_evento(tipo, dados, status='processado')
    return resultado


def registrar_evento_apontamento(tipo_acao, usuario=None, item=None, trabalho=None, ordem=None, lista=None, quantidade=None, motivo=None):
    tipo = TIPO_ACAO_EVENTO.get(tipo_acao, tipo_acao)
    return registrar_evento(
        tipo,
        operador=getattr(usuario, 'nome', None) or getattr(usuario, 'codigo_operador', None) or '-',
        item=getattr(item, 'codigo_acb', None) or getattr(item, 'nome', None) or '-',
        servico=getattr(trabalho, 'nome', None) or '-',
        os=getattr(ordem, 'numero', None) or '-',
        lista=lista or getattr(ordem, 'status', None) or '-',
        quantidade=quantidade,
        motivo=motivo,
        horario=datetime.now(),
    )
