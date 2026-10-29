from datetime import datetime
import logging
import os
from pathlib import Path
import shutil
import sys

from app.database import db_session, default_db_dir

logger = logging.getLogger(__name__)


def listar_ativos() -> list[dict]:
    with db_session() as conn:
        rows = conn.execute(
            "SELECT id, nome, croqui_path FROM bairro WHERE ativo=1 ORDER BY nome"
        ).fetchall()
    return [
        {
            "id": r["id"],
            "nome": r["nome"],
            "croqui_path": r["croqui_path"],
        }
        for r in rows
    ]


def listar_todos() -> list[dict]:
    with db_session() as conn:
        rows = conn.execute(
            "SELECT id, nome, ativo, croqui_path FROM bairro ORDER BY ativo DESC, nome"
        ).fetchall()
    return [
        {
            "id": r["id"],
            "nome": r["nome"],
            "ativo": r["ativo"],
            "croqui_path": r["croqui_path"],
        }
        for r in rows
    ]


def buscar_por_nome(nome: str) -> dict | None:
    with db_session() as conn:
        row = conn.execute(
            "SELECT id, nome, croqui_path FROM bairro WHERE LOWER(nome)=LOWER(?)",
            (nome.strip(),),
        ).fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "nome": row["nome"],
        "croqui_path": row["croqui_path"],
    }


def criar(nome: str) -> int:
    """Cria um bairro e devolve o id. Se já existir, devolve o id existente."""
    nome = nome.strip()
    if not nome:
        raise ValueError("Nome do bairro não pode ser vazio.")
    existente = buscar_por_nome(nome)
    if existente:
        return existente["id"]

    with db_session(commit=True) as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO bairro (nome, ativo, criado_em) VALUES (?, 1, ?)",
            (nome, datetime.now().isoformat()),
        )
        return int(cur.lastrowid)


def obter_ou_criar(nome: str) -> int | None:
    """Para uso na importação: cria se não existir. Devolve None se nome vazio."""
    if not nome or not nome.strip():
        return None
    return criar(nome)


def renomear(bairro_id: int, novo_nome: str) -> None:
    novo_nome = novo_nome.strip()
    if not novo_nome:
        raise ValueError("Nome não pode ser vazio.")
    with db_session(commit=True) as conn:
        conn.execute("UPDATE bairro SET nome=? WHERE id=?", (novo_nome, bairro_id))


def alternar_ativo(bairro_id: int, ativo: bool) -> None:
    with db_session(commit=True) as conn:
        conn.execute(
            "UPDATE bairro SET ativo=? WHERE id=?",
            (1 if ativo else 0, bairro_id),
        )


def buscar_por_id(bairro_id: int) -> dict | None:
    with db_session() as conn:
        row = conn.execute(
            "SELECT id, nome, croqui_path FROM bairro WHERE id=?",
            (bairro_id,),
        ).fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "nome": row["nome"],
        "croqui_path": row["croqui_path"],
    }


def obter_diretorio_croquis() -> Path:
    """Retorna o diretório privado onde os croquis são salvos."""
    croquis_dir = default_db_dir() / "croquis"
    croquis_dir.mkdir(parents=True, exist_ok=True)
    return croquis_dir


def obter_diretorio_croquis_publico() -> Path | None:
    """Retorna o diretório público de croquis no Android (Documents/BackupACE/croquis)
    ou None em desktop / se indisponível.
    """
    if sys.platform not in ("android", "ios") and "ANDROID_ARGUMENT" not in os.environ:
        return None

    candidatos = [
        Path("/storage/emulated/0/Documents/BackupACE/croquis"),
        Path("/storage/emulated/0/Download/BackupACE/croquis"),
    ]
    for p in candidatos:
        try:
            p.mkdir(parents=True, exist_ok=True)
            teste = p / ".write_test"
            teste.write_text("ok")
            teste.unlink()
            return p
        except Exception:
            continue
    return None


def salvar_croqui(bairro_id: int, caminho_origem: str) -> str:
    origem = Path(caminho_origem)
    if not origem.exists() or origem.suffix.lower() not in [".pdf", ".jpg", ".jpeg", ".png"]:
        raise ValueError("Arquivo inválido. Selecione um PDF ou Imagem.")
    
    # Mantém a extensão original do arquivo (jpg, png ou pdf)
    extensao = origem.suffix.lower()
    destino = obter_diretorio_croquis() / f"croqui_{bairro_id}{extensao}"

    if origem.resolve() != destino.resolve():
        shutil.copy2(origem, destino)

    # Cópia na pasta pública do Android (Documents/BackupACE/croquis/)
    pasta_pub = obter_diretorio_croquis_publico()
    if pasta_pub:
        try:
            destino_pub = pasta_pub / destino.name
            if origem.resolve() != destino_pub.resolve():
                shutil.copy2(destino, destino_pub)
        except Exception as ex:
            logger.warning("Não foi possível copiar croqui para pasta pública: %s", ex)

    with db_session(commit=True) as conn:
        conn.execute(
            "UPDATE bairro SET croqui_path=? WHERE id=?",
            (str(destino), bairro_id),
        )

    return str(destino)


def remover_croqui(bairro_id: int) -> None:
    """Remove o PDF do diretório privado, do diretório público (Android) e limpa o banco."""
    nome_padrao = f"croqui_{bairro_id}.pdf"

    with db_session(commit=True) as conn:
        row = conn.execute(
            "SELECT croqui_path FROM bairro WHERE id=?", (bairro_id,)
        ).fetchone()
        caminho_salvo = row["croqui_path"] if row else None
        conn.execute("UPDATE bairro SET croqui_path=NULL WHERE id=?", (bairro_id,))

    arquivos_privados = {obter_diretorio_croquis() / nome_padrao}
    if caminho_salvo:
        arquivos_privados.add(Path(caminho_salvo))

    for arq in arquivos_privados:
        if arq.exists():
            try:
                arq.unlink()
            except OSError:
                pass

    pasta_pub = obter_diretorio_croquis_publico()
    if pasta_pub:
        arquivos_publicos = {pasta_pub / nome_padrao}
        if caminho_salvo:
            arquivos_publicos.add(pasta_pub / Path(caminho_salvo).name)
        for arq_pub in arquivos_publicos:
            if arq_pub.exists():
                try:
                    arq_pub.unlink()
                except OSError:
                    pass
