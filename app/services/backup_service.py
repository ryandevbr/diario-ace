from datetime import datetime
import json
import logging
import os
from pathlib import Path
import shutil
import sys
import zipfile

from app.database import db_session, default_db_dir
from app.services import bairro_service

logger = logging.getLogger(__name__)

VERSAO_BACKUP = 1
CHAVES_OBRIGATORIAS = ("tr", "producao", "evento", "motivo")


def exportar_para_dict() -> dict:
    """Lê todos os dados operacionais do banco e devolve um dict serializável."""
    with db_session() as conn:
        trs = [dict(r) for r in conn.execute("SELECT * FROM tr").fetchall()]
        bairros = [dict(r) for r in conn.execute("SELECT * FROM bairro").fetchall()]
        producoes = [dict(r) for r in conn.execute("SELECT * FROM producao").fetchall()]
        eventos = [dict(r) for r in conn.execute("SELECT * FROM evento").fetchall()]
        motivos = [dict(r) for r in conn.execute("SELECT * FROM motivo").fetchall()]
        banco_horas = [
            dict(r) for r in conn.execute("SELECT * FROM banco_horas").fetchall()
        ]
        recuperacoes = [
            dict(r) for r in conn.execute("SELECT * FROM recuperacao").fetchall()
        ]
        configs = [dict(r) for r in conn.execute("SELECT * FROM config").fetchall()]

    return {
        "versao": VERSAO_BACKUP,
        "exportado_em": datetime.now().isoformat(),
        "tr": trs,
        "bairro": bairros,
        "producao": producoes,
        "evento": eventos,
        "motivo": motivos,
        "banco_horas": banco_horas,
        "recuperacao": recuperacoes,
        "config": configs,
    }


