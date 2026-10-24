from app.database import db_session


def obter(chave: str, padrao: str | None = None) -> str | None:
    with db_session() as conn:
        row = conn.execute(
            "SELECT valor FROM config WHERE chave=?", (chave,)
        ).fetchone()
    return row["valor"] if row else padrao


def definir(chave: str, valor: str) -> None:
    with db_session(commit=True) as conn:
        conn.execute(
            "INSERT INTO config (chave, valor) VALUES (?, ?) "
            "ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor",
            (chave, valor),
        )
