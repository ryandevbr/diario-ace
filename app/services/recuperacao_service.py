from datetime import datetime
from app.database import db_session

STATUS_VALIDOS = ("fechado", "atendida", "abandonada", "recusado")


def listar_por_tr(tr_id: int, status: str | None = None) -> list[dict]:
    with db_session() as conn:
        if status and status in STATUS_VALIDOS:
            rows = conn.execute(
                "SELECT * FROM recuperacao WHERE tr_id=? AND status=? "
                "ORDER BY rua, quarteirao, numero",
                (tr_id, status),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM recuperacao WHERE tr_id=? "
                "ORDER BY rua, quarteirao, numero",
                (tr_id,),
            ).fetchall()
    return [dict(r) for r in rows]


def contar_por_status(tr_id: int) -> dict[str, int]:
    with db_session() as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) AS total FROM recuperacao "
            "WHERE tr_id=? GROUP BY status",
            (tr_id,),
        ).fetchall()
    return {r["status"]: r["total"] for r in rows}


def adicionar(
    tr_id: int,
    quarteirao: str,
    lado: str,
    rua: str,
    numero: str,
    observacao: str | None = None,
) -> None:
    agora = datetime.now().isoformat()
    with db_session(commit=True) as conn:
        conn.execute(
            "INSERT INTO recuperacao (tr_id, quarteirao, lado, rua, numero, status, "
            "observacao, criado_em, atualizado_em) "
            "VALUES (?, ?, ?, ?, ?, 'fechado', ?, ?, ?)",
            (tr_id, quarteirao, lado, rua, numero, observacao, agora, agora),
        )


def atualizar_status(rec_id: int, status: str) -> None:
    if status not in STATUS_VALIDOS:
        raise ValueError(f"Status inválido: {status}")
    with db_session(commit=True) as conn:
        conn.execute(
            "UPDATE recuperacao SET status=?, atualizado_em=? WHERE id=?",
            (status, datetime.now().isoformat(), rec_id),
        )


def remover(rec_id: int) -> None:
    with db_session(commit=True) as conn:
        conn.execute("DELETE FROM recuperacao WHERE id=?", (rec_id,))
