import flet as ft


async def compartilhar_arquivo(page: ft.Page, caminho: str,
                               mime_type: str = "application/pdf",
                               texto: str = "") -> bool:
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
        print(f"Share indisponível: {ex}")
        return False