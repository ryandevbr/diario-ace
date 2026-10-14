from datetime import date, datetime, timedelta
from app.database import get_conn

def registrar_producao(
    d: date,
    tr_id: int,
    quantidade: int,
    bairro_id: int | None = None,
    atividade: str | None = None,
    fechados: int = 0,
    resgatados: int = 0,
    recusados: int = 0,
    pendencia: str | None = None,
    motivo_id: int | None = None,
    obs: str | None = None,
) -> None:
    conn = get_conn()
    agora = datetime.now().isoformat()
    existente = conn.execute(
        "SELECT id FROM producao WHERE data=?", (d.isoformat(),)
    ).fetchone()
    if existente:
        conn.execute(
            "UPDATE producao SET quantidade=?, tr_id=?, bairro_id=?, atividade=?, "
            "fechados=?, resgatados=?, recusados=?, pendencia=?, "
            "motivo_id=?, observacao=?, atualizado_em=? WHERE id=?",
            (quantidade, tr_id, bairro_id, atividade,
             fechados, resgatados, recusados, pendencia,
             motivo_id, obs, agora, existente["id"]),
        )
    else:
        conn.execute(
            "INSERT INTO producao (data, tr_id, bairro_id, atividade, quantidade, "
            "fechados, resgatados, recusados, pendencia, motivo_id, observacao, "
            "criado_em, atualizado_em) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (d.isoformat(), tr_id, bairro_id, atividade, quantidade,
             fechados, resgatados, recusados, pendencia, motivo_id, obs,
             agora, agora),
        )
    conn.commit()
    conn.close()

def atualizar_producao_completa(
    producao_id: int,
    quantidade: int,
    bairro_id: int | None = None,
    atividade: str | None = None,
    fechados: int = 0,
    resgatados: int = 0,
    recusados: int = 0,
    observacao: str | None = None,
) -> None:
    conn = get_conn()
    conn.execute(
        "UPDATE producao SET quantidade=?, bairro_id=?, atividade=?, "
        "fechados=?, resgatados=?, recusados=?, "
        "observacao=?, atualizado_em=? WHERE id=?",
        (quantidade, bairro_id, atividade,
         fechados, resgatados, recusados,
         observacao, datetime.now().isoformat(), producao_id),
    )
    conn.commit()
    conn.close()

def total_realizado(tr_id: int) -> int:
    conn = get_conn()
    row = conn.execute(
        "SELECT COALESCE(SUM(quantidade), 0) AS total FROM producao WHERE tr_id=?",
        (tr_id,),
    ).fetchone()
    tr_row = conn.execute(
        "SELECT producao_inicial FROM tr WHERE id=?", (tr_id,)
    ).fetchone()
    conn.close()
    total_diario = int(row["total"])
    inicial = int(tr_row["producao_inicial"]) if tr_row else 0
    return total_diario + inicial

def producao_do_dia(d: date) -> int | None:
    conn = get_conn()
    row = conn.execute(
        "SELECT quantidade FROM producao WHERE data=?", (d.isoformat(),)
    ).fetchone()
    conn.close()
    return int(row["quantidade"]) if row else None

def listar_producoes_do_tr(tr_id: int):
    """Retorna lista de dicts ordenada por data desc."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM producao WHERE tr_id=? ORDER BY data DESC",
        (tr_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def atualizar_producao(producao_id: int, quantidade: int, obs: str | None = None) -> None:
    conn = get_conn()
    conn.execute(
        "UPDATE producao SET quantidade=?, observacao=?, atualizado_em=? WHERE id=?",
        (quantidade, obs, datetime.now().isoformat(), producao_id),
    )
    conn.commit()
    conn.close()

def remover_producao(producao_id: int) -> None:
    conn = get_conn()
    conn.execute("DELETE FROM producao WHERE id=?", (producao_id,))
    conn.commit()
    conn.close()

def listar_motivos():
    conn = get_conn()
    rows = conn.execute("SELECT id, nome FROM motivo WHERE ativo=1 ORDER BY nome").fetchall()
    conn.close()
    return [(r["id"], r["nome"]) for r in rows]

def producao_completa_do_dia(d: date) -> dict | None:
    """Retorna o registro de produção completo do dia, ou None."""
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM producao WHERE data=?", (d.isoformat(),)
    ).fetchone()
    conn.close()
    return dict(row) if row else None

def dias_sem_producao(ano: int, hoje: date | None = None) -> list[dict]:
    """Retorna dias úteis (seg-sex) do ano, anteriores a hoje, que estejam dentro
    de algum TR do ano e não tenham produção registrada.

    Cada item: {"data": date, "eventos": [Evento, ...]}
    """
    from app.services import tr_service, evento_service  # evitar ciclo

    hoje = hoje or date.today()

    trs = tr_service.listar_trs(ano)
    if not trs:
        return []

    inicio = min(t.data_inicio for t in trs)
    fim = hoje - timedelta(days=1)
    if fim < inicio:
        return []

    # Datas com produção já registrada
    conn = get_conn()
    rows = conn.execute(
        "SELECT data FROM producao WHERE data BETWEEN ? AND ?",
        (inicio.isoformat(), fim.isoformat()),
    ).fetchall()
    conn.close()
    com_producao = {r["data"] for r in rows}

    # Eventos (para mostrar o motivo provável do dia vazio)
    eventos = evento_service.listar_eventos(inicio, fim)
    ev_por_data: dict[str, list] = {}
    for ev in eventos:
        ev_por_data.setdefault(ev.data.isoformat(), []).append(ev)

    faltantes: list[dict] = []
    d = inicio
    while d <= fim:
        if d.weekday() < 5:  # 0=seg, 4=sex
            dentro_de_tr = any(t.data_inicio <= d <= t.data_fim for t in trs)
            if dentro_de_tr and d.isoformat() not in com_producao:
                faltantes.append({
                    "data": d,
                    "eventos": ev_por_data.get(d.isoformat(), []),
                })
        d += timedelta(days=1)

    return faltantes

def eficiencia_simples(quantidade: int, fechados: int, recusados: int) -> float:
    """trabalhados / (trabalhados + fechados + recusados) × 100.
    Retorna 0.0 se não há nada no denominador.
    """
    denominador = (quantidade or 0) + (fechados or 0) + (recusados or 0)
    if denominador == 0:
        return 0.0
    return (quantidade or 0) / denominador * 100


def totais_do_dia(d: date) -> dict:
    """Resumo do dia (fechados, resgatados, recusados)."""
    p = producao_completa_do_dia(d)
    if not p:
        return {"fechados": 0, "resgatados": 0, "recusados": 0, "quantidade": 0}
    return {
        "quantidade": p.get("quantidade", 0) or 0,
        "fechados": p.get("fechados", 0) or 0,
        "resgatados": p.get("resgatados", 0) or 0,
        "recusados": p.get("recusados", 0) or 0,
    }