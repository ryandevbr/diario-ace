import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import date
import flet as ft

from app.database import init_db
from app.services import (
    tr_service,
    producao_service,
    config_service,
    backup_service,
    banco_horas_service,
)
from app.views import hoje, meu_tr, calendario, historico, config, recuperacao


def main(page: ft.Page):
    page.title = "Controle ACE"
    page.padding = 0

    init_db()
    tr_service.seed_trs_do_ano(date.today().year)

    modo_salvo = config_service.obter("tema", "system")
    page.theme_mode = {
        "light": ft.ThemeMode.LIGHT,
        "dark": ft.ThemeMode.DARK,
        "system": ft.ThemeMode.SYSTEM,
    }.get(modo_salvo, ft.ThemeMode.SYSTEM)

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
        print(f"Backup automático falhou: {ex}")

    body = ft.Container(expand=True)

    # ---------- Header: título + saldo BH + botão Sair ----------
    header_bh = ft.Text("", size=11, color=ft.Colors.GREY_500)

    def atualizar_header_bh():
        try:
            info = banco_horas_service.resumo_saldo()
            if info["horas"] == 0:
                header_bh.value = ""
            else:
                header_bh.value = (
                    f"BH {info['sinal']}{info['hhmm']} ({info['dias']})"
                )
        except Exception as ex:
            print(f"Erro ao atualizar header BH: {ex}")
            header_bh.value = ""

    # ---------- Renderizadores de aba ----------
    def render_hoje():
        body.content = hoje.build(page)

    def render_meu_tr():
        body.content = meu_tr.build(page)

    def render_calendario():
        body.content = calendario.build(page)

    def render_historico():
        body.content = historico.build(page)

    def render_recuperacao():
        body.content = recuperacao.build(page)

    def render_config():
        body.content = config.build(page)

    def _trocar_aba(idx):
        page._current_tab = idx
        if idx == 0:
            render_hoje()
        elif idx == 1:
            render_meu_tr()
        elif idx == 2:
            render_calendario()
        elif idx == 3:
            render_historico()
        elif idx == 4:
            render_recuperacao()
        else:
            render_config()
        page.navigation_bar.selected_index = idx
        atualizar_header_bh()
        page.update()

    # ---------- Detecção de alteração não salva na aba Hoje ----------
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

    def _salvar_producao_pendente():
        try:
            hoje_ = date.today()
            tr = tr_service.tr_por_data(hoje_)
            if tr is not None:
                producao_service.registrar_producao(
                    hoje_, tr.id, _valor_atual_hoje()
                )
        except Exception as ex:
            print(f"Erro ao salvar pendente: {ex}")

    # ---------- Diálogos de confirmação ----------
    def _pedir_confirmacao_troca_aba(idx_destino):
        def salvar_e_sair(ev):
            page.pop_dialog()
            _salvar_producao_pendente()
            _trocar_aba(idx_destino)

        def descartar_e_sair(ev):
            page.pop_dialog()
            _trocar_aba(idx_destino)

        dialog = ft.AlertDialog(
            title=ft.Text("Produção não salva"),
            content=ft.Text(
                "Você alterou o valor de imóveis visitados hoje, mas não salvou. "
                "O que deseja fazer?"
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda ev: page.pop_dialog()),
                ft.TextButton("Descartar", on_click=descartar_e_sair),
                ft.Button("Salvar e sair", on_click=salvar_e_sair),
            ],
        )
        page.show_dialog(dialog)

    def _pedir_confirmacao_fechar_app():
        def salvar_e_sair(ev):
            page.pop_dialog()
            _salvar_producao_pendente()
            page.window.destroy()

        def descartar_e_sair(ev):
            page.pop_dialog()
            page.window.destroy()

        dialog = ft.AlertDialog(
            title=ft.Text("Produção não salva"),
            content=ft.Text(
                "Você alterou o valor de imóveis visitados hoje, mas não salvou. "
                "O que deseja fazer antes de fechar?"
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda ev: page.pop_dialog()),
                ft.TextButton("Descartar e sair", on_click=descartar_e_sair),
                ft.Button("Salvar e sair", on_click=salvar_e_sair),
            ],
        )
        page.show_dialog(dialog)

    # ---------- Handlers de navegação e saída ----------
    def on_nav(e):
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

    def on_window_event(e):
        if e.data == "close":
            if _pode_sair_do_app():
                page.window.destroy()
            else:
                _pedir_confirmacao_fechar_app()

    def on_view_pop(e):
        if _pode_sair_do_app():
            return False
        _pedir_confirmacao_fechar_app()
        return True

    # ---------- Header ----------
    def _on_sair(e):
        try:
            page.window.destroy()
        except Exception:
            pass

    header = ft.Container(
        bgcolor=ft.Colors.SURFACE,
        padding=ft.Padding.symmetric(horizontal=16, vertical=10),
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Text("Diário ACE", weight=ft.FontWeight.BOLD,
                        color=ft.Colors.TEAL_700, size=14),
                ft.Row([
                    header_bh,
                    ft.TextButton("Sair", on_click=_on_sair),
                ], spacing=8),
            ],
        ),
    )

    # ---------- NavigationBar ----------
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

    # ---------- Montagem ----------
    render_hoje()
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