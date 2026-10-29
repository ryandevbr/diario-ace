import json
import logging
import os
from pathlib import Path
import ssl
import sys
from typing import Callable
import urllib.error
import urllib.request

from app.database import default_db_dir

logger = logging.getLogger(__name__)

VERSION_URL = "https://raw.githubusercontent.com/ryandevbr/diario-ace/main/version.json"
CHUNK_SIZE_PADRAO = 65536


def eh_android() -> bool:
    """Verifica via os.environ (e sys.platform) se o app está rodando no Android."""
    if os.environ.get("FLET_PLATFORM", "").lower() == "android":
        return True
    if any(
        chave in os.environ
        for chave in ("ANDROID_ARGUMENT", "ANDROID_ROOT", "ANDROID_DATA")
    ):
        return True
    return sys.platform == "android"


def _criar_ssl_context() -> ssl.SSLContext:
    """Cria contexto SSL usando certificados do certifi para evitar falhas no Android."""
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def obter_destino_apk() -> Path:
    """Retorna o caminho para salvar o APK (Documents/DiarioACE/update.apk no Android)."""
    if eh_android():
        ext_root = Path(os.environ.get("EXTERNAL_STORAGE", "/storage/emulated/0"))
        candidatos = [
            ext_root / "Documents" / "DiarioACE",
            ext_root / "Download" / "DiarioACE",
        ]
        for pasta in candidatos:
            try:
                pasta.mkdir(parents=True, exist_ok=True)
                arq = pasta / "update.apk"
                if arq.exists():
                    arq.unlink()
                teste = pasta / ".write_test"
                teste.write_text("ok", encoding="utf-8")
                teste.unlink()
                return arq
            except Exception:
                continue

        temp_env = os.environ.get("FLET_APP_STORAGE_TEMP")
        if temp_env:
            pasta_temp = Path(temp_env)
            pasta_temp.mkdir(parents=True, exist_ok=True)
            return pasta_temp / "update.apk"

    pasta_local = default_db_dir()
    pasta_local.mkdir(parents=True, exist_ok=True)
    return pasta_local / "update.apk"


def verificar_atualizacao(
    build_atual: int,
    url: str = VERSION_URL,
    timeout: int = 10,
) -> dict | None:
    """Consulta version.json no GitHub e retorna os dados se latest_version > build_atual."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "DiarioACE-Updater/1.0",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
    )
    try:
        with urllib.request.urlopen(
            req, timeout=timeout, context=_criar_ssl_context()
        ) as resp:
            conteudo = resp.read().decode("utf-8")
        dados = json.loads(conteudo)
    except (
        urllib.error.URLError,
        TimeoutError,
        ValueError,
        OSError,
    ) as ex:
        logger.warning("Não foi possível verificar atualização: %s", ex)
        return None

    if not isinstance(dados, dict):
        return None

    try:
        latest_version = int(dados.get("latest_version", 0))
    except (TypeError, ValueError):
        return None

    apk_url = str(dados.get("apk_url") or "").strip()
    if latest_version > int(build_atual) and apk_url:
        return {
            "latest_version": latest_version,
            "apk_url": apk_url,
            "changelog": str(dados.get("changelog") or ""),
        }
    return None


def baixar_apk(
    url: str,
    destino: str | Path,
    chunk_size: int = CHUNK_SIZE_PADRAO,
    on_progress: Callable[[int, int], None] | None = None,
    timeout: int = 60,
) -> str:
    """Baixa o APK em blocos (chunks) sem travar a memória e retorna o caminho final."""
    destino_path = Path(destino)
    destino_path.parent.mkdir(parents=True, exist_ok=True)

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "DiarioACE-Updater/1.0"},
    )
    with urllib.request.urlopen(
        req, timeout=timeout, context=_criar_ssl_context()
    ) as resp:
        try:
            total = int(resp.headers.get("Content-Length") or 0)
        except (TypeError, ValueError):
            total = 0

        baixado = 0
        with open(destino_path, "wb") as arquivo:
            while True:
                bloco = resp.read(chunk_size)
                if not bloco:
                    break
                arquivo.write(bloco)
                baixado += len(bloco)
                if on_progress is not None:
                    try:
                        on_progress(baixado, total)
                    except Exception:
                        pass

    return str(destino_path)

