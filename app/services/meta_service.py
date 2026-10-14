from datetime import date, timedelta
import math
from app.models import TR, Evento

def peso_dia(d: date, eventos: list[Evento]) -> float:
    # Sábado (5) e domingo (6) não são dias úteis
    if d.weekday() >= 5:
        return 0.0
    soma = sum(e.fracao for e in eventos if e.data == d)
    return max(0.0, 1.0 - soma)

def capacidade_restante(tr: TR, eventos: list[Evento], hoje: date) -> float:
    """Soma dos pesos dos dias do TR a partir de hoje (inclusive)."""
    inicio = max(hoje, tr.data_inicio)
    if inicio > tr.data_fim:
        return 0.0
    total = 0.0
    d = inicio
    while d <= tr.data_fim:
        total += peso_dia(d, eventos)
        d += timedelta(days=1)
    return total

def calcular_metas(tr: TR, realizado: int, eventos: list[Evento], hoje: date) -> dict:
    falta_min = max(0, tr.meta_min - realizado)
    falta_max = max(0, tr.meta_max - realizado)
    cap = capacidade_restante(tr, eventos, hoje)
    if cap <= 0:
        return {
            "falta_min": falta_min, "falta_max": falta_max,
            "capacidade": 0.0,
            "meta_diaria_min": None, "meta_diaria_max": None,
        }
    return {
        "falta_min": falta_min, "falta_max": falta_max,
        "capacidade": cap,
        "meta_diaria_min": falta_min / cap,
        "meta_diaria_max": falta_max / cap,
    }

def meta_do_dia(tr: TR, realizado: int, eventos: list[Evento], hoje: date) -> dict:
    info = calcular_metas(tr, realizado, eventos, hoje)
    peso = peso_dia(hoje, eventos)
    if info["meta_diaria_min"] is None:
        return {**info, "peso_hoje": peso, "meta_hoje_min": None, "meta_hoje_max": None}
    return {
        **info,
        "peso_hoje": peso,
        "meta_hoje_min": math.ceil(info["meta_diaria_min"] * peso),
        "meta_hoje_max": math.ceil(info["meta_diaria_max"] * peso),
    }