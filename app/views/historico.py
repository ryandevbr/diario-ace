from datetime import date
from dataclasses import asdict
from datetime import date, datetime, timedelta
import os
import tempfile
import flet as ft
from app.services import relatorio_service
from app.services import (
    tr_service, producao_service, evento_service,
    pdf_service, import_service,
)
from app.utils.datas import para_br, de_br, escolher_data
from app.utils.files import obter_file_picker
from app.utils.share import compartilhar_arquivo
from app.components.ui import snack
from app.services import bairro_service, atividade_service


def _cor_fundo_card(page: ft.Page, nivel: str = "principal") -> str:
    """Cor de fundo adaptada ao tema atual.

    Prioridade:
      1. Se theme_mode é LIGHT ou DARK → usa essa escolha.
      2. Se theme_mode é SYSTEM → consulta platform_brightness (preferência do SO).
    """
    if page.theme_mode == ft.ThemeMode.DARK:
        escuro = True
    elif page.theme_mode == ft.ThemeMode.LIGHT:
        escuro = False
    else:
        # SYSTEM
        brilho = getattr(page, "platform_brightness", None)
        escuro = (brilho == ft.Brightness.DARK)

    if escuro:
        return ft.Colors.GREY_800 if nivel == "principal" else ft.Colors.GREY_700
    return ft.Colors.WHITE if nivel == "principal" else ft.Colors.GREY_100


