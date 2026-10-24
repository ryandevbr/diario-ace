from calendar import monthrange
from datetime import date

from app.database import db_session
from app.models import TR

TR_MESES = {
    1: (1, 2),
    2: (3, 4),
    3: (5, 6),
    4: (7, 8),
    5: (9, 10),
    6: (11, 12),
}


def _row_to_tr(row) -> TR:
    return TR(
        id=row["id"],
        ano=row["ano"],
        numero=row["numero"],
        data_inicio=date.fromisoformat(row["data_inicio"]),
        data_fim=date.fromisoformat(row["data_fim"]),
        meta_min=row["meta_min"],
        meta_max=row["meta_max"],
        producao_inicial=(
            row["producao_inicial"] if "producao_inicial" in row.keys() else 0
        ),
    )


def seed_trs_do_ano(ano: int) -> None:
    """Cria os 6 TRs do ano se não existirem. Datas default: 1º ao último dia dos meses."""
    with db_session(commit=True) as conn:
        cur = conn.cursor()
        for numero, (m1, m2) in TR_MESES.items():
            cur.execute(
                "SELECT 1 FROM tr WHERE ano=? AND numero=?", (ano, numero)
            )
            if cur.fetchone():
                continue
            inicio = date(ano, m1, 1)
            ultimo_dia = monthrange(ano, m2)[1]
            fim = date(ano, m2, ultimo_dia)
            cur.execute(
                "INSERT INTO tr (ano, numero, data_inicio, data_fim, meta_min, meta_max) "
                "VALUES (?, ?, ?, ?, 800, 1000)",
                (ano, numero, inicio.isoformat(), fim.isoformat()),
            )


def atualizar_datas(tr_id: int, inicio: date, fim: date) -> None:
    with db_session(commit=True) as conn:
        conn.execute(
            "UPDATE tr SET data_inicio=?, data_fim=? WHERE id=?",
            (inicio.isoformat(), fim.isoformat(), tr_id),
        )


def listar_trs(ano: int) -> list[TR]:
    with db_session() as conn:
        rows = conn.execute(
            "SELECT * FROM tr WHERE ano=? ORDER BY numero", (ano,)
        ).fetchall()
    return [_row_to_tr(r) for r in rows]


def tr_por_data(d: date) -> TR | None:
    with db_session() as conn:
        row = conn.execute(
            "SELECT * FROM tr WHERE data_inicio<=? AND data_fim>=? LIMIT 1",
            (d.isoformat(), d.isoformat()),
        ).fetchone()
    return _row_to_tr(row) if row else None


def atualizar_tr(
    tr_id: int,
    inicio: date,
    fim: date,
    meta_min: int,
    meta_max: int,
    producao_inicial: int = 0,
) -> None:
    with db_session(commit=True) as conn:
        conn.execute(
            "UPDATE tr SET data_inicio=?, data_fim=?, meta_min=?, "
            "meta_max=?, producao_inicial=? WHERE id=?",
            (
                inicio.isoformat(),
                fim.isoformat(),
                meta_min,
                meta_max,
                producao_inicial,
                tr_id,
            ),
        )


def anos_disponiveis() -> list[int]:
    with db_session() as conn:
        rows = conn.execute(
            "SELECT DISTINCT ano FROM tr ORDER BY ano DESC"
        ).fetchall()
    anos = [r["ano"] for r in rows]
    ano_atual = date.today().year
    if ano_atual not in anos:
        anos.insert(0, ano_atual)
    return sorted(set(anos), reverse=True)


def listar_todos_trs() -> list[TR]:
    with db_session() as conn:
        rows = conn.execute(
            "SELECT * FROM tr ORDER BY ano DESC, numero DESC"
        ).fetchall()
    return [_row_to_tr(r) for r in rows]
