from datetime import date, datetime, time, timedelta
from pathlib import Path
import re

from app.database import db_session
from app.utils.planilha import (
    encontrar_coluna,
    ler_tabela_arquivo,
    parse_data_planilha,
    valor_vazio,
)


class BancoHorasErro(Exception):
    pass


TIPOS_VALIDOS = ("trabalhada", "compensacao")

LABEL_TIPO = {
    "trabalhada": "Horas Trabalhadas",
    "compensacao": "Compensação",
}

_RE_HORA = re.compile(r"^\s*(\d+):(\d{1,2})(?::(\d{1,2}))?\s*$")


def parse_horas(valor) -> float:
    """Converte datetime/time (Excel), '27:00', '27:00:00', 27.5, timedelta,
    ou fração de dia do Excel em total de horas (float)."""
    if valor is None or valor == "":
        raise BancoHorasErro("Valor de horas vazio.")

    if isinstance(valor, datetime):
        return (
            valor.hour
            + valor.minute / 60
            + valor.second / 3600
            + valor.microsecond / 3_600_000_000
        )

    if isinstance(valor, time):
        return valor.hour + valor.minute / 60 + valor.second / 3600

    if isinstance(valor, timedelta):
        return valor.total_seconds() / 3600.0

    if isinstance(valor, (int, float)):
        v = float(valor)
        if 0 < v < 10 and abs(v - int(v)) > 0.0001:
            return v * 24
        return v

    if isinstance(valor, str):
        s = valor.strip()
        m = _RE_HORA.match(s)
        if m:
            h = int(m.group(1))
            mi = int(m.group(2))
            se = int(m.group(3)) if m.group(3) else 0
            return h + mi / 60 + se / 3600
        try:
            return float(s.replace(",", "."))
        except ValueError:
            pass

    raise BancoHorasErro(f"Formato de horas não reconhecido: {valor!r}")


# Alias para compatibilidade retroativa
_parse_horas = parse_horas


def listar_todos() -> list[dict]:
    with db_session() as conn:
        rows = conn.execute(
            "SELECT * FROM banco_horas ORDER BY data DESC, id DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def saldo_atual() -> float:
    with db_session() as conn:
        row = conn.execute("""
            SELECT
                COALESCE(SUM(CASE WHEN tipo='trabalhada' THEN horas ELSE 0 END), 0) -
                COALESCE(SUM(CASE WHEN tipo='compensacao' THEN horas ELSE 0 END), 0)
            AS saldo
            FROM banco_horas
        """).fetchone()
    return float(row["saldo"] or 0)


def total_por_tipo(ano: int | None = None) -> dict[str, float]:
    """Devolve {'trabalhada': X, 'compensacao': Y} para o ano (ou total geral)."""
    with db_session() as conn:
        if ano:
            rows = conn.execute(
                "SELECT tipo, SUM(horas) AS total FROM banco_horas "
                "WHERE substr(data,1,4)=? GROUP BY tipo",
                (str(ano),),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT tipo, SUM(horas) AS total FROM banco_horas GROUP BY tipo"
            ).fetchall()

    resultado = {"trabalhada": 0.0, "compensacao": 0.0}
    for r in rows:
        resultado[r["tipo"]] = float(r["total"] or 0)
    return resultado


def _validar_movimentacao(horas: float, tipo: str) -> None:
    if tipo not in TIPOS_VALIDOS:
        raise BancoHorasErro(f"Tipo inválido: {tipo}")
    if horas <= 0:
        raise BancoHorasErro("Horas deve ser maior que zero.")


def adicionar(
    d: date,
    horas: float,
    tipo: str,
    descricao: str | None = None,
) -> None:
    _validar_movimentacao(horas, tipo)
    with db_session(commit=True) as conn:
        conn.execute(
            "INSERT INTO banco_horas (data, horas, tipo, descricao, criado_em) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                d.isoformat(),
                float(horas),
                tipo,
                descricao,
                datetime.now().isoformat(),
            ),
        )


def atualizar(
    mov_id: int,
    d: date,
    horas: float,
    tipo: str,
    descricao: str | None = None,
) -> None:
    _validar_movimentacao(horas, tipo)
    with db_session(commit=True) as conn:
        conn.execute(
            "UPDATE banco_horas SET data=?, horas=?, tipo=?, descricao=? WHERE id=?",
            (d.isoformat(), float(horas), tipo, descricao, mov_id),
        )


def remover(mov_id: int) -> None:
    with db_session(commit=True) as conn:
        conn.execute("DELETE FROM banco_horas WHERE id=?", (mov_id,))


def remover_todos() -> None:
    with db_session(commit=True) as conn:
        conn.execute("DELETE FROM banco_horas")


