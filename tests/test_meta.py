import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import date
from app.models import TR, Evento
from app.services.meta_service import calcular_metas, meta_do_dia, peso_dia

def test_peso_dia_sem_evento():
    assert peso_dia(date(2026, 9, 10), []) == 1.0

def test_peso_dia_meio_periodo():
    ev = [Evento(1, date(2026, 9, 10), "reuniao", 0.5, None)]
    assert peso_dia(date(2026, 9, 10), ev) == 0.5

def test_peso_dia_feriado():
    ev = [Evento(1, date(2026, 9, 10), "feriado", 1.0, None)]
    assert peso_dia(date(2026, 9, 10), ev) == 0.0

def test_meta_diaria_simples():
    tr = TR(1, 2026, 5, date(2026, 9, 1), date(2026, 9, 10), 800, 1000)
    # 10 dias, sem eventos, hoje = primeiro dia
    info = calcular_metas(tr, realizado=700, eventos=[], hoje=date(2026, 9, 1))
    assert info["falta_min"] == 100
    assert info["capacidade"] == 10.0
    assert round(info["meta_diaria_min"], 2) == 10.0

def test_meta_diaria_com_feriado():
    tr = TR(1, 2026, 5, date(2026, 9, 1), date(2026, 9, 10), 800, 1000)
    ev = [Evento(1, date(2026, 9, 5), "feriado", 1.0, None)]
    info = calcular_metas(tr, realizado=700, eventos=ev, hoje=date(2026, 9, 1))
    assert info["capacidade"] == 9.0

def test_meta_do_dia_meio_periodo():
    tr = TR(1, 2026, 5, date(2026, 9, 1), date(2026, 9, 10), 800, 1000)
    ev = [Evento(1, date(2026, 9, 1), "reuniao", 0.5, None)]
    info = meta_do_dia(tr, realizado=700, eventos=ev, hoje=date(2026, 9, 1))
    assert info["peso_hoje"] == 0.5
    assert info["meta_hoje_min"] == 6  # ceil(100/9.5 * 0.5) = ceil(5.26)

if __name__ == "__main__":
    test_peso_dia_sem_evento()
    test_peso_dia_meio_periodo()
    test_peso_dia_feriado()
    test_meta_diaria_simples()
    test_meta_diaria_com_feriado()
    test_meta_do_dia_meio_periodo()
    print("OK")