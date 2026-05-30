from datetime import datetime, timedelta
from .configuracao import ConfiguracaoNotificacoes
from .eventos import registrar_evento
from .logs import log_evento


_alertas_enviados = {}

def monitorar_producao():
    from models import ApontamentoProducao

    agora = datetime.now()
    abertos = ApontamentoProducao.query.filter(
        ApontamentoProducao.data_fim.is_(None),
        ApontamentoProducao.tipo_acao == 'inicio_setup'
    ).all()

    total_alertas = 0
    for ap in abertos:
        minutos = int((agora - ap.data_hora).total_seconds() // 60) if ap.data_hora else 0
        
        if ap.tipo_acao == 'inicio_setup' and minutos >= ConfiguracaoNotificacoes.ALERTA_SETUP_LONGO_MINUTOS:
            chave_alerta = f"setup_{ap.id}"
            if chave_alerta not in _alertas_enviados:
                _alertar_setup_longo(ap, minutos)
                _alertas_enviados[chave_alerta] = agora
                total_alertas += 1

    _limpar_alertas_antigos(agora)
    log_evento('monitoramento_producao', {'abertos': len(abertos), 'alertas': total_alertas}, status='executado')
    return {'abertos': len(abertos), 'alertas': total_alertas}


def _limpar_alertas_antigos(agora):
    limite = agora - timedelta(hours=2)
    chaves_antigas = [k for k, v in _alertas_enviados.items() if v < limite]
    for chave in chaves_antigas:
        del _alertas_enviados[chave]


def _alertar_servico_parado(ap, minutos):
    registrar_evento(
        'servico_parado',
        operador=getattr(ap.operador or ap.usuario, 'nome', '-'),
        item=getattr(ap.item, 'nome', None) or getattr(ap.item, 'codigo_acb', '-'),
        servico=getattr(ap.trabalho, 'nome', '-'),
        lista=ap.lista_kanban or getattr(ap.ordem_servico, 'status', '-'),
        tempo_parado=f'{minutos} minutos',
        os=getattr(ap.ordem_servico, 'numero', '-'),
    )


def _alertar_setup_longo(ap, minutos):
    registrar_evento(
        'atraso_detectado',
        operador=getattr(ap.operador or ap.usuario, 'nome', '-'),
        item=getattr(ap.item, 'nome', None) or getattr(ap.item, 'codigo_acb', '-'),
        servico=getattr(ap.trabalho, 'nome', '-'),
        lista=ap.lista_kanban or getattr(ap.ordem_servico, 'status', '-'),
        tempo=f'Setup em andamento há {minutos} minutos',
        os=getattr(ap.ordem_servico, 'numero', '-'),
    )


def _alertar_pausa_excessiva(ap, minutos):
    registrar_evento(
        'maquina_parada',
        operador=getattr(ap.operador or ap.usuario, 'nome', '-'),
        item=getattr(ap.item, 'nome', None) or getattr(ap.item, 'codigo_acb', '-'),
        servico=getattr(ap.trabalho, 'nome', '-'),
        lista=ap.lista_kanban or getattr(ap.ordem_servico, 'status', '-'),
        tempo_parado=f'{minutos} minutos',
        os=getattr(ap.ordem_servico, 'numero', '-'),
    )
