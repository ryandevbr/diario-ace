ATIVIDADES = [
    "Tratamento",
    "Levantamento de Índice",
    "Delimitação de Foco - Bloqueio de Transmissão",
    "Ação/Mutirão",
    "P.E. (Ponto Estratégico)",
    "Outros",
]


def listar() -> list[str]:
    return ATIVIDADES.copy()


def normalizar(valor: str | None) -> str | None:
    """Garante que o valor bate com a lista. Devolve 'Outros' se desconhecido."""
    if not valor:
        return None
    s = valor.strip()
    if not s:
        return None
    for a in ATIVIDADES:
        if a.lower() == s.lower():
            return a
    # Alguns aliases comuns do supervisor
    aliases = {
        "delimitação de foco": "Delimitação de Foco - Bloqueio de Transmissão",
        "delimitacao de foco": "Delimitação de Foco - Bloqueio de Transmissão",
        "bloqueio de transmissão": "Delimitação de Foco - Bloqueio de Transmissão",
        "ação/mutirão": "Ação/Mutirão",
        "acao/mutirao": "Ação/Mutirão",
        "mutirão": "Ação/Mutirão",
        "mutirao": "Ação/Mutirão",
        "pe": "P.E. (Ponto Estratégico)",
        "p.e.": "P.E. (Ponto Estratégico)",
        "p.e": "P.E. (Ponto Estratégico)",
        "ponto estratégico": "P.E. (Ponto Estratégico)",
        "ponto estrategico": "P.E. (Ponto Estratégico)",
    }
    chave = s.lower()
    if chave in aliases:
        return aliases[chave]
    return "Outros"