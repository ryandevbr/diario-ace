from datetime import date
import flet as ft

from app.components.formularios import (
    criar_campos_producao,
    extrair_valores_producao,
    resumo_contadores_chips,
)
from app.components.ui import (
    card,
    chip_tipo_evento,
    cor_fundo_item,
    kpi,
    snack,
)
from app.services import (
    atividade_service,
    bairro_service,
    evento_service,
    producao_service,
    tr_service,
)
from app.services.meta_service import meta_do_dia
from app.utils.datas import para_br

DIAS_SEMANA = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]


def build(page: ft.Page) -> ft.Control:
    conteudo = ft.Column(scroll=ft.ScrollMode.AUTO, spacing=0, controls=[])

    def montar() -> None:
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

        # Consulta única do registro de produção de hoje
        prod_hoje = producao_service.producao_completa_do_dia(hoje)
        produzido_hoje = int(prod_hoje.get("quantidade", 0) or 0) if prod_hoje else 0
        totais_hoje = {
            "quantidade": produzido_hoje,
            "fechados": int(prod_hoje.get("fechados", 0) or 0) if prod_hoje else 0,
            "resgatados": int(prod_hoje.get("resgatados", 0) or 0) if prod_hoje else 0,
            "recusados": int(prod_hoje.get("recusados", 0) or 0) if prod_hoje else 0,
        }

        meta_min = info["meta_hoje_min"] or 0
        meta_max = info["meta_hoje_max"] or 0

        if produzido_hoje >= meta_max and meta_max > 0:
            cor_meta = ft.Colors.GREEN_600
            status_meta = "Meta do dia batida!"
            icone_meta = ft.Icons.CHECK_CIRCLE
        elif meta_min > 0 and produzido_hoje >= meta_min:
            cor_meta = ft.Colors.AMBER_700
            status_meta = (
                f"Faltam {max(0, meta_max - produzido_hoje)} para a meta máxima"
            )
            icone_meta = ft.Icons.EMOJI_EVENTS
        else:
            cor_meta = ft.Colors.RED_500
            status_meta = (
                f"Faltam {max(0, meta_min - produzido_hoje)} para a meta mínima"
            )
            icone_meta = ft.Icons.TRENDING_UP

        bairros = bairro_service.listar_ativos()
        atividades = atividade_service.listar()
        campos = criar_campos_producao(
            page,
            bairros,
            atividades,
            valores_iniciais=prod_hoje or {"quantidade": produzido_hoje},
        )

        def persistir_valores_atuais() -> int:
            dados = extrair_valores_producao(campos)
            producao_service.registrar_producao(
                hoje,
                tr.id,
                dados["quantidade"],
                bairro_id=dados["bairro_id"],
                atividade=dados["atividade"],
                fechados=dados["fechados"],
                resgatados=dados["resgatados"],
                recusados=dados["recusados"],
            )
            return dados["quantidade"]

        page._hoje_dropdown = campos["qtd"]
        page._hoje_produzido_salvo = produzido_hoje
        page._hoje_salvar_fn = persistir_valores_atuais

        def salvar(e) -> None:
            try:
                qtd = persistir_valores_atuais()
            except ValueError:
                snack(page, "Selecione um valor válido.", ft.Colors.RED_500)
                return
            snack(page, f"Salvo: {qtd} imóveis em {para_br(hoje)}.")
            montar()
            page.update()

        inicial_visivel = getattr(tr, "producao_inicial", 0) > 0

        widgets: list[ft.Control] = [
            ft.Text("Hoje", size=28, weight=ft.FontWeight.BOLD),
            ft.Text(
                f"{para_br(hoje)} · TR {tr.numero}",
                size=13,
                color=ft.Colors.GREY_600,
            ),
            ft.Container(height=8),
            ft.Row(
                [
                    kpi(
                        page,
                        "Hoje",
                        str(produzido_hoje),
                        "imóveis",
                        cor=ft.Colors.TEAL_700,
                        icone=ft.Icons.HOME,
                    ),
                    kpi(
                        page,
                        "No TR",
                        str(realizado),
                        f"de {tr.meta_min}–{tr.meta_max}",
                        cor=ft.Colors.BLUE_700,
                        icone=ft.Icons.INSIGHTS,
                    ),
                ],
                spacing=10,
            ),
            ft.Text(
                f"Inclui {tr.producao_inicial} imóveis lançados como produção inicial.",
                size=11,
                color=ft.Colors.GREY_600,
                visible=inicial_visivel,
            ),
            resumo_contadores_chips(
                produzido_hoje,
                totais_hoje,
                producao_service.eficiencia_simples,
            ),
            ft.Container(height=8),
            card(
                page,
                ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Icon(icone_meta, color=cor_meta, size=28),
                                ft.Text(
                                    f"Meta de hoje: {meta_min}–{meta_max}",
                                    size=16,
                                    weight=ft.FontWeight.BOLD,
                                ),
                            ],
                            spacing=8,
                        ),
                        ft.Text(status_meta, size=13, color=cor_meta),
                        ft.Divider(height=10, color=ft.Colors.GREY_300),
                        ft.Text(
                            f"Peso do dia: {info['peso_hoje']:.2f}",
                            size=12,
                            color=ft.Colors.GREY_600,
                        ),
                    ],
                    spacing=6,
                ),
            ),
            ft.Container(height=12),
            card(
                page,
                ft.Column(
                    [
                        ft.Text(
                            "Registrar produção",
                            size=14,
                            weight=ft.FontWeight.BOLD,
                        ),
                        campos["bairro_ui"],
                        campos["atividade"],
                        campos["qtd"],
                        campos["linha_contadores"],
                        ft.Button(
                            "Salvar produção",
                            icon=ft.Icons.SAVE,
                            on_click=salvar,
                            style=ft.ButtonStyle(
                                bgcolor=ft.Colors.TEAL_700,
                                color=ft.Colors.WHITE,
                                shape=ft.RoundedRectangleBorder(radius=10),
                                padding=ft.Padding.symmetric(
                                    horizontal=20, vertical=14
                                ),
                            ),
                        ),
                    ],
                    spacing=12,
                ),
            ),
        ]

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


