from datetime import date, datetime, time, timedelta
from pathlib import Path
import csv
import re

try:
    import openpyxl
except ImportError:
    openpyxl = None

from app.database import get_conn


class BancoHorasErro(Exception):
    pass


TIPOS_VALIDOS = ("trabalhada", "compensacao")

LABEL_TIPO = {
    "trabalhada":  "Horas Trabalhadas",
    "compensacao": "Compensação",
}


# ---------- Conversão de "HH:MM" / "HH:MM:SS" ----------
_RE_HORA = re.compile(r"^\s*(\d+):(\d{1,2})(?::(\d{1,2}))?\s*$")


def _parse_horas(valor) -> float:
    """Aceita datetime/time (Excel), '27:00', '27:00:00', 27.5, timedelta,
    ou fração de dia do Excel."""
    if valor is None or valor == "":
        raise BancoHorasErro("Valor de horas vazio.")

    # datetime — típico do openpyxl quando a célula está formatada como hora.
    # O Excel "ancora" o horário em 1899-12-30 ou 1900-01-01. Só a parte
    # hora/minuto/segundo interessa.
    if isinstance(valor, datetime):
        return (
            valor.hour
            + valor.minute / 60
            + valor.second / 3600
            + valor.microsecond / 3_600_000_000
        )

    # time (também possível)
    from datetime import time as _time
    if isinstance(valor, _time):
        return (
            valor.hour
            + valor.minute / 60
            + valor.second / 3600
        )

    # timedelta
    if isinstance(valor, timedelta):
        return valor.total_seconds() / 3600.0

    # float ou int: pode ser hora decimal ou fração de dia do Excel
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


def _parse_data(valor) -> date:
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if isinstance(valor, str):
        s = valor.strip()
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y"):
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                continue
    raise BancoHorasErro(f"Data inválida: {valor!r}")


# ---------- CRUD ----------
def listar_todos() -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM banco_horas ORDER BY data DESC, id DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def saldo_atual() -> float:
    conn = get_conn()
    row = conn.execute("""
        SELECT
            COALESCE(SUM(CASE WHEN tipo='trabalhada' THEN horas ELSE 0 END), 0) -
            COALESCE(SUM(CASE WHEN tipo='compensacao' THEN horas ELSE 0 END), 0)
        AS saldo
        FROM banco_horas
    """).fetchone()
    conn.close()
    return float(row["saldo"] or 0)


def total_por_tipo(ano: int | None = None) -> dict:
    """Devolve {'trabalhada': X, 'compensacao': Y} para o ano (ou total geral)."""
    conn = get_conn()
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
    conn.close()
    resultado = {"trabalhada": 0.0, "compensacao": 0.0}
    for r in rows:
        resultado[r["tipo"]] = float(r["total"] or 0)
    return resultado


