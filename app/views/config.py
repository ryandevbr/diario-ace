from datetime import date
import flet as ft
from app.components.ui import snack, cor_fundo_item
from app.services import (
    backup_service, tr_service, config_service,
    bairro_service, banco_horas_service,
)
from app.utils.datas import para_br, de_br, escolher_data
from app.utils.files import obter_file_picker
from app.components.ui import snack


def build(page: ft.Page) -> ft.Control:
    picker = obter_file_picker(page)

    # ============ SEÇÃO: TRs ============
    anos = tr_service.anos_disponiveis()
    lista_trs = ft.Column(spacing=8)

    dropdown_ano = ft.Dropdown(
        label="Ano",
        options=[ft.dropdown.Option(key=str(a), text=str(a)) for a in anos],
        value=str(anos[0]) if anos else str(date.today().year),
    )

    def recarregar_trs():
        lista_trs.controls.clear()
        try:
            ano = int(dropdown_ano.value)
        except (TypeError, ValueError):
            ano = date.today().year
        trs = tr_service.listar_trs(ano)
        if not trs:
            lista_trs.controls.append(
                ft.Text("Nenhum TR cadastrado para este ano.", color=ft.Colors.GREY_500)
            )
            return
        for tr in trs:
            lista_trs.controls.append(_item_tr(page, tr, recarregar_trs))

    def on_mudar_ano(e):
        recarregar_trs()
        page.update()

    dropdown_ano.on_select = on_mudar_ano

    def criar_ano(e):
        try:
            ano = int(campo_novo_ano.value.strip())
        except ValueError:
            snack(page, "Digite um ano válido (ex.: 2027).", ft.Colors.RED_500)
            return
        tr_service.seed_trs_do_ano(ano)
        snack(page, f"TRs de {ano} criados. Ajuste as datas conforme o calendário.")
        campo_novo_ano.value = ""
        anos_atualizados = tr_service.anos_disponiveis()
        dropdown_ano.options = [
            ft.dropdown.Option(key=str(a), text=str(a)) for a in anos_atualizados
        ]
        dropdown_ano.value = str(ano)
        dropdown_ano.on_select = on_mudar_ano
        recarregar_trs()
        page.update()

    campo_novo_ano = ft.TextField(
        label="Criar TRs de outro ano",
        hint_text="Ex.: 2027",
        width=200,
        keyboard_type=ft.KeyboardType.NUMBER,
    )

    recarregar_trs()

    secao_trs = ft.Container(
        padding=16,
        border_radius=12,
        bgcolor=ft.Colors.SURFACE,
        content=ft.Column([
            ft.Text("TRs do ano", size=16, weight=ft.FontWeight.BOLD),
            ft.Text(
                "Ajuste as datas conforme o calendário enviado pelos supervisores.",
                size=12, color=ft.Colors.GREY_500,
            ),
            dropdown_ano,
            lista_trs,
            ft.Divider(),
            ft.Text("Criar novo ano", size=14, weight=ft.FontWeight.BOLD),
            ft.Row([
                campo_novo_ano,
                ft.Button("Criar", on_click=criar_ano),
            ], spacing=10, wrap=True),
        ], spacing=10),
    )

    # ============ SEÇÃO: Bairros ============
    lista_bairros = ft.Column(spacing=6)
    campo_novo_bairro = ft.TextField(
        label="Novo bairro",
        hint_text="Ex.: Centro",
        expand=True,
    )

    def recarregar_bairros():
        lista_bairros.controls.clear()
        bairros = bairro_service.listar_todos()
        if not bairros:
            lista_bairros.controls.append(
                ft.Text("Nenhum bairro cadastrado.", color=ft.Colors.GREY_500)
            )
            return
        for b in bairros:
            lista_bairros.controls.append(_item_bairro(page, b, recarregar_bairros))

    def criar_bairro(e):
        nome = (campo_novo_bairro.value or "").strip()
        if not nome:
            snack(page, "Digite um nome.", ft.Colors.RED_500)
            return
        if bairro_service.buscar_por_nome(nome):
            snack(page, f"'{nome}' já existe.", ft.Colors.ORANGE_600)
            return
        bairro_service.criar(nome)
        campo_novo_bairro.value = ""
        snack(page, f"Bairro '{nome}' criado.")
        recarregar_bairros()
        page.update()

    recarregar_bairros()

    secao_bairros = ft.Container(
        padding=16,
        border_radius=12,
        bgcolor=ft.Colors.SURFACE,
        content=ft.Column([
            ft.Text("Bairros", size=16, weight=ft.FontWeight.BOLD),
            ft.Text(
                "Bairros usados nos dropdowns de produção.",
                size=12, color=ft.Colors.GREY_500,
            ),
            ft.Row([
                campo_novo_bairro,
                ft.Button("Criar", on_click=criar_bairro),
            ], spacing=8),
            ft.Divider(),
            lista_bairros,
        ], spacing=10),
    )

    # ============ SEÇÃO: Banco de Horas ============
    saldo_lbl = ft.Text("", size=28, weight=ft.FontWeight.BOLD)
    totais_lbl = ft.Text("", size=12, color=ft.Colors.GREY_500)
    lista_bh = ft.Column(spacing=6)

    def recarregar_bh():
        info = banco_horas_service.resumo_saldo()
        saldo_lbl.value = (
            f"{info['sinal']}{info['hhmm']}"
            + (f"  ({info['dias']})" if info['horas'] != 0 else "")
        )
        saldo_lbl.color = (
            ft.Colors.GREEN_600 if info["horas"] >= 0 else ft.Colors.RED_500
        )

        ano_atual = date.today().year
        tot = banco_horas_service.total_por_tipo(ano_atual)
        totais_lbl.value = (
            f"Em {ano_atual}: +{banco_horas_service.formatar_horas(tot['trabalhada'])} "
            f"trabalhadas, −{banco_horas_service.formatar_horas(tot['compensacao'])} "
            f"compensadas. Equivalente a "
            f"{banco_horas_service.formatar_dias(info['horas'])} de folga."
        )

        # resto continua igual

        lista_bh.controls.clear()
        movs = banco_horas_service.listar_todos()
        if not movs:
            lista_bh.controls.append(
                ft.Text("Nenhuma movimentação cadastrada.", color=ft.Colors.GREY_500)
            )
            return
        for m in movs:
            lista_bh.controls.append(_item_banco_horas(page, m, recarregar_bh))

    def abrir_nova_movimentacao(e):
        campo_data = ft.TextField(
            label="Data (DD/MM/AAAA)",
            value=para_br(date.today()),
            read_only=True,
            expand=True,
        )
        campo_horas = ft.TextField(
            label="Horas (HH:MM)",
            hint_text="Ex.: 08:00",
            value="08:00",
        )
        dropdown_tipo = ft.Dropdown(
            label="Tipo",
            options=[
                ft.dropdown.Option(key="trabalhada", text="Horas Trabalhadas"),
                ft.dropdown.Option(key="compensacao", text="Compensação"),
            ],
            value="trabalhada",
        )
        campo_desc = ft.TextField(label="Descrição (opcional)")
        erro = ft.Text("", color=ft.Colors.RED)

        def escolher(ev):
            def cb(d):
                campo_data.value = para_br(d)
                page.update()
            escolher_data(page, cb)

        def salvar(ev):
            try:
                d = de_br(campo_data.value)
            except ValueError:
                erro.value = "Data inválida."
                page.update()
                return
            try:
                horas = banco_horas_service._parse_horas(campo_horas.value)
            except banco_horas_service.BancoHorasErro as ex:
                erro.value = str(ex)
                page.update()
                return
            try:
                banco_horas_service.adicionar(
                    d, horas, dropdown_tipo.value,
                    campo_desc.value.strip() or None,
                )
            except banco_horas_service.BancoHorasErro as ex:
                erro.value = str(ex)
                page.update()
                return

            # Fecha o diálogo principal primeiro
            page.pop_dialog()
            snack(page, "Movimentação registrada.")
            recarregar_bh()
            page.update()

            # Depois sugere o evento no calendário
            if dropdown_tipo.value == "compensacao":
                _sugerir_evento_calendario(
                    page, d, horas, campo_desc.value.strip() or None
                )

        dialog = ft.AlertDialog(
            title=ft.Text("Nova movimentação"),
            content=ft.Column(
                [
                    ft.Row([
                        campo_data,
                        ft.IconButton(
                            icon=ft.Icons.CALENDAR_MONTH,
                            on_click=escolher,
                        ),
                    ], spacing=4),
                    campo_horas,
                    dropdown_tipo,
                    campo_desc,
                    erro,
                ],
                tight=True, spacing=10, width=380,
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda ev: page.pop_dialog()),
                ft.Button("Salvar", on_click=salvar),
            ],
        )
        page.show_dialog(dialog)

    async def importar_extrato(e):
        try:
            arquivos = await picker.pick_files(
                dialog_title="Escolher extrato",
                allow_multiple=False,
                allowed_extensions=["csv", "xlsx", "xlsm"],
            )
            if not arquivos:
                return
            linhas = banco_horas_service.ler_planilha(arquivos[0].path)
            if not linhas:
                snack(page, "Nenhuma linha encontrada.", ft.Colors.ORANGE_600)
                return

            preview = "\n".join(
                f"• {para_br(l['data'])} — "
                f"{'+' if l['tipo'] == 'trabalhada' else '−'}"
                f"{banco_horas_service.formatar_horas(l['horas'])} "
                f"({l['tipo']})"
                for l in linhas[:5]
            )
            resto = len(linhas) - min(5, len(linhas))
            if resto > 0:
                preview += f"\n... e mais {resto} linha(s)."

            def confirmar(ev):
                page.pop_dialog()
                try:
                    resumo = banco_horas_service.importar_linhas(
                        linhas, substituir=True
                    )
                    snack(page, f"Importadas {resumo['inseridos']} movimentações.")
                    recarregar_bh()
                    page.update()
                except Exception as ex:
                    snack(page, f"Erro: {ex}", ft.Colors.RED_500)

            dialog = ft.AlertDialog(
                title=ft.Text("Importar extrato"),
                content=ft.Column([
                    ft.Text(f"{len(linhas)} movimentações encontradas."),
                    ft.Container(height=4),
                    ft.Text(preview, size=12, color=ft.Colors.GREY_500),
                    ft.Container(height=6),
                    ft.Text(
                        "A importação substitui TODAS as movimentações atuais. "
                        "Faça um backup antes se quiser preservar.",
                        size=11, color=ft.Colors.ORANGE_700,
                    ),
                ], tight=True, spacing=4, width=420),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda ev: page.pop_dialog()),
                    ft.Button("Importar", on_click=confirmar),
                ],
            )
            page.show_dialog(dialog)

        except banco_horas_service.BancoHorasErro as ex:
            snack(page, f"Erro no extrato: {ex}", ft.Colors.RED_500)
        except Exception as ex:
            snack(page, f"Erro inesperado: {ex}", ft.Colors.RED_500)

    recarregar_bh()

    secao_banco_horas = ft.Container(
        padding=16,
        border_radius=12,
        bgcolor=ft.Colors.SURFACE,
        content=ft.Column([
            ft.Text("Banco de Horas", size=16, weight=ft.FontWeight.BOLD),
            ft.Text(
                "Controle de horas extras trabalhadas e compensações.",
                size=12, color=ft.Colors.GREY_500,
            ),
            ft.Container(height=6),
            ft.Text("Saldo atual", size=11, color=ft.Colors.GREY_500),
            saldo_lbl,
            totais_lbl,
            ft.Container(height=8),
            ft.Row([
                ft.Button(
                    "Nova movimentação",
                    icon=ft.Icons.ADD,
                    on_click=abrir_nova_movimentacao,
                    style=ft.ButtonStyle(
                        bgcolor=ft.Colors.TEAL_700,
                        color=ft.Colors.WHITE,
                        shape=ft.RoundedRectangleBorder(radius=10),
                    ),
                ),
                ft.Button(
                    "Importar extrato",
                    icon=ft.Icons.UPLOAD_FILE,
                    on_click=importar_extrato,
                    style=ft.ButtonStyle(
                        bgcolor=ft.Colors.INDIGO_700,
                        color=ft.Colors.WHITE,
                        shape=ft.RoundedRectangleBorder(radius=10),
                    ),
                ),
            ], spacing=8, wrap=True),
            ft.Divider(),
            ft.Text("Movimentações", size=13, weight=ft.FontWeight.BOLD),
            lista_bh,
        ], spacing=10),
    )

    # ============ SEÇÃO: Aparência ============
    modo_atual = {"valor": config_service.obter("tema", "system")}

    def mudar_tema(novo_modo):
        config_service.definir("tema", novo_modo)
        modo_atual["valor"] = novo_modo
        page.theme_mode = {
            "light": ft.ThemeMode.LIGHT,
            "dark": ft.ThemeMode.DARK,
            "system": ft.ThemeMode.SYSTEM,
        }.get(novo_modo, ft.ThemeMode.SYSTEM)
        snack(page, f"Tema alterado para {novo_modo}.")
        page.update()

    def botao_tema(valor, label):
        ativo = modo_atual["valor"] == valor
        return ft.TextButton(
            label,
            on_click=lambda e, v=valor: mudar_tema(v),
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.TEAL_700 if ativo else ft.Colors.GREY_100,
                color=ft.Colors.WHITE if ativo else ft.Colors.GREY_800,
                shape=ft.RoundedRectangleBorder(radius=10),
                padding=ft.Padding.symmetric(horizontal=16, vertical=10),
            ),
        )

    secao_aparencia = ft.Container(
        padding=16,
        border_radius=12,
        bgcolor=ft.Colors.SURFACE,
        content=ft.Column([
            ft.Text("Aparência", size=16, weight=ft.FontWeight.BOLD),
            ft.Text("Escolha o tema do app.", size=12, color=ft.Colors.GREY_500),
            ft.Row([
                botao_tema("light", "Claro"),
                botao_tema("dark", "Escuro"),
                botao_tema("system", "Sistema"),
            ], spacing=8, wrap=True),
        ], spacing=10),
    )

    # ============ SEÇÃO: Backup ============
    async def exportar(e):
        try:
            nome = f"backup_ace_{date.today().isoformat()}.json"
            caminho = await picker.save_file(
                dialog_title="Salvar backup",
                file_name=nome,
                allowed_extensions=["json"],
            )
            if not caminho:
                snack(page, "Exportação cancelada.", ft.Colors.ORANGE_600)
                return
            backup_service.exportar_para_arquivo(caminho)
            snack(page, f"Backup salvo em: {caminho}")
        except Exception as ex:
            snack(page, f"Erro ao exportar: {ex}", ft.Colors.RED_500)

    async def importar(e):
        try:
            arquivos = await picker.pick_files(
                dialog_title="Escolher backup",
                allow_multiple=False,
                allowed_extensions=["json"],
            )
            if not arquivos:
                snack(page, "Importação cancelada.", ft.Colors.ORANGE_600)
                return
            resumo = backup_service.importar_de_arquivo(
                arquivos[0].path, substituir=True
            )
            snack(
                page,
                f"Importado: {resumo['tr']} TRs, {resumo['producao']} produções, "
                f"{resumo['evento']} eventos.",
            )
            recarregar_trs()
            recarregar_bairros()
            recarregar_bh()
            page.update()
        except Exception as ex:
            snack(page, f"Erro ao importar: {ex}", ft.Colors.RED_500)

    def confirmar_importacao(e):
        dialog = ft.AlertDialog(
            title=ft.Text("Importar backup?"),
            content=ft.Text(
                "Isso vai substituir TODOS os dados atuais. "
                "Faça um backup antes, se quiser preservar o que já existe."
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda ev: page.pop_dialog()),
                ft.Button(
                    "Escolher arquivo",
                    on_click=lambda ev: (page.pop_dialog(), page.run_task(importar, ev)),
                ),
            ],
        )
        page.show_dialog(dialog)

    secao_backup = ft.Container(
        padding=16,
        border_radius=12,
        bgcolor=ft.Colors.SURFACE,
        content=ft.Column([
            ft.Text("Backup", size=16, weight=ft.FontWeight.BOLD),
            ft.Text(
                "Exporte seus dados para um arquivo JSON e guarde em local seguro.",
                size=12, color=ft.Colors.GREY_500,
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
        ], spacing=10),
    )

    # ============ LAYOUT ============
    return ft.Column(
        scroll=ft.ScrollMode.AUTO,
        controls=[
            ft.Container(
                padding=20,
                content=ft.Column([
                    ft.Text("Configurações", size=22, weight=ft.FontWeight.BOLD),
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
                ], spacing=0),
            )
        ],
    )


def _item_tr(page: ft.Page, tr, recarregar) -> ft.Control:
    def abrir_edicao(e):
        campo_ini = ft.TextField(
            label="Início (DD/MM/AAAA)",
            value=para_br(tr.data_inicio),
            read_only=True,
            expand=True,
        )
        campo_fim = ft.TextField(
            label="Fim (DD/MM/AAAA)",
            value=para_br(tr.data_fim),
            read_only=True,
            expand=True,
        )
        campo_min = ft.TextField(
            label="Meta mínima",
            value=str(tr.meta_min),
            keyboard_type=ft.KeyboardType.NUMBER,
        )
        campo_max = ft.TextField(
            label="Meta máxima",
            value=str(tr.meta_max),
            keyboard_type=ft.KeyboardType.NUMBER,
        )
        campo_inicial = ft.TextField(
            label="Produção inicial",
            value=str(getattr(tr, "producao_inicial", 0)),
            keyboard_type=ft.KeyboardType.NUMBER,
        )
        erro = ft.Text("", color=ft.Colors.RED)

        def escolher_ini(e):
            def cb(d):
                campo_ini.value = para_br(d)
                page.update()
            escolher_data(page, cb)

        def escolher_fim(e):
            def cb(d):
                campo_fim.value = para_br(d)
                page.update()
            escolher_data(page, cb)

        def salvar(ev):
            try:
                ini = de_br(campo_ini.value)
                fim = de_br(campo_fim.value)
                meta_min = int(campo_min.value.strip())
                meta_max = int(campo_max.value.strip())
                inicial = int((campo_inicial.value or "0").strip())
            except ValueError:
                erro.value = "Verifique datas e valores numéricos."
                page.update()
                return
            if ini > fim:
                erro.value = "A data de início não pode ser posterior à data de fim."
                page.update()
                return
            if meta_min > meta_max:
                erro.value = "A meta mínima não pode ser maior que a máxima."
                page.update()
                return
            if inicial < 0:
                erro.value = "A produção inicial não pode ser negativa."
                page.update()
                return

            tr_service.atualizar_tr(tr.id, ini, fim, meta_min, meta_max, inicial)
            page.pop_dialog()
            snack(page, f"TR {tr.numero} atualizado.")
            recarregar()
            page.update()

        dialog = ft.AlertDialog(
            title=ft.Text(f"Editar TR {tr.numero} — {tr.ano}"),
            content=ft.Column(
                [
                    ft.Row([
                        campo_ini,
                        ft.IconButton(icon=ft.Icons.CALENDAR_MONTH, on_click=escolher_ini),
                    ], spacing=4),
                    ft.Row([
                        campo_fim,
                        ft.IconButton(icon=ft.Icons.CALENDAR_MONTH, on_click=escolher_fim),
                    ], spacing=4),
                    campo_min,
                    campo_max,
                    campo_inicial,
                    erro,
                ],
                tight=True, spacing=10, width=380,
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda ev: page.pop_dialog()),
                ft.Button("Salvar", on_click=salvar),
            ],
        )
        page.show_dialog(dialog)

    inicial_txt = ""
    if getattr(tr, "producao_inicial", 0) > 0:
        inicial_txt = f" · inicial: {tr.producao_inicial}"

    return ft.Container(
        padding=12,
        bgcolor=ft.Colors.SURFACE,
        border=ft.Border.all(1, ft.Colors.GREY_300),
        border_radius=10,
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Column([
                    ft.Text(f"TR {tr.numero}", weight=ft.FontWeight.BOLD),
                    ft.Text(f"{para_br(tr.data_inicio)} a {para_br(tr.data_fim)}", size=12),
                    ft.Text(f"Meta: {tr.meta_min}–{tr.meta_max}{inicial_txt}",
                            size=12, color=ft.Colors.GREY_500),
                ], spacing=2, expand=True),
                ft.IconButton(
                    icon=ft.Icons.EDIT_OUTLINED,
                    icon_color=ft.Colors.BLUE_400,
                    on_click=abrir_edicao,
                ),
            ],
        ),
    )