def _card_faltantes(
    page: ft.Page,
    faltantes: list[dict],
    on_after_save,
) -> ft.Control:
    """Card que mostra dias úteis sem produção. Tocar num dia abre o registro."""

    def abrir_registro(d: date) -> None:
        tr = tr_service.tr_por_data(d)
        if tr is None:
            snack(page, "Sem TR cadastrado para essa data.", ft.Colors.RED_500)
            return

        dropdown_qtd = ft.Dropdown(
            label="Imóveis visitados",
            options=[
                ft.dropdown.Option(key=str(n), text=str(n))
                for n in range(0, 41)
            ],
            value="0",
        )
        campo_obs = ft.TextField(label="Observação (opcional)", value="")

        def salvar(ev) -> None:
            try:
                qtd = int(dropdown_qtd.value or "0")
            except ValueError:
                return
            producao_service.registrar_producao(
                d,
                tr.id,
                qtd,
                obs=campo_obs.value.strip() or None,
            )
            page.pop_dialog()
            snack(page, f"Salvo: {qtd} imóveis em {para_br(d)}.")
            on_after_save()
            page.update()

        dialog = ft.AlertDialog(
            title=ft.Text(
                f"Registrar {para_br(d)} ({DIAS_SEMANA[d.weekday()]})"
            ),
            content=ft.Column(
                [dropdown_qtd, campo_obs],
                tight=True,
                spacing=10,
                width=320,
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e: page.pop_dialog()),
                ft.Button("Salvar", on_click=salvar),
            ],
        )
        page.show_dialog(dialog)

    total = len(faltantes)
    visiveis = faltantes[:8]
    restantes = total - len(visiveis)
    fundo_item = cor_fundo_item(page)

    def item_faltante(f: dict) -> ft.Control:
        d = f["data"]
        eventos = f["eventos"]
        texto_data = f"{para_br(d)} ({DIAS_SEMANA[d.weekday()]})"
        chips = [chip_tipo_evento(ev.tipo) for ev in eventos]

        return ft.Container(
            on_click=lambda e, dt=d: abrir_registro(dt),
            padding=ft.Padding.symmetric(horizontal=10, vertical=8),
            border_radius=8,
            bgcolor=fundo_item,
            content=ft.Row(
                spacing=8,
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Row(
                        spacing=6,
                        controls=[
                            ft.Text(
                                texto_data,
                                size=13,
                                weight=ft.FontWeight.W_500,
                            ),
                            *chips,
                        ],
                    ),
                    ft.Icon(
                        ft.Icons.CHEVRON_RIGHT,
                        size=18,
                        color=ft.Colors.GREY_500,
                    ),
                ],
            ),
        )

    itens_controles = [item_faltante(f) for f in visiveis]
    if restantes > 0:
        itens_controles.append(
            ft.Text(
                f"... e mais {restantes} dia(s). Veja o restante em Histórico.",
                size=12,
                color=ft.Colors.GREY_600,
            )
        )

    return card(
        page,
        ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(
                            ft.Icons.WARNING_AMBER_ROUNDED,
                            color=ft.Colors.AMBER_700,
                            size=22,
                        ),
                        ft.Text(
                            f"{total} dia(s) sem registro",
                            size=14,
                            weight=ft.FontWeight.BOLD,
                        ),
                    ],
                    spacing=8,
                ),
                ft.Text(
                    "Dias úteis anteriores a hoje, dentro de algum TR, sem produção lançada. "
                    "Toque em um dia para registrar.",
                    size=11,
                    color=ft.Colors.GREY_600,
                ),
                ft.Container(height=4),
                ft.Column(itens_controles, spacing=6),
            ],
            spacing=6,
        ),
    )
