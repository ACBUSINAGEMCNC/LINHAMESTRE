from datetime import datetime
import pytz


def _hora(valor=None):
    if valor is None:
        valor = datetime.now()
    try:
        # Converter para timezone de São Paulo
        if valor.tzinfo is None:
            tz = pytz.timezone('America/Sao_Paulo')
            valor = tz.localize(valor)
        else:
            valor = valor.astimezone(pytz.timezone('America/Sao_Paulo'))
        return valor.strftime('%H:%M')
    except Exception:
        return str(valor)


def mensagem_evento(tipo, dados):
    builders = {
        'producao_iniciada': mensagem_producao_iniciada,
        'producao_finalizada': mensagem_producao_finalizada,
        'pausa_iniciada': mensagem_pausa_iniciada,
        'pausa_finalizada': mensagem_pausa_finalizada,
        'setup_iniciado': mensagem_setup_iniciado,
        'setup_finalizado': mensagem_setup_finalizado,
        'kanban_movido': mensagem_kanban_movido,
        'atraso_detectado': mensagem_atraso_detectado,
        'maquina_parada': mensagem_maquina_parada,
        'servico_parado': mensagem_servico_parado,
    }
    builder = builders.get(tipo, mensagem_generica)
    return builder(dados or {})


def mensagem_generica(dados):
    return (
        '🔔 EVENTO DO SISTEMA\n\n'
        f"📌 Tipo: {dados.get('tipo', 'Evento')}\n"
        f"👤 Operador: {dados.get('operador', '-')}\n"
        f"📦 Item: {dados.get('item', '-')}\n"
        f"🛠 Serviço: {dados.get('servico', '-')}\n"
        f"⏰ Horário: {_hora(dados.get('horario'))}"
    )


def mensagem_producao_iniciada(dados):
    return _mensagem_operacao('🚀 PRODUÇÃO INICIADA', dados)


def mensagem_producao_finalizada(dados):
    return _mensagem_operacao('✅ PRODUÇÃO FINALIZADA', dados)


def mensagem_pausa_iniciada(dados):
    return _mensagem_operacao('⏸ PAUSA INICIADA', dados)


def mensagem_pausa_finalizada(dados):
    # Stop tem métricas especiais
    if dados.get('metricas'):
        return _mensagem_stop_com_metricas(dados)
    return _mensagem_operacao('▶️ PAUSA FINALIZADA', dados)


def mensagem_setup_iniciado(dados):
    return _mensagem_operacao('🧰 SETUP INICIADO', dados)


def mensagem_setup_finalizado(dados):
    # Se tiver métricas, mostrar detalhes
    if dados.get('metricas_setup'):
        return _mensagem_setup_finalizado_com_metricas(dados)
    return _mensagem_operacao('✅ SETUP FINALIZADO', dados)


def mensagem_kanban_movido(dados):
    return (
        '📋 ITEM MOVIDO NO KANBAN\n\n'
        f"📦 OS: {dados.get('os', '-')}\n"
        f"📦 Item: {dados.get('item', '-')}\n"
        f"➡️ De: {dados.get('lista_origem', '-')}\n"
        f"✅ Para: {dados.get('lista_destino', '-')}\n"
        f"⏰ Horário: {_hora(dados.get('horario'))}"
    )


def mensagem_atraso_detectado(dados):
    return _mensagem_alerta('⚠️ ATRASO DETECTADO', dados)


def mensagem_maquina_parada(dados):
    return _mensagem_alerta('🚨 MÁQUINA PARADA', dados)


def mensagem_servico_parado(dados):
    return _mensagem_alerta('🚨 ALERTA DE PARADA', dados)


def _mensagem_operacao(titulo, dados):
    msg = (
        f'{titulo}\n\n'
        f"👤 Operador: {dados.get('operador', '-')}\n"
        f"📦 Item: {dados.get('item', '-')}\n"
        f"🛠️ Serviço: {dados.get('servico', '-')}\n"
        f"📋 Lista: {dados.get('lista', '-')}\n"
    )
    
    quantidade = dados.get('quantidade')
    if quantidade is not None and quantidade > 0:
        msg += f"🔢 Quantidade: {quantidade} peças\n"
    
    msg += f"⏰ Horário: {_hora(dados.get('horario'))}"
    return msg