def exportar_para_arquivo(caminho: str | Path) -> Path:
    """Cria um arquivo .zip contendo dados.json e os PDFs da pasta croquis/."""
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    dados = exportar_para_dict()
    json_str = json.dumps(dados, ensure_ascii=False, indent=2)

    croquis_dir = bairro_service.obter_diretorio_croquis()
    pdfs = sorted(croquis_dir.glob("*.pdf")) if croquis_dir.exists() else []

    with zipfile.ZipFile(caminho, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("dados.json", json_str)
        for pdf in pdfs:
            if pdf.is_file():
                zf.write(pdf, arcname=f"croquis/{pdf.name}")

    return caminho


def validar_backup(dados: dict) -> None:
    if not isinstance(dados, dict):
        raise ValueError("Arquivo não é um JSON de backup válido.")
    if dados.get("versao") != VERSAO_BACKUP:
        raise ValueError(
            f"Versão de backup incompatível: {dados.get('versao')} "
            f"(esperado {VERSAO_BACKUP})."
        )
    for chave in CHAVES_OBRIGATORIAS:
        if chave not in dados or not isinstance(dados[chave], list):
            raise ValueError(f"Backup sem a chave obrigatória: {chave}.")


def _extrair_croquis_do_zip(zf: zipfile.ZipFile) -> set[str]:
    """Extrai os PDFs de croquis/ do ZIP para a pasta privada (e pública no Android).
    Retorna o conjunto de nomes de arquivos extraídos.
    """
    croquis_dir = bairro_service.obter_diretorio_croquis()
    pasta_pub = bairro_service.obter_diretorio_croquis_publico()
    extraidos: set[str] = set()

    for member in zf.infolist():
        if member.is_dir():
            continue
        partes = Path(member.filename).parts
        if len(partes) == 2 and partes[0] == "croquis" and partes[1].lower().endswith(".pdf"):
            nome_pdf = Path(partes[1]).name
            destino_priv = croquis_dir / nome_pdf
            with zf.open(member) as src, open(destino_priv, "wb") as dst:
                shutil.copyfileobj(src, dst)
            extraidos.add(nome_pdf)

            if pasta_pub:
                try:
                    shutil.copy2(destino_priv, pasta_pub / nome_pdf)
                except Exception as ex:
                    logger.warning(
                        "Não foi possível copiar croqui restaurado para pasta pública: %s",
                        ex,
                    )

    return extraidos


def importar_de_arquivo(caminho: str | Path, substituir: bool = True) -> dict:
    """Lê o backup (.zip ou .json legado), restaura o banco e extrai os croquis."""
    caminho = Path(caminho)
    croquis_extraidos: set[str] = set()

    if caminho.suffix.lower() == ".zip" or zipfile.is_zipfile(caminho):
        with zipfile.ZipFile(caminho, "r") as zf:
            nomes = zf.namelist()
            if "dados.json" not in nomes:
                raise ValueError(
                    "Arquivo ZIP de backup inválido: 'dados.json' não encontrado."
                )
            conteudo_json = zf.read("dados.json").decode("utf-8")
            dados = json.loads(conteudo_json)
            validar_backup(dados)
            croquis_extraidos = _extrair_croquis_do_zip(zf)
    else:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        validar_backup(dados)

    bairros = dados.get("bairro")
    banco_horas = dados.get("banco_horas")
    recuperacoes = dados.get("recuperacao")
    configs = dados.get("config")
    croquis_dir = bairro_service.obter_diretorio_croquis()

    with db_session(commit=True) as conn:
        cur = conn.cursor()
        if substituir:
            # Ordem respeitando integridade referencial (FKs)
            cur.execute("DELETE FROM producao")
            cur.execute("DELETE FROM recuperacao")
            cur.execute("DELETE FROM evento")
            cur.execute("DELETE FROM tr")
            cur.execute("DELETE FROM motivo")
            if isinstance(bairros, list):
                cur.execute("DELETE FROM bairro")
            if isinstance(banco_horas, list):
                cur.execute("DELETE FROM banco_horas")

        for m in dados["motivo"]:
            cur.execute(
                "INSERT OR IGNORE INTO motivo (id, nome, ativo) VALUES (?, ?, ?)",
                (m["id"], m["nome"], m.get("ativo", 1)),
            )

        if isinstance(bairros, list):
            agora_iso = datetime.now().isoformat()
            for b in bairros:
                croqui_local = None
                croqui_salvo = b.get("croqui_path")
                nome_padrao = f"croqui_{b['id']}.pdf"
                if croqui_salvo:
                    candidato = croquis_dir / Path(croqui_salvo).name
                    croqui_local = str(candidato)
                elif nome_padrao in croquis_extraidos:
                    croqui_local = str(croquis_dir / nome_padrao)

                cur.execute(
                    "INSERT OR REPLACE INTO bairro "
                    "(id, nome, ativo, criado_em, croqui_path) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        b["id"],
                        b["nome"],
                        b.get("ativo", 1),
                        b.get("criado_em") or agora_iso,
                        croqui_local,
                    ),
                )

        for t in dados["tr"]:
            cur.execute(
                "INSERT OR REPLACE INTO tr "
                "(id, ano, numero, data_inicio, data_fim, meta_min, meta_max, producao_inicial) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    t["id"],
                    t["ano"],
                    t["numero"],
                    t["data_inicio"],
                    t["data_fim"],
                    t["meta_min"],
                    t["meta_max"],
                    t.get("producao_inicial", 0) or 0,
                ),
            )

        for p in dados["producao"]:
            cur.execute(
                "INSERT OR REPLACE INTO producao "
                "(id, data, tr_id, bairro_id, atividade, quantidade, "
                "fechados, resgatados, recusados, pendencia, motivo_id, "
                "observacao, criado_em, atualizado_em) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    p["id"],
                    p["data"],
                    p["tr_id"],
                    p.get("bairro_id"),
                    p.get("atividade"),
                    p["quantidade"],
                    p.get("fechados", 0) or 0,
                    p.get("resgatados", 0) or 0,
                    p.get("recusados", 0) or 0,
                    p.get("pendencia"),
                    p.get("motivo_id"),
                    p.get("observacao"),
                    p["criado_em"],
                    p["atualizado_em"],
                ),
            )

        for e in dados["evento"]:
            cur.execute(
                "INSERT OR REPLACE INTO evento "
                "(id, data, tipo, fracao, observacao, criado_em) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    e["id"],
                    e["data"],
                    e["tipo"],
                    e["fracao"],
                    e.get("observacao"),
                    e["criado_em"],
                ),
            )

        if isinstance(banco_horas, list):
            for bh in banco_horas:
                cur.execute(
                    "INSERT OR REPLACE INTO banco_horas "
                    "(id, data, horas, tipo, descricao, criado_em) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        bh["id"],
                        bh["data"],
                        bh["horas"],
                        bh["tipo"],
                        bh.get("descricao"),
                        bh["criado_em"],
                    ),
                )

        if isinstance(recuperacoes, list):
            for rec in recuperacoes:
                cur.execute(
                    "INSERT OR REPLACE INTO recuperacao "
                    "(id, tr_id, quarteirao, lado, rua, numero, status, "
                    "observacao, criado_em, atualizado_em) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        rec["id"],
                        rec["tr_id"],
                        rec.get("quarteirao"),
                        rec.get("lado"),
                        rec["rua"],
                        rec["numero"],
                        rec.get("status", "fechado"),
                        rec.get("observacao"),
                        rec["criado_em"],
                        rec["atualizado_em"],
                    ),
                )

        if isinstance(configs, list):
            for cfg in configs:
                if "chave" in cfg:
                    cur.execute(
                        "INSERT OR REPLACE INTO config (chave, valor) VALUES (?, ?)",
                        (cfg["chave"], cfg.get("valor")),
                    )

    return {
        "tr": len(dados["tr"]),
        "producao": len(dados["producao"]),
        "evento": len(dados["evento"]),
        "motivo": len(dados["motivo"]),
        "bairro": len(bairros) if isinstance(bairros, list) else 0,
        "banco_horas": len(banco_horas) if isinstance(banco_horas, list) else 0,
        "recuperacao": len(recuperacoes) if isinstance(recuperacoes, list) else 0,
        "croquis": len(croquis_extraidos),
    }


