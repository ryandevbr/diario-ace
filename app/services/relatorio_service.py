from app.services import (
    bairro_service,
    evento_service,
    producao_service,
    tr_service,
)


def dados_do_ano(ano: int) -> dict:
    """Coleta todos os dados que o relatório anual precisa para um ano."""
    trs = tr_service.listar_trs(ano)
    bairros_por_id = {b["id"]: b["nome"] for b in bairro_service.listar_todos()}

    resultado_trs = []
    for tr in trs:
        producoes = producao_service.listar_producoes_do_tr(tr.id)
        eventos = evento_service.listar_eventos(tr.data_inicio, tr.data_fim)

        total_diario = sum(p["quantidade"] for p in producoes)
        inicial = getattr(tr, "producao_inicial", 0) or 0
        total = total_diario + inicial

        dias_trabalhados = sum(1 for p in producoes if p["quantidade"] > 0)
        dias_registrados = len(producoes)

        dias_pe = sum(
            1
            for p in producoes
            if (p.get("atividade") or "") == "P.E. (Ponto Estratégico)"
        )

        observacoes = [
            {"data": p["data"], "texto": p["observacao"]}
            for p in producoes
            if p.get("observacao")
        ]

        producoes_enriquecidas = []
        for p in producoes:
            copia = dict(p)
            copia["bairro_nome"] = bairros_por_id.get(p.get("bairro_id"))
            producoes_enriquecidas.append(copia)

        resultado_trs.append(
            {
                "tr": tr,
                "total": total,
                "total_diario": total_diario,
                "inicial": inicial,
                "dias_trabalhados": dias_trabalhados,
                "dias_registrados": dias_registrados,
                "observacoes": observacoes,
                "eventos": eventos,
                "producoes": producoes_enriquecidas,
                "dias_pe": dias_pe,
            }
        )

    total_ano = sum(r["total"] for r in resultado_trs)
    meta_min_ano = sum(r["tr"].meta_min for r in resultado_trs)
    meta_max_ano = sum(r["tr"].meta_max for r in resultado_trs)
    dias_trabalhados_ano = sum(r["dias_trabalhados"] for r in resultado_trs)
    eventos_ano = sum(len(r["eventos"]) for r in resultado_trs)
    dias_pe_ano = sum(r["dias_pe"] for r in resultado_trs)

    trs_com_registro = sum(
        1 for r in resultado_trs if r["total"] > 0 or len(r["eventos"]) > 0
    )

    contagem_eventos: dict[str, int] = {}
    for r in resultado_trs:
        for ev in r["eventos"]:
            contagem_eventos[ev.tipo] = contagem_eventos.get(ev.tipo, 0) + 1

    todas_producoes = [
        {"data": p["data"], "quantidade": p["quantidade"]}
        for r in resultado_trs
        for p in r["producoes"]
    ]
    melhor_dia = max(
        todas_producoes, key=lambda x: x["quantidade"], default=None
    )
    media_diaria = (
        sum(p["quantidade"] for p in todas_producoes) / len(todas_producoes)
        if todas_producoes
        else 0
    )

    return {
        "ano": ano,
        "trs": resultado_trs,
        "total_ano": total_ano,
        "meta_min_ano": meta_min_ano,
        "meta_max_ano": meta_max_ano,
        "dias_trabalhados_ano": dias_trabalhados_ano,
        "eventos_ano": eventos_ano,
        "trs_com_registro": trs_com_registro,
        "contagem_eventos": contagem_eventos,
        "melhor_dia": melhor_dia,
        "media_diaria": media_diaria,
        "dias_pe_ano": dias_pe_ano,
    }
