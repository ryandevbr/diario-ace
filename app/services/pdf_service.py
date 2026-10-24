from datetime import date, datetime
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.components.ui import LABEL_TIPO_EVENTO
from app.utils.datas import para_br

COR_PRIMARIA = colors.HexColor("#0f766e")
COR_ZEBRA = colors.HexColor("#f5f5f5")
COR_BORDA = colors.HexColor("#cccccc")


def _estilos():
    base = getSampleStyleSheet()
    titulo = ParagraphStyle(
        "titulo",
        parent=base["Title"],
        fontSize=16,
        textColor=COR_PRIMARIA,
        spaceAfter=4,
    )
    sub = ParagraphStyle(
        "sub",
        parent=base["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#555555"),
        spaceAfter=10,
    )
    normal = base["Normal"]
    return titulo, sub, normal


def _titulo_h2(normal):
    return ParagraphStyle(
        "h2",
        parent=normal,
        fontSize=13,
        spaceAfter=6,
        textColor=COR_PRIMARIA,
        fontName="Helvetica-Bold",
    )


def _p(texto: str | None, normal) -> Paragraph:
    """Envolve texto escapado em Paragraph para quebra de linha segura em tabelas."""
    seguro = escape(str(texto)) if texto else ""
    return Paragraph(seguro, normal)


def _cabecalho(elementos: list, titulo_txt: str, tr) -> None:
    titulo, sub, _ = _estilos()
    elementos.append(Paragraph(escape(titulo_txt), titulo))
    elementos.append(
        Paragraph(
            f"TR {tr.numero} — {para_br(tr.data_inicio)} a {para_br(tr.data_fim)} — "
            f"Meta: {tr.meta_min}–{tr.meta_max}",
            sub,
        )
    )


def _rodape(elementos: list) -> None:
    _, sub, _ = _estilos()
    elementos.append(Spacer(1, 10 * mm))
    elementos.append(
        Paragraph(
            f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')} pelo Diário ACE.",
            sub,
        )
    )


def _tabela_padrao(
    dados: list[list],
    col_widths: list[float | None],
) -> Table:
    tabela = Table(dados, colWidths=col_widths, repeatRows=1)
    tabela.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), COR_PRIMARIA),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("ALIGN", (1, 0), (1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("GRID", (0, 0), (-1, -1), 0.25, COR_BORDA),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, COR_ZEBRA]),
            ]
        )
    )
    return tabela


def _formatar_fracao(fracao: float) -> str:
    if fracao >= 1:
        return "dia todo"
    if fracao == 0.5:
        return "meio período"
    return f"{int(round(fracao * 100))}%"


def _formatar_evento(ev) -> str:
    def campo(obj, nome, default=None):
        if isinstance(obj, dict):
            return obj.get(nome, default)
        return getattr(obj, nome, default)

    tipo_raw = campo(ev, "tipo", "outro")
    tipo = LABEL_TIPO_EVENTO.get(tipo_raw, str(tipo_raw).capitalize())
    try:
        fracao = float(campo(ev, "fracao", 0) or 0)
    except (TypeError, ValueError):
        fracao = 0.0
    if fracao >= 1:
        return tipo
    return f"{tipo} ({_formatar_fracao(fracao)})"


def _iso(d) -> str:
    return d if isinstance(d, str) else d.isoformat()


