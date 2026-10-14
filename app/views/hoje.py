from datetime import date
import flet as ft

from app.services import (
    tr_service, evento_service, producao_service,
    bairro_service, atividade_service,
)
from app.services.meta_service import meta_do_dia
from app.utils.datas import para_br
from app.components.ui import card, kpi, snack, chip_tipo_evento


DIAS_SEMANA = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]


def build(page: ft.Page) -> ft.Control:
    conteudo = ft.Column(scroll=ft.ScrollMode.AUTO, spacing=0, controls=[])

    def montar():
        hoje = date.today()
        tr = tr_service.tr_por_data(hoje)

        if tr is None:
            conteudo.controls = [
                ft.Container(
                    padding=20,
                    content=ft.Text("Nenhum TR cadastrado para hoje."),
                )
            ]
            return

        eventos = evento_service.listar_eventos(tr.data_inicio, tr.data_fim)
        realizado = producao_service.total_realizado(tr.id)
        info = meta_do_dia(tr, realizado, eventos, hoje)
        produzido_hoje = producao_service.producao_do_dia(hoje) or 0
        prod_hoje_dia = producao_service.totais_do_dia(hoje)

        meta_min = info["meta_hoje_min"] or 0
        meta_max = info["meta_hoje_max"] or 0

        if produzido_hoje >= meta_max and meta_max > 0:
            cor_meta = ft.Colors.GREEN_600
            status_meta = "Meta do dia batida!"
            icone_meta = ft.Icons.CHECK_CIRCLE
        elif meta_min > 0 and produzido_hoje >= meta_min:
            cor_meta = ft.Colors.AMBER_700
            status_meta = f"Faltam {max(0, meta_max - produzido_hoje)} para a meta máxima"
            icone_meta = ft.Icons.EMOJI_EVENTS
        else:
            cor_meta = ft.Colors.RED_500
            status_meta = f"Faltam {max(0, meta_min - produzido_hoje)} para a meta mínima"
            icone_meta = ft.Icons.TRENDING_UP

        # Bairros e atividades
        bairros = bairro_service.listar_ativos()
        atividades = atividade_service.listar()

        dropdown_qtd = ft.Dropdown(
            label="Imóveis trabalhados",
            options=[ft.dropdown.Option(key=str(n), text=str(n)) for n in range(0, 41)],
            value=str(produzido_hoje),
        )
        dropdown_bairro = ft.Dropdown(
            label="Bairro",
            options=[ft.dropdown.Option(key=str(b["id"]), text=b["nome"]) for b in bairros],
            value=str(bairros[0]["id"]) if bairros else None,
        )
        dropdown_atividade = ft.Dropdown(
            label="Atividade",
            options=[ft.dropdown.Option(key=a, text=a) for a in atividades],
            value="Tratamento",
        )
        dropdown_fechados = ft.Dropdown(
            label="Fechados",
            options=[ft.dropdown.Option(key=str(n), text=str(n)) for n in range(0, 31)],
            value="0",
            width=100,
        )
        dropdown_resgatados = ft.Dropdown(
            label="Resgatados",
            options=[ft.dropdown.Option(key=str(n), text=str(n)) for n in range(0, 31)],
            value="0",
            width=100,
        )
        dropdown_recusados = ft.Dropdown(
            label="Recusados",
            options=[ft.dropdown.Option(key=str(n), text=str(n)) for n in range(0, 31)],
            value="0",
            width=100,
        )

        # Se já existe produção hoje, carrega os valores atuais
        prod_hoje = producao_service.producao_completa_do_dia(hoje)
        if prod_hoje:
            if prod_hoje.get("bairro_id"):
                dropdown_bairro.value = str(prod_hoje["bairro_id"])
            if prod_hoje.get("atividade"):
                dropdown_atividade.value = prod_hoje["atividade"]
            dropdown_qtd.value = str(prod_hoje.get("quantidade", 0) or 0)
            dropdown_fechados.value = str(prod_hoje.get("fechados", 0) or 0)
            dropdown_resgatados.value = str(prod_hoje.get("resgatados", 0) or 0)
            dropdown_recusados.value = str(prod_hoje.get("recusados", 0) or 0)

        page._hoje_dropdown = dropdown_qtd
        page._hoje_produzido_salvo = produzido_hoje

        def salvar(e):
            try:
                qtd = int(dropdown_qtd.value or "0")
                fechados = int(dropdown_fechados.value or "0")
                resgatados = int(dropdown_resgatados.value or "0")
                recusados = int(dropdown_recusados.value or "0")
            except ValueError:
                snack(page, "Selecione um valor válido.", ft.Colors.RED_500)
                return
            try:
                bairro_id = int(dropdown_bairro.value) if dropdown_bairro.value else None
            except (ValueError, TypeError):
                bairro_id = None

            producao_service.registrar_producao(
                hoje, tr.id, qtd,
                bairro_id=bairro_id,
                atividade=dropdown_atividade.value,
                fechados=fechados,
                resgatados=resgatados,
                recusados=recusados,
            )
            snack(page, f"Salvo: {qtd} imóveis em {para_br(hoje)}.")
            montar()
            page.update()

        inicial_visivel = getattr(tr, "producao_inicial", 0) > 0

        widgets = [
            ft.Text("Hoje", size=28, weight=ft.FontWeight.BOLD),
            ft.Text(
                f"{para_br(hoje)} · TR {tr.numero}",
                size=13, color=ft.Colors.GREY_600,
            ),
            ft.Container(height=8),

            ft.Row([
                kpi(page, "Hoje", str(produzido_hoje), "imóveis",
                    cor=ft.Colors.TEAL_700, icone=ft.Icons.HOME),
                kpi(page, "No TR", str(realizado), f"de {tr.meta_min}–{tr.meta_max}",
                    cor=ft.Colors.BLUE_700, icone=ft.Icons.INSIGHTS),
            ], spacing=10),

            ft.Text(
                f"Inclui {tr.producao_inicial} imóveis lançados como produção inicial.",
                size=11, color=ft.Colors.GREY_600,
                visible=inicial_visivel,
            ),

            _resumo_contadores(produzido_hoje, prod_hoje_dia),

            ft.Container(height=8),

            card(page, ft.Column([
                ft.Row([
                    ft.Icon(icone_meta, color=cor_meta, size=28),
                    ft.Text(
                        f"Meta de hoje: {meta_min}–{meta_max}",
                        size=16, weight=ft.FontWeight.BOLD,
                    ),
                ], spacing=8),
                ft.Text(status_meta, size=13, color=cor_meta),
                ft.Divider(height=10, color=ft.Colors.GREY_300),
                ft.Text(
                    f"Peso do dia: {info['peso_hoje']:.2f}",
                    size=12, color=ft.Colors.GREY_600,
                ),
            ], spacing=6)),

            ft.Container(height=12),

            card(page, ft.Column([
                ft.Text("Registrar produção", size=14, weight=ft.FontWeight.BOLD),
                dropdown_bairro,
                dropdown_atividade,
                dropdown_qtd,
                ft.Row([
                    dropdown_fechados,
                    dropdown_resgatados,
                    dropdown_recusados,
                ], spacing=8),
                ft.Button(
                    "Salvar produção",
                    icon=ft.Icons.SAVE,
                    on_click=salvar,
                    style=ft.ButtonStyle(
                        bgcolor=ft.Colors.TEAL_700,
                        color=ft.Colors.WHITE,
                        shape=ft.RoundedRectangleBorder(radius=10),
                        padding=ft.Padding.symmetric(horizontal=20, vertical=14),
                    ),
                ),
            ], spacing=12)),
        ]

        # Card de dias sem registro (aparece só se houver)
        faltantes = producao_service.dias_sem_producao(hoje.year, hoje)
        if faltantes:
            widgets.append(ft.Container(height=12))
            widgets.append(_card_faltantes(page, faltantes, on_after_save=montar))

        conteudo.controls = [
            ft.Container(
                padding=20,
                content=ft.Column(widgets),
            )
        ]

    montar()
    return conteudo


