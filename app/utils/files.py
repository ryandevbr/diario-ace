import flet as ft


def obter_file_picker(page: ft.Page) -> ft.FilePicker:
    """Devolve um FilePicker compartilhado por page."""
    if not getattr(page, "_shared_file_picker", None):
        picker = ft.FilePicker()
        page.services.append(picker)
        page._shared_file_picker = picker
    return page._shared_file_picker