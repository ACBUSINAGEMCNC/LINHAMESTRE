from datetime import timedelta
from .configuracao import ConfiguracaoNotificacoes
from .eventos import registrar_evento
from .logs import log_evento


# Cache de alertas em memória (fallback)
_alertas_enviados = {}


def _garantir_tabela_cache_alerta():
    try:
        from models import db
        from sqlalchemy import text

        dialect = (db.engine.dialect.name or '').lower()
        if dialect.startswith('postgres'):
            db.session.execute(text(
                """
                CREATE TABLE IF NOT EXISTS cache_alerta (
                    id SERIAL PRIMARY KEY,
                    chave VARCHAR(100) UNIQUE NOT NULL,
                    data_envio TIMESTAMP NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ix_cache_alerta_chave ON cache_alerta(chave);
                """
            ))
        else:
            db.session.execute(text(
                """
                CREATE TABLE IF NOT EXISTS cache_alerta (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chave VARCHAR(100) UNIQUE NOT NULL,
                    data_envio DATETIME NOT NULL
                );
                """
            ))
            try:
                db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_cache_alerta_chave ON cache_alerta(chave);"))
            except Exception:
                pass
        db.session.commit()
        return True
    except Exception as e:
        try:
            from models import db
            db.session.rollback()
        except Exception:
            pass
        log_evento('cache_db_erro_tabela', {'erro': str(e)}, status='aviso')
        return False