def _item_bairro(page: ft.Page, b: dict, recarregar) -> ft.Control:
    ativo = bool(b.get("ativo", 1))

    def alternar(e):
        bairro_service.alternar_ativo(b["id"], not ativo)
        snack(page, f"'{b['nome']}' agora está {'inativo' if ativo else 'ativo'}.")
        recarregar()
        page.update()

    def renomear(e):
        campo = ft.TextField(label="Novo nome", value=b["nome"])
        erro = ft.Text("", color=ft.Colors.RED)

        def salvar(ev):
            novo = (campo.value or "").strip()
            if not novo:
                erro.value = "Nome não pode ser vazio."
                page.update()
                return
            outro = bairro_service.buscar_por_nome(novo)
            if outro and outro["id"] != b["id"]:
                erro.value = "Já existe outro bairro com esse nome."
                page.update()
                return
            bairro_service.renomear(b["id"], novo)
            page.pop_dialog()
            snack(page, "Bairro renomeado.")
            recarregar()
            page.update()

        dialog = ft.AlertDialog(
            title=ft.Text(f"Renomear '{b['nome']}'"),
            content=ft.Column([campo, erro], tight=True, spacing=10, width=320),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda ev: page.pop_dialog()),
                ft.Button("Salvar", on_click=salvar),
            ],
        )
        page.show_dialog(dialog)

    return ft.Container(
        padding=10,
        border_radius=8,
        bgcolor=cor_fundo_item(page),
        content=ft.Row([
            ft.Text(b["nome"], size=13, expand=True,
                    color=ft.Colors.GREY_500 if not ativo else None),
            ft.IconButton(
                icon=ft.Icons.EDIT_OUTLINED,
                icon_color=ft.Colors.BLUE_400,
                tooltip="Renomear",
                on_click=renomear,
            ),
            ft.Switch(
                value=ativo,
                on_change=alternar,
                active_color=ft.Colors.TEAL_700,
            ),
        ], spacing=6),
    )


