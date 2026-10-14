from app.database import get_conn


def obter(chave: str, padrao: str | None = None) -> str | None:
    conn = get_conn()
    row = conn.execute("SELECT valor FROM config WHERE chave=?", (chave,)).fetchone()
    conn.close()
    return row["valor"] if row else padrao


def definir(chave: str, valor: str) -> None:
    conn = get_conn()
    conn.execute(
        "INSERT INTO config (chave, valor) VALUES (?, ?) "
        "ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor",
        (chave, valor),
    )
    conn.commit()
    conn.close()