def adicionar(d: date, horas: float, tipo: str, descricao: str | None = None) -> None:
    if tipo not in TIPOS_VALIDOS:
        raise BancoHorasErro(f"Tipo inválido: {tipo}")
    if horas <= 0:
        raise BancoHorasErro("Horas deve ser maior que zero.")
    conn = get_conn()
    conn.execute(
        "INSERT INTO banco_horas (data, horas, tipo, descricao, criado_em) "
        "VALUES (?, ?, ?, ?, ?)",
        (d.isoformat(), float(horas), tipo, descricao,
         datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def atualizar(mov_id: int, d: date, horas: float, tipo: str,
              descricao: str | None = None) -> None:
    if tipo not in TIPOS_VALIDOS:
        raise BancoHorasErro(f"Tipo inválido: {tipo}")
    conn = get_conn()
    conn.execute(
        "UPDATE banco_horas SET data=?, horas=?, tipo=?, descricao=? WHERE id=?",
        (d.isoformat(), float(horas), tipo, descricao, mov_id),
    )
    conn.commit()
    conn.close()


def remover(mov_id: int) -> None:
    conn = get_conn()
    conn.execute("DELETE FROM banco_horas WHERE id=?", (mov_id,))
    conn.commit()
    conn.close()


def remover_todos() -> None:
    conn = get_conn()
    conn.execute("DELETE FROM banco_horas")
    conn.commit()
    conn.close()


# ---------- Formatação ----------
def formatar_horas(horas: float) -> str:
    """3.5 → '03:30'. Aceita negativo."""
    sinal = "-" if horas < 0 else ""
    horas = abs(horas)
    h = int(horas)
    m = int(round((horas - h) * 60))
    if m == 60:
        h += 1
        m = 0
    return f"{sinal}{h:02d}:{m:02d}"


def formatar_dias(horas: float, horas_por_dia: int = 8) -> str:
    """Converte um total de horas em 'Xd Yh Zmin'.

    Ex.: 175.0 → '21d 7h'
         8.0   → '1d'
         3.5   → '3h 30min'
         0.5   → '30min'
    """
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

# ---------- Importação ----------
ALIASES_DATA   = ("data", "dt", "dia", "date")
ALIASES_HORAS  = ("hora registrada", "hora", "horas", "hora registrada",
                  "horas registradas", "quantidade")
ALIASES_TIPO   = ("tipo",)
ALIASES_DESC   = ("descrição", "descricao", "desc", "observação", "observacao")


def _normalizar(s: str) -> str:
    return s.strip().lower()


def _encontrar_coluna(headers: list[str], aliases) -> str | None:
    mapa = {_normalizar(h): h for h in headers if h}
    for alias in aliases:
        if alias in mapa:
            return mapa[alias]
    return None


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
    col_data = _encontrar_coluna(headers, ALIASES_DATA)
    col_horas = _encontrar_coluna(headers, ALIASES_HORAS)
    col_tipo = _encontrar_coluna(headers, ALIASES_TIPO)
    col_desc = _encontrar_coluna(headers, ALIASES_DESC)

    if not col_data:
        raise BancoHorasErro(
            f"Precisa da coluna 'Data'. Encontradas: {headers}"
        )
    if not col_horas:
        raise BancoHorasErro(
            f"Precisa da coluna 'Hora Registrada'. Encontradas: {headers}"
        )
    if not col_tipo:
        raise BancoHorasErro(
            f"Precisa da coluna 'Tipo'. Encontradas: {headers}"
        )

    if by_index:
        idx = {c: headers.index(c) for c in [col_data, col_horas, col_tipo, col_desc] if c}
    else:
        idx = {c: c for c in [col_data, col_horas, col_tipo, col_desc] if c}

    def val(row, col):
        if col is None:
            return None
        return getter(row, idx[col])

    def linha_vazia(row) -> bool:
        for c in [col_data, col_horas, col_tipo]:
            v = val(row, c)
            if v is None:
                continue
            if isinstance(v, str) and not v.strip():
                continue
            return False
        return True

    resultado = []
    for i, row in enumerate(dados_iter, start=2):
        if linha_vazia(row):
            continue
        try:
            d = _parse_data(val(row, col_data))
            horas = _parse_horas(val(row, col_horas))
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
            raise BancoHorasErro(f"Linha {i}: {ex}")

        resultado.append({
            "data": d,
            "horas": horas,
            "tipo": tipo,
            "descricao": descricao,
        })
    return resultado


def _ler_csv(caminho: Path) -> list[dict]:
    with open(caminho, "r", encoding="utf-8-sig", newline="") as f:
        amostra = f.read(4096)
        f.seek(0)
        try:
            dialecto = csv.Sniffer().sniff(amostra, delimiters=",;")
        except csv.Error:
            dialecto = csv.excel
        leitor = csv.DictReader(f, dialect=dialecto)
        headers = leitor.fieldnames or []
        return _extrair_linhas(
            headers, leitor,
            getter=lambda row, h: row.get(h),
            by_index=False,
        )


def _ler_xlsx(caminho: Path) -> list[dict]:
    if openpyxl is None:
        raise BancoHorasErro("openpyxl não instalado.")
    wb = openpyxl.load_workbook(caminho, data_only=True, read_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    if not rows:
        return []
    headers = [str(c) if c is not None else "" for c in rows[0]]
    dados = rows[1:]
    return _extrair_linhas(
        headers, dados,
        getter=lambda row, i: row[i] if i < len(row) else None,
        by_index=True,
    )


def ler_planilha(caminho) -> list[dict]:
    caminho = Path(caminho)
    sufixo = caminho.suffix.lower()
    if sufixo == ".csv":
        return _ler_csv(caminho)
    if sufixo in (".xlsx", ".xlsm"):
        return _ler_xlsx(caminho)
    raise BancoHorasErro(f"Formato não suportado: {sufixo}. Use .csv ou .xlsx.")


def importar_linhas(linhas: list[dict], substituir: bool = False) -> dict:
    """Importa movimentações. Se substituir=True, apaga tudo antes."""
    if substituir:
        remover_todos()

    conn = get_conn()
    agora = datetime.now().isoformat()
    inseridos = 0
    try:
        for linha in linhas:
            conn.execute(
                "INSERT INTO banco_horas (data, horas, tipo, descricao, criado_em) "
                "VALUES (?, ?, ?, ?, ?)",
                (linha["data"].isoformat(), float(linha["horas"]),
                 linha["tipo"], linha.get("descricao"), agora),
            )
            inseridos += 1
        conn.commit()
    finally:
        conn.close()

    return {"inseridos": inseridos, "total": len(linhas)}