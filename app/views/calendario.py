from datetime import date
import flet as ft

from app.services import tr_service, evento_service
from app.utils.datas import para_br, de_br, escolher_data
from app.components.ui import snack, chip_tipo_evento, CORES_TIPO_EVENTO

TIPOS = [
    ("feriado", "Feriado"),
    ("ferias", "Férias"),
    ("atestado", "Atestado"),
    ("reuniao", "Reunião"),
    ("capacitacao", "Capacitação"),
    ("folga", "Folga"),
    ("chuva", "Chuva"),
    ("deslocamento", "Deslocamento"),
    ("mudanca_atividade", "Mudança de Atividade"),
    ("compensacao", "Compensação de Hora-Extra"),
    ("resgate_vacinacao", "Resgate de Vacinação Antirrábica"),
    ("outro", "Outro"),
]

FRACOES = [
    ("1.0", "Dia todo / ausente"),
    ("0.5", "Meio período"),
    ("0.25", "Um quarto do dia"),
]


def build(page: ft.Page) -> ft.Control:
    hoje = date.today()
    tr = tr_service.tr_por_data(hoje)

    if tr is None:
        return ft.Container(padding=20, content=ft.Text("Sem TR ativo para hoje."))

    campo_data = ft.TextField(
        label="Data (DD/MM/AAAA)",
        value=para_br(hoje),
        read_only=True,
        expand=True,
    )

    def abrir_calendario(e):
        def ao_escolher(d):
            campo_data.value = para_br(d)
            page.update()
        escolher_data(page, ao_escolher)

    dropdown_tipo = ft.Dropdown(
        label="Tipo",
        options=[ft.dropdown.Option(key=k, text=v) for k, v in TIPOS],
        value="reuniao",
    )
    dropdown_fracao = ft.Dropdown(
        label="Duração",
        options=[ft.dropdown.Option(key=k, text=v) for k, v in FRACOES],
        value="0.5",
    )
    campo_obs = ft.TextField(label="Observação (opcional)")

    lista_eventos = ft.Column(spacing=8)

    def carregar_eventos():
        lista_eventos.controls.clear()
        eventos = evento_service.listar_eventos_do_tr(tr)
        if not eventos:
            lista_eventos.controls.append(
                ft.Text("Nenhum evento cadastrado neste TR.", color=ft.Colors.GREY_600)
            )
            return
        for ev in eventos:
            cor = CORES_TIPO_EVENTO.get(ev.tipo, ft.Colors.GREY_500)

            def remover(e, ev_id=ev.id):
                evento_service.remover_evento(ev_id)
                snack(page, "Evento removido.", ft.Colors.ORANGE_600)
                carregar_eventos()
                page.update()

            detalhes = [
                ft.Row([
                    ft.Text(para_br(ev.data), weight=ft.FontWeight.BOLD, size=14),
                    chip_tipo_evento(ev.tipo),
                ], spacing=8),
                ft.Text(f"Duração: {ev.fracao}", size=12, color=ft.Colors.GREY_600),
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
                            ft.Container(width=4, height=40, bgcolor=cor, border_radius=2),
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

    def salvar(e):
        try:
            d = de_br(campo_data.value)
        except ValueError:
            snack(page, "Data inválida. Use o formato DD/MM/AAAA.", ft.Colors.RED_500)
            return

        try:
            fracao = float(dropdown_fracao.value)
        except (TypeError, ValueError):
            fracao = 1.0

        evento_service.adicionar_evento(
            d, dropdown_tipo.value, fracao, campo_obs.value.strip() or None
        )

        # Se for compensação, sugere lançar no banco de horas
        if dropdown_tipo.value == "compensacao":
            _sugerir_lancamento_bh(page, d, fracao, campo_obs.value.strip() or None)
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
                content=ft.Column([
                    ft.Text("Calendário", size=22, weight=ft.FontWeight.BOLD),
                    ft.Text(f"TR {tr.numero} — {para_br(tr.data_inicio)} a {para_br(tr.data_fim)}"),
                    ft.Divider(),
                    ft.Row([
                        campo_data,
                        ft.IconButton(
                            icon=ft.Icons.CALENDAR_MONTH,
                            tooltip="Escolher data",
                            on_click=abrir_calendario,
                        ),
                    ], spacing=4),
                    dropdown_tipo,
                    dropdown_fracao,
                    campo_obs,
                    ft.Button("Adicionar evento", on_click=salvar),
                    ft.Divider(),
                    ft.Text("Eventos do TR", weight=ft.FontWeight.BOLD),
                    lista_eventos,
                ]),
            )
        ],
    )

def _sugerir_lancamento_bh(page: ft.Page, d, fracao: float, obs: str | None):
    """Depois de registrar um evento de compensação, sugere lançar no BH."""
    from app.services import banco_horas_service

    horas = fracao * 8.0

    def confirmar(ev):
        page.pop_dialog()
        try:
            banco_horas_service.adicionar(
                d, horas, "compensacao",
                obs or "Folga referente ao banco de horas",
            )
            snack(page, f"Lançado no BH: −{banco_horas_service.formatar_horas(horas)}.")
        except Exception as ex:
            snack(page, f"Erro ao lançar no BH: {ex}", ft.Colors.RED_500)

    def ignorar(ev):
        page.pop_dialog()

    dialog = ft.AlertDialog(
        title=ft.Text("Lançar no banco de horas?"),
        content=ft.Text(
            f"Esse evento representa −{banco_horas_service.formatar_horas(horas)} "
            f"({fracao:.2f} dia) de compensação. Deseja lançar também no banco de horas?"
        ),
        actions=[
            ft.TextButton("Não", on_click=ignorar),
            ft.Button("Sim, lançar", on_click=confirmar),
        ],
    )
    page.show_dialog(dialog)