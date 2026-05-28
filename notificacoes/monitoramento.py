from datetime import datetime, timedelta
from .configuracao import ConfiguracaoNotificacoes
from .eventos import registrar_evento
from .logs import log_evento


def monitorar_producao():
    from models import ApontamentoProducao

    agora = datetime.now()
    abertos = ApontamentoProducao.query.filter(
        ApontamentoProducao.data_fim.is_(None),
        ApontamentoProducao.tipo_acao.in_(['inicio_setup', 'inicio_producao', 'pausa'])
    ).all()

    total_alertas = 0
    for ap in abertos:
        minutos = int((agora - ap.data_hora).total_seconds() // 60) if ap.data_hora else 0
        if ap.tipo_acao == 'inicio_producao' and minutos >= ConfiguracaoNotificacoes.ALERTA_SERVICO_PARADO_MINUTOS:
            _alertar_servico_parado(ap, minutos)
            total_alertas += 1
        elif ap.tipo_acao == 'inicio_setup' and minutos >= ConfiguracaoNotificacoes.ALERTA_SETUP_LONGO_MINUTOS:
            _alertar_setup_longo(ap, minutos)
            total_alertas += 1
        elif ap.tipo_acao == 'pausa' and minutos >= ConfiguracaoNotificacoes.ALERTA_PAUSA_EXCESSIVA_MINUTOS:
            _alertar_pausa_excessiva(ap, minutos)
            total_alertas += 1

    log_evento('monitoramento_producao', {'abertos': len(abertos), 'alertas': total_alertas}, status='executado')
    return {'abertos': len(abertos), 'alertas': total_alertas}


def _alertar_servico_parado(ap, minutos):
    registrar_evento(
        'servico_parado',
        operador=getattr(ap.operador or ap.usuario, 'nome', '-'),
        item=getattr(ap.item, 'codigo_acb', None) or getattr(ap.item, 'nome', '-'),
        servico=getattr(ap.trabalho, 'nome', '-'),
        lista=ap.lista_kanban or getattr(ap.ordem_servico, 'status', '-'),
        tempo_parado=f'{minutos} minutos',
        os=getattr(ap.ordem_servico, 'numero', '-'),
    )


def _alertar_setup_longo(ap, minutos):
    registrar_evento(
        'atraso_detectado',
        operador=getattr(ap.operador or ap.usuario, 'nome', '-'),
        item=getattr(ap.item, 'codigo_acb', None) or getattr(ap.item, 'nome', '-'),
        servico=getattr(ap.trabalho, 'nome', '-'),
        lista=ap.lista_kanban or getattr(ap.ordem_servico, 'status', '-'),
        tempo=f'Setup em andamento há {minutos} minutos',
        os=getattr(ap.ordem_servico, 'numero', '-'),
    )


def _alertar_pausa_excessiva(ap, minutos):
    registrar_evento(
        'maquina_parada',
        operador=getattr(ap.operador or ap.usuario, 'nome', '-'),
        item=getattr(ap.item, 'codigo_acb', None) or getattr(ap.item, 'nome', '-'),
        servico=getattr(ap.trabalho, 'nome', '-'),
        lista=ap.lista_kanban or getattr(ap.ordem_servico, 'status', '-'),
        tempo_parado=f'{minutos} minutos',
        os=getattr(ap.ordem_servico, 'numero', '-'),
    )
