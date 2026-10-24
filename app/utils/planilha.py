import csv
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Iterable

try:
    import openpyxl
except ImportError:
    openpyxl = None


FORMATOS_DATA = ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y")


def normalizar_header(texto: str) -> str:
    return texto.strip().lower()


def encontrar_coluna(headers: Iterable[str], aliases: Iterable[str]) -> str | None:
    """Encontra o nome original da coluna correspondente ao primeiro alias encontrado."""
    mapa = {normalizar_header(h): h for h in headers if h}
    for alias in aliases:
        chave = normalizar_header(alias)
        if chave in mapa:
            return mapa[chave]
    return None


def parse_data_planilha(valor: Any, erro_cls: type[Exception] = ValueError) -> date:
    """Converte célula de data (datetime, date ou texto) para datetime.date."""
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if isinstance(valor, str):
        s = valor.strip()
        for fmt in FORMATOS_DATA:
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                continue
    raise erro_cls(f"Data inválida: {valor!r}")


def valor_vazio(valor: Any) -> bool:
    if valor is None:
        return True
    if isinstance(valor, str) and not valor.strip():
        return True
    return False


def ler_tabela_arquivo(
    caminho: str | Path,
    extrator: Callable[[list[str], Iterable[Any], Callable[[Any, Any], Any], bool], list[dict]],
    erro_cls: type[Exception] = ValueError,
) -> list[dict]:
    """Lê um arquivo CSV ou XLSX/XLSM e delega as linhas para a função extratora."""
    caminho_path = Path(caminho)
    sufixo = caminho_path.suffix.lower()

    if sufixo == ".csv":
        with open(caminho_path, "r", encoding="utf-8-sig", newline="") as f:
            amostra = f.read(4096)
            f.seek(0)
            try:
                dialecto = csv.Sniffer().sniff(amostra, delimiters=",;")
            except csv.Error:
                dialecto = csv.excel
            leitor = csv.DictReader(f, dialect=dialecto)
            headers = list(leitor.fieldnames or [])
            return extrator(
                headers,
                leitor,
                lambda row, h: row.get(h),
                False,
            )

    if sufixo in (".xlsx", ".xlsm"):
        if openpyxl is None:
            raise erro_cls("openpyxl não instalado. Rode: pip install openpyxl")
        wb = openpyxl.load_workbook(caminho_path, data_only=True, read_only=True)
        try:
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))
        finally:
            wb.close()
        if not rows:
            return []
        headers = [str(c) if c is not None else "" for c in rows[0]]
        dados = rows[1:]
        return extrator(
            headers,
            dados,
            lambda row, i: row[i] if i < len(row) else None,
            True,
        )

    raise erro_cls(
        f"Formato não suportado: {sufixo}. Use .csv, .xlsx ou .xlsm."
    )

