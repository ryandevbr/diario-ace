from datetime import date
import flet as ft

from app.components.formularios import (
    criar_campos_producao,
    extrair_valores_producao,
    resumo_contadores_texto,
)
from app.components.ui import cor_fundo_card, snack
from app.services import atividade_service, bairro_service, producao_service
from app.utils.datas import para_br


def criar_item_producao(
    page: ft.Page,
    p: dict,
    bairros_map: dict[int, str],
    recarregar,
) -> ft.Control:
    """Cria o card de um lançamento diário no Histórico."""
    bairro_nome = (
        bairros_map.get(p["bairro_id"]) if p.get("bairro_id") else None
    )
    atividade = p.get("atividade")

    def abrir_edicao(e) -> None:
        bairros = bairro_service.listar_ativos()
        atividades = atividade_service.listar()
        campos = criar_campos_producao(
            page,
            bairros,
            atividades,
            valores_iniciais=p,
            label_qtd="Quantidade",
        )
        erro = ft.Text("", color=ft.Colors.RED)

        def salvar(ev) -> None:
            try:
                dados = extrair_valores_producao(campos)
            except ValueError:
                erro.value = "Valor inválido."
                page.update()
                return

            producao_service.atualizar_producao_completa(
                p["id"],
                dados["quantidade"],
                bairro_id=dados["bairro_id"],
                atividade=dados["atividade"],
                fechados=dados["fechados"],
                resgatados=dados["resgatados"],
                recusados=dados["recusados"],
                observacao=dados["observacao"],
            )

            page.pop_dialog()
            snack(
                page,
                f"Lançamento de {para_br(date.fromisoformat(p['data']))} atualizado.",
            )
            recarregar()
            page.update()

        dialog = ft.AlertDialog(
            title=ft.Text(f"Editar {para_br(date.fromisoformat(p['data']))}"),
            content=ft.Column(
                [
                    campos["bairro_ui"],
                    campos["atividade"],
                    campos["qtd"],
                    campos["linha_contadores"],
                    campos["obs"],
                    erro,
                ],
                tight=True,
                spacing=10,
                width=420,
            ),
            actions=[
                ft.TextButton(
                    "Cancelar", on_click=lambda ev: page.pop_dialog()
                ),
                ft.Button("Salvar", on_click=salvar),
            ],
        )
        page.show_dialog(dialog)

    def abrir_confirmacao(e) -> None:
        def confirmar(ev):
            producao_service.remover_producao(p["id"])
            page.pop_dialog()
            snack(
                page,
                f"Lançamento de {para_br(date.fromisoformat(p['data']))} removido.",
                ft.Colors.ORANGE_600,
            )
            recarregar()
            page.update()

        dialog = ft.AlertDialog(
            title=ft.Text("Excluir lançamento?"),
            content=ft.Text(
                f"Produção de {para_br(date.fromisoformat(p['data']))} — "
                f"{p['quantidade']} imóveis."
            ),
            actions=[
                ft.TextButton(
                    "Cancelar", on_click=lambda ev: page.pop_dialog()
                ),
                ft.Button("Excluir", on_click=confirmar),
            ],
        )
        page.show_dialog(dialog)

    obs_txt = p.get("observacao") or ""
    return ft.Container(
        padding=12,
        bgcolor=cor_fundo_card(page, "item"),
        border=ft.Border.all(1, ft.Colors.GREY_600),
        border_radius=10,
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Column(
                    [
                        ft.Text(
                            para_br(date.fromisoformat(p["data"])),
                            weight=ft.FontWeight.BOLD,
                        ),
                        ft.Text(
                            f"{bairro_nome or '—'} · {atividade or '—'}",
                            size=12,
                            color=ft.Colors.GREY_500,
                        ),
                        ft.Text(f"{p['quantidade']} imóveis", size=13),
                        resumo_contadores_texto(
                            p, producao_service.eficiencia_simples
                        ),
                        (
                            ft.Text(obs_txt, size=12, color=ft.Colors.GREY_500)
                            if obs_txt
                            else ft.Text("")
                        ),
                    ],
                    spacing=2,
                    expand=True,
                ),
                ft.Row(
                    [
                        ft.IconButton(
                            icon=ft.Icons.EDIT_OUTLINED,
                            icon_color=ft.Colors.BLUE_400,
                            on_click=abrir_edicao,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DELETE_OUTLINE,
                            icon_color=ft.Colors.RED_400,
                            on_click=abrir_confirmacao,
                        ),
                    ],
                    spacing=0,
                ),
            ],
        ),
    )


