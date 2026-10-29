import asyncio
from datetime import date
import logging
import os
from pathlib import Path
import sys
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import flet as ft

from app.components.ui import resolver_theme_mode, snack
from app.database import init_db
from app.services import (
    backup_service,
    banco_horas_service,
    config_service,
    producao_service,
    tr_service,
    update_service,
)
from app.utils.share import compartilhar_arquivo
from app.views import calendario, config, historico, hoje, meu_tr, recuperacao, calculadora

logger = logging.getLogger(__name__)

def _obter_build_atual(padrao: int = 11) -> int:
    """Lê o build_number do pyproject.toml para manter sincronizado."""
    try:
        import tomllib

        caminho_toml = Path(__file__).resolve().parent / "pyproject.toml"
        with open(caminho_toml, "rb") as f:
            dados = tomllib.load(f)
        return int(
            dados.get("tool", {}).get("flet", {}).get("build_number", padrao)
        )
    except Exception:
        return padrao


BUILD_ATUAL = _obter_build_atual()
MIME_APK = "application/vnd.android.package-archive"

RENDERIZADORES_ABA = (
    hoje.build,
    meu_tr.build,
    calendario.build,
    historico.build,
    recuperacao.build,
    calculadora.build,
    config.build,
)


async def _abrir_instalador_apk(page: ft.Page, caminho_apk: str):
    """Abre o instalador de pacotes do Android usando Share (FileProvider)."""
    try:
        from app.utils.share import compartilhar_arquivo
        
        ok = await compartilhar_arquivo(
            page, 
            caminho_apk, 
            mime_type="application/vnd.android.package-archive",
            texto="Instalar atualização do Diário ACE"
        )
        if not ok:
            from app.components.ui import snack
            snack(page, "Não foi possível abrir o instalador.", ft.Colors.RED_500)
    except Exception as ex:
        print(f"Erro ao abrir instalador: {ex}")
        from app.components.ui import snack
        snack(page, f"Erro: {ex}", ft.Colors.RED_500)


def checar_atualizacao(page: ft.Page) -> None:
    """Verifica na inicialização se há nova versão disponível (apenas no Android)."""
    es_android = (
        os.environ.get("FLET_PLATFORM", "").lower() == "android"
        or update_service.eh_android()
    )
    if not es_android:
        print("Checagem de atualização ignorada no desktop.")
        return

    async def _executar_checagem() -> None:
        dados = await asyncio.to_thread(
            update_service.verificar_atualizacao, build_atual=BUILD_ATUAL
        )
        if not dados:
            return

        await asyncio.sleep(0.1)

        changelog = (dados.get("changelog") or "Melhorias e correções.").strip()
        texto_aviso = (
            f"Nova versão disponível!\n\n{changelog}\n\nDeseja atualizar agora?"
        )
        texto_progresso = ft.Text(
            "Baixando atualização... Aguarde.",
            size=13,
            text_align=ft.TextAlign.CENTER,
        )

        async def confirmar_atualizacao(ev) -> None:
            dialog.modal = True
            dialog.actions = []
            dialog.content = ft.Column(
                [
                    ft.ProgressRing(),
                    texto_progresso,
                ],
                tight=True,
                spacing=14,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            )
            page.update()

            ultimo_mb_exibido = {"valor": -1}

            def ao_progresso(baixado: int, total: int) -> None:
                mb_atual = baixado // (1024 * 1024)
                if mb_atual == ultimo_mb_exibido["valor"] and baixado != total:
                    return
                ultimo_mb_exibido["valor"] = mb_atual
                mb_fmt = baixado / (1024 * 1024)
                if total > 0:
                    total_fmt = total / (1024 * 1024)
                    pct = int((baixado / total) * 100)
                    texto_progresso.value = (
                        f"Baixando atualização... {pct}% "
                        f"({mb_fmt:.1f} / {total_fmt:.1f} MB)"
                    )
                else:
                    texto_progresso.value = (
                        f"Baixando atualização... ({mb_fmt:.1f} MB)"
                    )
                try:
                    page.update()
                except Exception:
                    pass

            try:
                destino = await asyncio.to_thread(
                    update_service.obter_destino_apk
                )
                caminho_apk = await asyncio.to_thread(
                    update_service.baixar_apk,
                    dados["apk_url"],
                    str(destino),
                    on_progress=ao_progresso,
                )
                page.pop_dialog()
                page.update()
                await _abrir_instalador_apk(page, caminho_apk)
            except Exception as ex:
                logger.warning("Erro durante atualização do app: %s", ex)
                try:
                    page.pop_dialog()
                    page.update()
                except Exception:
                    pass
                snack(
                    page,
                    f"Erro ao baixar atualização: {ex}",
                    ft.Colors.RED_500,
                )

        dialog = ft.AlertDialog(
            title=ft.Text("Atualização disponível"),
            content=ft.Text(texto_aviso),
            actions=[
                ft.TextButton("Não", on_click=lambda ev: page.pop_dialog()),
                ft.Button("Sim", on_click=confirmar_atualizacao),
            ],
        )
        page.show_dialog(dialog)

    page.run_task(_executar_checagem)


