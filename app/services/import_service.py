from datetime import date, datetime
from pathlib import Path

from app.database import db_session
from app.services import atividade_service, tr_service
from app.utils.planilha import (
    encontrar_coluna,
    ler_tabela_arquivo,
    parse_data_planilha,
    valor_vazio,
)


class ImportacaoErro(Exception):
    """Erro controlado durante a leitura/importação da planilha."""


ALIASES_DATA = ("data", "dt", "dia", "date")
ALIASES_TOTAL = (
    "total t",
    "total",
    "produção",
    "producao",
    "quantidade",
    "imóveis",
    "imoveis",
)
ALIASES_BAIRRO = ("bairro", "bairros", "localidade")
ALIASES_ATIVIDADE = ("atividade", "tipo de atividade", "tipo")
ALIASES_FECHADOS = ("fechados", "fechado", "casas fechadas")
ALIASES_RESGATADOS = ("resgates", "resgatados", "resgate")
ALIASES_RECUSADOS = ("recusas", "recusados", "recusa")
ALIASES_PENDENCIA = ("pendência", "pendencia", "pendências", "pendencias")
ALIASES_OBS = (
    "observações",
    "observacao",
    "observação",
    "obs",
    "comentário",
    "comentario",
)


def _parse_int(valor, campo: str) -> int:
    if valor is None or valor == "":
        return 0
    try:
        return int(float(valor))
    except (TypeError, ValueError) as ex:
        raise ImportacaoErro(f"{campo} inválido: {valor!r}") from ex


def _parse_texto(valor) -> str | None:
    if valor is None:
        return None
    s = str(valor).strip()
    return s or None


def _extrair_linhas(headers, dados_iter, getter, by_index: bool) -> list[dict]:
    col_data = encontrar_coluna(headers, ALIASES_DATA)
    col_total = encontrar_coluna(headers, ALIASES_TOTAL)
    col_bairro = encontrar_coluna(headers, ALIASES_BAIRRO)
    col_atividade = encontrar_coluna(headers, ALIASES_ATIVIDADE)
    col_fechados = encontrar_coluna(headers, ALIASES_FECHADOS)
    col_resgatados = encontrar_coluna(headers, ALIASES_RESGATADOS)
    col_recusados = encontrar_coluna(headers, ALIASES_RECUSADOS)
    col_pendencia = encontrar_coluna(headers, ALIASES_PENDENCIA)
    col_obs = encontrar_coluna(headers, ALIASES_OBS)

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

    todas_colunas = [
        col_data,
        col_total,
        col_bairro,
        col_atividade,
        col_fechados,
        col_resgatados,
        col_recusados,
        col_pendencia,
        col_obs,
    ]
    idx = (
        {c: headers.index(c) for c in todas_colunas if c}
        if by_index
        else {c: c for c in todas_colunas if c}
    )

    def val(row, col):
        return None if col is None else getter(row, idx[col])

    resultado = []
    for i, row in enumerate(dados_iter, start=2):
        if all(valor_vazio(val(row, c)) for c in todas_colunas):
            continue
        try:
            d = parse_data_planilha(val(row, col_data), ImportacaoErro)
            total = _parse_int(val(row, col_total), "Total T")
            fechados = _parse_int(val(row, col_fechados), "Fechados")
            resgatados = _parse_int(val(row, col_resgatados), "Resgates")
            recusados = _parse_int(val(row, col_recusados), "Recusas")
        except ImportacaoErro as ex:
            raise ImportacaoErro(f"Linha {i}: {ex}") from ex

        bairro = _parse_texto(val(row, col_bairro))
        atividade = atividade_service.normalizar(
            _parse_texto(val(row, col_atividade))
        )
        pendencia = _parse_texto(val(row, col_pendencia))
        obs = _parse_texto(val(row, col_obs))

        if pendencia and obs:
            observacao = f"{pendencia} — {obs}"
        elif pendencia:
            observacao = pendencia
        else:
            observacao = obs

        resultado.append(
            {
                "data": d,
                "quantidade": total,
                "bairro": bairro,
                "atividade": atividade,
                "fechados": fechados,
                "resgatados": resgatados,
                "recusados": recusados,
                "observacao": observacao,
            }
        )
    return resultado


def ler_planilha(caminho: str | Path) -> list[dict]:
    """Lê o arquivo e devolve lista de dicts com os dados de produção."""
    return ler_tabela_arquivo(caminho, _extrair_linhas, ImportacaoErro)


def importar_linhas(linhas: list[dict]) -> dict:
    """Insere/atualiza as produções em lote usando uma única transação."""
    todos_trs = tr_service.listar_todos_trs()

    inseridos = 0
    atualizados = 0
    ignorados: list[tuple[str, str]] = []
    bairros_criados: set[str] = set()

    with db_session(commit=True) as conn:
        cur = conn.cursor()
        agora = datetime.now().isoformat()

        bairros_cache: dict[str, int] = {
            r["nome"].lower(): r["id"]
            for r in cur.execute("SELECT id, nome FROM bairro").fetchall()
        }

        for linha in linhas:
            d: date = linha["data"]
            qtd: int = linha["quantidade"]
            obs: str | None = linha["observacao"]
            bairro_nome: str | None = linha.get("bairro")
            atividade: str | None = linha.get("atividade")
            fechados: int = linha.get("fechados", 0) or 0
            resgatados: int = linha.get("resgatados", 0) or 0
            recusados: int = linha.get("recusados", 0) or 0

            tr = next(
                (t for t in todos_trs if t.data_inicio <= d <= t.data_fim),
                None,
            )
            if tr is None:
                ignorados.append((d.isoformat(), "fora de qualquer TR"))
                continue

            bairro_id = None
            if bairro_nome:
                nome_limpo = bairro_nome.strip()
                chave_b = nome_limpo.lower()
                if chave_b in bairros_cache:
                    bairro_id = bairros_cache[chave_b]
                else:
                    cur.execute(
                        "INSERT INTO bairro (nome, ativo, criado_em) VALUES (?, 1, ?)",
                        (nome_limpo, agora),
                    )
                    bairro_id = int(cur.lastrowid)
                    bairros_cache[chave_b] = bairro_id
                    bairros_criados.add(nome_limpo)

            existente = cur.execute(
                "SELECT id FROM producao WHERE data=?", (d.isoformat(),)
            ).fetchone()

            if existente:
                cur.execute(
                    "UPDATE producao SET quantidade=?, tr_id=?, bairro_id=?, "
                    "atividade=?, fechados=?, resgatados=?, recusados=?, "
                    "observacao=?, atualizado_em=? WHERE id=?",
                    (
                        qtd,
                        tr.id,
                        bairro_id,
                        atividade,
                        fechados,
                        resgatados,
                        recusados,
                        obs,
                        agora,
                        existente["id"],
                    ),
                )
                atualizados += 1
            else:
                cur.execute(
                    "INSERT INTO producao (data, tr_id, bairro_id, atividade, "
                    "quantidade, fechados, resgatados, recusados, "
                    "observacao, criado_em, atualizado_em) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        d.isoformat(),
                        tr.id,
                        bairro_id,
                        atividade,
                        qtd,
                        fechados,
                        resgatados,
                        recusados,
                        obs,
                        agora,
                        agora,
                    ),
                )
                inseridos += 1

    return {
        "inseridos": inseridos,
        "atualizados": atualizados,
        "ignorados": ignorados,
        "total": len(linhas),
        "bairros_criados": sorted(bairros_criados),
    }