def formatar_horas(horas: float) -> str:
    """Converte horas decimais (ex.: 3.5) para '03:30'. Aceita negativo."""
    sinal = "-" if horas < 0 else ""
    horas = abs(horas)
    h = int(horas)
    m = int(round((horas - h) * 60))
    if m == 60:
        h += 1
        m = 0
    return f"{sinal}{h:02d}:{m:02d}"


def formatar_dias(horas: float, horas_por_dia: int = 8) -> str:
    """Converte um total de horas em 'Xd Yh Zmin'."""
    abs_h = abs(horas)
    dias = int(abs_h // horas_por_dia)
    resto = abs_h - (dias * horas_por_dia)
    h = int(resto)
    m = int(round((resto - h) * 60))
    if m == 60:
        h += 1
        m = 0

    partes = []
    if dias > 0:
        partes.append(f"{dias}d")
    if h > 0:
        partes.append(f"{h}h")
    if m > 0:
        partes.append(f"{m}min")
    if not partes:
        partes.append("0h")
    return " ".join(partes)


def resumo_saldo() -> dict:
    """Retorna saldo em horas e o texto curto para header/tela."""
    saldo = saldo_atual()
    return {
        "horas": saldo,
        "hhmm": formatar_horas(saldo),
        "dias": formatar_dias(saldo),
        "sinal": "+" if saldo >= 0 else "−",
    }


ALIASES_DATA = ("data", "dt", "dia", "date")
ALIASES_HORAS = (
    "hora registrada",
    "hora",
    "horas",
    "horas registradas",
    "quantidade",
)
ALIASES_TIPO = ("tipo",)
ALIASES_DESC = ("descrição", "descricao", "desc", "observação", "observacao")


def _normalizar_tipo(valor: str) -> str | None:
    if not valor:
        return None
    s = valor.strip().lower()
    if "trab" in s or "extra" in s:
        return "trabalhada"
    if "comp" in s or "folga" in s:
        return "compensacao"
    return None


def _extrair_linhas(headers, dados_iter, getter, by_index: bool) -> list[dict]:
    col_data = encontrar_coluna(headers, ALIASES_DATA)
    col_horas = encontrar_coluna(headers, ALIASES_HORAS)
    col_tipo = encontrar_coluna(headers, ALIASES_TIPO)
    col_desc = encontrar_coluna(headers, ALIASES_DESC)

    if not col_data:
        raise BancoHorasErro(f"Precisa da coluna 'Data'. Encontradas: {headers}")
    if not col_horas:
        raise BancoHorasErro(
            f"Precisa da coluna 'Hora Registrada'. Encontradas: {headers}"
        )
    if not col_tipo:
        raise BancoHorasErro(f"Precisa da coluna 'Tipo'. Encontradas: {headers}")

    colunas = [col_data, col_horas, col_tipo, col_desc]
    idx = (
        {c: headers.index(c) for c in colunas if c}
        if by_index
        else {c: c for c in colunas if c}
    )

    def val(row, col):
        return None if col is None else getter(row, idx[col])

    resultado = []
    for i, row in enumerate(dados_iter, start=2):
        if all(valor_vazio(val(row, c)) for c in (col_data, col_horas, col_tipo)):
            continue
        try:
            d = parse_data_planilha(val(row, col_data), BancoHorasErro)
            horas = parse_horas(val(row, col_horas))
            tipo_raw = str(val(row, col_tipo) or "").strip()
            tipo = _normalizar_tipo(tipo_raw)
            if tipo is None:
                raise BancoHorasErro(
                    f"Tipo não reconhecido: {tipo_raw!r}. "
                    f"Use 'Horas Trab.' ou 'Horas Compen.'"
                )
            descricao = val(row, col_desc)
            descricao = str(descricao).strip() if descricao else None
        except BancoHorasErro as ex:
            raise BancoHorasErro(f"Linha {i}: {ex}") from ex

        resultado.append(
            {
                "data": d,
                "horas": horas,
                "tipo": tipo,
                "descricao": descricao,
            }
        )
    return resultado


def ler_planilha(caminho: str | Path) -> list[dict]:
    return ler_tabela_arquivo(caminho, _extrair_linhas, BancoHorasErro)


def importar_linhas(linhas: list[dict], substituir: bool = False) -> dict:
    """Importa movimentações. Se substituir=True, apaga tudo antes."""
    agora = datetime.now().isoformat()
    inseridos = 0
    with db_session(commit=True) as conn:
        if substituir:
            conn.execute("DELETE FROM banco_horas")
        for linha in linhas:
            conn.execute(
                "INSERT INTO banco_horas (data, horas, tipo, descricao, criado_em) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    linha["data"].isoformat(),
                    float(linha["horas"]),
                    linha["tipo"],
                    linha.get("descricao"),
                    agora,
                ),
            )
            inseridos += 1

    return {"inseridos": inseridos, "total": len(linhas)}