def _pasta_backup_publica() -> Path | None:
    """Tenta achar uma pasta pública acessível no Android (Documents/BackupACE)."""
    if sys.platform not in ("android", "ios") and "ANDROID_ARGUMENT" not in os.environ:
        return None

    candidatos = [
        Path("/storage/emulated/0/Documents/BackupACE"),
        Path("/storage/emulated/0/Download/BackupACE"),
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


def _listar_backups_auto(pasta: Path) -> list[Path]:
    arquivos = list(pasta.glob("auto_*.zip")) + list(pasta.glob("auto_*.json"))
    return sorted(arquivos, key=lambda p: p.name)


def _limpar_backups_antigos(pasta: Path, manter: int) -> None:
    todos = _listar_backups_auto(pasta)
    if len(todos) > manter:
        for antigo in todos[:-manter]:
            try:
                antigo.unlink()
            except OSError:
                pass


def _sincronizar_croquis_publicos(pasta_pub: Path) -> None:
    """Garante que a subpasta croquis/ em Documents/BackupACE tenha cópia dos PDFs."""
    croquis_priv = bairro_service.obter_diretorio_croquis()
    if not croquis_priv.exists():
        return
    croquis_pub = pasta_pub / "croquis"
    croquis_pub.mkdir(parents=True, exist_ok=True)
    for pdf in croquis_priv.glob("*.pdf"):
        if pdf.is_file():
            shutil.copy2(pdf, croquis_pub / pdf.name)


def fazer_backup_automatico(
    manter: int = 7,
    intervalo_horas: int = 24,
) -> Path | None:
    """Cria backup ZIP automático se passou mais de `intervalo_horas` desde o último."""
    backups_dir = default_db_dir() / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)

    existentes = _listar_backups_auto(backups_dir)
    if existentes:
        try:
            mtime = existentes[-1].stat().st_mtime
            if (datetime.now().timestamp() - mtime) < intervalo_horas * 3600:
                return None
        except OSError:
            pass

    nome = f"auto_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    caminho = backups_dir / nome
    exportar_para_arquivo(caminho)
    _limpar_backups_antigos(backups_dir, manter)

    pasta_pub = _pasta_backup_publica()
    if pasta_pub:
        try:
            exportar_para_arquivo(pasta_pub / nome)
            _sincronizar_croquis_publicos(pasta_pub)
            _limpar_backups_antigos(pasta_pub, manter)
        except Exception as ex:
            logger.warning("Não foi possível salvar cópia pública: %s", ex)

    return caminho