def exportar_historico_pdf(
    caminho: str | Path,
    tr,
    producoes: list[dict],
    eventos: list[dict] | None = None,
    bairros_por_id: dict | None = None,
) -> None:
    eventos = eventos or []
    bairros_por_id = bairros_por_id or {}

    doc = SimpleDocTemplate(
        str(caminho),
        pagesize=landscape(A4),
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title=f"Diário ACE - Produção TR {tr.numero}",
    )
    elementos: list = []
    _cabecalho(elementos, "Diário ACE — Histórico de Produção", tr)

    _, _, normal = _estilos()
    total = sum(p["quantidade"] for p in producoes)
    inicial = getattr(tr, "producao_inicial", 0)
    total_geral = total + inicial

    texto_resumo = (
        f"Total lançado em <b>{len(producoes)}</b> dia(s): <b>{total}</b> imóveis."
    )
    if inicial:
        texto_resumo += f" Produção inicial: <b>{inicial}</b>."
    texto_resumo += f" Total geral do TR: <b>{total_geral}</b>."
    if eventos:
        texto_resumo += f" Eventos registrados: <b>{len(eventos)}</b>."
    elementos.append(Paragraph(texto_resumo, normal))
    elementos.append(Spacer(1, 6 * mm))

    prod_por_data = {_iso(p["data"]): p for p in producoes}
    ev_por_data: dict[str, list] = {}
    for ev in eventos:
        chave = _iso(ev["data"] if isinstance(ev, dict) else ev.data)
        ev_por_data.setdefault(chave, []).append(ev)

    todas_datas = sorted(set(prod_por_data.keys()) | set(ev_por_data.keys()))

    if todas_datas:
        dados: list[list] = [
            ["Data", "Bairro", "Atividade", "T", "Eventos / Motivo", "Obs."]
        ]
        for dt in todas_datas:
            p = prod_por_data.get(dt)
            qtd = p["quantidade"] if p else 0
            obs = (p.get("observacao") if p else "") or ""

            bairro_nome = ""
            if p and p.get("bairro_id"):
                b = bairros_por_id.get(p["bairro_id"])
                if isinstance(b, dict):
                    bairro_nome = b.get("nome", "")
                elif isinstance(b, str):
                    bairro_nome = b

            atividade = (p.get("atividade") if p else "") or ""
            evs = ev_por_data.get(dt, [])
            ev_txt = ", ".join(_formatar_evento(e) for e in evs)

            dados.append(
                [
                    para_br(date.fromisoformat(dt)),
                    _p(bairro_nome, normal),
                    _p(atividade, normal),
                    str(qtd),
                    _p(ev_txt, normal),
                    _p(obs, normal),
                ]
            )

        elementos.append(
            _tabela_padrao(
                dados,
                [22 * mm, 40 * mm, 48 * mm, 12 * mm, 55 * mm, None],
            )
        )
    else:
        elementos.append(Paragraph("Nenhuma produção lançada neste TR.", normal))

    _rodape(elementos)
    doc.build(elementos)


def exportar_recuperacao_pdf(
    caminho: str | Path,
    tr,
    itens: list[dict],
) -> None:
    doc = SimpleDocTemplate(
        str(caminho),
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title=f"Diário ACE - Recuperação TR {tr.numero}",
    )
    elementos: list = []
    _cabecalho(elementos, "Diário ACE — Lista de Recuperação", tr)

    _, _, normal = _estilos()

    contagem = {"fechado": 0, "atendida": 0, "abandonada": 0, "recusado": 0}
    for it in itens:
        if it["status"] in contagem:
            contagem[it["status"]] += 1

    elementos.append(
        Paragraph(
            f"Total de endereços: <b>{len(itens)}</b> — "
            f"Fechados: <b>{contagem['fechado']}</b>, "
            f"Atendidos: <b>{contagem['atendida']}</b>, "
            f"Abandonados: <b>{contagem['abandonada']}</b>, "
            f"Recusados: <b>{contagem['recusado']}</b>.",
            normal,
        )
    )
    elementos.append(Spacer(1, 6 * mm))

    if itens:
        dados: list[list] = [["Quadra", "Lado", "Rua", "Número", "Status", "Obs."]]
        for it in itens:
            dados.append(
                [
                    it.get("quarteirao") or "",
                    it.get("lado") or "",
                    _p(it.get("rua") or "", normal),
                    _p(it.get("numero") or "", normal),
                    it["status"].capitalize(),
                    _p(it.get("observacao") or "", normal),
                ]
            )
        elementos.append(
            _tabela_padrao(
                dados,
                [14 * mm, 14 * mm, 40 * mm, 22 * mm, 22 * mm, None],
            )
        )
    else:
        elementos.append(
            Paragraph("Nenhum endereço cadastrado neste TR.", normal)
        )

    _rodape(elementos)
    doc.build(elementos)


def _secao_por_bairro(elementos: list, dados: dict, normal) -> None:
    contagem: dict[str, dict] = {}
    for r in dados["trs"]:
        for p in r["producoes"]:
            b = p.get("bairro_nome") or "—"
            if b not in contagem:
                contagem[b] = {"total": 0, "dias": 0}
            contagem[b]["total"] += p["quantidade"]
            if p["quantidade"] > 0:
                contagem[b]["dias"] += 1

    if not contagem:
        return

    elementos.append(Paragraph("Consolidado por bairro", _titulo_h2(normal)))

    linhas: list[list] = [["Bairro", "Imóveis", "Dias com produção", "Média/dia"]]
    for bairro in sorted(contagem.keys()):
        info = contagem[bairro]
        media = info["total"] / info["dias"] if info["dias"] else 0
        linhas.append(
            [
                _p(bairro, normal),
                str(info["total"]),
                str(info["dias"]),
                f"{media:.1f}",
            ]
        )

    elementos.append(
        _tabela_padrao(linhas, [60 * mm, 25 * mm, 35 * mm, 25 * mm])
    )
    elementos.append(Spacer(1, 8 * mm))