def build(page: ft.Page) -> ft.Control:
    hoje = date.today()
    todos = tr_service.listar_todos_trs()
    modo_visao = {"valor": "diario"}

    if not todos:
        return ft.Container(
            padding=20,
            content=ft.Text("Nenhum TR cadastrado."),
        )

    # Agrupa por ano
    trs_por_ano: dict[int, list] = {}
    for t in todos:
        trs_por_ano.setdefault(t.ano, []).append(t)
    for ano in trs_por_ano:
        trs_por_ano[ano].sort(key=lambda x: x.numero)

    anos_disponiveis = sorted(trs_por_ano.keys(), reverse=True)

    tr_ativo = tr_service.tr_por_data(hoje)
    ano_inicial = tr_ativo.ano if tr_ativo else anos_disponiveis[0]
    numero_inicial = tr_ativo.numero if tr_ativo else trs_por_ano[ano_inicial][0].numero

    estado = {"ano": ano_inicial, "numero": numero_inicial}
    picker = obter_file_picker(page)

    def tr_selecionado():
        lista = trs_por_ano.get(estado["ano"], [])
        return next((t for t in lista if t.numero == estado["numero"]), None)

    
    botoes_visao = ft.Row(spacing=6)

    def montar_botoes_visao():
        botoes_visao.controls.clear()
        for valor, label in [("diario", "Diário"), ("semanal", "Semanal")]:
            ativo = modo_visao["valor"] == valor
            botoes_visao.controls.append(
                ft.TextButton(
                    label,
                    on_click=lambda e, v=valor: definir_visao(v),
                    style=ft.ButtonStyle(
                        bgcolor=ft.Colors.TEAL_700 if ativo else ft.Colors.GREY_100,
                        color=ft.Colors.WHITE if ativo else ft.Colors.GREY_800,
                        shape=ft.RoundedRectangleBorder(radius=20),
                        padding=ft.Padding.symmetric(horizontal=14, vertical=8),
                    ),
                )
            )

    def definir_visao(valor):
        modo_visao["valor"] = valor
        recarregar()

    montar_botoes_visao()

    lista_widget = ft.Column(spacing=8)
    total_lbl = ft.Text("", size=13, color=ft.Colors.GREY_500)

    dropdown_ano = ft.Dropdown(
        label="Ano",
        options=[ft.dropdown.Option(key=str(a), text=str(a)) for a in anos_disponiveis],
        value=str(estado["ano"]),
        width=140,
    )

    dropdown_numero = ft.Dropdown(
        label="TR",
        options=[],
        value=str(estado["numero"]),
        width=140,
    )

    def atualizar_dropdown_numero():
        trs = trs_por_ano.get(estado["ano"], [])
        dropdown_numero.options = [
            ft.dropdown.Option(key=str(t.numero), text=str(t.numero))
            for t in trs
        ]
        numeros = {t.numero for t in trs}
        if estado["numero"] not in numeros:
            estado["numero"] = trs[0].numero if trs else 1
        dropdown_numero.value = str(estado["numero"])

    def on_ano_change(e):
        try:
            estado["ano"] = int(dropdown_ano.value)
        except (TypeError, ValueError):
            return
        atualizar_dropdown_numero()
        recarregar()
        page.update()

    def on_numero_change(e):
        try:
            estado["numero"] = int(dropdown_numero.value)
        except (TypeError, ValueError):
            return
        recarregar()
        page.update()

    dropdown_ano.on_select = on_ano_change
    dropdown_numero.on_select = on_numero_change
    atualizar_dropdown_numero()

    # ---------- Lista ----------
    def recarregar():
        tr = tr_selecionado()
        lista_widget.controls.clear()
        if tr is None:
            total_lbl.value = "TR não encontrado."
            page.update()
            return

        producoes = producao_service.listar_producoes_do_tr(tr.id)
        soma = sum(p["quantidade"] for p in producoes)
        total_lbl.value = (
            f"TR {tr.numero} — {para_br(tr.data_inicio)} a {para_br(tr.data_fim)}: "
            f"{soma} imóveis em {len(producoes)} dia(s)."
        )

        if not producoes:
            lista_widget.controls.append(
                ft.Text("Nenhuma produção registrada neste TR.", color=ft.Colors.GREY_500)
            )
            return

        if modo_visao["valor"] == "semanal":
            _montar_visao_semanal(producoes, lista_widget)
        else:
            for p in producoes:
                lista_widget.controls.append(_item_producao(page, p, recarregar))

        montar_botoes_visao()

    # ---------- Novo lançamento ----------
    def abrir_novo_lancamento(e):
        tr = tr_selecionado()
        if tr is None:
            snack(page, "Nenhum TR selecionado.", ft.Colors.RED_500)
            return
        data_padrao = max(tr.data_inicio, min(hoje, tr.data_fim))

        campo_data = ft.TextField(
            label="Data (DD/MM/AAAA)",
            value=para_br(data_padrao),
            read_only=True,
            expand=True,
        )
        bairros = bairro_service.listar_ativos()
        atividades = atividade_service.listar()

        dropdown_qtd = ft.Dropdown(
            label="Imóveis trabalhados",
            options=[ft.dropdown.Option(key=str(n), text=str(n)) for n in range(0, 41)],
            value="0",
        )
        dropdown_bairro = ft.Dropdown(
            label="Bairro",
            options=[ft.dropdown.Option(key=str(b["id"]), text=b["nome"]) for b in bairros],
            value=str(bairros[0]["id"]) if bairros else None,
        )
        dropdown_atividade = ft.Dropdown(
            label="Atividade",
            options=[ft.dropdown.Option(key=a, text=a) for a in atividades],
            value="Tratamento",
        )
        dropdown_fechados = ft.Dropdown(
            label="Fechados",
            options=[ft.dropdown.Option(key=str(n), text=str(n)) for n in range(0, 31)],
            value="0",
            width=100,
        )
        dropdown_resgatados = ft.Dropdown(
            label="Resgatados",
            options=[ft.dropdown.Option(key=str(n), text=str(n)) for n in range(0, 31)],
            value="0",
            width=100,
        )
        dropdown_recusados = ft.Dropdown(
            label="Recusados",
            options=[ft.dropdown.Option(key=str(n), text=str(n)) for n in range(0, 31)],
            value="0",
            width=100,
        )
        campo_obs = ft.TextField(label="Observação (opcional)")
        erro = ft.Text("", color=ft.Colors.RED)

        def escolher(e):
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

            if d < tr.data_inicio or d > tr.data_fim:
                erro.value = "A data precisa estar dentro do TR selecionado."
                page.update()
                return

            if d > hoje:
                erro.value = "Não é possível lançar produção futura."
                page.update()
                return

            try:
                qtd = int(dropdown_qtd.value or "0")
            except ValueError:
                erro.value = "Quantidade inválida."
                page.update()
                return

            try:
                bairro_id = int(dropdown_bairro.value) if dropdown_bairro.value else None
            except (ValueError, TypeError):
                bairro_id = None

            try:
                fechados = int(dropdown_fechados.value or "0")
                resgatados = int(dropdown_resgatados.value or "0")
                recusados = int(dropdown_recusados.value or "0")
            except ValueError:
                fechados = resgatados = recusados = 0

            producao_service.registrar_producao(
                d, tr.id, qtd,
                bairro_id=bairro_id,
                atividade=dropdown_atividade.value,
                fechados=fechados,
                resgatados=resgatados,
                recusados=recusados,
                obs=campo_obs.value.strip() or None,
            )

            page.pop_dialog()
            snack(page, f"Lançado: {qtd} imóveis em {para_br(d)}.")
            recarregar()
            page.update()

        dialog = ft.AlertDialog(
            title=ft.Text(f"Novo lançamento — TR {tr.numero}/{tr.ano}"),
            content=ft.Column(
                [
                    ft.Row([
                        campo_data,
                        ft.IconButton(
                            icon=ft.Icons.CALENDAR_MONTH,
                            tooltip="Escolher data",
                            on_click=escolher,
                        ),
                    ], spacing=4),
                    dropdown_qtd,
                    dropdown_bairro,
                    dropdown_atividade,
                    campo_obs,
                    erro,

                    ft.Row([
                        dropdown_fechados,
                        dropdown_resgatados,
                        dropdown_recusados,
                    ], spacing=8),
                ],
                tight=True, spacing=10, width=360,
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda ev: page.pop_dialog()),
                ft.Button("Salvar", on_click=salvar),
            ],
        )
        page.show_dialog(dialog)

    # ---------- Exportar PDF ----------
    async def exportar_pdf(e):
        tr = tr_selecionado()
        if tr is None:
            snack(page, "Nenhum TR selecionado.", ft.Colors.RED_500)
            return

        producoes = producao_service.listar_producoes_do_tr(tr.id)
        eventos = [
            asdict(ev)
            for ev in evento_service.listar_eventos(tr.data_inicio, tr.data_fim)
        ]

        total = sum(p["quantidade"] for p in producoes)
        resumo_txt = (
            f"TR {tr.numero}/{tr.ano}\n"
            f"Período: {para_br(tr.data_inicio)} a {para_br(tr.data_fim)}\n"
            f"{len(producoes)} dia(s) com produção\n"
            f"{total} imóveis no total\n"
            f"{len(eventos)} evento(s) no período"
        )

        def confirmar(ev):
            page.pop_dialog()
            page.run_task(_salvar_historico_pdf, tr, producoes, eventos)

        dialog = ft.AlertDialog(
            title=ft.Text("Gerar PDF do Histórico?"),
            content=ft.Column([
                ft.Text("Confira antes de gerar:"),
                ft.Container(height=6),
                ft.Text(resumo_txt, size=12, color=ft.Colors.GREY_700),
            ], tight=True, spacing=4, width=340),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda ev: page.pop_dialog()),
                ft.Button("Gerar PDF", on_click=confirmar),
            ],
        )
        page.show_dialog(dialog)

    async def _salvar_historico_pdf(tr, producoes, eventos):
        try:
            bairros_por_id = {b["id"]: b for b in bairro_service.listar_ativos()}
            nome = f"producao_TR{tr.numero}_{tr.ano}_{date.today().isoformat()}.pdf"
            caminho = await picker.save_file(
                dialog_title="Salvar PDF",
                file_name=nome,
                allowed_extensions=["pdf"],
            )
            if not caminho:
                snack(page, "Exportação cancelada.", ft.Colors.ORANGE_600)
                return
            pdf_service.exportar_historico_pdf(
                caminho, tr, producoes, eventos, bairros_por_id
            )
            snack(page, f"PDF salvo em {caminho}")
        except Exception as ex:
            snack(page, f"Erro ao gerar PDF: {ex}", ft.Colors.RED_500)

    def exportar_relatorio_anual(e):
        ano = estado["ano"]

        def confirmar(ev):
            page.pop_dialog()
            page.run_task(_salvar_relatorio_anual, ano)

        dialog = ft.AlertDialog(
            title=ft.Text("Gerar Relatório Anual?"),
            content=ft.Column([
                ft.Text(f"Ano: {ano}"),
                ft.Text("Inclui todos os TRs, consolidado por bairro e por atividade."),
                ft.Container(height=6),
                ft.Text(
                    "O PDF fica em paisagem e pode ter várias páginas.",
                    size=11, color=ft.Colors.GREY_500,
                ),
            ], tight=True, spacing=4, width=340),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda ev: page.pop_dialog()),
                ft.Button("Gerar PDF", on_click=confirmar),
            ],
        )
        page.show_dialog(dialog)

    async def _salvar_relatorio_anual(ano):
        try:
            dados = relatorio_service.dados_do_ano(ano)
            nome = f"relatorio_anual_{ano}_{date.today().isoformat()}.pdf"
            caminho = await picker.save_file(
                dialog_title="Salvar relatório anual",
                file_name=nome,
                allowed_extensions=["pdf"],
            )
            if not caminho:
                snack(page, "Exportação cancelada.", ft.Colors.ORANGE_600)
                return
            pdf_service.exportar_relatorio_anual_pdf(caminho, dados)
            snack(page, f"Relatório salvo em {caminho}")
        except Exception as ex:
            snack(page, f"Erro ao gerar relatório: {ex}", ft.Colors.RED_500)

    #--------- Exportar relatório anual ----------
    async def compartilhar_relatorio_anual(e):
        try:
            ano = estado["ano"]
            dados = relatorio_service.dados_do_ano(ano)
            nome = f"relatorio_anual_{ano}_{date.today().isoformat()}.pdf"
            caminho = os.path.join(tempfile.gettempdir(), nome)
            pdf_service.exportar_relatorio_anual_pdf(caminho, dados)

            ok = await compartilhar_arquivo(
                page, caminho,
                texto=f"Relatório anual {ano} — Diário ACE",
            )
            if not ok:
                caminho_salvo = await picker.save_file(
                    dialog_title="Salvar relatório",
                    file_name=nome,
                    allowed_extensions=["pdf"],
                )
                if caminho_salvo:
                    pdf_service.exportar_relatorio_anual_pdf(caminho_salvo, dados)
                    snack(page, f"Relatório salvo em {caminho_salvo}")
                else:
                    snack(page, "Compartilhamento indisponível.", ft.Colors.ORANGE_600)
        except Exception as ex:
            snack(page, f"Erro ao compartilhar relatório: {ex}", ft.Colors.RED_500)

    # ---------- Compartilhar PDF ----------
    async def compartilhar_pdf(e):
        tr = tr_selecionado()
        if tr is None:
            snack(page, "Nenhum TR selecionado.", ft.Colors.RED_500)
            return
        try:
            producoes = producao_service.listar_producoes_do_tr(tr.id)
            eventos = [
                asdict(ev)
                for ev in evento_service.listar_eventos(tr.data_inicio, tr.data_fim)
            ]
            nome = f"producao_TR{tr.numero}_{tr.ano}_{date.today().isoformat()}.pdf"
            caminho = os.path.join(tempfile.gettempdir(), nome)
            bairros_por_id = {b["id"]: b for b in bairro_service.listar_ativos()}
            pdf_service.exportar_historico_pdf(
                caminho, tr, producoes, eventos, bairros_por_id
            )

            ok = await compartilhar_arquivo(
                page, caminho,
                texto=f"Produção TR {tr.numero} — {tr.ano}",
            )
            if not ok:
                caminho_salvo = await picker.save_file(
                    dialog_title="Salvar PDF",
                    file_name=nome,
                    allowed_extensions=["pdf"],
                )
                if caminho_salvo:
                    pdf_service.exportar_historico_pdf(caminho_salvo, tr, producoes, eventos)
                    snack(page, f"PDF salvo em {caminho_salvo}")
                else:
                    snack(page, "Compartilhamento indisponível.", ft.Colors.ORANGE_600)
        except Exception as ex:
            snack(page, f"Erro ao compartilhar: {ex}", ft.Colors.RED_500)
            
    # ---------- Importar planilha ----------
    async def importar_planilha(e):
        try:
            arquivos = await picker.pick_files(
                dialog_title="Escolher planilha",
                allow_multiple=False,
                allowed_extensions=["csv", "xlsx", "xlsm"],
            )
            if not arquivos:
                return

            caminho = arquivos[0].path
            linhas = import_service.ler_planilha(caminho)

            if not linhas:
                snack(page, "Nenhuma linha encontrada na planilha.",
                      ft.Colors.ORANGE_600)
                return

            preview = linhas[:5]
            preview_txt = "\n".join(
                f"• {para_br(l['data'])}: {l['quantidade']} imóveis"
                + (f" ({l['observacao']})" if l['observacao'] else "")
                for l in preview
            )
            resto = len(linhas) - len(preview)
            if resto > 0:
                preview_txt += f"\n... e mais {resto} lançamentos."

            def confirmar(ev):
                page.pop_dialog()
                try:
                    resumo = import_service.importar_linhas(linhas)
                    partes = [
                        f"{resumo['inseridos']} inseridos",
                        f"{resumo['atualizados']} atualizados",
                    ]
                    if resumo["ignorados"]:
                        partes.append(f"{len(resumo['ignorados'])} ignorados")
                    snack(page, "Importação concluída: " + ", ".join(partes) + ".",
                          ft.Colors.GREEN_600)
                    recarregar()
                    page.update()
                except Exception as ex:
                    snack(page, f"Erro ao importar: {ex}", ft.Colors.RED_500)

            dialog = ft.AlertDialog(
                title=ft.Text("Importar planilha"),
                content=ft.Column([
                    ft.Text(f"Encontrados {len(linhas)} lançamentos."),
                    ft.Container(height=4),
                    ft.Text(preview_txt, size=12, color=ft.Colors.GREY_500),
                    ft.Container(height=6),
                    ft.Text(
                        "Datas que já existem no sistema serão sobrescritas. "
                        "A importação considera todos os TRs, não apenas o selecionado.",
                        size=11, color=ft.Colors.ORANGE_700,
                    ),
                ], tight=True, spacing=4, width=400),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda ev: page.pop_dialog()),
                    ft.Button("Importar", on_click=confirmar),
                ],
            )
            page.show_dialog(dialog)

        except import_service.ImportacaoErro as ex:
            snack(page, f"Erro na planilha: {ex}", ft.Colors.RED_500)
        except Exception as ex:
            snack(page, f"Erro inesperado: {ex}", ft.Colors.RED_500)

    recarregar()

    # ---------- Layout ----------
    secao_principal = ft.Container(
        padding=16,
        border_radius=12,
        bgcolor=_cor_fundo_card(page, "principal"),
        content=ft.Column([
            ft.Row([
                dropdown_ano,
                dropdown_numero,
            ], spacing=8),
            total_lbl,
            botoes_visao,
            ft.Divider(),
            ft.Row([
                ft.Button(
                    "Novo lançamento",
                    icon=ft.Icons.ADD,
                    on_click=abrir_novo_lancamento,
                    style=ft.ButtonStyle(
                        bgcolor=ft.Colors.TEAL_700,
                        color=ft.Colors.WHITE,
                        shape=ft.RoundedRectangleBorder(radius=10),
                    ),
                ),
                ft.Button(
                    "Exportar PDF",
                    icon=ft.Icons.PICTURE_AS_PDF,
                    on_click=exportar_pdf,
                    style=ft.ButtonStyle(
                        bgcolor=ft.Colors.GREY_800,
                        color=ft.Colors.WHITE,
                        shape=ft.RoundedRectangleBorder(radius=10),
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

                ft.Button(
                    "Relatório anual",
                    icon=ft.Icons.ASSESSMENT,
                    on_click=exportar_relatorio_anual,
                    style=ft.ButtonStyle(
                        bgcolor=ft.Colors.PURPLE_700,
                        color=ft.Colors.WHITE,
                        shape=ft.RoundedRectangleBorder(radius=10),
                    ),
                ),
                ft.Button(
                    "Compartilhar relatório",
                    icon=ft.Icons.SHARE,
                    on_click=compartilhar_relatorio_anual,
                    style=ft.ButtonStyle(
                        bgcolor=ft.Colors.PURPLE_400,
                        color=ft.Colors.WHITE,
                        shape=ft.RoundedRectangleBorder(radius=10),
                    ),
                ),

                ft.Button(
                    "Importar planilha",
                    icon=ft.Icons.UPLOAD_FILE,
                    on_click=importar_planilha,
                    style=ft.ButtonStyle(
                        bgcolor=ft.Colors.INDIGO_700,
                        color=ft.Colors.WHITE,
                        shape=ft.RoundedRectangleBorder(radius=10),
                    ),
                ),
            ], spacing=8, wrap=True),
            ft.Container(height=8),
            lista_widget,
        ], spacing=10),
    )

    return ft.Column(
        scroll=ft.ScrollMode.AUTO,
        controls=[
            ft.Container(
                padding=20,
                content=ft.Column([
                    ft.Text("Histórico", size=22, weight=ft.FontWeight.BOLD),
                    ft.Container(height=8),
                    secao_principal,
                ], spacing=0),
            )
        ],
    )


def _item_producao(page: ft.Page, p: dict, recarregar) -> ft.Control:
    bairro_nome = None
    if p.get("bairro_id"):
        b = bairro_service.buscar_por_id(p["bairro_id"])
        bairro_nome = b["nome"] if b else None
    atividade = p.get("atividade")
    def abrir_edicao(e):
        bairros = bairro_service.listar_ativos()
        atividades = atividade_service.listar()

        campo_qtd = ft.Dropdown(
            label="Quantidade",
            options=[ft.dropdown.Option(key=str(n), text=str(n)) for n in range(0, 41)],
            value=str(p["quantidade"]),
        )
        campo_bairro = ft.Dropdown(
            label="Bairro",
            options=[ft.dropdown.Option(key=str(b["id"]), text=b["nome"]) for b in bairros],
            value=str(p["bairro_id"]) if p.get("bairro_id") else None,
        )
        campo_atividade = ft.Dropdown(
            label="Atividade",
            options=[ft.dropdown.Option(key=a, text=a) for a in atividades],
            value=p.get("atividade") or "Tratamento",
        )
        campo_fechados = ft.Dropdown(
            label="Fechados",
            options=[ft.dropdown.Option(key=str(n), text=str(n)) for n in range(0, 31)],
            value=str(p.get("fechados", 0) or 0),
            width=100,
        )
        campo_resgatados = ft.Dropdown(
            label="Resgatados",
            options=[ft.dropdown.Option(key=str(n), text=str(n)) for n in range(0, 31)],
            value=str(p.get("resgatados", 0) or 0),
            width=100,
        )
        campo_recusados = ft.Dropdown(
            label="Recusados",
            options=[ft.dropdown.Option(key=str(n), text=str(n)) for n in range(0, 31)],
            value=str(p.get("recusados", 0) or 0),
            width=100,
        )
        campo_obs = ft.TextField(
            label="Observação (opcional)",
            value=p.get("observacao") or "",
        )
        erro = ft.Text("", color=ft.Colors.RED)

        def salvar(ev):
            try:
                qtd = int(campo_qtd.value or "0")
            except ValueError:
                erro.value = "Valor inválido."
                page.update()
                return
            try:
                bairro_id = int(campo_bairro.value) if campo_bairro.value else None
            except (ValueError, TypeError):
                bairro_id = None

            try:
                fechados = int(campo_fechados.value or "0")
                resgatados = int(campo_resgatados.value or "0")
                recusados = int(campo_recusados.value or "0")
            except ValueError:
                fechados = resgatados = recusados = 0

            producao_service.atualizar_producao_completa(
                p["id"], qtd,
                bairro_id=bairro_id,
                atividade=campo_atividade.value,
                fechados=fechados,
                resgatados=resgatados,
                recusados=recusados,
                observacao=campo_obs.value.strip() or None,
            )

            page.pop_dialog()
            snack(page, f"Lançamento de {para_br(date.fromisoformat(p['data']))} atualizado.")
            recarregar()
            page.update()

        dialog = ft.AlertDialog(
            title=ft.Text(f"Editar {para_br(date.fromisoformat(p['data']))}"),            
            content=ft.Column(
                [
                    campo_bairro,
                    campo_atividade,
                    campo_qtd,
                    ft.Row([campo_fechados, campo_resgatados, campo_recusados], spacing=8),
                    campo_obs,
                    erro,
                ],
                tight=True, spacing=10, width=420,
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda ev: page.pop_dialog()),
                ft.Button("Salvar", on_click=salvar),
            ],
        )
        page.show_dialog(dialog)

    def abrir_confirmacao(e):
        def confirmar(ev):
            producao_service.remover_producao(p["id"])
            page.pop_dialog()
            snack(page, f"Lançamento de {para_br(date.fromisoformat(p['data']))} removido.",
                  ft.Colors.ORANGE_600)
            recarregar()
            page.update()

        dialog = ft.AlertDialog(
            title=ft.Text("Excluir lançamento?"),
            content=ft.Text(
                f"Produção de {para_br(date.fromisoformat(p['data']))} — {p['quantidade']} imóveis."
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda ev: page.pop_dialog()),
                ft.Button("Excluir", on_click=confirmar),
            ],
        )
        page.show_dialog(dialog)

    obs_txt = p.get("observacao") or ""
    return ft.Container(
        padding=12,
        bgcolor=_cor_fundo_card(page, "item"),
        border=ft.Border.all(1, ft.Colors.GREY_600),
        border_radius=10,
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Column([
                    ft.Text(para_br(date.fromisoformat(p["data"])),
                            weight=ft.FontWeight.BOLD),
                    ft.Text(f"{bairro_nome or '—'} · {atividade or '—'}",
                            size=12, color=ft.Colors.GREY_500),
                    ft.Text(f"{p['quantidade']} imóveis", size=13),
                    _resumo_contadores_card(p),
                    ft.Text(obs_txt, size=12, color=ft.Colors.GREY_500) if obs_txt else ft.Text(""),
                ], spacing=2, expand=True),
                ft.Row([
                    ft.IconButton(
                        icon=ft.Icons.EDIT_OUTLINED,
                        icon_color=ft.Colors.BLUE_400,
                        on_click=abrir_edicao,
                    ),
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE,
                        icon_color=ft.Colors.RED_400,
                        on_click=abrir_confirmacao,
                    ),
                ], spacing=0),
            ],
        ),
    )

