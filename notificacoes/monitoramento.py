from datetime import timedelta
from .configuracao import ConfiguracaoNotificacoes
from .eventos import registrar_evento
from .logs import log_evento


_alertas_enviados = {}

def monitorar_producao():
    from models import ApontamentoProducao
    from models import local_now_naive

    # Usar horário local naive (America/Sao_Paulo) para casar com o padrão do sistema.
    # Isso evita alertas incorretos (ex.: +180min) quando o servidor está em UTC.
    agora = local_now_naive()
    
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
        
        # VERIFICAÇÃO CRÍTICA: Confirmar que este serviço está REALMENTE em setup agora
        # Verificar se não há produção ou pausa mais recente para o mesmo OS/Item/Trabalho
        apontamento_mais_recente = ApontamentoProducao.query.filter(
            ApontamentoProducao.ordem_servico_id == ap.ordem_servico_id,
            ApontamentoProducao.item_id == ap.item_id,
            ApontamentoProducao.trabalho_id == ap.trabalho_id,
            ApontamentoProducao.data_hora > ap.data_hora,
            ApontamentoProducao.tipo_acao.in_(['inicio_producao', 'pausa', 'stop'])
        ).first()
        
        if apontamento_mais_recente:
            setups_ignorados += 1
            log_evento('monitoramento_setup_ignorado', {
                'id': ap.id,
                'motivo': 'serviço não está mais em setup (já iniciou produção/pausa/stop)',
                'acao_posterior': apontamento_mais_recente.tipo_acao,
                'data_posterior': str(apontamento_mais_recente.data_hora)
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
        
        limite_alerta = ConfiguracaoNotificacoes.ALERTA_SETUP_LONGO_MINUTOS
        intervalo_alerta = getattr(ConfiguracaoNotificacoes, 'ALERTA_SETUP_LONGO_INTERVALO_MINUTOS', 15)
        
        # Cada setup tem seu próprio controle de alerta
        if minutos >= limite_alerta:
            chave_alerta = f"setup_{ap.id}"
            ultimo_envio = _alertas_enviados.get(chave_alerta)
            
            # Verificar se já passaram 15min desde o último alerta DESTE setup
            deve_enviar = False
            if ultimo_envio is None:
                # Primeiro alerta deste setup
                deve_enviar = True
            else:
                minutos_desde_ultimo = int((agora - ultimo_envio).total_seconds() // 60)
                if minutos_desde_ultimo >= intervalo_alerta:
                    deve_enviar = True
            
            if deve_enviar:
                _alertar_setup_longo(ap, minutos)
                _alertas_enviados[chave_alerta] = agora
                total_alertas += 1
                log_evento('alerta_setup_enviado', {
                    'id': ap.id,
                    'minutos': minutos,
                    'minutos_desde_ultimo': int((agora - ultimo_envio).total_seconds() // 60) if ultimo_envio else None
                }, status='enviado')
            else:
                log_evento('alerta_setup_ignorado', {
                    'id': ap.id,
                    'minutos': minutos,
                    'minutos_desde_ultimo': int((agora - ultimo_envio).total_seconds() // 60),
                    'motivo': f'aguardando {intervalo_alerta}min desde último alerta'
                }, status='ignorado')

    _limpar_alertas_antigos(agora)
    log_evento('monitoramento_producao', {
        'abertos': len(abertos),
        'alertas': total_alertas,
        'ignorados': setups_ignorados
    }, status='executado')
    return {'abertos': len(abertos), 'alertas': total_alertas, 'ignorados': setups_ignorados}


def _limpar_alertas_antigos(agora):
    limite = agora - timedelta(hours=2)
    chaves_antigas = []
    for k, v in _alertas_enviados.items():
        if isinstance(v, dict):
            sent_at = v.get('sent_at')
            if sent_at and sent_at < limite:
                chaves_antigas.append(k)
        # Compatibilidade com versões antigas que salvavam datetime diretamente
        elif hasattr(v, 'strftime'):
            if v < limite:
                chaves_antigas.append(k)
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


def _alertar_setup_longo_consolidado(setups_em_atraso):
    """
    Envia um único alerta consolidado com todos os setups em atraso.
    """
    from .whatsapp import enviar_whatsapp
    
    msg = f"⚠️ ALERTAS DE SETUP EM ANDAMENTO\n\n"
    msg += f"📊 Total: {len(setups_em_atraso)} setup(s) em atraso\n\n"
    
    for i, setup in enumerate(setups_em_atraso, 1):
        ap = setup['apontamento']
        minutos = setup['minutos']
        
        horas = minutos // 60
        mins = minutos % 60
        tempo_str = f"{horas}h {mins}min" if horas > 0 else f"{mins}min"
        
        msg += f"{i}. 📦 {getattr(ap.item, 'nome', None) or getattr(ap.item, 'codigo_acb', '-')}\n"
        msg += f"   🛠️ {getattr(ap.trabalho, 'nome', '-')}\n"
        msg += f"   👤 {getattr(ap.operador or ap.usuario, 'nome', '-')}\n"
        msg += f"   ⏰ {tempo_str}\n"
        msg += f"   📋 {ap.lista_kanban or getattr(ap.ordem_servico, 'status', '-')}\n\n"
    
    enviar_whatsapp(msg)


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
