from datetime import date
from typing import Callable
import flet as ft
from app.utils.files import obter_file_picker
from app.components.ui import campo_data_picker, cor_fundo_item, snack
from app.services import (
    bairro_service,
    banco_horas_service,
    evento_service,
    tr_service,
)
from app.utils.datas import de_br, para_br


def criar_secao_trs(page: ft.Page) -> tuple[ft.Container, Callable[[], None]]:
    """Constrói a seção de gerenciamento de TRs e retorna (container, recarregar_fn)."""
    anos = tr_service.anos_disponiveis()
    lista_trs = ft.Column(spacing=8)

    dropdown_ano = ft.Dropdown(
        label="Ano",
        options=[ft.dropdown.Option(key=str(a), text=str(a)) for a in anos],
        value=str(anos[0]) if anos else str(date.today().year),
    )

    def recarregar_trs() -> None:
        anos_atuais = tr_service.anos_disponiveis()
        dropdown_ano.options = [
            ft.dropdown.Option(key=str(a), text=str(a)) for a in anos_atuais
        ]
        if dropdown_ano.value not in {str(a) for a in anos_atuais}:
            dropdown_ano.value = str(anos_atuais[0])

        lista_trs.controls.clear()
        try:
            ano = int(dropdown_ano.value)
        except (TypeError, ValueError):
            ano = date.today().year
        trs = tr_service.listar_trs(ano)
        if not trs:
            lista_trs.controls.append(
                ft.Text(
                    "Nenhum TR cadastrado para este ano.",
                    color=ft.Colors.GREY_500,
                )
            )
            return
        for tr in trs:
            lista_trs.controls.append(_item_tr(page, tr, recarregar_trs))

    def on_mudar_ano(e) -> None:
        recarregar_trs()
        page.update()

    dropdown_ano.on_select = on_mudar_ano

    campo_novo_ano = ft.TextField(
        label="Criar TRs de outro ano",
        hint_text="Ex.: 2027",
        width=200,
        keyboard_type=ft.KeyboardType.NUMBER,
    )

    def criar_ano(e) -> None:
        try:
            ano = int((campo_novo_ano.value or "").strip())
        except ValueError:
            snack(page, "Digite um ano válido (ex.: 2027).", ft.Colors.RED_500)
            return
        tr_service.seed_trs_do_ano(ano)
        snack(
            page,
            f"TRs de {ano} criados. Ajuste as datas conforme o calendário.",
        )
        campo_novo_ano.value = ""
        dropdown_ano.value = str(ano)
        recarregar_trs()
        page.update()

    recarregar_trs()

    secao = ft.Container(
        padding=16,
        border_radius=12,
        bgcolor=ft.Colors.SURFACE,
        content=ft.Column(
            [
                ft.Text("TRs do ano", size=16, weight=ft.FontWeight.BOLD),
                ft.Text(
                    "Ajuste as datas conforme o calendário enviado pelos supervisores.",
                    size=12,
                    color=ft.Colors.GREY_500,
                ),
                dropdown_ano,
                lista_trs,
                ft.Divider(),
                ft.Text("Criar novo ano", size=14, weight=ft.FontWeight.BOLD),
                ft.Row(
                    [
                        campo_novo_ano,
                        ft.Button("Criar", on_click=criar_ano),
                    ],
                    spacing=10,
                    wrap=True,
                ),
            ],
            spacing=10,
        ),
    )
    return secao, recarregar_trs


