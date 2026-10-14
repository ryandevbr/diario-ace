import json
import os
from datetime import datetime
from pathlib import Path
from app.database import get_conn

VERSAO_BACKUP = 1

def exportar_para_dict() -> dict:
    """Lê tudo do banco e devolve um dict serializável."""
    conn = get_conn()
    trs = [dict(r) for r in conn.execute("SELECT * FROM tr").fetchall()]
    producoes = [dict(r) for r in conn.execute("SELECT * FROM producao").fetchall()]
    eventos = [dict(r) for r in conn.execute("SELECT * FROM evento").fetchall()]
    motivos = [dict(r) for r in conn.execute("SELECT * FROM motivo").fetchall()]
    conn.close()
    return {
        "versao": VERSAO_BACKUP,
        "exportado_em": datetime.now().isoformat(),
        "tr": trs,
        "producao": producoes,
        "evento": eventos,
        "motivo": motivos,
    }

def exportar_para_arquivo(caminho: str | Path) -> Path:
    caminho = Path(caminho)
    dados = exportar_para_dict()
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    return caminho

def validar_backup(dados: dict) -> None:
    if not isinstance(dados, dict):
        raise ValueError("Arquivo não é um JSON de backup válido.")
    if dados.get("versao") != VERSAO_BACKUP:
        raise ValueError(
            f"Versão de backup incompatível: {dados.get('versao')} "
            f"(esperado {VERSAO_BACKUP})."
        )
    for chave in ("tr", "producao", "evento", "motivo"):
        if chave not in dados or not isinstance(dados[chave], list):
            raise ValueError(f"Backup sem a chave obrigatória: {chave}.")

def importar_de_arquivo(caminho: str | Path, substituir: bool = True) -> dict:
    """Lê o JSON, valida e grava no banco. Se substituir=True, apaga tudo antes."""
    caminho = Path(caminho)
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    validar_backup(dados)

    conn = get_conn()
    cur = conn.cursor()
    try:
        if substituir:
            cur.execute("DELETE FROM producao")
            cur.execute("DELETE FROM evento")
            cur.execute("DELETE FROM tr")
            cur.execute("DELETE FROM motivo")

        for m in dados["motivo"]:
            cur.execute(
                "INSERT OR IGNORE INTO motivo (id, nome, ativo) VALUES (?, ?, ?)",
                (m["id"], m["nome"], m.get("ativo", 1)),
            )
        for t in dados["tr"]:
            cur.execute(
                "INSERT OR REPLACE INTO tr "
                "(id, ano, numero, data_inicio, data_fim, meta_min, meta_max) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (t["id"], t["ano"], t["numero"], t["data_inicio"],
                 t["data_fim"], t["meta_min"], t["meta_max"]),
            )
        for p in dados["producao"]:
            cur.execute(
                "INSERT OR REPLACE INTO producao "
                "(id, data, tr_id, quantidade, motivo_id, observacao, criado_em, atualizado_em) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (p["id"], p["data"], p["tr_id"], p["quantidade"],
                 p.get("motivo_id"), p.get("observacao"),
                 p["criado_em"], p["atualizado_em"]),
            )
        for e in dados["evento"]:
            cur.execute(
                "INSERT OR REPLACE INTO evento "
                "(id, data, tipo, fracao, observacao, criado_em) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (e["id"], e["data"], e["tipo"], e["fracao"],
                 e.get("observacao"), e["criado_em"]),
            )
        conn.commit()
    finally:
        conn.close()

    return {
        "tr": len(dados["tr"]),
        "producao": len(dados["producao"]),
        "evento": len(dados["evento"]),
        "motivo": len(dados["motivo"]),
    }

def _pasta_backup_publica() -> Path | None:
    """Tenta achar uma pasta pública acessível (Documents/BackupACE).

    No Android, FLET_APP_STORAGE_DATA é privado. Salvamos também em
    /storage/emulated/0/Documents/BackupACE para o Autosync/Drive ver.
    Retorna None em desktop (onde não faz sentido).
    """
    import sys
    if sys.platform not in ("android", "ios") and "ANDROID_ARGUMENT" not in os.environ:
        return None

    candidatos = [
        Path("/storage/emulated/0/Documents/BackupACE"),
        Path("/storage/emulated/0/Download/BackupACE"),
    ]
    for p in candidatos:
        try:
            p.mkdir(parents=True, exist_ok=True)
            # Testa escrita
            teste = p / ".write_test"
            teste.write_text("ok")
            teste.unlink()
            return p
        except Exception:
            continue
    return None


def fazer_backup_automatico(manter: int = 7, intervalo_horas: int = 24) -> Path | None:
    """Cria backup JSON automático se passou mais de `intervalo_horas` desde o último.

    Mantém no máximo `manter` arquivos em cada local, e salva em dois lugares:
    1. Pasta privada do app (FLET_APP_STORAGE_DATA/backups) — sempre funciona.
    2. Pasta pública em Documents/BackupACE — visível para o Autosync.
    """
    db_dir = Path(
        os.getenv("FLET_APP_STORAGE_DATA")
        or Path(__file__).resolve().parent.parent.parent / "data"
    )
    backups_dir = db_dir / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)

    existentes = sorted(backups_dir.glob("auto_*.json"))
    if existentes:
        try:
            mtime = existentes[-1].stat().st_mtime
            if (datetime.now().timestamp() - mtime) < intervalo_horas * 3600:
                return None
        except OSError:
            pass

    nome = f"auto_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    caminho = backups_dir / nome
    exportar_para_arquivo(caminho)

    # Cópia em pasta pública (Android)
    pasta_pub = _pasta_backup_publica()
    if pasta_pub:
        try:
            exportar_para_arquivo(pasta_pub / nome)
            print(f"Cópia pública salva em: {pasta_pub / nome}")

            # Limpa antigos da pasta pública também
            todos_pub = sorted(pasta_pub.glob("auto_*.json"))
            if len(todos_pub) > manter:
                for antigo in todos_pub[:-manter]:
                    try:
                        antigo.unlink()
                    except OSError:
                        pass
        except Exception as ex:
            print(f"Não foi possível salvar cópia pública: {ex}")

    # Limpeza da pasta privada
    todos = sorted(backups_dir.glob("auto_*.json"))
    if len(todos) > manter:
        for antigo in todos[:-manter]:
            try:
                antigo.unlink()
            except OSError:
                pass

    return caminho