from datetime import date
import flet as ft

from app.components.ui import (
    CORES_TIPO_EVENTO,
    TIPOS_EVENTO,
    campo_data_picker,
    chip_tipo_evento,
    snack,
)
from app.services import banco_horas_service, evento_service, tr_service
from app.utils.datas import de_br, para_br

FRACOES = [
    ("1.0", "Dia todo / ausente"),
    ("0.5", "Meio período"),
    ("0.25", "Um quarto do dia"),
]


def build(page: ft.Page) -> ft.Control:
    hoje = date.today()
    tr = tr_service.tr_por_data(hoje)

    if tr is None:
        return ft.Container(
            padding=20, content=ft.Text("Sem TR ativo para hoje.")
        )

    campo_data, linha_data = campo_data_picker(page, hoje)

    dropdown_tipo = ft.Dropdown(
        label="Tipo",
        options=[ft.dropdown.Option(key=k, text=v) for k, v in TIPOS_EVENTO],
        value="reuniao",
    )
    dropdown_fracao = ft.Dropdown(
        label="Duração",
        options=[ft.dropdown.Option(key=k, text=v) for k, v in FRACOES],
        value="0.5",
    )
    campo_obs = ft.TextField(label="Observação (opcional)")
    lista_eventos = ft.Column(spacing=8)

    def carregar_eventos() -> None:
        lista_eventos.controls.clear()
        eventos = evento_service.listar_eventos_do_tr(tr)
        if not eventos:
            lista_eventos.controls.append(
                ft.Text(
                    "Nenhum evento cadastrado neste TR.",
                    color=ft.Colors.GREY_600,
                )
            )
            return
        for ev in eventos:
            cor = CORES_TIPO_EVENTO.get(ev.tipo, ft.Colors.GREY_500)

            def remover(e, ev_id=ev.id):
                evento_service.remover_evento(ev_id)
                snack(page, "Evento removido.", ft.Colors.ORANGE_600)
                carregar_eventos()
                page.update()

            detalhes: list[ft.Control] = [
                ft.Row(
                    [
                        ft.Text(
                            para_br(ev.data),
                            weight=ft.FontWeight.BOLD,
                            size=14,
                        ),
                        chip_tipo_evento(ev.tipo),
                    ],
                    spacing=8,
                ),
                ft.Text(
                    f"Duração: {ev.fracao}",
                    size=12,
                    color=ft.Colors.GREY_600,
                ),
            ]
            if ev.observacao:
                detalhes.append(
                    ft.Text(ev.observacao, size=11, color=ft.Colors.GREY_500)
                )

            lista_eventos.controls.append(
                ft.Container(
                    padding=12,
                    bgcolor=ft.Colors.SURFACE,
                    border_radius=10,
                    border=ft.Border.all(1, ft.Colors.GREY_200),
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Container(
                                width=4,
                                height=40,
                                bgcolor=cor,
                                border_radius=2,
                            ),
                            ft.Column(detalhes, spacing=2, expand=True),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE,
                                icon_color=ft.Colors.RED_400,
                                on_click=remover,
                            ),
                        ],
                        spacing=10,
                    ),
                )
            )

    def salvar(e) -> None:
        try:
            d = de_br(campo_data.value)
        except ValueError:
            snack(
                page,
                "Data inválida. Use o formato DD/MM/AAAA.",
                ft.Colors.RED_500,
            )
            return

        try:
            fracao = float(dropdown_fracao.value)
        except (TypeError, ValueError):
            fracao = 1.0

        obs = (campo_obs.value or "").strip() or None
        evento_service.adicionar_evento(d, dropdown_tipo.value, fracao, obs)

        if dropdown_tipo.value == "compensacao":
            _sugerir_lancamento_bh(page, d, fracao, obs)
            campo_obs.value = ""
            carregar_eventos()
            page.update()
            return

        snack(page, f"Evento salvo em {para_br(d)}.")
        campo_obs.value = ""
        carregar_eventos()
        page.update()

    carregar_eventos()

    return ft.Column(
        scroll=ft.ScrollMode.AUTO,
        controls=[
            ft.Container(
                padding=20,
                content=ft.Column(
                    [
                        ft.Text(
                            "Calendário", size=22, weight=ft.FontWeight.BOLD
                        ),
                        ft.Text(
                            f"TR {tr.numero} — {para_br(tr.data_inicio)} a {para_br(tr.data_fim)}"
                        ),
                        ft.Divider(),
                        linha_data,
                        dropdown_tipo,
                        dropdown_fracao,
                        campo_obs,
                        ft.Button("Adicionar evento", on_click=salvar),
                        ft.Divider(),
                        ft.Text("Eventos do TR", weight=ft.FontWeight.BOLD),
                        lista_eventos,
                    ]
                ),
            )
        ],
    )


def _sugerir_lancamento_bh(
    page: ft.Page,
    d: date,
    fracao: float,
    obs: str | None,
) -> None:
    """Depois de registrar um evento de compensação, sugere lançar no BH."""
    horas = fracao * 8.0

    def confirmar(ev):
        page.pop_dialog()
        try:
            banco_horas_service.adicionar(
                d,
                horas,
                "compensacao",
                obs or "Folga referente ao banco de horas",
            )
            atualizar_hdr = getattr(page, "_atualizar_header_bh", None)
            if callable(atualizar_hdr):
                atualizar_hdr()
            snack(
                page,
                f"Lançado no BH: −{banco_horas_service.formatar_horas(horas)}.",
            )
            page.update()
        except Exception as ex:
            snack(page, f"Erro ao lançar no BH: {ex}", ft.Colors.RED_500)

    dialog = ft.AlertDialog(
        title=ft.Text("Lançar no banco de horas?"),
        content=ft.Text(
            f"Esse evento representa −{banco_horas_service.formatar_horas(horas)} "
            f"({fracao:.2f} dia) de compensação. Deseja lançar também no banco de horas?"
        ),
        actions=[
            ft.TextButton("Não", on_click=lambda ev: page.pop_dialog()),
            ft.Button("Sim, lançar", on_click=confirmar),
        ],
    )
    page.show_dialog(dialog)
