from datetime import datetime


def agora_formatado():
    return datetime.now().strftime('%d/%m/%Y %H:%M:%S')


def minutos_para_label(minutos):
    try:
        minutos = int(minutos)
    except Exception:
        return '-'
    if minutos < 60:
        return f'{minutos} minutos'
    horas = minutos // 60
    resto = minutos % 60
    if resto:
        return f'{horas}h {resto}min'
    return f'{horas}h'


def safe_getattr(obj, attr, default='-'):
    try:
        return getattr(obj, attr, default) or default
    except Exception:
        return default
