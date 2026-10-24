from datetime import date
import flet as ft

from app.components.ui import card, snack
from app.services import pdf_service, recuperacao_service, tr_service
from app.utils.datas import para_br
from app.utils.share import compartilhar_ou_salvar_pdf, salvar_pdf_com_picker

CORES_STATUS = {
    "fechado": ft.Colors.RED_500,
    "atendida": ft.Colors.GREEN_600,
    "abandonada": ft.Colors.GREY_600,
    "recusado": ft.Colors.ORANGE_700,
}

LABEL_STATUS = {
    "fechado": "Fechado",
    "atendida": "Atendida",
    "abandonada": "Abandonada",
    "recusado": "Recusado",
}

LADOS = [f"Lado {i}" for i in range(1, 9)]
QUARTEIROES = [str(i) for i in range(1, 61)]

FUNDO_INATIVO = getattr(ft.Colors, "SURFACE_VARIANT", ft.Colors.GREY_100)
TEXTO_SECUNDARIO = getattr(ft.Colors, "ON_SURFACE_VARIANT", ft.Colors.GREY_700)
PEQUENAS_PREPOSICOES = {
    "de",
    "da",
    "do",
    "das",
    "dos",
    "e",
    "a",
    "o",
    "as",
    "os",
    "na",
    "no",
}


def capitalizar_rua(s: str) -> str:
    """Capitaliza cada palavra, exceto preposições curtas no meio."""
    palavras = s.strip().split()
    if not palavras:
        return ""
    resultado = []
    for i, p in enumerate(palavras):
        if i == 0:
            resultado.append(p.capitalize())
        elif p.lower() in PEQUENAS_PREPOSICOES:
            resultado.append(p.lower())
        else:
            resultado.append(p.capitalize())
    return " ".join(resultado)


