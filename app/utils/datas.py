from datetime import date, datetime
from typing import Callable
import flet as ft


def para_br(d: date) -> str:
    """Converte date para string 'DD/MM/AAAA'."""
    return d.strftime("%d/%m/%Y")


def de_br(s: str) -> date:
    """Converte string 'DD/MM/AAAA' para date. Levanta ValueError se inválido."""
    return datetime.strptime(s.strip(), "%d/%m/%Y").date()


def obter_date_picker(page: ft.Page) -> ft.DatePicker:
    """Cria (uma vez por page) e devolve o DatePicker compartilhado."""
    if not getattr(page, "_date_picker_registrado", False):
        picker = ft.DatePicker(
            first_date=date(2020, 1, 1),
            last_date=date(2035, 12, 31),
        )
        page.services.append(picker)
        page._date_picker = picker
        page._date_picker_registrado = True
    return page._date_picker


def bairro_label(bairro: dict | None) -> str:
    return bairro["nome"] if bairro else "—"


def escolher_data(page: ft.Page, callback: Callable[[date], None]) -> None:
    """Abre o DatePicker. O callback recebe um datetime.date."""
    picker = obter_date_picker(page)

    def handler(e):
        v = picker.value
        if v:
            d = v.date() if hasattr(v, "date") else v
            callback(d)

    picker.on_change = handler
    page.show_dialog(picker)
