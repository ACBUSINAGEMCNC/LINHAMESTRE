from datetime import datetime


def _hora(valor=None):
    if valor is None:
        valor = datetime.now()
    try:
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
    return _mensagem_operacao('▶️ PAUSA FINALIZADA', dados)


def mensagem_setup_iniciado(dados):
    return _mensagem_operacao('🧰 SETUP INICIADO', dados)


def mensagem_setup_finalizado(dados):
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
    return (
        f'{titulo}\n\n'
        f"👤 Operador: {dados.get('operador', '-')}\n"
        f"📦 Item: {dados.get('item', '-')}\n"
        f"🛠 Serviço: {dados.get('servico', '-')}\n"
        f"📋 Lista: {dados.get('lista', '-')}\n"
        f"⏰ Horário: {_hora(dados.get('horario'))}"
    )


def _mensagem_alerta(titulo, dados):
    return (
        f'{titulo}\n\n'
        f"📦 Item: {dados.get('item', '-')}\n"
        f"🛠 Serviço: {dados.get('servico', '-')}\n"
        f"👤 Último operador: {dados.get('operador', '-')}\n"
        f"⏰ Tempo parado: {dados.get('tempo_parado', dados.get('tempo', '-'))}\n"
        f"📋 Lista: {dados.get('lista', '-')}"
    )
