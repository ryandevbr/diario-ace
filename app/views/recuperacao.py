from datetime import date
import os
import tempfile
import flet as ft

from app.services import tr_service, recuperacao_service, pdf_service
from app.utils.datas import para_br
from app.utils.files import obter_file_picker
from app.utils.share import compartilhar_arquivo
from app.components.ui import card, snack


CORES_STATUS = {
    "fechado":    ft.Colors.RED_500,
    "atendida":   ft.Colors.GREEN_600,
    "abandonada": ft.Colors.GREY_600,
    "recusado":   ft.Colors.ORANGE_700,
}

LABEL_STATUS = {
    "fechado":    "Fechado",
    "atendida":   "Atendida",
    "abandonada": "Abandonada",
    "recusado":   "Recusado",
}

LADOS = [f"Lado {i}" for i in range(1, 9)]
QUARTEIROES = [str(i) for i in range(1, 61)]

# Fundo de botões/chips inativos, adaptável ao tema
FUNDO_INATIVO = getattr(ft.Colors, "SURFACE_VARIANT", ft.Colors.GREY_100)
# Cor secundária do tema para textos que precisam funcionar nos dois modos
TEXTO_SECUNDARIO = getattr(ft.Colors, "ON_SURFACE_VARIANT", ft.Colors.GREY_700)


def capitalizar_rua(s: str) -> str:
    """Capitaliza cada palavra, exceto preposições curtas no meio."""
    pequenas = {"de", "da", "do", "das", "dos", "e", "a", "o",
                "as", "os", "na", "no"}
    palavras = s.strip().split()
    if not palavras:
        return ""
    resultado = []
    for i, p in enumerate(palavras):
        if i == 0:
            resultado.append(p.capitalize())
        elif p.lower() in pequenas:
            resultado.append(p.lower())
        else:
            resultado.append(p.capitalize())
    return " ".join(resultado)


