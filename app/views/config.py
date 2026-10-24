from datetime import date
import flet as ft

from app.components.ui import resolver_theme_mode, snack
from app.services import backup_service, config_service
from app.utils.files import obter_file_picker
from app.views.config_secoes import (
    criar_secao_bairros,
    criar_secao_banco_horas,
    criar_secao_trs,
)


def build(page: ft.Page) -> ft.Control:
    picker = obter_file_picker(page)

    secao_trs, recarregar_trs = criar_secao_trs(page)
    secao_bairros, recarregar_bairros = criar_secao_bairros(page)
    secao_banco_horas, recarregar_bh = criar_secao_banco_horas(page, picker)

    # ============ SEÇÃO: Aparência ============
    modo_atual = {"valor": config_service.obter("tema", "system")}
    linha_botoes_tema = ft.Row(spacing=8, wrap=True)

    def montar_botoes_tema() -> None:
        linha_botoes_tema.controls.clear()
        for valor, label in [
            ("light", "Claro"),
            ("dark", "Escuro"),
            ("system", "Sistema"),
        ]:
            ativo = modo_atual["valor"] == valor
            linha_botoes_tema.controls.append(
                ft.TextButton(
                    label,
                    on_click=lambda e, v=valor: mudar_tema(v),
                    style=ft.ButtonStyle(
                        bgcolor=(
                            ft.Colors.TEAL_700 if ativo else ft.Colors.GREY_100
                        ),
                        color=(
                            ft.Colors.WHITE if ativo else ft.Colors.GREY_800
                        ),
                        shape=ft.RoundedRectangleBorder(radius=10),
                        padding=ft.Padding.symmetric(
                            horizontal=16, vertical=10
                        ),
                    ),
                )
            )

    def mudar_tema(novo_modo: str) -> None:
        config_service.definir("tema", novo_modo)
        modo_atual["valor"] = novo_modo
        page.theme_mode = resolver_theme_mode(novo_modo)
        montar_botoes_tema()
        recarregar_bairros()
        recarregar_bh()
        snack(page, f"Tema alterado para {novo_modo}.")
        page.update()

    montar_botoes_tema()

    secao_aparencia = ft.Container(
        padding=16,
        border_radius=12,
        bgcolor=ft.Colors.SURFACE,
        content=ft.Column(
            [
                ft.Text("Aparência", size=16, weight=ft.FontWeight.BOLD),
                ft.Text(
                    "Escolha o tema do app.",
                    size=12,
                    color=ft.Colors.GREY_500,
                ),
                linha_botoes_tema,
            ],
            spacing=10,
        ),
    )

    # ============ SEÇÃO: Backup ============
    async def exportar(e) -> None:
        try:
            nome = f"backup_ace_{date.today().isoformat()}.zip"
            caminho = await picker.save_file(
                dialog_title="Salvar backup (dados e croquis)",
                file_name=nome,
                allowed_extensions=["zip", "json"],
            )
            if not caminho:
                snack(page, "Exportação cancelada.", ft.Colors.ORANGE_600)
                return
            backup_service.exportar_para_arquivo(caminho)
            snack(page, f"Backup (com croquis) salvo em: {caminho}")
        except Exception as ex:
            snack(page, f"Erro ao exportar: {ex}", ft.Colors.RED_500)

    async def importar(e) -> None:
        try:
            arquivos = await picker.pick_files(
                dialog_title="Escolher backup (.zip ou .json)",
                allow_multiple=False,
                allowed_extensions=["zip", "json"],
            )
            if not arquivos:
                snack(page, "Importação cancelada.", ft.Colors.ORANGE_600)
                return
            resumo = backup_service.importar_de_arquivo(
                arquivos[0].path, substituir=True
            )
            croquis_txt = (
                f", {resumo.get('croquis', 0)} croquis"
                if resumo.get("croquis")
                else ""
            )
            snack(
                page,
                f"Importado: {resumo['tr']} TRs, {resumo['producao']} produções, "
                f"{resumo['evento']} eventos{croquis_txt}.",
            )
            modo_atual["valor"] = config_service.obter("tema", "system")
            page.theme_mode = resolver_theme_mode(modo_atual["valor"])
            montar_botoes_tema()
            recarregar_trs()
            recarregar_bairros()
            recarregar_bh()
            page.update()
        except Exception as ex:
            snack(page, f"Erro ao importar: {ex}", ft.Colors.RED_500)

    def confirmar_importacao(e) -> None:
        dialog = ft.AlertDialog(
            title=ft.Text("Importar backup?"),
            content=ft.Text(
                "Isso vai substituir TODOS os dados atuais e restaurar os croquis "
                "dos bairros incluídos no arquivo (.zip ou .json). "
                "Faça um backup antes, se quiser preservar o que já existe."
            ),
            actions=[
                ft.TextButton(
                    "Cancelar", on_click=lambda ev: page.pop_dialog()
                ),
                ft.Button(
                    "Escolher arquivo",
                    on_click=lambda ev: (
                        page.pop_dialog(),
                        page.run_task(importar, ev),
                    ),
                ),
            ],
        )
        page.show_dialog(dialog)

    secao_backup = ft.Container(
        padding=16,
        border_radius=12,
        bgcolor=ft.Colors.SURFACE,
        content=ft.Column(
            [
                ft.Text("Backup", size=16, weight=ft.FontWeight.BOLD),
                ft.Text(
                    "Exporte seus dados e os croquis (PDFs) dos bairros em um arquivo ZIP.",
                    size=12,
                    color=ft.Colors.GREY_500,
                ),
                ft.Button(
                    "Exportar backup",
                    icon=ft.Icons.DOWNLOAD,
                    on_click=exportar,
                    style=ft.ButtonStyle(
                        bgcolor=ft.Colors.TEAL_700,
                        color=ft.Colors.WHITE,
                        shape=ft.RoundedRectangleBorder(radius=10),
                    ),
                ),
                ft.Button(
                    "Importar backup",
                    icon=ft.Icons.UPLOAD,
                    on_click=confirmar_importacao,
                    style=ft.ButtonStyle(
                        bgcolor=ft.Colors.GREY_800,
                        color=ft.Colors.WHITE,
                        shape=ft.RoundedRectangleBorder(radius=10),
                    ),
                ),
            ],
            spacing=10,
        ),
    )

    return ft.Column(
        scroll=ft.ScrollMode.AUTO,
        controls=[
            ft.Container(
                padding=20,
                content=ft.Column(
                    [
                        ft.Text(
                            "Configurações",
                            size=22,
                            weight=ft.FontWeight.BOLD,
                        ),
                        ft.Container(height=8),
                        secao_trs,
                        ft.Container(height=12),
                        secao_bairros,
                        ft.Container(height=12),
                        secao_banco_horas,
                        ft.Container(height=12),
                        secao_aparencia,
                        ft.Container(height=12),
                        secao_backup,
                    ],
                    spacing=0,
                ),
            )
        ],
    )