def _deve_enviar_alerta_db(chave, agora, intervalo_minutos):
    try:
        from models import db
        from sqlalchemy import text

        if not _garantir_tabela_cache_alerta():
            return None

        dialect = (db.engine.dialect.name or '').lower()
        if dialect.startswith('postgres'):
            res = db.session.execute(
                text(
                    """
                    INSERT INTO cache_alerta (chave, data_envio)
                    VALUES (:chave, :agora)
                    ON CONFLICT (chave)
                    DO UPDATE SET data_envio = EXCLUDED.data_envio
                    WHERE cache_alerta.data_envio <= (:agora - (:intervalo * INTERVAL '1 minute'))
                    RETURNING data_envio;
                    """
                ),
                {'chave': chave, 'agora': agora, 'intervalo': int(intervalo_minutos)}
            )
            row = res.first()
            db.session.commit()
            return True if row else False

        # SQLite fallback (não é atômico como Postgres, mas ajuda para dev local)
        ultimo = db.session.execute(
            text("SELECT data_envio FROM cache_alerta WHERE chave = :chave"),
            {'chave': chave}
        ).first()
        if ultimo and ultimo[0] is not None:
            try:
                delta_min = int((agora - ultimo[0]).total_seconds() // 60)
                if delta_min < int(intervalo_minutos):
                    db.session.rollback()
                    return False
            except Exception:
                pass

        db.session.execute(
            text("INSERT OR REPLACE INTO cache_alerta (chave, data_envio) VALUES (:chave, :agora)"),
            {'chave': chave, 'agora': agora}
        )
        db.session.commit()
        return True
    except Exception as e:
        try:
            from models import db
            db.session.rollback()
        except Exception:
            pass
        log_evento('cache_db_erro_dedup', {'chave': chave, 'erro': str(e)}, status='aviso')
        return None

def monitorar_producao():
    from models import ApontamentoProducao
    from models import local_now_naive

    # Usar horário local naive (America/Sao_Paulo) para casar com o padrão do sistema.
    # Isso evita alertas incorretos (ex.: +180min) quando o servidor está em UTC.
    agora = local_now_naive()
    
    # Limite de tempo: apenas setups das últimas 12 horas (para não pegar setups antigos/bugados)
    limite_tempo = agora - timedelta(hours=12)

    # Janela para somatória (setup acumulado) - última 24h
    limite_somatoria = agora - timedelta(hours=24)
    
    # IMPORTANTE: Buscar APENAS setups que estão ABERTOS (data_fim = NULL) e recentes
    abertos = ApontamentoProducao.query.filter(
        ApontamentoProducao.data_fim.is_(None),
        ApontamentoProducao.tipo_acao == 'inicio_setup',
        ApontamentoProducao.data_hora >= limite_tempo
    ).all()

    total_alertas = 0
    setups_ignorados = 0
    
    # Log de debug
    log_evento('monitoramento_inicio', {
        'total_abertos': len(abertos),
        'limite_alerta_min': ConfiguracaoNotificacoes.ALERTA_SETUP_LONGO_MINUTOS,
        'intervalo_alerta_min': getattr(ConfiguracaoNotificacoes, 'ALERTA_SETUP_LONGO_INTERVALO_MINUTOS', 15)
    }, status='debug')
    
    # Se existir mais de 1 setup aberto para a MESMA OS/Item/Trabalho,
    # vamos considerar apenas o MAIS RECENTE para monitoramento.
    abertos_por_chave = {}
    for ap in abertos:
        chave_combo = (ap.ordem_servico_id, ap.item_id, ap.trabalho_id)
        atual = abertos_por_chave.get(chave_combo)
        if atual is None or (ap.data_hora and atual.data_hora and ap.data_hora > atual.data_hora) or (atual.data_hora is None and ap.data_hora is not None):
            abertos_por_chave[chave_combo] = ap

    for ap in abertos_por_chave.values():
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
        
        minutos_aberto = int((agora - ap.data_hora).total_seconds() // 60) if ap.data_hora else 0
        
        # Verificar se minutos é negativo (horário futuro - bug de timezone)
        if minutos_aberto < 0:
            setups_ignorados += 1
            log_evento('monitoramento_setup_ignorado', {
                'id': ap.id,
                'motivo': 'horário no futuro',
                'minutos': minutos_aberto,
                'data_hora': str(ap.data_hora)
            }, status='ignorado')
            continue

        # Calcular setup acumulado (últimas 24h) para este OS/Item/Trabalho
        # - soma tempo_decorrido de ciclos já encerrados (inicio_setup com tempo_decorrido)
        # - soma o tempo do setup em andamento
        soma_setup_min = 0
        try:
            ciclos = ApontamentoProducao.query.filter(
                ApontamentoProducao.ordem_servico_id == ap.ordem_servico_id,
                ApontamentoProducao.item_id == ap.item_id,
                ApontamentoProducao.trabalho_id == ap.trabalho_id,
                ApontamentoProducao.tipo_acao == 'inicio_setup',
                ApontamentoProducao.data_hora >= limite_somatoria,
            ).all()
            for c in ciclos:
                if c.id == ap.id:
                    continue
                if c.tempo_decorrido:
                    soma_setup_min += int(c.tempo_decorrido // 60)
        except Exception as exc:
            log_evento('monitoramento_setup_soma_erro', {
                'id': ap.id,
                'erro': str(exc),
            }, status='aviso')

        minutos = max(0, soma_setup_min + minutos_aberto)
        
        limite_alerta = ConfiguracaoNotificacoes.ALERTA_SETUP_LONGO_MINUTOS
        intervalo_alerta = getattr(ConfiguracaoNotificacoes, 'ALERTA_SETUP_LONGO_INTERVALO_MINUTOS', 15)
        
        # Cada setup tem seu próprio controle de alerta
        if minutos >= limite_alerta:
            # Deduplicação por OS/Item/Trabalho (e não por id do apontamento)
            # Isso evita spam quando existirem múltiplos inicio_setup abertos por bug.
            chave_alerta = f"setup_{ap.ordem_servico_id}_{ap.item_id}_{ap.trabalho_id}"
            
            # Log de debug
            log_evento('setup_passou_limite', {
                'id': ap.id,
                'minutos': minutos,
                'limite': limite_alerta,
                'item': getattr(ap.item, 'nome', None) or getattr(ap.item, 'codigo_acb', '-'),
                'servico': getattr(ap.trabalho, 'nome', '-')
            }, status='debug')
            
            # Deduplicação entre múltiplas instâncias (Vercel) usando banco de dados.
            # Se DB falhar, usa fallback em memória (pode duplicar se houver múltiplas instâncias).
            deve_enviar = _deve_enviar_alerta_db(chave_alerta, agora, intervalo_alerta)
            ultimo_envio = None
            if deve_enviar is None:
                ultimo_envio = _alertas_enviados.get(chave_alerta)
                if ultimo_envio is None:
                    deve_enviar = True
                else:
                    minutos_desde_ultimo = int((agora - ultimo_envio).total_seconds() // 60)
                    deve_enviar = minutos_desde_ultimo >= intervalo_alerta
            
            if deve_enviar:
                _alertar_setup_longo(ap, minutos)
                # Salvar em memória (DB já foi atualizado quando disponível)
                _alertas_enviados[chave_alerta] = agora
                total_alertas += 1
                log_evento('alerta_setup_enviado', {
                    'id': ap.id,
                    'minutos': minutos,
                    'minutos_desde_ultimo': int((agora - ultimo_envio).total_seconds() // 60) if ultimo_envio else None,
                    'dedup_db': True if deve_enviar is True and ultimo_envio is None else None
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
