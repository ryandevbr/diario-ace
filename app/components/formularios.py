from typing import Any, Callable
import flet as ft
import os
from app.services import bairro_service
from app.utils.share import compartilhar_arquivo
import sys


def criar_campos_producao(
    page: ft.Page,
    bairros: list[dict],
    atividades: list[str],
    valores_iniciais: dict[str, Any] | None = None,
    label_qtd: str = "Imóveis trabalhados",
    on_bairro_change: Callable[[int], None] | None = None,
) -> dict[str, Any]:
    """Cria e devolve os controles padronizados de formulário de produção."""
    valores = valores_iniciais or {}

    bairro_padrao = str(bairros[0]["id"]) if bairros else None
    if valores.get("bairro_id") is not None:
        bairro_padrao = str(valores["bairro_id"])

    atividade_padrao = valores.get("atividade") or "Tratamento"
    qtd_padrao = str(valores.get("quantidade", 0) or 0)
    fechados_padrao = str(valores.get("fechados", 0) or 0)
    resgatados_padrao = str(valores.get("resgatados", 0) or 0)
    recusados_padrao = str(valores.get("recusados", 0) or 0)
    obs_padrao = valores.get("observacao") or ""

    dropdown_qtd = ft.Dropdown(
        label=label_qtd,
        options=[ft.dropdown.Option(key=str(n), text=str(n)) for n in range(0, 41)],
        value=qtd_padrao,
    )
    dropdown_bairro = ft.Dropdown(
        label="Bairro",
        options=[
            ft.dropdown.Option(key=str(b["id"]), text=b["nome"]) for b in bairros
        ],
        value=bairro_padrao,
    )

    # --- Lógica para salvar o bairro selecionado ---
    def _bairro_alterado(e):
        if dropdown_bairro.value and on_bairro_change:
            on_bairro_change(int(dropdown_bairro.value))
        _atualizar_estado_croqui(e) # Chama a atualização do botão do croqui

    dropdown_bairro.on_select = _bairro_alterado
    # ----------------------------------------------
    
    # --- Início da lógica do Croqui ---
    btn_croqui = ft.Button(
        "Abrir Croqui do Bairro",
        icon=ft.Icons.MAP,
        style=ft.ButtonStyle(
            bgcolor=ft.Colors.ORANGE_600,
            color=ft.Colors.WHITE,
            shape=ft.RoundedRectangleBorder(radius=10),
        ),
        visible=False,
    )

    def _atualizar_estado_croqui(e=None):
        val = dropdown_bairro.value
        if not val:
            btn_croqui.visible = False
            if page: page.update()
            return

        b_info = bairro_service.buscar_por_id(int(val))
        croqui_path = b_info.get("croqui_path") if b_info else None

        if croqui_path and os.path.exists(croqui_path):
            btn_croqui.visible = True
            
            async def abrir_croqui(ev):
                try:
                    if croqui_path.lower().endswith(".pdf"):
                        if sys.platform == "win32":
                            os.startfile(croqui_path)
                        else:
                            from app.utils.share import compartilhar_arquivo
                            await compartilhar_arquivo(page, croqui_path, "application/pdf", "Abrir Croqui")
                        return

                    def fechar_img(e):
                        page.pop_dialog()
                        page.update()

                    # InteractiveViewer permite zoom e pan na imagem
                    imagem_zoom = ft.InteractiveViewer(
                        content=ft.Image(
                            src=croqui_path,
                            fit=ft.BoxFit.CONTAIN,
                        ),
                        boundary_margin=ft.Margin.all(20),
                        min_scale=0.5,
                        max_scale=5.0,
                        expand=True,
                    )

                    # Usa AlertDialog (que possui on_dismiss) em vez de Container
                    dialog_img = ft.AlertDialog(
                        content_padding=0,
                        title_padding=0,
                        actions_padding=0,
                        inset_padding=0,
                        content=ft.Container(
                            content=ft.Column([
                                ft.Row([
                                    ft.IconButton(
                                        icon=ft.Icons.CLOSE,
                                        icon_color=ft.Colors.WHITE,
                                        on_click=fechar_img,
                                    ),
                                    ft.Text(
                                        f"Croqui - {b_info.get('nome', '')}",
                                        size=16,
                                        weight=ft.FontWeight.BOLD,
                                        color=ft.Colors.WHITE,
                                    ),
                                ], spacing=10),
                                imagem_zoom,
                            ], expand=True),
                            bgcolor=ft.Colors.BLACK,
                            expand=True,
                            padding=10,
                        ),
                    )

                    page.show_dialog(dialog_img)
                    page.update()

                except Exception as ex:
                    print(f"Erro ao abrir croqui: {ex}")
                    from app.components.ui import snack
                    snack(page, f"Erro ao abrir imagem: {ex}", ft.Colors.RED_500)
            
            btn_croqui.on_click = abrir_croqui
        else:
            btn_croqui.visible = False
            
        if page: page.update()
    
    dropdown_bairro.on_select = _atualizar_estado_croqui
    
    # Executa uma vez na criação para checar se o bairro inicial já tem croqui
    _atualizar_estado_croqui()

    # Agrupamos o dropdown e o botão em uma coluna para facilitar o layout
    container_bairro = ft.Column(
        [dropdown_bairro, btn_croqui],
        spacing=6
    )
    # --- Fim da lógica do Croqui ---

    dropdown_atividade = ft.Dropdown(
        label="Atividade",
        options=[ft.dropdown.Option(key=a, text=a) for a in atividades],
        value=atividade_padrao,
    )
    dropdown_fechados = ft.Dropdown(
        label="Fechados",
        options=[ft.dropdown.Option(key=str(n), text=str(n)) for n in range(0, 31)],
        value=fechados_padrao,
        width=100,
    )
    dropdown_resgatados = ft.Dropdown(
        label="Resgatados",
        options=[ft.dropdown.Option(key=str(n), text=str(n)) for n in range(0, 31)],
        value=resgatados_padrao,
        width=100,
    )
    dropdown_recusados = ft.Dropdown(
        label="Recusados",
        options=[ft.dropdown.Option(key=str(n), text=str(n)) for n in range(0, 31)],
        value=recusados_padrao,
        width=100,
    )
    campo_obs = ft.TextField(
        label="Observação (opcional)",
        value=obs_padrao,
    )
    linha_contadores = ft.Row(
        [dropdown_fechados, dropdown_resgatados, dropdown_recusados],
        spacing=8,
    )

    return {
        "qtd": dropdown_qtd,
        "bairro": dropdown_bairro,       # Mantido para extrair_valores_producao funcionar
        "bairro_ui": container_bairro,   # Novo: usado para exibir na tela (dropdown + botão)
        "atividade": dropdown_atividade,
        "fechados": dropdown_fechados,
        "resgatados": dropdown_resgatados,
        "recusados": dropdown_recusados,
        "obs": campo_obs,
        "linha_contadores": linha_contadores,
    }


