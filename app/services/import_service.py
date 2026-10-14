from datetime import date, datetime
import csv
from pathlib import Path

try:
    import openpyxl
except ImportError:
    openpyxl = None

from app.database import get_conn
from app.services import bairro_service, atividade_service


class ImportacaoErro(Exception):
    """Erro controlado durante a leitura/importação da planilha."""
    pass


# ---------- Aliases de cabeçalho ----------
ALIASES_DATA       = ("data", "dt", "dia", "date")
ALIASES_TOTAL      = ("total t", "total", "produção", "producao",
                      "quantidade", "imóveis", "imoveis")
ALIASES_BAIRRO     = ("bairro", "bairros", "localidade")
ALIASES_ATIVIDADE  = ("atividade", "tipo de atividade", "tipo")
ALIASES_FECHADOS   = ("fechados", "fechado", "casas fechadas")
ALIASES_RESGATADOS = ("resgates", "resgatados", "resgate")
ALIASES_RECUSADOS  = ("recusas", "recusados", "recusa")
ALIASES_PENDENCIA  = ("pendência", "pendencia", "pendências", "pendencias")
ALIASES_OBS        = ("observações", "observacao", "observação", "obs",
                      "comentário", "comentario")


def _normalizar(s: str) -> str:
    return s.strip().lower()


def _encontrar_coluna(headers: list[str], aliases) -> str | None:
    mapa = {_normalizar(h): h for h in headers if h}
    for alias in aliases:
        if alias in mapa:
            return mapa[alias]
    return None


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
    raise ImportacaoErro(f"Data inválida: {valor!r}")


def _parse_int(valor, campo: str) -> int:
    if valor is None or valor == "":
        return 0
    try:
        return int(float(valor))
    except (TypeError, ValueError):
        raise ImportacaoErro(f"{campo} inválido: {valor!r}")


def _parse_texto(valor) -> str | None:
    if valor is None:
        return None
    s = str(valor).strip()
    return s or None


def _extrair_linhas(headers, dados_iter, getter, by_index: bool) -> list[dict]:
    col_data = _encontrar_coluna(headers, ALIASES_DATA)
    col_total = _encontrar_coluna(headers, ALIASES_TOTAL)
    col_bairro = _encontrar_coluna(headers, ALIASES_BAIRRO)
    col_atividade = _encontrar_coluna(headers, ALIASES_ATIVIDADE)
    col_fechados = _encontrar_coluna(headers, ALIASES_FECHADOS)
    col_resgatados = _encontrar_coluna(headers, ALIASES_RESGATADOS)
    col_recusados = _encontrar_coluna(headers, ALIASES_RECUSADOS)
    col_pendencia = _encontrar_coluna(headers, ALIASES_PENDENCIA)
    col_obs = _encontrar_coluna(headers, ALIASES_OBS)

    if not col_data:
        raise ImportacaoErro(
            f"A planilha precisa ter a coluna 'Data'. "
            f"Colunas encontradas: {headers}"
        )
    if not col_total:
        raise ImportacaoErro(
            f"A planilha precisa ter a coluna 'Total T' (ou 'Produção', "
            f"'Quantidade'). Colunas encontradas: {headers}"
        )

    if by_index:
        idx = {c: headers.index(c) for c in
               [col_data, col_total, col_bairro, col_atividade,
                col_fechados, col_resgatados, col_recusados,
                col_pendencia, col_obs] if c}
    else:
        idx = {c: c for c in
               [col_data, col_total, col_bairro, col_atividade,
                col_fechados, col_resgatados, col_recusados,
                col_pendencia, col_obs] if c}

    def val(row, col):
        if col is None:
            return None
        return getter(row, idx[col])

    def linha_vazia(row) -> bool:
        for c in [col_data, col_total, col_bairro, col_atividade,
                  col_fechados, col_resgatados, col_recusados,
                  col_pendencia, col_obs]:
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
            total = _parse_int(val(row, col_total), "Total T")
            fechados = _parse_int(val(row, col_fechados), "Fechados")
            resgatados = _parse_int(val(row, col_resgatados), "Resgates")
            recusados = _parse_int(val(row, col_recusados), "Recusas")
        except ImportacaoErro as ex:
            raise ImportacaoErro(f"Linha {i}: {ex}")

        bairro = _parse_texto(val(row, col_bairro))
        atividade = atividade_service.normalizar(
            _parse_texto(val(row, col_atividade))
        )
        pendencia = _parse_texto(val(row, col_pendencia))
        obs = _parse_texto(val(row, col_obs))

        # Junta Pendência com Observação, sem duplicar
        if pendencia and obs:
            observacao = f"{pendencia} — {obs}"
        elif pendencia:
            observacao = pendencia
        else:
            observacao = obs

        resultado.append({
            "data": d,
            "quantidade": total,
            "bairro": bairro,
            "atividade": atividade,
            "fechados": fechados,
            "resgatados": resgatados,
            "recusados": recusados,
            "observacao": observacao,
        })
    return resultado