def build(page: ft.Page) -> ft.Control:
    hoje = date.today()
    tr = tr_service.tr_por_data(hoje)
    if tr is None:
        return ft.Container(padding=20, content=ft.Text("Sem TR ativo para hoje."))

    filtro_atual = {"status": None, "quarteirao": None}

    filtros_btns = ft.Row(spacing=6, wrap=True)
    lista = ft.Column(spacing=8, controls=[])
    resumo = ft.Text("", size=13, color=TEXTO_SECUNDARIO)

    # ---------- Filtro por quarteirão ----------
    filtro_quarteirao_dd = ft.Dropdown(
        label="Filtrar por quarteirão",
        options=[ft.dropdown.Option(key="", text="Todos")],
        value="",
        width=200,
    )

    def on_quarteirao_change(e):
        v = filtro_quarteirao_dd.value or ""
        filtro_atual["quarteirao"] = v or None
        recarregar()

    filtro_quarteirao_dd.on_select = on_quarteirao_change

    # ---------- Montagem dos filtros ----------
    def montar_filtros():
        filtros_btns.controls.clear()
        contagem = recuperacao_service.contar_por_status(tr.id)
        opcoes = [
            (None, "Todas", ft.Colors.TEAL_700),
            ("fechado", f"Fechadas ({contagem.get('fechado', 0)})", CORES_STATUS["fechado"]),
            ("atendida", f"Atendidas ({contagem.get('atendida', 0)})", CORES_STATUS["atendida"]),
            ("abandonada", f"Abandonadas ({contagem.get('abandonada', 0)})", CORES_STATUS["abandonada"]),
            ("recusado", f"Recusados ({contagem.get('recusado', 0)})", CORES_STATUS["recusado"]),
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

        todos = recuperacao_service.listar_por_tr(tr.id, None)
        quarteiroes = sorted(
            {it.get("quarteirao") for it in todos if it.get("quarteirao")},
            key=lambda q: int(q) if str(q).isdigit() else 0,
        )
        filtro_quarteirao_dd.options = [ft.dropdown.Option(key="", text="Todos")] + [
            ft.dropdown.Option(key=q, text=f"Quadra {q}") for q in quarteiroes
        ]
        if filtro_atual["quarteirao"] in quarteiroes:
            filtro_quarteirao_dd.value = filtro_atual["quarteirao"]
        else:
            filtro_atual["quarteirao"] = None
            filtro_quarteirao_dd.value = ""

    def definir_filtro(valor):
        filtro_atual["status"] = valor
        recarregar()

    def montar_resumo(contagem: dict):
        total = sum(contagem.values())
        resumo.value = (
            f"Total no TR: {total} endereços — "
            f"{contagem.get('fechado', 0)} fechados, "
            f"{contagem.get('atendida', 0)} atendidos, "
            f"{contagem.get('abandonada', 0)} abandonados."
        )

    def montar_lista():
        lista.controls.clear()
        itens = recuperacao_service.listar_por_tr(tr.id, filtro_atual["status"])
        if filtro_atual["quarteirao"]:
            itens = [it for it in itens if it.get("quarteirao") == filtro_atual["quarteirao"]]
        if not itens:
            lista.controls.append(
                ft.Text("Nenhum endereço cadastrado nesta categoria.",
                        color=TEXTO_SECUNDARIO)
            )
            return
        for item in itens:
            lista.controls.append(_item_recuperacao(page, item, recarregar))

    picker = obter_file_picker(page)

    def _itens_filtrados():
        itens = recuperacao_service.listar_por_tr(tr.id, filtro_atual["status"])
        if filtro_atual["quarteirao"]:
            itens = [it for it in itens if it.get("quarteirao") == filtro_atual["quarteirao"]]
        return itens

    def _sufixo_filtros():
        partes = []
        if filtro_atual["status"]:
            partes.append(filtro_atual["status"])
        if filtro_atual["quarteirao"]:
            partes.append(f"q{filtro_atual['quarteirao']}")
        return f"_{'_'.join(partes)}" if partes else ""

    # ---------- PDF ----------
    async def exportar_pdf(e):
        try:
            itens = _itens_filtrados()
            sufixo = _sufixo_filtros()
            nome = f"recuperacao_TR{tr.numero}{sufixo}_{date.today().isoformat()}.pdf"
            caminho = await picker.save_file(
                dialog_title="Salvar PDF",
                file_name=nome,
                allowed_extensions=["pdf"],
            )
            if not caminho:
                snack(page, "Exportação cancelada.", ft.Colors.ORANGE_600)
                return
            pdf_service.exportar_recuperacao_pdf(caminho, tr, itens)
            snack(page, f"PDF salvo em {caminho}")
        except Exception as ex:
            snack(page, f"Erro ao gerar PDF: {ex}", ft.Colors.RED_500)

    async def compartilhar_pdf(e):
        try:
            itens = _itens_filtrados()
            sufixo = _sufixo_filtros()
            nome = f"recuperacao_TR{tr.numero}{sufixo}_{date.today().isoformat()}.pdf"
            caminho = os.path.join(tempfile.gettempdir(), nome)
            pdf_service.exportar_recuperacao_pdf(caminho, tr, itens)

            ok = await compartilhar_arquivo(
                page, caminho,
                texto=f"Recuperação TR {tr.numero}",
            )
            if not ok:
                caminho_salvo = await picker.save_file(
                    dialog_title="Salvar PDF",
                    file_name=nome,
                    allowed_extensions=["pdf"],
                )
                if caminho_salvo:
                    pdf_service.exportar_recuperacao_pdf(caminho_salvo, tr, itens)
                    snack(page, f"PDF salvo em {caminho_salvo}")
                else:
                    snack(page, "Compartilhamento indisponível.", ft.Colors.ORANGE_600)
        except Exception as ex:
            snack(page, f"Erro ao compartilhar: {ex}", ft.Colors.RED_500)

    def recarregar():
        contagem = recuperacao_service.contar_por_status(tr.id)
        montar_resumo(contagem)
        montar_filtros()
        montar_lista()
        page.update()

    # ---------- Formulário de cadastro ----------
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

    def salvar(e):
        rua = campo_rua.value.strip()
        numero = campo_numero.value.strip()
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
            campo_obs.value.strip() or None,
        )
        campo_rua.value = ""
        campo_numero.value = ""
        campo_obs.value = ""
        snack(page, "Endereço adicionado à lista de recuperação.")
        recarregar()

    form = card(page, ft.Column([
        ft.Text("Adicionar endereço", size=14, weight=ft.FontWeight.BOLD),
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
                padding=ft.Padding.symmetric(horizontal=20, vertical=14),
            ),
        ),
    ], spacing=10))

    recarregar()

    return ft.Column(
        scroll=ft.ScrollMode.AUTO,
        controls=[
            ft.Container(
                padding=20,
                content=ft.Column([
                    ft.Text("Recuperação", size=28, weight=ft.FontWeight.BOLD),
                    ft.Text(
                        f"TR {tr.numero} — {para_br(tr.data_inicio)} a {para_br(tr.data_fim)}",
                        size=13, color=TEXTO_SECUNDARIO,
                    ),
                    ft.Container(height=8),
                    resumo,
                    ft.Container(height=4),
                    ft.Row([
                        ft.Button(
                            "Exportar PDF",
                            icon=ft.Icons.PICTURE_AS_PDF,
                            on_click=exportar_pdf,
                            style=ft.ButtonStyle(
                                bgcolor=ft.Colors.GREY_800,
                                color=ft.Colors.WHITE,
                                shape=ft.RoundedRectangleBorder(radius=10),
                                padding=ft.Padding.symmetric(horizontal=16, vertical=10),
                            ),
                        ),
                        ft.Button(
                            "Compartilhar PDF",
                            icon=ft.Icons.SHARE,
                            on_click=compartilhar_pdf,
                            style=ft.ButtonStyle(
                                bgcolor=ft.Colors.BLUE_700,
                                color=ft.Colors.WHITE,
                                shape=ft.RoundedRectangleBorder(radius=10),
                            ),
                        ),
                    ], spacing=8, wrap=True),
                    ft.Container(height=8),
                    form,
                    ft.Container(height=8),
                    ft.Text("Filtrar por status", size=12,
                            weight=ft.FontWeight.BOLD, color=TEXTO_SECUNDARIO),
                    filtros_btns,
                    ft.Container(height=6),
                    filtro_quarteirao_dd,
                    ft.Container(height=8),
                    lista,
                ]),
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

    def mudar_status(novo):
        recuperacao_service.atualizar_status(item["id"], novo)
        snack(page, f"Marcado como {LABEL_STATUS[novo].lower()}.")
        recarregar()

    def excluir(e):
        def confirmar(ev):
            recuperacao_service.remover(item["id"])
            page.pop_dialog()
            snack(page, "Endereço removido.", ft.Colors.ORANGE_600)
            recarregar()

        dialog = ft.AlertDialog(
            title=ft.Text("Excluir endereço?"),
            content=ft.Text(endereco),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda ev: page.pop_dialog()),
                ft.Button("Excluir", on_click=confirmar),
            ],
        )
        page.show_dialog(dialog)

    def botao_status(valor, label, icone):
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

    return card(page, ft.Column([
        ft.Row([
            ft.Column([
                ft.Text(endereco, weight=ft.FontWeight.BOLD, size=15),
                ft.Text(local_txt, size=12, color=TEXTO_SECUNDARIO) if local_txt else ft.Container(),
                ft.Text(item.get("observacao") or "", size=11,
                        color=TEXTO_SECUNDARIO) if item.get("observacao") else ft.Container(),
            ], spacing=2, expand=True),
            ft.Container(
                content=ft.Text(LABEL_STATUS[status], size=11,
                                color=ft.Colors.WHITE, weight=ft.FontWeight.W_600),
                padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                bgcolor=cor,
                border_radius=20,
            ),
            ft.IconButton(
                icon=ft.Icons.DELETE_OUTLINE,
                icon_color=ft.Colors.RED_400,
                on_click=excluir,
            ),
        ], spacing=6),
        ft.Row([
            botao_status("fechado", "Fechada", ft.Icons.LOCK_OUTLINE),
            botao_status("atendida", "Atendida", ft.Icons.CHECK_CIRCLE_OUTLINE),
            botao_status("abandonada", "Abandonada", ft.Icons.BLOCK),
            botao_status("recusado", "Recusado", ft.Icons.DO_NOT_DISTURB),
        ], spacing=6, wrap=True),
    ], spacing=8))