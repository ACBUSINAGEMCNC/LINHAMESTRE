from datetime import datetime, timedelta
from .configuracao import ConfiguracaoNotificacoes
from .eventos import registrar_evento
from .logs import log_evento


_alertas_enviados = {}

def monitorar_producao():
    from models import ApontamentoProducao

    agora = datetime.now()
    
    # Limite de tempo: apenas setups das últimas 12 horas
    limite_tempo = agora - timedelta(hours=12)
    
    # IMPORTANTE: Buscar APENAS setups que estão ABERTOS (data_fim = NULL) e recentes
    abertos = ApontamentoProducao.query.filter(
        ApontamentoProducao.data_fim.is_(None),
        ApontamentoProducao.tipo_acao == 'inicio_setup',
        ApontamentoProducao.data_hora >= limite_tempo
    ).all()

    total_alertas = 0
    setups_ignorados = 0
    
    for ap in abertos:
        # VERIFICAÇÃO EXTRA: Confirmar que data_fim é realmente NULL
        if ap.data_fim is not None:
            setups_ignorados += 1
            log_evento('monitoramento_setup_ignorado', {
                'id': ap.id,
                'motivo': 'data_fim não é NULL',
                'data_fim': str(ap.data_fim)
            }, status='ignorado')
            continue
        
        minutos = int((agora - ap.data_hora).total_seconds() // 60) if ap.data_hora else 0
        
        # Verificar se minutos é negativo (horário futuro - bug de timezone)
        if minutos < 0:
            setups_ignorados += 1
            log_evento('monitoramento_setup_ignorado', {
                'id': ap.id,
                'motivo': 'horário no futuro',
                'minutos': minutos,
                'data_hora': str(ap.data_hora)
            }, status='ignorado')
            continue
        
        if minutos >= ConfiguracaoNotificacoes.ALERTA_SETUP_LONGO_MINUTOS:
            chave_alerta = f"setup_{ap.id}"
            ultimo_envio = _alertas_enviados.get(chave_alerta)
            
            # Enviar se nunca foi enviado OU se já passaram 10 minutos desde o último envio
            deve_enviar = False
            if ultimo_envio is None:
                deve_enviar = True
            else:
                minutos_desde_ultimo = int((agora - ultimo_envio).total_seconds() // 60)
                if minutos_desde_ultimo >= 10:
                    deve_enviar = True
            
            if deve_enviar:
                _alertar_setup_longo(ap, minutos)
                _alertas_enviados[chave_alerta] = agora
                total_alertas += 1

    _limpar_alertas_antigos(agora)
    log_evento('monitoramento_producao', {
        'abertos': len(abertos),
        'alertas': total_alertas,
        'ignorados': setups_ignorados
    }, status='executado')
    return {'abertos': len(abertos), 'alertas': total_alertas, 'ignorados': setups_ignorados}


def _limpar_alertas_antigos(agora):
    limite = agora - timedelta(hours=2)
    chaves_antigas = [k for k, v in _alertas_enviados.items() if v < limite]
    for chave in chaves_antigas:
        del _alertas_enviados[chave]


def limpar_alerta_setup(apontamento_id):
    """
    Limpa o cache de alertas quando um setup é fechado.
    Deve ser chamado ao finalizar um setup.
    """
    chave = f"setup_{apontamento_id}"
    if chave in _alertas_enviados:
        del _alertas_enviados[chave]
        log_evento('alerta_setup_limpo', {'apontamento_id': apontamento_id}, status='limpo')


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