def _item_tr(page: ft.Page, tr, recarregar: Callable[[], None]) -> ft.Control:
    def abrir_edicao(e) -> None:
        campo_ini, linha_ini = campo_data_picker(
            page, tr.data_inicio, label="Início (DD/MM/AAAA)"
        )
        campo_fim, linha_fim = campo_data_picker(
            page, tr.data_fim, label="Fim (DD/MM/AAAA)"
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

        def salvar(ev) -> None:
            try:
                ini = de_br(campo_ini.value)
                fim = de_br(campo_fim.value)
                meta_min = int((campo_min.value or "").strip())
                meta_max = int((campo_max.value or "").strip())
                inicial = int((campo_inicial.value or "0").strip())
            except ValueError:
                erro.value = "Verifique datas e valores numéricos."
                page.update()
                return
            if ini > fim:
                erro.value = (
                    "A data de início não pode ser posterior à data de fim."
                )
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

            tr_service.atualizar_tr(
                tr.id, ini, fim, meta_min, meta_max, inicial
            )
            page.pop_dialog()
            snack(page, f"TR {tr.numero} atualizado.")
            recarregar()
            page.update()

        dialog = ft.AlertDialog(
            title=ft.Text(f"Editar TR {tr.numero} — {tr.ano}"),
            content=ft.Column(
                [
                    linha_ini,
                    linha_fim,
                    campo_min,
                    campo_max,
                    campo_inicial,
                    erro,
                ],
                tight=True,
                spacing=10,
                width=380,
            ),
            actions=[
                ft.TextButton(
                    "Cancelar", on_click=lambda ev: page.pop_dialog()
                ),
                ft.Button("Salvar", on_click=salvar),
            ],
        )
        page.show_dialog(dialog)

    inicial_txt = (
        f" · inicial: {tr.producao_inicial}"
        if getattr(tr, "producao_inicial", 0) > 0
        else ""
    )

    return ft.Container(
        padding=12,
        bgcolor=ft.Colors.SURFACE,
        border=ft.Border.all(1, ft.Colors.GREY_300),
        border_radius=10,
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Column(
                    [
                        ft.Text(f"TR {tr.numero}", weight=ft.FontWeight.BOLD),
                        ft.Text(
                            f"{para_br(tr.data_inicio)} a {para_br(tr.data_fim)}",
                            size=12,
                        ),
                        ft.Text(
                            f"Meta: {tr.meta_min}–{tr.meta_max}{inicial_txt}",
                            size=12,
                            color=ft.Colors.GREY_500,
                        ),
                    ],
                    spacing=2,
                    expand=True,
                ),
                ft.IconButton(
                    icon=ft.Icons.EDIT_OUTLINED,
                    icon_color=ft.Colors.BLUE_400,
                    on_click=abrir_edicao,
                ),
            ],
        ),
    )


def criar_secao_bairros(
    page: ft.Page,
) -> tuple[ft.Container, Callable[[], None]]:
    """Constrói a seção de gerenciamento de Bairros e retorna (container, recarregar_fn)."""
    lista_bairros = ft.Column(spacing=6)
    campo_novo_bairro = ft.TextField(
        label="Novo bairro",
        hint_text="Ex.: Centro",
        expand=True,
    )

    def recarregar_bairros() -> None:
        lista_bairros.controls.clear()
        bairros = bairro_service.listar_todos()
        if not bairros:
            lista_bairros.controls.append(
                ft.Text("Nenhum bairro cadastrado.", color=ft.Colors.GREY_500)
            )
            return
        for b in bairros:
            lista_bairros.controls.append(
                _item_bairro(page, b, recarregar_bairros)
            )

    def criar_bairro(e) -> None:
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

    secao = ft.Container(
        padding=16,
        border_radius=12,
        bgcolor=ft.Colors.SURFACE,
        content=ft.Column(
            [
                ft.Text("Bairros", size=16, weight=ft.FontWeight.BOLD),
                ft.Text(
                    "Bairros usados nos dropdowns de produção.",
                    size=12,
                    color=ft.Colors.GREY_500,
                ),
                ft.Row(
                    [
                        campo_novo_bairro,
                        ft.Button("Criar", on_click=criar_bairro),
                    ],
                    spacing=8,
                ),
                ft.Divider(),
                lista_bairros,
            ],
            spacing=10,
        ),
    )
    return secao, recarregar_bairros