def _item_banco_horas(page: ft.Page, m: dict, recarregar) -> ft.Control:
    positivo = m["tipo"] == "trabalhada"
    sinal = "+" if positivo else "−"
    cor = ft.Colors.GREEN_600 if positivo else ft.Colors.RED_500

    def editar(e):
        campo_data = ft.TextField(
            label="Data (DD/MM/AAAA)",
            value=para_br(date.fromisoformat(m["data"])),
            read_only=True,
            expand=True,
        )
        campo_horas = ft.TextField(
            label="Horas (HH:MM)",
            value=banco_horas_service.formatar_horas(m["horas"]),
        )
        dropdown_tipo = ft.Dropdown(
            label="Tipo",
            options=[
                ft.dropdown.Option(key="trabalhada", text="Horas Trabalhadas"),
                ft.dropdown.Option(key="compensacao", text="Compensação"),
            ],
            value=m["tipo"],
        )
        campo_desc = ft.TextField(
            label="Descrição (opcional)",
            value=m.get("descricao") or "",
        )
        erro = ft.Text("", color=ft.Colors.RED)

        def escolher(ev):
            def cb(d):
                campo_data.value = para_br(d)
                page.update()
            escolher_data(page, cb)

        def salvar(ev):
            try:
                d = de_br(campo_data.value)
                horas = banco_horas_service._parse_horas(campo_horas.value)
                banco_horas_service.atualizar(
                    m["id"], d, horas, dropdown_tipo.value,
                    campo_desc.value.strip() or None,
                )
            except Exception as ex:
                erro.value = str(ex)
                page.update()
                return
            page.pop_dialog()
            snack(page, "Movimentação atualizada.")
            recarregar()
            page.update()

        dialog = ft.AlertDialog(
            title=ft.Text("Editar movimentação"),
            content=ft.Column(
                [
                    ft.Row([
                        campo_data,
                        ft.IconButton(
                            icon=ft.Icons.CALENDAR_MONTH,
                            on_click=escolher,
                        ),
                    ], spacing=4),
                    campo_horas,
                    dropdown_tipo,
                    campo_desc,
                    erro,
                ],
                tight=True, spacing=10, width=380,
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda ev: page.pop_dialog()),
                ft.Button("Salvar", on_click=salvar),
            ],
        )
        page.show_dialog(dialog)

    def excluir(e):
        def confirmar(ev):
            banco_horas_service.remover(m["id"])
            page.pop_dialog()
            snack(page, "Movimentação removida.", ft.Colors.ORANGE_600)
            recarregar()
            page.update()

        dialog = ft.AlertDialog(
            title=ft.Text("Excluir movimentação?"),
            content=ft.Text(
                f"{para_br(date.fromisoformat(m['data']))} — "
                f"{sinal}{banco_horas_service.formatar_horas(m['horas'])}"
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda ev: page.pop_dialog()),
                ft.Button("Excluir", on_click=confirmar),
            ],
        )
        page.show_dialog(dialog)

    return ft.Container(
        padding=10,
        border_radius=8,
        bgcolor=cor_fundo_item(page),
        content=ft.Row([
            ft.Column([
                ft.Text(para_br(date.fromisoformat(m["data"])),
                        weight=ft.FontWeight.BOLD, size=12),
                ft.Text(
                    f"{sinal}{banco_horas_service.formatar_horas(m['horas'])} — "
                    f"{banco_horas_service.LABEL_TIPO.get(m['tipo'], m['tipo'])}",
                    size=12, color=cor, weight=ft.FontWeight.W_600,
                ),
                ft.Text(m.get("descricao") or "", size=11,
                        color=ft.Colors.GREY_500) if m.get("descricao") else ft.Container(),
            ], spacing=2, expand=True),
            ft.IconButton(
                icon=ft.Icons.EDIT_OUTLINED,
                icon_color=ft.Colors.BLUE_400,
                on_click=editar,
            ),
            ft.IconButton(
                icon=ft.Icons.DELETE_OUTLINE,
                icon_color=ft.Colors.RED_400,
                on_click=excluir,
            ),
        ], spacing=4),
    )

def _sugerir_evento_calendario(page: ft.Page, d, horas: float, obs: str | None):
    """Depois de lançar compensação no BH, sugere evento no calendário."""
    from app.services import evento_service, tr_service

    tr = tr_service.tr_por_data(d)
    if tr is None:
        return

    fracao = min(1.0, horas / 8.0)

    def confirmar(ev):
        page.pop_dialog()
        try:
            evento_service.adicionar_evento(
                d, "compensacao", fracao,
                obs or "Folga referente ao banco de horas",
            )
            snack(page, "Evento adicionado ao calendário.")
        except Exception as ex:
            snack(page, f"Erro: {ex}", ft.Colors.RED_500)

    def ignorar(ev):
        page.pop_dialog()

    dialog = ft.AlertDialog(
        title=ft.Text("Criar evento no calendário?"),
        content=ft.Text(
            f"Deseja registrar esse dia como compensação no calendário "
            f"(peso {fracao:.2f})? Isso ajusta o cálculo das metas."
        ),
        actions=[
            ft.TextButton("Não", on_click=ignorar),
            ft.Button("Sim, criar", on_click=confirmar),
        ],
    )
    page.show_dialog(dialog)