def _iso_semana(d_str: str) -> tuple[int, int]:
    """Retorna (ano_iso, numero_semana)."""
    d = date.fromisoformat(d_str)
    iso = d.isocalendar()
    return iso[0], iso[1]


def montar_visao_semanal(
    producoes: list[dict],
    bairros_map: dict[int, str],
    lista_widget: ft.Column,
) -> None:
    """Agrupa produções por semana ISO e adiciona cards semanais em lista_widget."""
    semanas: dict[tuple[int, int], list[dict]] = {}
    for p in producoes:
        chave = _iso_semana(p["data"])
        semanas.setdefault(chave, []).append(p)

    fundo_semana = getattr(ft.Colors, "SURFACE_VARIANT", ft.Colors.GREY_100)

    for chave in sorted(semanas.keys(), reverse=True):
        itens = sorted(semanas[chave], key=lambda x: x["data"])
        total = sum(i["quantidade"] for i in itens)
        fechados = sum(i.get("fechados", 0) or 0 for i in itens)
        resgatados = sum(i.get("resgatados", 0) or 0 for i in itens)
        recusados = sum(i.get("recusados", 0) or 0 for i in itens)
        dias_uteis = sum(1 for i in itens if i["quantidade"] > 0)

        efic = producao_service.eficiencia_simples(total, fechados, recusados)

        bairros_da_semana = sorted(
            {
                bairros_map.get(i.get("bairro_id"), "—")
                for i in itens
                if i.get("bairro_id")
            }
        )
        atividades_da_semana = sorted(
            {i.get("atividade") for i in itens if i.get("atividade")}
        )

        primeira = min(i["data"] for i in itens)
        ultima = max(i["data"] for i in itens)
        ano, num = chave
        titulo = (
            f"Semana {num:02d}/{ano}  ·  "
            f"{para_br(date.fromisoformat(primeira))} a "
            f"{para_br(date.fromisoformat(ultima))}"
        )

        linhas_extras: list[ft.Control] = []
        if bairros_da_semana:
            linhas_extras.append(
                ft.Text(
                    "Bairros: " + ", ".join(bairros_da_semana),
                    size=11,
                    color=ft.Colors.GREY_500,
                )
            )
        if atividades_da_semana:
            linhas_extras.append(
                ft.Text(
                    "Atividades: " + ", ".join(atividades_da_semana),
                    size=11,
                    color=ft.Colors.GREY_500,
                )
            )
        if fechados or resgatados or recusados:
            linhas_extras.append(
                ft.Text(
                    f"F: {fechados} · R: {resgatados} · Re: {recusados} · "
                    f"Eficiência: {efic:.0f}%",
                    size=11,
                    color=ft.Colors.GREY_500,
                )
            )

        lista_widget.controls.append(
            ft.Container(
                padding=12,
                bgcolor=fundo_semana,
                border=ft.Border.all(1, ft.Colors.GREY_300),
                border_radius=10,
                content=ft.Column(
                    [
                        ft.Text(titulo, weight=ft.FontWeight.BOLD, size=13),
                        ft.Text(
                            f"{total} imóveis em {dias_uteis} dia(s) de produção",
                            size=13,
                        ),
                        *linhas_extras,
                    ],
                    spacing=3,
                ),
            )
        )