def _item_bairro(page: ft.Page, b: dict, recarregar) -> ft.Control:
    ativo = bool(b.get("ativo", 1))
    tem_croqui = bool(b.get("croqui_path"))

    picker = obter_file_picker(page)

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

    async def anexar_croqui(e):
        try:
            arquivos = await picker.pick_files(
                dialog_title="Escolher Croqui (Imagem)",
                allow_multiple=False,
                allowed_extensions=["jpg", "jpeg", "png"], # <-- Alterado aqui
            )
            if not arquivos:
                return
            # O bairro_service.salvar_croqui vai precisar aceitar imagens também
            bairro_service.salvar_croqui(b["id"], arquivos[0].path)
            snack(page, f"Croqui anexado ao bairro {b['nome']}.")
            recarregar()
            page.update()
        except Exception as ex:
            snack(page, f"Erro ao salvar croqui: {ex}", ft.Colors.RED_500)

    def remover_croqui_action(e):
        bairro_service.remover_croqui(b["id"])
        snack(page, "Croqui removido.", ft.Colors.ORANGE_600)
        recarregar()
        page.update()

    # Botões extras baseados na existência do croqui
    controles_direita = [
        ft.IconButton(
            icon=ft.Icons.EDIT_OUTLINED,
            icon_color=ft.Colors.BLUE_400,
            tooltip="Renomear",
            on_click=renomear,
        ),
    ]

    if tem_croqui:
        controles_direita.extend([
            ft.IconButton(
                icon=ft.Icons.PICTURE_AS_PDF,
                icon_color=ft.Colors.GREEN_600,
                tooltip="Croqui anexado. Clique para trocar.",
                on_click=anexar_croqui,
            ),
            ft.IconButton(
                icon=ft.Icons.DELETE_FOREVER,
                icon_color=ft.Colors.RED_400,
                tooltip="Remover croqui",
                on_click=remover_croqui_action,
            ),
        ])
    else:
        controles_direita.append(
            ft.IconButton(
                icon=ft.Icons.UPLOAD_FILE,
                icon_color=ft.Colors.GREY_500,
                tooltip="Anexar Croqui (PDF)",
                on_click=anexar_croqui,
            )
        )

    controles_direita.append(
        ft.Switch(
            value=ativo,
            on_change=alternar,
            active_color=ft.Colors.TEAL_700,
        )
    )

    return ft.Container(
        padding=10,
        border_radius=8,
        bgcolor=cor_fundo_item(page),
        content=ft.Row([
            ft.Text(b["nome"], size=13, expand=True,
                    color=ft.Colors.GREY_500 if not ativo else None),
            ft.Row(controles_direita, spacing=0)
        ], spacing=6),
    )


