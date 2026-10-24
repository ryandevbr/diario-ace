from dataclasses import asdict
from datetime import date
import flet as ft

from app.components.formularios import (
    criar_campos_producao,
    extrair_valores_producao,
)
from app.components.ui import campo_data_picker, cor_fundo_card, snack
from app.services import (
    atividade_service,
    bairro_service,
    evento_service,
    import_service,
    pdf_service,
    producao_service,
    relatorio_service,
    tr_service,
)
from app.utils.datas import de_br, para_br
from app.utils.files import obter_file_picker
from app.utils.share import compartilhar_ou_salvar_pdf, salvar_pdf_com_picker
from app.views.historico_semanal import criar_item_producao, montar_visao_semanal


def build(page: ft.Page) -> ft.Control:
    hoje = date.today()
    todos = tr_service.listar_todos_trs()
    modo_visao = {"valor": "diario"}

    if not todos:
        return ft.Container(
            padding=20,
            content=ft.Text("Nenhum TR cadastrado."),
        )

    trs_por_ano: dict[int, list] = {}
    for t in todos:
        trs_por_ano.setdefault(t.ano, []).append(t)
    for ano in trs_por_ano:
        trs_por_ano[ano].sort(key=lambda x: x.numero)

    anos_disponiveis = sorted(trs_por_ano.keys(), reverse=True)

    tr_ativo = tr_service.tr_por_data(hoje)
    ano_inicial = tr_ativo.ano if tr_ativo else anos_disponiveis[0]
    numero_inicial = (
        tr_ativo.numero if tr_ativo else trs_por_ano[ano_inicial][0].numero
    )

    estado = {"ano": ano_inicial, "numero": numero_inicial}
    picker = obter_file_picker(page)

    def tr_selecionado():
        lista = trs_por_ano.get(estado["ano"], [])
        return next((t for t in lista if t.numero == estado["numero"]), None)

    botoes_visao = ft.Row(spacing=6)

    def montar_botoes_visao() -> None:
        botoes_visao.controls.clear()
        for valor, label in [("diario", "Diário"), ("semanal", "Semanal")]:
            ativo = modo_visao["valor"] == valor
            botoes_visao.controls.append(
                ft.TextButton(
                    label,
                    on_click=lambda e, v=valor: definir_visao(v),
                    style=ft.ButtonStyle(
                        bgcolor=(
                            ft.Colors.TEAL_700 if ativo else ft.Colors.GREY_100
                        ),
                        color=(
                            ft.Colors.WHITE if ativo else ft.Colors.GREY_800
                        ),
                        shape=ft.RoundedRectangleBorder(radius=20),
                        padding=ft.Padding.symmetric(
                            horizontal=14, vertical=8
                        ),
                    ),
                )
            )

    def definir_visao(valor: str) -> None:
        modo_visao["valor"] = valor
        recarregar()
        page.update()

    montar_botoes_visao()

    lista_widget = ft.Column(spacing=8)
    total_lbl = ft.Text("", size=13, color=ft.Colors.GREY_500)

    dropdown_ano = ft.Dropdown(
        label="Ano",
        options=[
            ft.dropdown.Option(key=str(a), text=str(a))
            for a in anos_disponiveis
        ],
        value=str(estado["ano"]),
        width=140,
    )

    dropdown_numero = ft.Dropdown(
        label="TR",
        options=[],
        value=str(estado["numero"]),
        width=140,
    )

    def atualizar_dropdown_numero() -> None:
        trs = trs_por_ano.get(estado["ano"], [])
        dropdown_numero.options = [
            ft.dropdown.Option(key=str(t.numero), text=str(t.numero))
            for t in trs
        ]
        numeros = {t.numero for t in trs}
        if estado["numero"] not in numeros:
            estado["numero"] = trs[0].numero if trs else 1
        dropdown_numero.value = str(estado["numero"])

    def on_ano_change(e) -> None:
        try:
            estado["ano"] = int(dropdown_ano.value)
        except (TypeError, ValueError):
            return
        atualizar_dropdown_numero()
        recarregar()
        page.update()

    def on_numero_change(e) -> None:
        try:
            estado["numero"] = int(dropdown_numero.value)
        except (TypeError, ValueError):
            return
        recarregar()
        page.update()

    dropdown_ano.on_select = on_ano_change
    dropdown_numero.on_select = on_numero_change
    atualizar_dropdown_numero()

    def recarregar() -> None:
        tr = tr_selecionado()
        lista_widget.controls.clear()
        montar_botoes_visao()

        if tr is None:
            total_lbl.value = "TR não encontrado."
            return

        producoes = producao_service.listar_producoes_do_tr(tr.id)
        soma = sum(p["quantidade"] for p in producoes)
        total_lbl.value = (
            f"TR {tr.numero} — {para_br(tr.data_inicio)} a {para_br(tr.data_fim)}: "
            f"{soma} imóveis em {len(producoes)} dia(s)."
        )

        if not producoes:
            lista_widget.controls.append(
                ft.Text(
                    "Nenhuma produção registrada neste TR.",
                    color=ft.Colors.GREY_500,
                )
            )
            return

        # Pré-carrega mapa de todos os bairros (evita query N+1 e preserva inativos)
        bairros_map = {
            b["id"]: b["nome"] for b in bairro_service.listar_todos()
        }

        if modo_visao["valor"] == "semanal":
            montar_visao_semanal(producoes, bairros_map, lista_widget)
        else:
            for p in producoes:
                lista_widget.controls.append(
                    criar_item_producao(page, p, bairros_map, recarregar)
                )

    def abrir_novo_lancamento(e) -> None:
        tr = tr_selecionado()
        if tr is None:
            snack(page, "Nenhum TR selecionado.", ft.Colors.RED_500)
            return
        data_padrao = max(tr.data_inicio, min(hoje, tr.data_fim))

        campo_data, linha_data = campo_data_picker(page, data_padrao)
        bairros = bairro_service.listar_ativos()
        atividades = atividade_service.listar()
        campos = criar_campos_producao(
            page,
            bairros, 
            atividades)
        erro = ft.Text("", color=ft.Colors.RED)

        def salvar(ev) -> None:
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
                dados = extrair_valores_producao(campos)
            except ValueError:
                erro.value = "Quantidade inválida."
                page.update()
                return

            producao_service.registrar_producao(
                d,
                tr.id,
                dados["quantidade"],
                bairro_id=dados["bairro_id"],
                atividade=dados["atividade"],
                fechados=dados["fechados"],
                resgatados=dados["resgatados"],
                recusados=dados["recusados"],
                obs=dados["observacao"],
            )

            page.pop_dialog()
            snack(
                page,
                f"Lançado: {dados['quantidade']} imóveis em {para_br(d)}.",
            )
            recarregar()
            page.update()

        dialog = ft.AlertDialog(
            title=ft.Text(f"Novo lançamento — TR {tr.numero}/{tr.ano}"),
            content=ft.Column(
                [
                    linha_data,
                    campos["qtd"],
                    campos["bairro_ui"],
                    campos["atividade"],
                    campos["obs"],
                    erro,
                    campos["linha_contadores"],
                ],
                tight=True,
                spacing=10,
                width=360,
            ),
            actions=[
                ft.TextButton(
                    "Cancelar", on_click=lambda ev: page.pop_dialog()
                ),
                ft.Button("Salvar", on_click=salvar),
            ],
        )
        page.show_dialog(dialog)

    def _preparar_dados_pdf_historico(tr):
        producoes = producao_service.listar_producoes_do_tr(tr.id)
        eventos = [
            asdict(ev)
            for ev in evento_service.listar_eventos(
                tr.data_inicio, tr.data_fim
            )
        ]
        bairros_por_id = {b["id"]: b for b in bairro_service.listar_todos()}
        nome = f"producao_TR{tr.numero}_{tr.ano}_{date.today().isoformat()}.pdf"
        return producoes, eventos, bairros_por_id, nome

    async def exportar_pdf(e) -> None:
        tr = tr_selecionado()
        if tr is None:
            snack(page, "Nenhum TR selecionado.", ft.Colors.RED_500)
            return

        producoes, eventos, bairros_por_id, nome = (
            _preparar_dados_pdf_historico(tr)
        )
        total = sum(p["quantidade"] for p in producoes)
        resumo_txt = (
            f"TR {tr.numero}/{tr.ano}\n"
            f"Período: {para_br(tr.data_inicio)} a {para_br(tr.data_fim)}\n"
            f"{len(producoes)} dia(s) com produção\n"
            f"{total} imóveis no total\n"
            f"{len(eventos)} evento(s) no período"
        )

        async def _salvar():
            try:
                await salvar_pdf_com_picker(
                    page,
                    nome,
                    lambda caminho: pdf_service.exportar_historico_pdf(
                        caminho, tr, producoes, eventos, bairros_por_id
                    ),
                )
            except Exception as ex:
                snack(page, f"Erro ao gerar PDF: {ex}", ft.Colors.RED_500)

        def confirmar(ev):
            page.pop_dialog()
            page.run_task(_salvar)

        dialog = ft.AlertDialog(
            title=ft.Text("Gerar PDF do Histórico?"),
            content=ft.Column(
                [
                    ft.Text("Confira antes de gerar:"),
                    ft.Container(height=6),
                    ft.Text(resumo_txt, size=12, color=ft.Colors.GREY_700),
                ],
                tight=True,
                spacing=4,
                width=340,
            ),
            actions=[
                ft.TextButton(
                    "Cancelar", on_click=lambda ev: page.pop_dialog()
                ),
                ft.Button("Gerar PDF", on_click=confirmar),
            ],
        )
        page.show_dialog(dialog)

    async def compartilhar_pdf(e) -> None:
        tr = tr_selecionado()
        if tr is None:
            snack(page, "Nenhum TR selecionado.", ft.Colors.RED_500)
            return
        try:
            producoes, eventos, bairros_por_id, nome = (
                _preparar_dados_pdf_historico(tr)
            )
            await compartilhar_ou_salvar_pdf(
                page,
                nome,
                f"Produção TR {tr.numero} — {tr.ano}",
                lambda caminho: pdf_service.exportar_historico_pdf(
                    caminho, tr, producoes, eventos, bairros_por_id
                ),
            )
        except Exception as ex:
            snack(page, f"Erro ao compartilhar: {ex}", ft.Colors.RED_500)

    def exportar_relatorio_anual(e) -> None:
        ano = estado["ano"]

        async def _salvar():
            try:
                dados = relatorio_service.dados_do_ano(ano)
                nome = f"relatorio_anual_{ano}_{date.today().isoformat()}.pdf"
                await salvar_pdf_com_picker(
                    page,
                    nome,
                    lambda caminho: pdf_service.exportar_relatorio_anual_pdf(
                        caminho, dados
                    ),
                    titulo_dialogo="Salvar relatório anual",
                    msg_sucesso="Relatório salvo em",
                )
            except Exception as ex:
                snack(page, f"Erro ao gerar relatório: {ex}", ft.Colors.RED_500)

        def confirmar(ev):
            page.pop_dialog()
            page.run_task(_salvar)

        dialog = ft.AlertDialog(
            title=ft.Text("Gerar Relatório Anual?"),
            content=ft.Column(
                [
                    ft.Text(f"Ano: {ano}"),
                    ft.Text(
                        "Inclui todos os TRs, consolidado por bairro e por atividade."
                    ),
                    ft.Container(height=6),
                    ft.Text(
                        "O PDF fica em paisagem e pode ter várias páginas.",
                        size=11,
                        color=ft.Colors.GREY_500,
                    ),
                ],
                tight=True,
                spacing=4,
                width=340,
            ),
            actions=[
                ft.TextButton(
                    "Cancelar", on_click=lambda ev: page.pop_dialog()
                ),
                ft.Button("Gerar PDF", on_click=confirmar),
            ],
        )
        page.show_dialog(dialog)

    async def compartilhar_relatorio_anual(e) -> None:
        try:
            ano = estado["ano"]
            dados = relatorio_service.dados_do_ano(ano)
            nome = f"relatorio_anual_{ano}_{date.today().isoformat()}.pdf"
            await compartilhar_ou_salvar_pdf(
                page,
                nome,
                f"Relatório anual {ano} — Diário ACE",
                lambda caminho: pdf_service.exportar_relatorio_anual_pdf(
                    caminho, dados
                ),
                titulo_dialogo="Salvar relatório",
                msg_sucesso="Relatório salvo em",
            )
        except Exception as ex:
            snack(
                page,
                f"Erro ao compartilhar relatório: {ex}",
                ft.Colors.RED_500,
            )

    async def importar_planilha(e) -> None:
        try:
            arquivos = await picker.pick_files(
                dialog_title="Escolher planilha",
                allow_multiple=False,
                allowed_extensions=["csv", "xlsx", "xlsm"],
            )
            if not arquivos:
                return

            linhas = import_service.ler_planilha(arquivos[0].path)
            if not linhas:
                snack(
                    page,
                    "Nenhuma linha encontrada na planilha.",
                    ft.Colors.ORANGE_600,
                )
                return

            preview = linhas[:5]
            preview_txt = "\n".join(
                f"• {para_br(l['data'])}: {l['quantidade']} imóveis"
                + (f" ({l['observacao']})" if l["observacao"] else "")
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
                    snack(
                        page,
                        "Importação concluída: " + ", ".join(partes) + ".",
                        ft.Colors.GREEN_600,
                    )
                    recarregar()
                    page.update()
                except Exception as ex:
                    snack(page, f"Erro ao importar: {ex}", ft.Colors.RED_500)

            dialog = ft.AlertDialog(
                title=ft.Text("Importar planilha"),
                content=ft.Column(
                    [
                        ft.Text(f"Encontrados {len(linhas)} lançamentos."),
                        ft.Container(height=4),
                        ft.Text(preview_txt, size=12, color=ft.Colors.GREY_500),
                        ft.Container(height=6),
                        ft.Text(
                            "Datas que já existem no sistema serão sobrescritas. "
                            "A importação considera todos os TRs, não apenas o selecionado.",
                            size=11,
                            color=ft.Colors.ORANGE_700,
                        ),
                    ],
                    tight=True,
                    spacing=4,
                    width=400,
                ),
                actions=[
                    ft.TextButton(
                        "Cancelar", on_click=lambda ev: page.pop_dialog()
                    ),
                    ft.Button("Importar", on_click=confirmar),
                ],
            )
            page.show_dialog(dialog)

        except import_service.ImportacaoErro as ex:
            snack(page, f"Erro na planilha: {ex}", ft.Colors.RED_500)
        except Exception as ex:
            snack(page, f"Erro inesperado: {ex}", ft.Colors.RED_500)

    def _botao_acao(texto: str, icone: str, cor: str, handler) -> ft.Button:
        return ft.Button(
            texto,
            icon=icone,
            on_click=handler,
            style=ft.ButtonStyle(
                bgcolor=cor,
                color=ft.Colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=10),
            ),
        )

    recarregar()

    secao_principal = ft.Container(
        padding=16,
        border_radius=12,
        bgcolor=cor_fundo_card(page, "principal"),
        content=ft.Column(
            [
                ft.Row([dropdown_ano, dropdown_numero], spacing=8),
                total_lbl,
                botoes_visao,
                ft.Divider(),
                ft.Row(
                    [
                        _botao_acao(
                            "Novo lançamento",
                            ft.Icons.ADD,
                            ft.Colors.TEAL_700,
                            abrir_novo_lancamento,
                        ),
                        _botao_acao(
                            "Exportar PDF",
                            ft.Icons.PICTURE_AS_PDF,
                            ft.Colors.GREY_800,
                            exportar_pdf,
                        ),
                        _botao_acao(
                            "Compartilhar PDF",
                            ft.Icons.SHARE,
                            ft.Colors.BLUE_700,
                            compartilhar_pdf,
                        ),
                        _botao_acao(
                            "Relatório anual",
                            ft.Icons.ASSESSMENT,
                            ft.Colors.PURPLE_700,
                            exportar_relatorio_anual,
                        ),
                        _botao_acao(
                            "Compartilhar relatório",
                            ft.Icons.SHARE,
                            ft.Colors.PURPLE_400,
                            compartilhar_relatorio_anual,
                        ),
                        _botao_acao(
                            "Importar planilha",
                            ft.Icons.UPLOAD_FILE,
                            ft.Colors.INDIGO_700,
                            importar_planilha,
                        ),
                    ],
                    spacing=8,
                    wrap=True,
                ),
                ft.Container(height=8),
                lista_widget,
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
                            "Histórico", size=22, weight=ft.FontWeight.BOLD
                        ),
                        ft.Container(height=8),
                        secao_principal,
                    ],
                    spacing=0,
                ),
            )
        ],
    )
