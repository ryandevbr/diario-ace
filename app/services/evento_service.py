from datetime import date, datetime
from app.database import get_conn
from app.models import Evento

def listar_eventos(inicio: date, fim: date) -> list[Evento]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM evento WHERE data BETWEEN ? AND ? ORDER BY data",
        (inicio.isoformat(), fim.isoformat()),
    ).fetchall()
    conn.close()
    return [
        Evento(
            id=r["id"], data=date.fromisoformat(r["data"]),
            tipo=r["tipo"], fracao=r["fracao"], observacao=r["observacao"],
        )
        for r in rows
    ]

def listar_eventos_do_tr(tr) -> list[Evento]:
    return listar_eventos(tr.data_inicio, tr.data_fim)

def adicionar_evento(d: date, tipo: str, fracao: float, obs: str | None = None) -> None:
    conn = get_conn()
    conn.execute(
        "INSERT INTO evento (data, tipo, fracao, observacao, criado_em) VALUES (?, ?, ?, ?, ?)",
        (d.isoformat(), tipo, fracao, obs, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()

def remover_evento(evento_id: int) -> None:
    conn = get_conn()
    conn.execute("DELETE FROM evento WHERE id=?", (evento_id,))
    conn.commit()
    conn.close()