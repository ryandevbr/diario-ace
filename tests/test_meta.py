from datetime import date
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models import Evento, TR
from app.services.meta_service import calcular_metas, meta_do_dia, peso_dia


def test_peso_dia_sem_evento():
    # 10/09/2026 é quinta-feira (dia útil)
    assert peso_dia(date(2026, 9, 10), []) == 1.0


def test_peso_dia_fim_de_semana():
    # 05/09/2026 (sábado) e 06/09/2026 (domingo) têm peso 0.0
    assert peso_dia(date(2026, 9, 5), []) == 0.0
    assert peso_dia(date(2026, 9, 6), []) == 0.0


def test_peso_dia_meio_periodo():
    ev = [Evento(1, date(2026, 9, 10), "reuniao", 0.5, None)]
    assert peso_dia(date(2026, 9, 10), ev) == 0.5


def test_peso_dia_feriado():
    ev = [Evento(1, date(2026, 9, 10), "feriado", 1.0, None)]
    assert peso_dia(date(2026, 9, 10), ev) == 0.0


def test_meta_diaria_simples():
    tr = TR(1, 2026, 5, date(2026, 9, 1), date(2026, 9, 10), 800, 1000)
    # De 01/09 a 10/09/2026 há 8 dias úteis (05 e 06/09 são fim de semana)
    info = calcular_metas(tr, realizado=700, eventos=[], hoje=date(2026, 9, 1))
    assert info["falta_min"] == 100
    assert info["capacidade"] == 8.0
    assert round(info["meta_diaria_min"], 2) == 12.5


def test_meta_diaria_com_feriado():
    tr = TR(1, 2026, 5, date(2026, 9, 1), date(2026, 9, 10), 800, 1000)
    # 07/09/2026 (segunda-feira) feriado -> reduz capacidade de 8.0 para 7.0
    ev = [Evento(1, date(2026, 9, 7), "feriado", 1.0, None)]
    info = calcular_metas(tr, realizado=700, eventos=ev, hoje=date(2026, 9, 1))
    assert info["capacidade"] == 7.0


def test_meta_do_dia_meio_periodo():
    tr = TR(1, 2026, 5, date(2026, 9, 1), date(2026, 9, 10), 800, 1000)
    ev = [Evento(1, date(2026, 9, 1), "reuniao", 0.5, None)]
    info = meta_do_dia(tr, realizado=700, eventos=ev, hoje=date(2026, 9, 1))
    assert info["peso_hoje"] == 0.5
    assert info["capacidade"] == 7.5
    assert info["meta_hoje_min"] == 7  # ceil(100 / 7.5 * 0.5) = ceil(6.67) = 7


if __name__ == "__main__":
    test_peso_dia_sem_evento()
    test_peso_dia_fim_de_semana()
    test_peso_dia_meio_periodo()
    test_peso_dia_feriado()
    test_meta_diaria_simples()
    test_meta_diaria_com_feriado()
    test_meta_do_dia_meio_periodo()
    print("OK")