def main(page: ft.Page):
    page.window.prevent_close = True
    page.title = "Controle ACE"
    page.padding = 0

    init_db()
    tr_service.seed_trs_do_ano(date.today().year)

    modo_salvo = config_service.obter("tema", "system")
    page.theme_mode = resolver_theme_mode(modo_salvo)

    page.theme = ft.Theme(
        color_scheme_seed=ft.Colors.TEAL,
        color_scheme=ft.ColorScheme(
            primary=ft.Colors.TEAL_700,
            secondary=ft.Colors.AMBER_700,
        ),
        visual_density=ft.VisualDensity.COMFORTABLE,
    )
    page.dark_theme = ft.Theme(color_scheme_seed=ft.Colors.TEAL)

    try:
        backup_service.fazer_backup_automatico()
    except Exception as ex:
        logger.warning("Backup automático falhou: %s", ex)

    body = ft.Container(expand=True)
    header_bh = ft.Text("", size=11, color=ft.Colors.GREY_500)
    
    # Título que muda dinamicamente no cabeçalho
    titulo_header = ft.Text(
        "Diário ACE",
        weight=ft.FontWeight.BOLD,
        color=ft.Colors.TEAL_700,
        size=16,
    )

    # Lista de abas para o menu lateral
    abas = [
        (0, "Hoje", ft.Icons.TODAY),
        (1, "Meu TR", ft.Icons.INSIGHTS),
        (2, "Calendário", ft.Icons.CALENDAR_MONTH),
        (3, "Histórico", ft.Icons.HISTORY),
        (4, "Recuperação", ft.Icons.LOCATION_ON),
        (5, "Calc. Larvicida", ft.Icons.WATER_DROP),
        (6, "Configurações", ft.Icons.SETTINGS),
    ]

    def atualizar_header_bh() -> None:
        try:
            info = banco_horas_service.resumo_saldo()
            if info["horas"] == 0:
                header_bh.value = ""
            else:
                header_bh.value = (
                    f"BH {info['sinal']}{info['hhmm']} ({info['dias']})"
                )
        except Exception as ex:
            logger.warning("Erro ao atualizar header BH: %s", ex)
            header_bh.value = ""

    page._atualizar_header_bh = atualizar_header_bh

    def _trocar_aba(idx: int) -> None:
        page._current_tab = idx
        construtor = (
            RENDERIZADORES_ABA[idx]
            if 0 <= idx < len(RENDERIZADORES_ABA)
            else config.build
        )
        body.content = construtor(page)
        
        # Atualiza o título no cabeçalho com o nome da aba
        for i, label, _ in abas:
            if i == idx:
                titulo_header.value = label
                break

        atualizar_header_bh()
        page.update()

    def _valor_atual_hoje() -> int:
        dropdown = getattr(page, "_hoje_dropdown", None)
        if dropdown is None:
            return 0
        try:
            return int(dropdown.value or "0")
        except (ValueError, TypeError):
            return 0

    def _tem_alteracao_nao_salva() -> bool:
        dropdown = getattr(page, "_hoje_dropdown", None)
        if dropdown is None:
            return False
        salvo = getattr(page, "_hoje_produzido_salvo", 0)
        return _valor_atual_hoje() != salvo

    def _salvar_producao_pendente() -> None:
        try:
            salvar_fn = getattr(page, "_hoje_salvar_fn", None)
            if callable(salvar_fn):
                salvar_fn()
                return
            hoje_ = date.today()
            tr = tr_service.tr_por_data(hoje_)
            if tr is not None:
                producao_service.registrar_producao(
                    hoje_, tr.id, _valor_atual_hoje()
                )
        except Exception as ex:
            logger.warning("Erro ao salvar pendente: %s", ex)

    def _pedir_confirmacao_saida(
        mensagem: str,
        label_descartar: str,
        acao_continuar: Callable[[], None],
    ) -> None:
        def salvar_e_continuar(ev):
            page.pop_dialog()
            _salvar_producao_pendente()
            acao_continuar()

        def descartar_e_continuar(ev):
            page.pop_dialog()
            acao_continuar()

        dialog = ft.AlertDialog(
            title=ft.Text("Produção não salva"),
            content=ft.Text(mensagem),
            actions=[
                ft.TextButton(
                    "Cancelar", on_click=lambda ev: page.pop_dialog()
                ),
                ft.TextButton(label_descartar, on_click=descartar_e_continuar),
                ft.Button("Salvar e sair", on_click=salvar_e_continuar),
            ],
        )
        page.show_dialog(dialog)

    def _pedir_confirmacao_troca_aba(idx_destino: int) -> None:
        _pedir_confirmacao_saida(
            "Você alterou o valor de imóveis visitados hoje, mas não salvou. "
            "O que deseja fazer?",
            "Descartar",
            lambda: _trocar_aba(idx_destino),
        )

    def _pedir_confirmacao_fechar_app() -> None:
        _pedir_confirmacao_saida(
            "Você alterou o valor de imóveis visitados hoje, mas não salvou. "
            "O que deseja fazer antes de fechar?",
            "Descartar e sair",
            lambda: page.window.destroy(),
        )

    # --- Lógica do Menu Lateral (Drawer) ---
    async def abrir_menu(e) -> None:
        # A função correta na v1.0 é show_drawer()
        await page.show_drawer()

    async def selecionar_aba_menu(e) -> None:
        # A função correta na v1.0 é close_drawer()
        await page.close_drawer()
        
        idx = e.control.selected_index
        atual = getattr(page, "_current_tab", 0)
        if atual == 0 and idx != 0 and _tem_alteracao_nao_salva():
            _pedir_confirmacao_troca_aba(idx)
            return

        _trocar_aba(idx)

    page.drawer = ft.NavigationDrawer(
        on_change=selecionar_aba_menu,
        controls=[
            ft.Container(
                padding=20,
                content=ft.Column([
                    ft.Text("Diário ACE", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.TEAL_700),
                    ft.Text("Agente de Combate a Endemias", size=12, color=ft.Colors.GREY_500),
                ], spacing=2)
            ),
            ft.Divider(),
            *[
                ft.NavigationDrawerDestination(
                    icon=icone,
                    label=label,
                )
                for _, label, icone in abas
            ],
            ft.Divider(),
            ft.Container(
                padding=10,
                content=ft.TextButton(
                    "Sair do App",
                    icon=ft.Icons.LOGOUT,
                    icon_color=ft.Colors.RED_500,
                    style=ft.ButtonStyle(color=ft.Colors.RED_500),
                    on_click=lambda e: _tentar_sair(),
                )
            )
        ],
    )

    def _pode_sair_do_app() -> bool:
        atual = getattr(page, "_current_tab", 0)
        if atual != 0:
            return True
        return not _tem_alteracao_nao_salva()

    def _tentar_sair() -> None:
        if _pode_sair_do_app():
            try:
                page.window.destroy()
            except Exception:
                pass
        else:
            _pedir_confirmacao_fechar_app()

    def on_window_event(e) -> None:
        if e.data == "close":
            _tentar_sair()

    def on_view_pop(e) -> bool:
        if _pode_sair_do_app():
            return False
        _pedir_confirmacao_fechar_app()
        return True

    # Cabeçalho atualizado com o botão de Menu (hambúrguer)
    header = ft.Container(
        bgcolor=ft.Colors.SURFACE,
        padding=ft.Padding.symmetric(horizontal=8, vertical=8),
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Row([
                    ft.IconButton(
                        icon=ft.Icons.MENU,
                        icon_color=ft.Colors.TEAL_700,
                        on_click=abrir_menu, # O Flet executa funções async automaticamente
                    ),
                    titulo_header,
                ], spacing=0),
                ft.Row(
                    [
                        header_bh,
                    ],
                    spacing=8,
                ),
            ],
        ),
    )

    page.window.on_event = on_window_event
    page.on_view_pop = on_view_pop

    # Inicializa a tela Hoje
    page._current_tab = 0
    body.content = hoje.build(page)
    titulo_header.value = "Hoje"
    atualizar_header_bh()

    checar_atualizacao(page)

    page.add(
        ft.Column(
            expand=True,
            spacing=0,
            controls=[
                header,
                body,
            ],
        )
    )


if __name__ == "__main__":
    ft.run(main)