def _ler_csv(caminho: Path) -> list[dict]:
    # Detecta delimitador (vírgula ou ponto e vírgula)
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
        raise ImportacaoErro("openpyxl não instalado. Rode: pip install openpyxl")
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
    """Lê o arquivo e devolve lista de dicts com os dados de produção."""
    caminho = Path(caminho)
    sufixo = caminho.suffix.lower()
    if sufixo == ".csv":
        return _ler_csv(caminho)
    if sufixo in (".xlsx", ".xlsm"):
        return _ler_xlsx(caminho)
    raise ImportacaoErro(
        f"Formato não suportado: {sufixo}. Use .csv, .xlsx ou .xlsm."
    )


def importar_linhas(linhas: list[dict]) -> dict:
    """Insere/atualiza as produções. Cria bairros conforme necessário."""
    from app.services import tr_service

    inseridos = 0
    atualizados = 0
    ignorados: list[tuple[str, str]] = []
    bairros_criados: set[str] = set()

    conn = get_conn()
    try:
        agora = datetime.now().isoformat()
        for linha in linhas:
            d: date = linha["data"]
            qtd: int = linha["quantidade"]
            obs: str | None = linha["observacao"]
            bairro_nome: str | None = linha.get("bairro")
            atividade: str | None = linha.get("atividade")
            fechados: int = linha.get("fechados", 0) or 0
            resgatados: int = linha.get("resgatados", 0) or 0
            recusados: int = linha.get("recusados", 0) or 0

            tr = tr_service.tr_por_data(d)
            if tr is None:
                ignorados.append((d.isoformat(), "fora de qualquer TR"))
                continue

            bairro_id = None
            if bairro_nome:
                existente_b = bairro_service.buscar_por_nome(bairro_nome)
                if existente_b:
                    bairro_id = existente_b["id"]
                else:
                    bairro_id = bairro_service.criar(bairro_nome)
                    bairros_criados.add(bairro_nome)

            existente = conn.execute(
                "SELECT id FROM producao WHERE data=?", (d.isoformat(),)
            ).fetchone()

            if existente:
                conn.execute(
                    "UPDATE producao SET quantidade=?, tr_id=?, bairro_id=?, "
                    "atividade=?, fechados=?, resgatados=?, recusados=?, "
                    "observacao=?, atualizado_em=? WHERE id=?",
                    (qtd, tr.id, bairro_id, atividade, fechados, resgatados,
                     recusados, obs, agora, existente["id"]),
                )
                atualizados += 1
            else:
                conn.execute(
                    "INSERT INTO producao (data, tr_id, bairro_id, atividade, "
                    "quantidade, fechados, resgatados, recusados, "
                    "observacao, criado_em, atualizado_em) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (d.isoformat(), tr.id, bairro_id, atividade, qtd,
                     fechados, resgatados, recusados, obs, agora, agora),
                )
                inseridos += 1
        conn.commit()
    finally:
        conn.close()

    return {
        "inseridos": inseridos,
        "atualizados": atualizados,
        "ignorados": ignorados,
        "total": len(linhas),
        "bairros_criados": sorted(bairros_criados),
    }