def _resumo_contadores_card(p: dict) -> ft.Control:
    fechados = p.get("fechados", 0) or 0
    resgatados = p.get("resgatados", 0) or 0
    recusados = p.get("recusados", 0) or 0

    if fechados == 0 and resgatados == 0 and recusados == 0:
        return ft.Container()

    efic = producao_service.eficiencia_simples(
        p.get("quantidade", 0) or 0, fechados, recusados
    )

    return ft.Text(
        f"F: {fechados} · R: {resgatados} · Re: {recusados} · Efic: {efic:.0f}%",
        size=11, color=ft.Colors.GREY_500,
    )

def _iso_semana(d_str: str) -> tuple[int, int]:
    """(ano_iso, numero_semana)."""
    d = date.fromisoformat(d_str)
    iso = d.isocalendar()
    return iso[0], iso[1]


def _montar_visao_semanal(producoes: list[dict], lista_widget: ft.Column):
    """Agrupa produções por semana ISO e mostra cards semanais."""
    from app.services import bairro_service

    bairros_map = {b["id"]: b["nome"] for b in bairro_service.listar_ativos()}

    semanas: dict[tuple[int, int], list[dict]] = {}
    for p in producoes:
        chave = _iso_semana(p["data"])
        semanas.setdefault(chave, []).append(p)

    for chave in sorted(semanas.keys(), reverse=True):
        itens = sorted(semanas[chave], key=lambda x: x["data"])
        total = sum(i["quantidade"] for i in itens)
        fechados = sum(i.get("fechados", 0) or 0 for i in itens)
        resgatados = sum(i.get("resgatados", 0) or 0 for i in itens)
        recusados = sum(i.get("recusados", 0) or 0 for i in itens)
        dias_uteis = sum(1 for i in itens if i["quantidade"] > 0)

        efic = producao_service.eficiencia_simples(total, fechados, recusados)

        bairros_da_semana = sorted({
            bairros_map.get(i.get("bairro_id"), "—") for i in itens
            if i.get("bairro_id")
        })

        atividades_da_semana = sorted({
            i.get("atividade") for i in itens if i.get("atividade")
        })

        primeira = min(i["data"] for i in itens)
        ultima = max(i["data"] for i in itens)
        ano, num = chave
        titulo = f"Semana {num:02d}/{ano}  ·  {para_br(date.fromisoformat(primeira))} a {para_br(date.fromisoformat(ultima))}"

        linhas_extras = []
        if bairros_da_semana:
            linhas_extras.append(
                ft.Text("Bairros: " + ", ".join(bairros_da_semana),
                        size=11, color=ft.Colors.GREY_500)
            )
        if atividades_da_semana:
            linhas_extras.append(
                ft.Text("Atividades: " + ", ".join(atividades_da_semana),
                        size=11, color=ft.Colors.GREY_500)
            )
        if fechados or resgatados or recusados:
            linhas_extras.append(
                ft.Text(
                    f"F: {fechados} · R: {resgatados} · Re: {recusados} · "
                    f"Eficiência: {efic:.0f}%",
                    size=11, color=ft.Colors.GREY_500,
                )
            )

        lista_widget.controls.append(
            ft.Container(
                padding=12,
                bgcolor=ft.Colors.SURFACE_VARIANT if hasattr(ft.Colors, "SURFACE_VARIANT")
                        else ft.Colors.GREY_100,
                border=ft.Border.all(1, ft.Colors.GREY_300),
                border_radius=10,
                content=ft.Column([
                    ft.Text(titulo, weight=ft.FontWeight.BOLD, size=13),
                    ft.Text(
                        f"{total} imóveis em {dias_uteis} dia(s) de produção",
                        size=13,
                    ),
                    *linhas_extras,
                ], spacing=3),
            )
        )