def _mensagem_setup_finalizado_com_metricas(dados):
    metricas = dados.get('metricas_setup', {})
    
    msg = (
        f"✅ SETUP FINALIZADO\n\n"
        f"👤 Operador: {dados.get('operador', '-')}\n"
        f"📦 Item: {dados.get('item', '-')}\n"
        f"🛠️ Serviço: {dados.get('servico', '-')}\n"
        f"📋 Lista: {dados.get('lista', '-')}\n\n"
    )
    
    # Tempo de setup
    tempo_setup = metricas.get('tempo_setup_minutos', 0)
    if tempo_setup > 0:
        horas = tempo_setup // 60
        minutos = tempo_setup % 60
        if horas > 0:
            msg += f"⏱️ Tempo de setup: {horas}h {minutos}min\n"
        else:
            msg += f"⏱️ Tempo de setup: {minutos}min\n"
    
    # Horários
    hora_inicio = metricas.get('hora_inicio')
    hora_fim = metricas.get('hora_fim')
    if hora_inicio and hora_fim:
        msg += f"🕐 Início: {_hora(hora_inicio)} | Fim: {_hora(hora_fim)}\n"
    
    return msg


def _mensagem_stop_com_metricas(dados):
    metricas = dados.get('metricas', {})
    
    msg = (
        f"🛑 STOP - APONTAMENTO FINALIZADO\n\n"
        f"👤 Operador: {dados.get('operador', '-')}\n"
        f"📦 Item: {dados.get('item', '-')}\n"
        f"🛠️ Serviço: {dados.get('servico', '-')} ⭐\n"
        f"📋 Lista: {dados.get('lista', '-')}\n\n"
        f"📊 MÉTRICAS DO SERVIÇO ATUAL:\n"
    )
    
    # Quantidade inicial e final
    qtd_inicial = metricas.get('quantidade_inicial', 0)
    qtd_final = dados.get('quantidade', 0)
    qtd_produzida = qtd_final - qtd_inicial
    
    if qtd_inicial > 0 or qtd_final > 0:
        msg += f"🔢 Quantidade: {qtd_inicial} → {qtd_final} peças"
        if qtd_produzida > 0:
            msg += f" (+{qtd_produzida})"
        msg += "\n"
    
    # Tempo total
    tempo_total = metricas.get('tempo_total_minutos', 0)
    if tempo_total > 0:
        horas = tempo_total // 60
        minutos = tempo_total % 60
        if horas > 0:
            msg += f"⏱️ Tempo total: {horas}h {minutos}min\n"
        else:
            msg += f"⏱️ Tempo total: {minutos}min\n"
    
    # Tempo de setup
    tempo_setup = metricas.get('tempo_setup_minutos', 0)
    if tempo_setup > 0:
        horas = tempo_setup // 60
        minutos = tempo_setup % 60
        if horas > 0:
            msg += f"🔧 Tempo de setup: {horas}h {minutos}min\n"
        else:
            msg += f"🔧 Tempo de setup: {minutos}min\n"
    
    # Tempo de produção
    tempo_producao = metricas.get('tempo_producao_minutos', 0)
    if tempo_producao > 0:
        horas = tempo_producao // 60
        minutos = tempo_producao % 60
        if horas > 0:
            msg += f"⚙️ Tempo de produção: {horas}h {minutos}min\n"
        else:
            msg += f"⚙️ Tempo de produção: {minutos}min\n"
    
    # Outros serviços da mesma OS
    outros_servicos = metricas.get('outros_servicos', [])
    if outros_servicos:
        msg += f"\n📋 OUTROS SERVIÇOS DESTA OS:\n"
        for servico in outros_servicos:
            nome = servico.get('nome', '-')
            qtd = servico.get('ultima_quantidade', 0)
            tempo = servico.get('tempo_total_minutos', 0)
            
            msg += f"• {nome}"
            if qtd > 0:
                msg += f" - {qtd} peças"
            if tempo > 0:
                h = tempo // 60
                m = tempo % 60
                if h > 0:
                    msg += f" - {h}h {m}min"
                else:
                    msg += f" - {m}min"
            msg += "\n"
    
    msg += f"\n⏰ Finalizado: {_hora(dados.get('horario'))}"
    
    motivo = dados.get('motivo')
    if motivo:
        msg += f"\n💬 Motivo: {motivo}"
    
    return msg


def _mensagem_alerta(titulo, dados):
    return (
        f'{titulo}\n\n'
        f"📦 Item: {dados.get('item', '-')}\n"
        f"🛠 Serviço: {dados.get('servico', '-')}\n"
        f"👤 Último operador: {dados.get('operador', '-')}\n"
        f"⏰ Tempo parado: {dados.get('tempo_parado', dados.get('tempo', '-'))}\n"
        f"📋 Lista: {dados.get('lista', '-')}"
    )
