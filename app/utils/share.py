import logging
import os
import tempfile
from typing import Callable
import flet as ft

from app.components.ui import snack
from app.utils.files import obter_file_picker

logger = logging.getLogger(__name__)


async def compartilhar_arquivo(
    page: ft.Page,
    caminho: str,
    mime_type: str = "application/pdf",
    texto: str = "",
) -> bool:
    """Compartilha um arquivo via sheet nativo do sistema.

    Retorna True se conseguiu, False se o serviço não está disponível.
    """
    try:
        if not getattr(page, "_share_service", None):
            share = ft.Share()
            page.services.append(share)
            page._share_service = share

        share = page._share_service
        arquivo = ft.ShareFile(path=caminho, mime_type=mime_type)
        await share.share_files(files=[arquivo], text=texto)
        return True
    except Exception as ex:
        logger.warning("Share indisponível: %s", ex)
        return False


async def salvar_pdf_com_picker(
    page: ft.Page,
    nome_arquivo: str,
    gerador_pdf: Callable[[str], None],
    titulo_dialogo: str = "Salvar PDF",
    msg_sucesso: str = "PDF salvo em",
) -> None:
    """Abre o FilePicker para salvar um PDF e executa a função geradora."""
    picker = obter_file_picker(page)
    caminho = await picker.save_file(
        dialog_title=titulo_dialogo,
        file_name=nome_arquivo,
        allowed_extensions=["pdf"],
    )
    if not caminho:
        snack(page, "Exportação cancelada.", ft.Colors.ORANGE_600)
        return
    gerador_pdf(caminho)
    snack(page, f"{msg_sucesso} {caminho}")


async def compartilhar_ou_salvar_pdf(
    page: ft.Page,
    nome_arquivo: str,
    texto_share: str,
    gerador_pdf: Callable[[str], None],
    titulo_dialogo: str = "Salvar PDF",
    msg_sucesso: str = "PDF salvo em",
) -> None:
    """Gera o PDF em pasta temporária, tenta compartilhar e faz fallback para salvar."""
    caminho_temp = os.path.join(tempfile.gettempdir(), nome_arquivo)
    gerador_pdf(caminho_temp)

    ok = await compartilhar_arquivo(page, caminho_temp, texto=texto_share)
    if not ok:
        picker = obter_file_picker(page)
        caminho_salvo = await picker.save_file(
            dialog_title=titulo_dialogo,
            file_name=nome_arquivo,
            allowed_extensions=["pdf"],
        )
        if caminho_salvo:
            gerador_pdf(caminho_salvo)
            snack(page, f"{msg_sucesso} {caminho_salvo}")
        else:
            snack(page, "Compartilhamento indisponível.", ft.Colors.ORANGE_600)