def _resumo_contadores(produzido_hoje: int, totais: dict) -> ft.Control:
    fechados = totais.get("fechados", 0)
    resgatados = totais.get("resgatados", 0)
    recusados = totais.get("recusados", 0)

    if fechados == 0 and resgatados == 0 and recusados == 0:
        return ft.Container()

    efic = producao_service.eficiencia_simples(produzido_hoje, fechados, recusados)

    def _chip(label: str, valor: int, cor: str):
        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=10, vertical=6),
            bgcolor=cor,
            border_radius=20,
            content=ft.Text(
                f"{label}: {valor}",
                size=11, color=ft.Colors.WHITE, weight=ft.FontWeight.W_600,
            ),
        )

    return ft.Row([
        _chip("Fechados", fechados, ft.Colors.RED_500),
        _chip("Resgatados", resgatados, ft.Colors.GREEN_600),
        _chip("Recusados", recusados, ft.Colors.ORANGE_700),
        ft.Text(f"Eficiência: {efic:.1f}%", size=11, color=ft.Colors.GREY_500),
    ], spacing=6, wrap=True)


def _card_faltantes(page: ft.Page, faltantes: list[dict], on_after_save):
    """Card que mostra dias úteis sem produção. Tocar num dia abre o registro."""

    def abrir_registro(d: date, eventos: list):
        tr = tr_service.tr_por_data(d)
        if tr is None:
            snack(page, "Sem TR cadastrado para essa data.", ft.Colors.RED_500)
            return

        dropdown_qtd = ft.Dropdown(
            label="Imóveis visitados",
            options=[ft.dropdown.Option(key=str(n), text=str(n)) for n in range(0, 41)],
            value="0",
        )
        campo_obs = ft.TextField(label="Observação (opcional)", value="")

        def salvar(ev):
            try:
                qtd = int(dropdown_qtd.value or "0")
            except ValueError:
                return
            producao_service.registrar_producao(
                d, tr.id, qtd,
                obs=campo_obs.value.strip() or None,
            )
            page.pop_dialog()
            snack(page, f"Salvo: {qtd} imóveis em {para_br(d)}.")
            on_after_save()
            page.update()

        dialog = ft.AlertDialog(
            title=ft.Text(f"Registrar {para_br(d)} ({DIAS_SEMANA[d.weekday()]})"),
            content=ft.Column(
                [dropdown_qtd, campo_obs],
                tight=True, spacing=10, width=320,
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e: page.pop_dialog()),
                ft.Button("Salvar", on_click=salvar),
            ],
        )
        page.show_dialog(dialog)

    total = len(faltantes)
    VISIVEIS = 8
    visiveis = faltantes[:VISIVEIS]
    restantes = total - len(visiveis)

    def item_faltante(f: dict) -> ft.Control:
        d = f["data"]
        eventos = f["eventos"]
        texto_data = f"{para_br(d)} ({DIAS_SEMANA[d.weekday()]})"
        chips = [chip_tipo_evento(ev.tipo) for ev in eventos]

        def on_tap(e):
            abrir_registro(d, eventos)

        return ft.Container(
            on_click=on_tap,
            padding=ft.Padding.symmetric(horizontal=10, vertical=8),
            border_radius=8,
            bgcolor=ft.Colors.GREY_100,
            content=ft.Row(
                spacing=8,
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Row(
                        spacing=6,
                        controls=[
                            ft.Text(texto_data, size=13, weight=ft.FontWeight.W_500),
                        ] + chips,
                    ),
                    ft.Icon(ft.Icons.CHEVRON_RIGHT, size=18, color=ft.Colors.GREY_500),
                ],
            ),
        )

    itens_controles = [item_faltante(f) for f in visiveis]
    if restantes > 0:
        itens_controles.append(
            ft.Text(
                f"... e mais {restantes} dia(s). Veja o restante em Histórico.",
                size=12, color=ft.Colors.GREY_600,
            )
        )

    return card(page, ft.Column(
        [
            ft.Row([
                ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED,
                        color=ft.Colors.AMBER_700, size=22),
                ft.Text(
                    f"{total} dia(s) sem registro",
                    size=14, weight=ft.FontWeight.BOLD,
                ),
            ], spacing=8),
            ft.Text(
                "Dias úteis anteriores a hoje, dentro de algum TR, sem produção lançada. "
                "Toque em um dia para registrar.",
                size=11, color=ft.Colors.GREY_600,
            ),
            ft.Container(height=4),
            ft.Column(itens_controles, spacing=6),
        ],
        spacing=6,
    ))