def build(page: ft.Page) -> ft.Control:
    hoje = date.today()
    tr = tr_service.tr_por_data(hoje)
    if tr is None:
        return ft.Container(
            padding=20, content=ft.Text("Sem TR ativo para hoje.")
        )

    filtro_atual: dict[str, str | None] = {"status": None, "quarteirao": None}

    filtros_btns = ft.Row(spacing=6, wrap=True)
    lista = ft.Column(spacing=8, controls=[])
    resumo = ft.Text("", size=13, color=TEXTO_SECUNDARIO)

    filtro_quarteirao_dd = ft.Dropdown(
        label="Filtrar por quarteirão",
        options=[ft.dropdown.Option(key="", text="Todos")],
        value="",
        width=200,
    )

    def on_quarteirao_change(e) -> None:
        v = filtro_quarteirao_dd.value or ""
        filtro_atual["quarteirao"] = v or None
        recarregar()

    filtro_quarteirao_dd.on_select = on_quarteirao_change

    def _filtrar_itens(todos: list[dict]) -> list[dict]:
        itens = todos
        if filtro_atual["status"]:
            itens = [
                it for it in itens if it["status"] == filtro_atual["status"]
            ]
        if filtro_atual["quarteirao"]:
            itens = [
                it
                for it in itens
                if it.get("quarteirao") == filtro_atual["quarteirao"]
            ]
        return itens

    def montar_filtros(todos: list[dict], contagem: dict[str, int]) -> None:
        filtros_btns.controls.clear()
        opcoes = [
            (None, "Todas", ft.Colors.TEAL_700),
            (
                "fechado",
                f"Fechadas ({contagem.get('fechado', 0)})",
                CORES_STATUS["fechado"],
            ),
            (
                "atendida",
                f"Atendidas ({contagem.get('atendida', 0)})",
                CORES_STATUS["atendida"],
            ),
            (
                "abandonada",
                f"Abandonadas ({contagem.get('abandonada', 0)})",
                CORES_STATUS["abandonada"],
            ),
            (
                "recusado",
                f"Recusados ({contagem.get('recusado', 0)})",
                CORES_STATUS["recusado"],
            ),
        ]
        for valor, label, cor in opcoes:
            ativo = filtro_atual["status"] == valor
            filtros_btns.controls.append(
                ft.TextButton(
                    label,
                    on_click=lambda e, v=valor: definir_filtro(v),
                    style=ft.ButtonStyle(
                        bgcolor=cor if ativo else FUNDO_INATIVO,
                        color=ft.Colors.WHITE if ativo else cor,
                        shape=ft.RoundedRectangleBorder(radius=20),
                        padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                    ),
                )
            )

        quarteiroes = sorted(
            {it.get("quarteirao") for it in todos if it.get("quarteirao")},
            key=lambda q: int(q) if str(q).isdigit() else 0,
        )
        filtro_quarteirao_dd.options = [
            ft.dropdown.Option(key="", text="Todos"),
            *[ft.dropdown.Option(key=q, text=f"Quadra {q}") for q in quarteiroes],
        ]
        if filtro_atual["quarteirao"] in quarteiroes:
            filtro_quarteirao_dd.value = filtro_atual["quarteirao"]
        else:
            filtro_atual["quarteirao"] = None
            filtro_quarteirao_dd.value = ""

    def definir_filtro(valor: str | None) -> None:
        filtro_atual["status"] = valor
        recarregar()

    def montar_resumo(contagem: dict[str, int]) -> None:
        total = sum(contagem.values())
        resumo.value = (
            f"Total no TR: {total} endereços — "
            f"{contagem.get('fechado', 0)} fechados, "
            f"{contagem.get('atendida', 0)} atendidos, "
            f"{contagem.get('abandonada', 0)} abandonados."
        )

    def montar_lista(itens_filtrados: list[dict]) -> None:
        lista.controls.clear()
        if not itens_filtrados:
            lista.controls.append(
                ft.Text(
                    "Nenhum endereço cadastrado nesta categoria.",
                    color=TEXTO_SECUNDARIO,
                )
            )
            return
        for item in itens_filtrados:
            lista.controls.append(_item_recuperacao(page, item, recarregar))

    def _itens_e_nome_pdf() -> tuple[list[dict], str]:
        todos = recuperacao_service.listar_por_tr(tr.id, None)
        itens = _filtrar_itens(todos)
        partes = []
        if filtro_atual["status"]:
            partes.append(filtro_atual["status"])
        if filtro_atual["quarteirao"]:
            partes.append(f"q{filtro_atual['quarteirao']}")
        sufixo = f"_{'_'.join(partes)}" if partes else ""
        nome = f"recuperacao_TR{tr.numero}{sufixo}_{date.today().isoformat()}.pdf"
        return itens, nome

    async def exportar_pdf(e) -> None:
        try:
            itens, nome = _itens_e_nome_pdf()
            await salvar_pdf_com_picker(
                page,
                nome,
                lambda caminho: pdf_service.exportar_recuperacao_pdf(
                    caminho, tr, itens
                ),
            )
        except Exception as ex:
            snack(page, f"Erro ao gerar PDF: {ex}", ft.Colors.RED_500)

    async def compartilhar_pdf(e) -> None:
        try:
            itens, nome = _itens_e_nome_pdf()
            await compartilhar_ou_salvar_pdf(
                page,
                nome,
                f"Recuperação TR {tr.numero}",
                lambda caminho: pdf_service.exportar_recuperacao_pdf(
                    caminho, tr, itens
                ),
            )
        except Exception as ex:
            snack(page, f"Erro ao compartilhar: {ex}", ft.Colors.RED_500)

    def recarregar() -> None:
        # Consulta única ao banco por atualização de tela
        todos = recuperacao_service.listar_por_tr(tr.id, None)
        contagem: dict[str, int] = {}
        for it in todos:
            st = it["status"]
            contagem[st] = contagem.get(st, 0) + 1

        montar_resumo(contagem)
        montar_filtros(todos, contagem)
        montar_lista(_filtrar_itens(todos))
        page.update()

    form_quarteirao_dd = ft.Dropdown(
        label="Quarteirão",
        options=[ft.dropdown.Option(key=q, text=q) for q in QUARTEIROES],
        value="1",
        width=140,
    )
    form_lado_dd = ft.Dropdown(
        label="Lado",
        options=[ft.dropdown.Option(key=l, text=l) for l in LADOS],
        value="Lado 1",
        width=140,
    )
    campo_rua = ft.TextField(label="Rua (ex.: Guanabara)")
    campo_numero = ft.TextField(label="Número (ex.: 130A, 130/1)")
    campo_obs = ft.TextField(label="Observação (opcional)")

    def salvar(e) -> None:
        rua = (campo_rua.value or "").strip()
        numero = (campo_numero.value or "").strip()
        if not rua or not numero:
            snack(page, "Rua e número são obrigatórios.", ft.Colors.RED_500)
            return
        rua = capitalizar_rua(rua)

        recuperacao_service.adicionar(
            tr.id,
            form_quarteirao_dd.value or "",
            form_lado_dd.value or "",
            rua,
            numero,
            (campo_obs.value or "").strip() or None,
        )
        campo_rua.value = ""
        campo_numero.value = ""
        campo_obs.value = ""
        snack(page, "Endereço adicionado à lista de recuperação.")
        recarregar()

    form = card(
        page,
        ft.Column(
            [
                ft.Text(
                    "Adicionar endereço", size=14, weight=ft.FontWeight.BOLD
                ),
                ft.Row([form_quarteirao_dd, form_lado_dd], spacing=8),
                campo_rua,
                campo_numero,
                campo_obs,
                ft.Button(
                    "Adicionar à lista",
                    icon=ft.Icons.ADD_LOCATION_ALT,
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
            spacing=10,
        ),
    )

    recarregar()

    return ft.Column(
        scroll=ft.ScrollMode.AUTO,
        controls=[
            ft.Container(
                padding=20,
                content=ft.Column(
                    [
                        ft.Text(
                            "Recuperação", size=28, weight=ft.FontWeight.BOLD
                        ),
                        ft.Text(
                            f"TR {tr.numero} — {para_br(tr.data_inicio)} a {para_br(tr.data_fim)}",
                            size=13,
                            color=TEXTO_SECUNDARIO,
                        ),
                        ft.Container(height=8),
                        resumo,
                        ft.Container(height=4),
                        ft.Row(
                            [
                                ft.Button(
                                    "Exportar PDF",
                                    icon=ft.Icons.PICTURE_AS_PDF,
                                    on_click=exportar_pdf,
                                    style=ft.ButtonStyle(
                                        bgcolor=ft.Colors.GREY_800,
                                        color=ft.Colors.WHITE,
                                        shape=ft.RoundedRectangleBorder(
                                            radius=10
                                        ),
                                        padding=ft.Padding.symmetric(
                                            horizontal=16, vertical=10
                                        ),
                                    ),
                                ),
                                ft.Button(
                                    "Compartilhar PDF",
                                    icon=ft.Icons.SHARE,
                                    on_click=compartilhar_pdf,
                                    style=ft.ButtonStyle(
                                        bgcolor=ft.Colors.BLUE_700,
                                        color=ft.Colors.WHITE,
                                        shape=ft.RoundedRectangleBorder(
                                            radius=10
                                        ),
                                    ),
                                ),
                            ],
                            spacing=8,
                            wrap=True,
                        ),
                        ft.Container(height=8),
                        form,
                        ft.Container(height=8),
                        ft.Text(
                            "Filtrar por status",
                            size=12,
                            weight=ft.FontWeight.BOLD,
                            color=TEXTO_SECUNDARIO,
                        ),
                        filtros_btns,
                        ft.Container(height=6),
                        filtro_quarteirao_dd,
                        ft.Container(height=8),
                        lista,
                    ]
                ),
            )
        ],
    )


def _item_recuperacao(page: ft.Page, item: dict, recarregar) -> ft.Control:
    status = item["status"]
    cor = CORES_STATUS.get(status, ft.Colors.GREY_500)

    partes_rua = [item["rua"], item["numero"]]
    endereco = ", ".join(p for p in partes_rua if p)

    local = []
    if item.get("quarteirao"):
        local.append(f"Quarteirão {item['quarteirao']}")
    if item.get("lado"):
        local.append(item["lado"])
    local_txt = " · ".join(local)

    def mudar_status(novo: str) -> None:
        recuperacao_service.atualizar_status(item["id"], novo)
        snack(page, f"Marcado como {LABEL_STATUS[novo].lower()}.")
        recarregar()

    def excluir(e) -> None:
        def confirmar(ev):
            recuperacao_service.remover(item["id"])
            page.pop_dialog()
            snack(page, "Endereço removido.", ft.Colors.ORANGE_600)
            recarregar()

        dialog = ft.AlertDialog(
            title=ft.Text("Excluir endereço?"),
            content=ft.Text(endereco),
            actions=[
                ft.TextButton(
                    "Cancelar", on_click=lambda ev: page.pop_dialog()
                ),
                ft.Button("Excluir", on_click=confirmar),
            ],
        )
        page.show_dialog(dialog)

    def botao_status(valor: str, label: str, icone: str) -> ft.TextButton:
        ativo = valor == status
        return ft.TextButton(
            label,
            icon=icone,
            on_click=lambda e, v=valor: mudar_status(v),
            style=ft.ButtonStyle(
                bgcolor=CORES_STATUS[valor] if ativo else FUNDO_INATIVO,
                color=ft.Colors.WHITE if ativo else TEXTO_SECUNDARIO,
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                text_style=ft.TextStyle(size=12),
            ),
        )

    return card(
        page,
        ft.Column(
            [
                ft.Row(
                    [
                        ft.Column(
                            [
                                ft.Text(
                                    endereco,
                                    weight=ft.FontWeight.BOLD,
                                    size=15,
                                ),
                                (
                                    ft.Text(
                                        local_txt,
                                        size=12,
                                        color=TEXTO_SECUNDARIO,
                                    )
                                    if local_txt
                                    else ft.Container()
                                ),
                                (
                                    ft.Text(
                                        item.get("observacao") or "",
                                        size=11,
                                        color=TEXTO_SECUNDARIO,
                                    )
                                    if item.get("observacao")
                                    else ft.Container()
                                ),
                            ],
                            spacing=2,
                            expand=True,
                        ),
                        ft.Container(
                            content=ft.Text(
                                LABEL_STATUS[status],
                                size=11,
                                color=ft.Colors.WHITE,
                                weight=ft.FontWeight.W_600,
                            ),
                            padding=ft.Padding.symmetric(
                                horizontal=10, vertical=4
                            ),
                            bgcolor=cor,
                            border_radius=20,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DELETE_OUTLINE,
                            icon_color=ft.Colors.RED_400,
                            on_click=excluir,
                        ),
                    ],
                    spacing=6,
                ),
                ft.Row(
                    [
                        botao_status("fechado", "Fechada", ft.Icons.LOCK_OUTLINE),
                        botao_status(
                            "atendida",
                            "Atendida",
                            ft.Icons.CHECK_CIRCLE_OUTLINE,
                        ),
                        botao_status("abandonada", "Abandonada", ft.Icons.BLOCK),
                        botao_status(
                            "recusado", "Recusado", ft.Icons.DO_NOT_DISTURB
                        ),
                    ],
                    spacing=6,
                    wrap=True,
                ),
            ],
            spacing=8,
        ),
    )
