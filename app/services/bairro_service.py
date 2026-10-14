from datetime import datetime
from app.database import get_conn


def listar_ativos() -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, nome FROM bairro WHERE ativo=1 ORDER BY nome"
    ).fetchall()
    conn.close()
    return [{"id": r["id"], "nome": r["nome"]} for r in rows]


def listar_todos() -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, nome, ativo FROM bairro ORDER BY ativo DESC, nome"
    ).fetchall()
    conn.close()
    return [{"id": r["id"], "nome": r["nome"], "ativo": r["ativo"]} for r in rows]


def buscar_por_nome(nome: str) -> dict | None:
    conn = get_conn()
    row = conn.execute(
        "SELECT id, nome FROM bairro WHERE LOWER(nome)=LOWER(?)",
        (nome.strip(),),
    ).fetchone()
    conn.close()
    return {"id": row["id"], "nome": row["nome"]} if row else None


def criar(nome: str) -> int:
    """Cria um bairro e devolve o id. Se já existir, devolve o id existente."""
    nome = nome.strip()
    if not nome:
        raise ValueError("Nome do bairro não pode ser vazio.")
    existente = buscar_por_nome(nome)
    if existente:
        return existente["id"]

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO bairro (nome, ativo, criado_em) VALUES (?, 1, ?)",
        (nome, datetime.now().isoformat()),
    )
    novo_id = cur.lastrowid
    conn.commit()
    conn.close()
    return novo_id


def obter_ou_criar(nome: str) -> int | None:
    """Para uso na importação: cria se não existir. Devolve None se nome vazio."""
    if not nome or not nome.strip():
        return None
    return criar(nome)


def renomear(bairro_id: int, novo_nome: str) -> None:
    novo_nome = novo_nome.strip()
    if not novo_nome:
        raise ValueError("Nome não pode ser vazio.")
    conn = get_conn()
    conn.execute("UPDATE bairro SET nome=? WHERE id=?", (novo_nome, bairro_id))
    conn.commit()
    conn.close()


def alternar_ativo(bairro_id: int, ativo: bool) -> None:
    conn = get_conn()
    conn.execute("UPDATE bairro SET ativo=? WHERE id=?", (1 if ativo else 0, bairro_id))
    conn.commit()
    conn.close()

def buscar_por_id(bairro_id: int) -> dict | None:
    conn = get_conn()
    row = conn.execute(
        "SELECT id, nome FROM bairro WHERE id=?", (bairro_id,)
    ).fetchone()
    conn.close()
    return {"id": row["id"], "nome": row["nome"]} if row else None