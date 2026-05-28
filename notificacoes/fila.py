import queue
import threading
from flask import current_app
from .configuracao import ConfiguracaoNotificacoes
from .logs import log_evento

_fila = queue.Queue()
_worker = None
_stop_event = threading.Event()
_app_ref = None


def iniciar_fila(app=None):
    global _worker, _app_ref
    _app_ref = app
    if not ConfiguracaoNotificacoes.FILA_ATIVA:
        return False
    if _worker and _worker.is_alive():
        return True
    _stop_event.clear()
    _worker = threading.Thread(target=_processar_loop, name='notificacoes-worker', daemon=True)
    _worker.start()
    return True


def parar_fila():
    _stop_event.set()
    return True


def enfileirar_evento(evento):
    if not ConfiguracaoNotificacoes.FILA_ATIVA:
        from .eventos import processar_evento
        return processar_evento(evento)
    _fila.put(evento)
    log_evento(evento.get('tipo'), evento.get('dados'), status='enfileirado')
    return {'success': True, 'queued': True}


def tamanho_fila():
    return _fila.qsize()


def _processar_loop():
    while not _stop_event.is_set():
        try:
            evento = _fila.get(timeout=1)
        except queue.Empty:
            continue
        try:
            from .eventos import processar_evento
            if _app_ref:
                with _app_ref.app_context():
                    processar_evento(evento)
            else:
                processar_evento(evento)
        except Exception as exc:
            try:
                current_app.logger.exception('Erro ao processar evento de notificacao')
            except Exception:
                pass
            log_evento(evento.get('tipo'), evento.get('dados'), status='erro_worker', erro=exc)
        finally:
            _fila.task_done()