def criar_secao_banco_horas(
    page: ft.Page,
    picker: ft.FilePicker,
) -> tuple[ft.Container, Callable[[], None]]:
    """Constrói a seção do Banco de Horas e retorna (container, recarregar_fn)."""
    saldo_lbl = ft.Text("", size=28, weight=ft.FontWeight.BOLD)
    totais_lbl = ft.Text("", size=12, color=ft.Colors.GREY_500)
    lista_bh = ft.Column(spacing=6)

    def recarregar_bh() -> None:
        info = banco_horas_service.resumo_saldo()
        saldo_lbl.value = (
            f"{info['sinal']}{info['hhmm']}"
            + (f"  ({info['dias']})" if info["horas"] != 0 else "")
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

        atualizar_hdr = getattr(page, "_atualizar_header_bh", None)
        if callable(atualizar_hdr):
            atualizar_hdr()

        lista_bh.controls.clear()
        movs = banco_horas_service.listar_todos()
        if not movs:
            lista_bh.controls.append(
                ft.Text(
                    "Nenhuma movimentação cadastrada.",
                    color=ft.Colors.GREY_500,
                )
            )
            return
        for m in movs:
            lista_bh.controls.append(_item_banco_horas(page, m, recarregar_bh))

    async def importar_extrato(e) -> None:
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
                    snack(
                        page,
                        f"Importadas {resumo['inseridos']} movimentações.",
                    )
                    recarregar_bh()
                    page.update()
                except Exception as ex:
                    snack(page, f"Erro: {ex}", ft.Colors.RED_500)

            dialog = ft.AlertDialog(
                title=ft.Text("Importar extrato"),
                content=ft.Column(
                    [
                        ft.Text(f"{len(linhas)} movimentações encontradas."),
                        ft.Container(height=4),
                        ft.Text(preview, size=12, color=ft.Colors.GREY_500),
                        ft.Container(height=6),
                        ft.Text(
                            "A importação substitui TODAS as movimentações atuais. "
                            "Faça um backup antes se quiser preservar.",
                            size=11,
                            color=ft.Colors.ORANGE_700,
                        ),
                    ],
                    tight=True,
                    spacing=4,
                    width=420,
                ),
                actions=[
                    ft.TextButton(
                        "Cancelar", on_click=lambda ev: page.pop_dialog()
                    ),
                    ft.Button("Importar", on_click=confirmar),
                ],
            )
            page.show_dialog(dialog)

        except banco_horas_service.BancoHorasErro as ex:
            snack(page, f"Erro no extrato: {ex}", ft.Colors.RED_500)
        except Exception as ex:
            snack(page, f"Erro inesperado: {ex}", ft.Colors.RED_500)

    recarregar_bh()

    secao = ft.Container(
        padding=16,
        border_radius=12,
        bgcolor=ft.Colors.SURFACE,
        content=ft.Column(
            [
                ft.Text("Banco de Horas", size=16, weight=ft.FontWeight.BOLD),
                ft.Text(
                    "Controle de horas extras trabalhadas e compensações.",
                    size=12,
                    color=ft.Colors.GREY_500,
                ),
                ft.Container(height=6),
                ft.Text("Saldo atual", size=11, color=ft.Colors.GREY_500),
                saldo_lbl,
                totais_lbl,
                ft.Container(height=8),
                ft.Row(
                    [
                        ft.Button(
                            "Nova movimentação",
                            icon=ft.Icons.ADD,
                            on_click=lambda e: _abrir_dialogo_movimentacao(
                                page, recarregar_bh
                            ),
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
                    ],
                    spacing=8,
                    wrap=True,
                ),
                ft.Divider(),
                ft.Text("Movimentações", size=13, weight=ft.FontWeight.BOLD),
                lista_bh,
            ],
            spacing=10,
        ),
    )
    return secao, recarregar_bh


def _abrir_dialogo_movimentacao(
    page: ft.Page,
    recarregar: Callable[[], None],
    mov_existente: dict | None = None,
) -> None:
    """Abre diálogo para criar ou editar uma movimentação do Banco de Horas."""
    editando = mov_existente is not None
    data_ini = (
        date.fromisoformat(mov_existente["data"])
        if editando
        else date.today()
    )
    horas_ini = (
        banco_horas_service.formatar_horas(mov_existente["horas"])
        if editando
        else "08:00"
    )
    tipo_ini = mov_existente["tipo"] if editando else "trabalhada"
    desc_ini = (mov_existente.get("descricao") or "") if editando else ""

    campo_data, linha_data = campo_data_picker(page, data_ini)
    campo_horas = ft.TextField(
        label="Horas (HH:MM)",
        hint_text="Ex.: 08:00",
        value=horas_ini,
    )
    dropdown_tipo = ft.Dropdown(
        label="Tipo",
        options=[
            ft.dropdown.Option(key="trabalhada", text="Horas Trabalhadas"),
            ft.dropdown.Option(key="compensacao", text="Compensação"),
        ],
        value=tipo_ini,
    )
    campo_desc = ft.TextField(label="Descrição (opcional)", value=desc_ini)
    erro = ft.Text("", color=ft.Colors.RED)

    def salvar(ev) -> None:
        try:
            d = de_br(campo_data.value)
        except ValueError:
            erro.value = "Data inválida."
            page.update()
            return
        try:
            horas = banco_horas_service.parse_horas(campo_horas.value)
            desc = (campo_desc.value or "").strip() or None
            if editando:
                banco_horas_service.atualizar(
                    mov_existente["id"],
                    d,
                    horas,
                    dropdown_tipo.value,
                    desc,
                )
            else:
                banco_horas_service.adicionar(
                    d, horas, dropdown_tipo.value, desc
                )
        except Exception as ex:
            erro.value = str(ex)
            page.update()
            return

        page.pop_dialog()
        snack(
            page,
            "Movimentação atualizada."
            if editando
            else "Movimentação registrada.",
        )
        recarregar()
        page.update()

        if not editando and dropdown_tipo.value == "compensacao":
            _sugerir_evento_calendario(page, d, horas, desc)

    dialog = ft.AlertDialog(
        title=ft.Text(
            "Editar movimentação" if editando else "Nova movimentação"
        ),
        content=ft.Column(
            [
                linha_data,
                campo_horas,
                dropdown_tipo,
                campo_desc,
                erro,
            ],
            tight=True,
            spacing=10,
            width=380,
        ),
        actions=[
            ft.TextButton("Cancelar", on_click=lambda ev: page.pop_dialog()),
            ft.Button("Salvar", on_click=salvar),
        ],
    )
    page.show_dialog(dialog)


def _item_banco_horas(
    page: ft.Page,
    m: dict,
    recarregar: Callable[[], None],
) -> ft.Control:
    positivo = m["tipo"] == "trabalhada"
    sinal = "+" if positivo else "−"
    cor = ft.Colors.GREEN_600 if positivo else ft.Colors.RED_500

    def excluir(e) -> None:
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
                ft.TextButton(
                    "Cancelar", on_click=lambda ev: page.pop_dialog()
                ),
                ft.Button("Excluir", on_click=confirmar),
            ],
        )
        page.show_dialog(dialog)

    return ft.Container(
        padding=10,
        border_radius=8,
        bgcolor=cor_fundo_item(page),
        content=ft.Row(
            [
                ft.Column(
                    [
                        ft.Text(
                            para_br(date.fromisoformat(m["data"])),
                            weight=ft.FontWeight.BOLD,
                            size=12,
                        ),
                        ft.Text(
                            f"{sinal}{banco_horas_service.formatar_horas(m['horas'])} — "
                            f"{banco_horas_service.LABEL_TIPO.get(m['tipo'], m['tipo'])}",
                            size=12,
                            color=cor,
                            weight=ft.FontWeight.W_600,
                        ),
                        (
                            ft.Text(
                                m.get("descricao") or "",
                                size=11,
                                color=ft.Colors.GREY_500,
                            )
                            if m.get("descricao")
                            else ft.Container()
                        ),
                    ],
                    spacing=2,
                    expand=True,
                ),
                ft.IconButton(
                    icon=ft.Icons.EDIT_OUTLINED,
                    icon_color=ft.Colors.BLUE_400,
                    on_click=lambda e: _abrir_dialogo_movimentacao(
                        page, recarregar, mov_existente=m
                    ),
                ),
                ft.IconButton(
                    icon=ft.Icons.DELETE_OUTLINE,
                    icon_color=ft.Colors.RED_400,
                    on_click=excluir,
                ),
            ],
            spacing=4,
        ),
    )


def _sugerir_evento_calendario(
    page: ft.Page,
    d: date,
    horas: float,
    obs: str | None,
) -> None:
    """Depois de lançar compensação no BH, sugere criar evento no calendário."""
    tr = tr_service.tr_por_data(d)
    if tr is None:
        return

    fracao = min(1.0, horas / 8.0)

    def confirmar(ev):
        page.pop_dialog()
        try:
            evento_service.adicionar_evento(
                d,
                "compensacao",
                fracao,
                obs or "Folga referente ao banco de horas",
            )
            snack(page, "Evento adicionado ao calendário.")
        except Exception as ex:
            snack(page, f"Erro: {ex}", ft.Colors.RED_500)

    dialog = ft.AlertDialog(
        title=ft.Text("Criar evento no calendário?"),
        content=ft.Text(
            f"Deseja registrar esse dia como compensação no calendário "
            f"(peso {fracao:.2f})? Isso ajusta o cálculo das metas."
        ),
        actions=[
            ft.TextButton("Não", on_click=lambda ev: page.pop_dialog()),
            ft.Button("Sim, criar", on_click=confirmar),
        ],
    )
    page.show_dialog(dialog)

