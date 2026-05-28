from .configuracao import ConfiguracaoNotificacoes
from .logs import log_evento

_scheduler = None


def iniciar_scheduler(app):
    global _scheduler
    if not ConfiguracaoNotificacoes.SCHEDULER_ATIVO:
        app.logger.info('Scheduler de notificacoes desativado')
        return False

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except Exception as exc:
        app.logger.warning('APScheduler nao instalado/configurado: %s', exc)
        return False

    if _scheduler and _scheduler.running:
        return True

    _scheduler = BackgroundScheduler(timezone='America/Sao_Paulo')

    def job_monitoramento():
        with app.app_context():
            from .monitoramento import monitorar_producao
            try:
                monitorar_producao()
            except Exception as exc:
                log_evento('monitoramento_producao', {}, status='erro_scheduler', erro=exc)
                app.logger.exception('Erro no monitoramento automatico de producao')

    _scheduler.add_job(
        job_monitoramento,
        'interval',
        seconds=ConfiguracaoNotificacoes.MONITORAMENTO_INTERVALO_SEGUNDOS,
        id='monitoramento_producao',
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()
    app.logger.info('Scheduler de notificacoes iniciado')
    return True


def parar_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        return True
    return False