def extrair_valores_producao(campos: dict[str, Any]) -> dict[str, Any]:
    """Lê e converte com segurança os valores preenchidos nos controles de produção."""
    qtd = int(campos["qtd"].value or "0")

    try:
        fechados = int(campos["fechados"].value or "0")
        resgatados = int(campos["resgatados"].value or "0")
        recusados = int(campos["recusados"].value or "0")
    except (ValueError, TypeError):
        fechados = resgatados = recusados = 0

    try:
        val_bairro = campos["bairro"].value
        bairro_id = int(val_bairro) if val_bairro else None
    except (ValueError, TypeError):
        bairro_id = None

    obs_ctrl = campos.get("obs")
    obs = (obs_ctrl.value or "").strip() or None if obs_ctrl is not None else None

    return {
        "quantidade": qtd,
        "bairro_id": bairro_id,
        "atividade": campos["atividade"].value,
        "fechados": fechados,
        "resgatados": resgatados,
        "recusados": recusados,
        "observacao": obs,
    }


def resumo_contadores_chips(
    produzido_hoje: int,
    totais: dict[str, Any],
    eficiencia_fn: Callable[[int, int, int], float],
) -> ft.Control:
    """Exibe chips de Fechados, Resgatados, Recusados e percentual de eficiência."""
    fechados = totais.get("fechados", 0) or 0
    resgatados = totais.get("resgatados", 0) or 0
    recusados = totais.get("recusados", 0) or 0

    if fechados == 0 and resgatados == 0 and recusados == 0:
        return ft.Container()

    efic = eficiencia_fn(produzido_hoje, fechados, recusados)

    def _chip(label: str, valor: int, cor: str) -> ft.Container:
        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=10, vertical=6),
            bgcolor=cor,
            border_radius=20,
            content=ft.Text(
                f"{label}: {valor}",
                size=11,
                color=ft.Colors.WHITE,
                weight=ft.FontWeight.W_600,
            ),
        )

    return ft.Row(
        [
            _chip("Fechados", fechados, ft.Colors.RED_500),
            _chip("Resgatados", resgatados, ft.Colors.GREEN_600),
            _chip("Recusados", recusados, ft.Colors.ORANGE_700),
            ft.Text(f"Eficiência: {efic:.1f}%", size=11, color=ft.Colors.GREY_500),
        ],
        spacing=6,
        wrap=True,
    )


def resumo_contadores_texto(
    p: dict[str, Any],
    eficiencia_fn: Callable[[int, int, int], float],
) -> ft.Control:
    """Exibe linha compacta de contadores para cards de histórico."""
    fechados = p.get("fechados", 0) or 0
    resgatados = p.get("resgatados", 0) or 0
    recusados = p.get("recusados", 0) or 0

    if fechados == 0 and resgatados == 0 and recusados == 0:
        return ft.Container()

    efic = eficiencia_fn(p.get("quantidade", 0) or 0, fechados, recusados)
    return ft.Text(
        f"F: {fechados} · R: {resgatados} · Re: {recusados} · Efic: {efic:.0f}%",
        size=11,
        color=ft.Colors.GREY_500,
    )

