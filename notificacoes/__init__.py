from .eventos import registrar_evento, processar_evento
from .scheduler import iniciar_scheduler
from .fila import iniciar_fila, parar_fila


def init_notificacoes(app):
    app.extensions = getattr(app, 'extensions', {})
    app.extensions['notificacoes'] = {
        'fila_iniciada': iniciar_fila(app),
        'scheduler_iniciado': iniciar_scheduler(app),
    }
    app.logger.info('Modulo de notificacoes inicializado')
    return app.extensions['notificacoes']
