from datetime import date
import flet as ft

from app.services import tr_service, evento_service, producao_service
from app.services.meta_service import calcular_metas
from app.utils.datas import para_br
from app.components.ui import card, kpi, barra_progresso


def build(page: ft.Page) -> ft.Control:
    hoje = date.today()
    tr = tr_service.tr_por_data(hoje)
    if tr is None:
        return ft.Container(padding=20, content=ft.Text("Sem TR ativo."))

    eventos = evento_service.listar_eventos(tr.data_inicio, tr.data_fim)
    realizado = producao_service.total_realizado(tr.id)
    info = calcular_metas(tr, realizado, eventos, hoje)

    pct_min = min(100.0, realizado / tr.meta_min * 100) if tr.meta_min else 0
    pct_max = min(100.0, realizado / tr.meta_max * 100) if tr.meta_max else 0

    # Projeção: ritmo médio diário × dias totais do TR
    dias_passados = max(1, (hoje - tr.data_inicio).days + 1)
    dias_totais = (tr.data_fim - tr.data_inicio).days + 1
    if dias_passados > 0:
        projecao = int((realizado / dias_passados) * dias_totais)
    else:
        projecao = 0

    meta_min_dia = info["meta_diaria_min"]
    meta_max_dia = info["meta_diaria_max"]
    meta_min_txt = f"{meta_min_dia:.1f}" if meta_min_dia else "-"
    meta_max_txt = f"{meta_max_dia:.1f}" if meta_max_dia else "-"

    cor_proj = ft.Colors.GREEN_600 if projecao >= tr.meta_min else ft.Colors.RED_500

    return ft.Column(
        scroll=ft.ScrollMode.AUTO,
        controls=[
            ft.Container(
                padding=20,
                content=ft.Column([
                    # Cabeçalho
                    ft.Text(f"TR {tr.numero}", size=28, weight=ft.FontWeight.BOLD),
                    ft.Text(
                        f"{para_br(tr.data_inicio)} a {para_br(tr.data_fim)}",
                        size=13, color=ft.Colors.GREY_600,
                    ),
                    ft.Container(height=8),

                    # KPIs
                    ft.Row([
                        kpi(page, "Realizado", str(realizado), "imóveis",
                            cor=ft.Colors.TEAL_700, icone=ft.Icons.HOME),
                        kpi(page, "Projeção", str(projecao),
                            "no ritmo atual",
                            cor=cor_proj, icone=ft.Icons.TRENDING_UP),
                    ], spacing=10),

                    ft.Container(height=8),

                    # Progresso meta mínima
                    card(page, ft.Column([
                        ft.Text(
                            f"Meta mínima — {tr.meta_min}",
                            size=14, weight=ft.FontWeight.BOLD,
                        ),
                        barra_progresso(pct_min, cor=ft.Colors.TEAL_600),
                        ft.Text(
                            f"Faltam {info['falta_min']} imóveis",
                            size=12, color=ft.Colors.GREY_600,
                        ),
                    ], spacing=8)),

                    ft.Container(height=8),

                    # Progresso meta máxima
                    card(page, ft.Column([
                        ft.Text(
                            f"Meta máxima — {tr.meta_max}",
                            size=14, weight=ft.FontWeight.BOLD,
                        ),
                        barra_progresso(pct_max, cor=ft.Colors.AMBER_600),
                        ft.Text(
                            f"Faltam {info['falta_max']} imóveis",
                            size=12, color=ft.Colors.GREY_600,
                        ),
                    ], spacing=8)),

                    ft.Container(height=8),

                    # Ritmo necessário
                    card(page, ft.Column([
                        ft.Text(
                            "Ritmo necessário até o fim do TR",
                            size=14, weight=ft.FontWeight.BOLD,
                        ),
                        ft.Row([
                            kpi(page, "Mín/dia", meta_min_txt, cor=ft.Colors.TEAL_700),
                            kpi(page, "Máx/dia", meta_max_txt, cor=ft.Colors.AMBER_700),
                        ], spacing=10),
                        ft.Text(
                            f"Capacidade restante: {info['capacidade']:.1f} dias úteis",
                            size=12, color=ft.Colors.GREY_600,
                        ),
                    ], spacing=8)),
                ]),
            )
        ],
    )