def _secao_por_atividade(elementos: list, dados: dict, normal) -> None:
    contagem: dict[str, dict] = {}
    for r in dados["trs"]:
        for p in r["producoes"]:
            a = p.get("atividade") or "—"
            if a not in contagem:
                contagem[a] = {"total": 0, "dias_prod": 0, "dias_reg": 0}
            contagem[a]["total"] += p["quantidade"]
            contagem[a]["dias_reg"] += 1
            if p["quantidade"] > 0:
                contagem[a]["dias_prod"] += 1

    if not contagem:
        return

    elementos.append(Paragraph("Consolidado por atividade", _titulo_h2(normal)))

    linhas: list[list] = [
        [
            "Atividade",
            "Imóveis",
            "Dias com produção",
            "Dias registrados",
            "Média/dia",
        ]
    ]
    for a in sorted(contagem.keys()):
        info = contagem[a]
        media = info["total"] / info["dias_prod"] if info["dias_prod"] else 0
        linhas.append(
            [
                _p(a, normal),
                str(info["total"]),
                str(info["dias_prod"]),
                str(info["dias_reg"]),
                f"{media:.1f}",
            ]
        )

    elementos.append(
        _tabela_padrao(
            linhas,
            [70 * mm, 25 * mm, 35 * mm, 35 * mm, 25 * mm],
        )
    )
    elementos.append(Spacer(1, 8 * mm))


