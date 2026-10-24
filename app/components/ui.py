from datetime import date
import flet as ft

from app.utils.datas import escolher_data, para_br

TIPOS_EVENTO: list[tuple[str, str]] = [
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

LABEL_TIPO_EVENTO: dict[str, str] = dict(TIPOS_EVENTO)

CORES_TIPO_EVENTO: dict[str, str] = {
    "feriado": ft.Colors.RED_400,
    "ferias": ft.Colors.GREEN_400,
    "atestado": ft.Colors.ORANGE_400,
    "reuniao": ft.Colors.BLUE_400,
    "capacitacao": ft.Colors.PURPLE_400,
    "folga": ft.Colors.TEAL_400,
    "chuva": ft.Colors.INDIGO_400,
    "deslocamento": ft.Colors.BROWN_400,
    "mudanca_atividade": ft.Colors.CYAN_600,
    "compensacao": ft.Colors.LIME_700,
    "resgate_vacinacao": ft.Colors.PINK_400,
    "outro": ft.Colors.GREY_500,
}

ICONES_TIPO_EVENTO: dict[str, str] = {
    "feriado": ft.Icons.EVENT,
    "ferias": ft.Icons.BEACH_ACCESS,
    "atestado": ft.Icons.SICK,
    "reuniao": ft.Icons.GROUPS,
    "capacitacao": ft.Icons.SCHOOL,
    "folga": ft.Icons.WEEKEND,
    "chuva": ft.Icons.CLOUD,
    "deslocamento": ft.Icons.DIRECTIONS_CAR,
    "mudanca_atividade": ft.Icons.SWAP_HORIZ,
    "compensacao": ft.Icons.SCHEDULE,
    "resgate_vacinacao": ft.Icons.VACCINES,
    "outro": ft.Icons.MORE_HORIZ,
}

MAPA_THEME_MODE: dict[str, ft.ThemeMode] = {
    "light": ft.ThemeMode.LIGHT,
    "dark": ft.ThemeMode.DARK,
    "system": ft.ThemeMode.SYSTEM,
}


def resolver_theme_mode(modo: str | None) -> ft.ThemeMode:
    """Converte string ('light', 'dark', 'system') para ft.ThemeMode."""
    return MAPA_THEME_MODE.get(modo or "system", ft.ThemeMode.SYSTEM)


def tema_escuro_ativo(page: ft.Page) -> bool:
    """Indica se o tema efetivo atual da página é escuro."""
    if page.theme_mode == ft.ThemeMode.DARK:
        return True
    if page.theme_mode == ft.ThemeMode.LIGHT:
        return False
    brilho = getattr(page, "platform_brightness", None)
    return brilho == ft.Brightness.DARK


def cor_fundo_card(page: ft.Page, nivel: str = "principal") -> str:
    """Cor de fundo adaptada ao tema atual ('principal' ou 'item')."""
    escuro = tema_escuro_ativo(page)
    if escuro:
        return ft.Colors.GREY_800 if nivel == "principal" else ft.Colors.GREY_700
    return ft.Colors.WHITE if nivel == "principal" else ft.Colors.GREY_100


def cor_fundo_item(page: ft.Page) -> str:
    """Cor de fundo para itens internos de listas (cards), adaptada ao tema."""
    return cor_fundo_card(page, nivel="item")


def card(
    page: ft.Page,
    conteudo: ft.Control,
    cor_fundo: str | None = None,
) -> ft.Container:
    """Card padrão com sombra suave e cantos arredondados."""
    if cor_fundo is None:
        if page.theme_mode == ft.ThemeMode.DARK:
            cor_fundo = ft.Colors.GREY_800
        elif page.theme_mode == ft.ThemeMode.LIGHT:
            cor_fundo = ft.Colors.WHITE
        else:
            cor_fundo = getattr(ft.Colors, "SURFACE", ft.Colors.WHITE)

    return ft.Container(
        content=conteudo,
        padding=16,
        bgcolor=cor_fundo,
        border_radius=12,
        shadow=ft.BoxShadow(
            blur_radius=6,
            spread_radius=0,
            color=ft.Colors.with_opacity(0.08, ft.Colors.BLACK),
            offset=ft.Offset(0, 2),
        ),
    )


def kpi(
    page: ft.Page,
    titulo: str,
    valor: str,
    subtitulo: str = "",
    cor: str = ft.Colors.TEAL_700,
    icone: str | None = None,
) -> ft.Control:
    linha_topo: list[ft.Control] = [
        ft.Text(
            titulo,
            size=12,
            color=ft.Colors.GREY_600,
            weight=ft.FontWeight.W_500,
        ),
    ]
    if icone:
        linha_topo.append(ft.Icon(icone, size=16, color=cor))

    conteudo: list[ft.Control] = [
        ft.Row(linha_topo, alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ft.Text(valor, size=26, weight=ft.FontWeight.BOLD, color=cor),
    ]
    if subtitulo:
        conteudo.append(ft.Text(subtitulo, size=11, color=ft.Colors.GREY_600))

    return card(page, ft.Column(conteudo, spacing=4))


def barra_progresso(
    percentual: float,
    cor: str = ft.Colors.TEAL_600,
) -> ft.Control:
    """ProgressBar com percentual textual."""
    pct = max(0.0, min(1.0, percentual / 100))
    return ft.Column(
        [
            ft.Row(
                [
                    ft.Text(
                        f"{percentual:.1f}%",
                        size=14,
                        weight=ft.FontWeight.BOLD,
                        color=cor,
                    ),
                ],
                alignment=ft.MainAxisAlignment.END,
            ),
            ft.ProgressBar(
                value=pct,
                color=cor,
                bgcolor=ft.Colors.GREY_200,
                height=10,
                border_radius=6,
            ),
        ],
        spacing=4,
    )


def chip_tipo_evento(tipo: str) -> ft.Control:
    """Chip colorido com ícone, usado na lista de eventos."""
    cor = CORES_TIPO_EVENTO.get(tipo, ft.Colors.GREY_500)
    icone = ICONES_TIPO_EVENTO.get(tipo, ft.Icons.CIRCLE)
    label = LABEL_TIPO_EVENTO.get(tipo, tipo.capitalize())
    return ft.Container(
        content=ft.Row(
            [
                ft.Icon(icone, size=14, color=ft.Colors.WHITE),
                ft.Text(
                    label,
                    size=11,
                    color=ft.Colors.WHITE,
                    weight=ft.FontWeight.W_600,
                ),
            ],
            spacing=4,
            tight=True,
        ),
        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
        bgcolor=cor,
        border_radius=20,
    )


def snack(
    page: ft.Page,
    mensagem: str,
    cor: str = ft.Colors.GREEN_600,
) -> None:
    """Mostra um SnackBar no rodapé."""
    page.show_dialog(
        ft.SnackBar(
            content=ft.Text(mensagem, color=ft.Colors.WHITE),
            bgcolor=cor,
            duration=2500,
        )
    )


def campo_data_picker(
    page: ft.Page,
    valor_inicial: date,
    label: str = "Data (DD/MM/AAAA)",
    tooltip: str = "Escolher data",
) -> tuple[ft.TextField, ft.Row]:
    """Cria um TextField de data somente-leitura acompanhado de botão de calendário."""
    campo = ft.TextField(
        label=label,
        value=para_br(valor_inicial),
        read_only=True,
        expand=True,
    )

    def abrir(e):
        def ao_escolher(d: date):
            campo.value = para_br(d)
            page.update()

        escolher_data(page, ao_escolher)

    linha = ft.Row(
        [
            campo,
            ft.IconButton(
                icon=ft.Icons.CALENDAR_MONTH,
                tooltip=tooltip,
                on_click=abrir,
            ),
        ],
        spacing=4,
    )
    return campo, linha
