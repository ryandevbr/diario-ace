from datetime import date
import logging
from pathlib import Path
import sys
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import flet as ft

from app.components.ui import resolver_theme_mode
from app.database import init_db
from app.services import (
    backup_service,
    banco_horas_service,
    config_service,
    producao_service,
    tr_service,
)
from app.views import calendario, config, historico, hoje, meu_tr, recuperacao

logger = logging.getLogger(__name__)

RENDERIZADORES_ABA = (
    hoje.build,
    meu_tr.build,
    calendario.build,
    historico.build,
    recuperacao.build,
    config.build,
)


def main(page: ft.Page) -> None:
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
        page.navigation_bar.selected_index = idx
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

    def on_nav(e) -> None:
        idx = page.navigation_bar.selected_index
        atual = getattr(page, "_current_tab", 0)

        if atual == 0 and idx != 0 and _tem_alteracao_nao_salva():
            page.navigation_bar.selected_index = atual
            page.update()
            _pedir_confirmacao_troca_aba(idx)
            return

        _trocar_aba(idx)

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

    header = ft.Container(
        bgcolor=ft.Colors.SURFACE,
        padding=ft.Padding.symmetric(horizontal=16, vertical=10),
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Text(
                    "Diário ACE",
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.TEAL_700,
                    size=14,
                ),
                ft.Row(
                    [
                        header_bh,
                        ft.TextButton("Sair", on_click=lambda e: _tentar_sair()),
                    ],
                    spacing=8,
                ),
            ],
        ),
    )

    page.navigation_bar = ft.NavigationBar(
        selected_index=0,
        indicator_color=ft.Colors.TEAL_100,
        destinations=[
            ft.NavigationBarDestination(
                icon=ft.Icons.TODAY_OUTLINED,
                selected_icon=ft.Icons.TODAY,
                label="Hoje",
            ),
            ft.NavigationBarDestination(
                icon=ft.Icons.INSIGHTS_OUTLINED,
                selected_icon=ft.Icons.INSIGHTS,
                label="Meu TR",
            ),
            ft.NavigationBarDestination(
                icon=ft.Icons.CALENDAR_MONTH_OUTLINED,
                selected_icon=ft.Icons.CALENDAR_MONTH,
                label="Calendário",
            ),
            ft.NavigationBarDestination(
                icon=ft.Icons.HISTORY_OUTLINED,
                selected_icon=ft.Icons.HISTORY,
                label="Histórico",
            ),
            ft.NavigationBarDestination(
                icon=ft.Icons.LOCATION_ON_OUTLINED,
                selected_icon=ft.Icons.LOCATION_ON,
                label="Recuperação",
            ),
            ft.NavigationBarDestination(
                icon=ft.Icons.SETTINGS_OUTLINED,
                selected_icon=ft.Icons.SETTINGS,
                label="Config",
            ),
        ],
        on_change=on_nav,
    )

    page.window.prevent_close = True
    page.window.on_event = on_window_event
    page.on_view_pop = on_view_pop

    body.content = hoje.build(page)
    atualizar_header_bh()

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