def exportar_relatorio_anual_pdf(caminho: str | Path, dados: dict) -> None:
    """Gera o relatório anual detalhado."""
    ano = dados["ano"]
    trs = dados["trs"]

    doc = SimpleDocTemplate(
        str(caminho),
        pagesize=landscape(A4),
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title=f"Diário ACE - Relatório Anual {ano}",
    )
    elementos: list = []
    _, _, normal = _estilos()

    elementos.append(
        Paragraph(
            f"Diário ACE — Relatório Anual {ano}",
            ParagraphStyle(
                "titulo_ano",
                parent=getSampleStyleSheet()["Title"],
                fontSize=18,
                textColor=COR_PRIMARIA,
                spaceAfter=8,
            ),
        )
    )
    elementos.append(
        Paragraph(
            f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}.",
            ParagraphStyle(
                "sub",
                parent=normal,
                fontSize=9,
                textColor=colors.HexColor("#666666"),
                spaceAfter=12,
            ),
        )
    )

    elementos.append(Paragraph("Resumo geral do ano", _titulo_h2(normal)))

    total = dados["total_ano"]
    meta_min = dados["meta_min_ano"]
    meta_max = dados["meta_max_ano"]

    pct_meta_min = total / meta_min * 100 if meta_min else 0
    pct_meta_max = total / meta_max * 100 if meta_max else 0

    resumo = [
        ["Total de imóveis visitados", f"{total}"],
        ["Meta mínima do ano", f"{meta_min}  ({pct_meta_min:.1f}% atingido)"],
        ["Meta máxima do ano", f"{meta_max}  ({pct_meta_max:.1f}% atingido)"],
        ["TRs com registro", f"{dados['trs_com_registro']} de {len(trs)}"],
        ["Dias com produção", f"{dados['dias_trabalhados_ano']}"],
        ["Eventos registrados", f"{dados['eventos_ano']}"],
        [
            "Média diária (dias com produção)",
            f"{dados['media_diaria']:.1f} imóveis/dia",
        ],
    ]

    if dados.get("dias_pe_ano", 0) > 0:
        resumo.append(
            [
                "Dias em P.E. (Ponto Estratégico)",
                str(dados["dias_pe_ano"]),
            ]
        )

    if dados["melhor_dia"]:
        md = dados["melhor_dia"]
        resumo.append(
            [
                "Melhor dia",
                f"{para_br(date.fromisoformat(md['data']))} — {md['quantidade']} imóveis",
            ]
        )

    elementos.append(_tabela_padrao(resumo, [70 * mm, None]))
    elementos.append(Spacer(1, 6 * mm))

    if dados["contagem_eventos"]:
        elementos.append(
            Paragraph(
                "Eventos por tipo (ano)",
                ParagraphStyle(
                    "h3",
                    parent=normal,
                    fontSize=11,
                    spaceAfter=4,
                    fontName="Helvetica-Bold",
                ),
            )
        )
        linhas_ev = [["Tipo", "Quantidade"]]
        for tipo, qtd in sorted(
            dados["contagem_eventos"].items(), key=lambda x: -x[1]
        ):
            linhas_ev.append(
                [
                    LABEL_TIPO_EVENTO.get(tipo, tipo.capitalize()),
                    str(qtd),
                ]
            )
        elementos.append(_tabela_padrao(linhas_ev, [60 * mm, 30 * mm]))
        elementos.append(Spacer(1, 8 * mm))

    _secao_por_bairro(elementos, dados, normal)
    _secao_por_atividade(elementos, dados, normal)

    elementos.append(Paragraph("Detalhamento por TR", _titulo_h2(normal)))

    estilo_sub_h = ParagraphStyle(
        "sub_h",
        parent=normal,
        fontSize=9,
        fontName="Helvetica-Bold",
        spaceAfter=3,
    )
    estilo_tr_titulo = ParagraphStyle(
        "tr_titulo",
        parent=normal,
        fontSize=11,
        spaceAfter=4,
        fontName="Helvetica-Bold",
        textColor=COR_PRIMARIA,
    )

    for item in trs:
        tr = item["tr"]
        elementos.append(
            Paragraph(
                f"TR {tr.numero} — {para_br(tr.data_inicio)} a {para_br(tr.data_fim)}",
                estilo_tr_titulo,
            )
        )

        total_tr = item["total"]
        pct = (total_tr / tr.meta_min * 100) if tr.meta_min else 0

        linhas: list[list] = [
            ["Imóveis visitados", str(total_tr)],
            ["Meta", f"{tr.meta_min}–{tr.meta_max}  ({pct:.1f}% da mínima)"],
            ["Dias com produção", str(item["dias_trabalhados"])],
            ["Dias com lançamento registrado", str(item["dias_registrados"])],
        ]
        if item["inicial"] > 0:
            linhas.append(["Produção inicial", str(item["inicial"])])

        bairros_do_tr = sorted(
            {
                p.get("bairro_nome")
                for p in item["producoes"]
                if p.get("bairro_nome")
            }
        )
        if bairros_do_tr:
            linhas.append(
                ["Bairros atendidos", _p(", ".join(bairros_do_tr), normal)]
            )

        atividades_do_tr = sorted(
            {p.get("atividade") for p in item["producoes"] if p.get("atividade")}
        )
        if atividades_do_tr:
            linhas.append(
                ["Atividades", _p(", ".join(atividades_do_tr), normal)]
            )

        elementos.append(_tabela_padrao(linhas, [70 * mm, None]))

        if item["observacoes"]:
            elementos.append(Spacer(1, 3 * mm))
            elementos.append(Paragraph("Observações", estilo_sub_h))
            obs_dados: list[list] = [["Data", "Observação"]]
            for o in item["observacoes"]:
                obs_dados.append(
                    [
                        para_br(date.fromisoformat(o["data"])),
                        _p(o["texto"], normal),
                    ]
                )
            elementos.append(_tabela_padrao(obs_dados, [25 * mm, None]))

        if item["eventos"]:
            elementos.append(Spacer(1, 3 * mm))
            elementos.append(Paragraph("Eventos", estilo_sub_h))
            ev_dados: list[list] = [["Data", "Tipo", "Duração", "Observação"]]
            for ev in item["eventos"]:
                ev_dados.append(
                    [
                        para_br(ev.data),
                        LABEL_TIPO_EVENTO.get(ev.tipo, ev.tipo.capitalize()),
                        _formatar_fracao(ev.fracao),
                        _p(ev.observacao or "", normal),
                    ]
                )
            elementos.append(
                _tabela_padrao(
                    ev_dados,
                    [22 * mm, 25 * mm, 22 * mm, None],
                )
            )

        elementos.append(Spacer(1, 8 * mm))

    _rodape(elementos)
    doc.build(elementos)
