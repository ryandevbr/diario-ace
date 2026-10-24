from datetime import date, time, timedelta
import json
from pathlib import Path
import zipfile
import pytest

import app.database as database
from app.services import (
    atividade_service,
    backup_service,
    bairro_service,
    banco_horas_service,
    config_service,
    evento_service,
    import_service,
    pdf_service,
    producao_service,
    recuperacao_service,
    relatorio_service,
    tr_service,
)


@pytest.fixture()
def temp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db_file = tmp_path / "test_controle_ace.db"
    monkeypatch.setattr(database, "DB_PATH", db_file)
    monkeypatch.setattr(database, "default_db_dir", lambda: tmp_path)
    monkeypatch.setattr(bairro_service, "default_db_dir", lambda: tmp_path)
    monkeypatch.setattr(backup_service, "default_db_dir", lambda: tmp_path)
    database.init_db()
    tr_service.seed_trs_do_ano(2026)
    return db_file


def test_backup_zip_preserva_tabelas_colunas_e_croquis(
    temp_db: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pasta_pub_croquis = tmp_path / "public_backup" / "croquis"
    pasta_pub_croquis.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        bairro_service,
        "obter_diretorio_croquis_publico",
        lambda: pasta_pub_croquis,
    )

    trs = tr_service.listar_trs(2026)
    tr1 = trs[0]
    tr_service.atualizar_tr(
        tr1.id, tr1.data_inicio, tr1.data_fim, 850, 1050, producao_inicial=120
    )

    bairro_id = bairro_service.criar("Bairro Teste Backup")
    bairro_service.alternar_ativo(bairro_id, False)

    # Anexa um PDF de croqui ao bairro
    pdf_origem = tmp_path / "meu_mapa.pdf"
    pdf_origem.write_bytes(b"%PDF-1.4 fake croqui content")
    caminho_croqui = bairro_service.salvar_croqui(bairro_id, str(pdf_origem))
    assert Path(caminho_croqui).exists()
    assert (pasta_pub_croquis / f"croqui_{bairro_id}.pdf").exists()

    producao_service.registrar_producao(
        date(2026, 1, 15),
        tr1.id,
        quantidade=25,
        bairro_id=bairro_id,
        atividade="Tratamento",
        fechados=3,
        resgatados=1,
        recusados=2,
        pendencia="Pendência X",
        obs="Casa 1 & 2 <teste>",
    )
    evento_service.adicionar_evento(
        date(2026, 1, 16), "reuniao", 0.5, "Reunião mensal"
    )
    banco_horas_service.adicionar(
        date(2026, 1, 17), 4.5, "trabalhada", "Mutirão sábado"
    )
    recuperacao_service.adicionar(
        tr1.id, "10", "Lado 2", "Rua das Flores", "100A", "Portão fechado"
    )
    config_service.definir("tema", "dark")

    arquivo_backup = tmp_path / "backup_completo.zip"
    backup_service.exportar_para_arquivo(arquivo_backup)
    assert zipfile.is_zipfile(arquivo_backup)

    with zipfile.ZipFile(arquivo_backup, "r") as zf:
        nomes_zip = set(zf.namelist())
        assert "dados.json" in nomes_zip
        assert f"croquis/croqui_{bairro_id}.pdf" in nomes_zip

    # Remove o croqui antes de restaurar para garantir que a restauração o recria
    bairro_service.remover_croqui(bairro_id)
    assert not Path(caminho_croqui).exists()
    assert not (pasta_pub_croquis / f"croqui_{bairro_id}.pdf").exists()

    resumo = backup_service.importar_de_arquivo(arquivo_backup, substituir=True)
    assert resumo["tr"] == 6
    assert resumo["producao"] == 1
    assert resumo["recuperacao"] == 1
    assert resumo["banco_horas"] == 1
    assert resumo["croquis"] == 1

    # Croqui foi extraído fisicamente e vinculado no banco
    assert Path(caminho_croqui).exists()
    assert Path(caminho_croqui).read_bytes() == b"%PDF-1.4 fake croqui content"
    b_info = bairro_service.buscar_por_id(bairro_id)
    assert b_info is not None
    assert b_info["croqui_path"] == str(caminho_croqui)

    tr_restaurado = tr_service.listar_trs(2026)[0]
    assert tr_restaurado.producao_inicial == 120
    assert tr_restaurado.meta_min == 850

    prod = producao_service.producao_completa_do_dia(date(2026, 1, 15))
    assert prod is not None
    assert prod["quantidade"] == 25
    assert prod["bairro_id"] == bairro_id
    assert prod["atividade"] == "Tratamento"
    assert prod["fechados"] == 3
    assert prod["resgatados"] == 1
    assert prod["recusados"] == 2
    assert prod["pendencia"] == "Pendência X"
    assert prod["observacao"] == "Casa 1 & 2 <teste>"

    assert banco_horas_service.saldo_atual() == 4.5
    assert len(recuperacao_service.listar_por_tr(tr1.id)) == 1
    assert config_service.obter("tema") == "dark"


def test_backup_automatico_zip_e_pasta_publica(
    temp_db: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pasta_pub = tmp_path / "Documents" / "BackupACE"
    pasta_pub.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(backup_service, "_pasta_backup_publica", lambda: pasta_pub)

    b_id = bairro_service.criar("Bairro Auto")
    pdf_origem = tmp_path / "auto.pdf"
    pdf_origem.write_bytes(b"%PDF-1.4 auto")
    bairro_service.salvar_croqui(b_id, str(pdf_origem))

    caminho_auto = backup_service.fazer_backup_automatico()
    assert caminho_auto is not None
    assert caminho_auto.suffix == ".zip"
    assert zipfile.is_zipfile(caminho_auto)
    assert (pasta_pub / caminho_auto.name).exists()
    assert (pasta_pub / "croquis" / f"croqui_{b_id}.pdf").exists()


def test_backup_compatibilidade_v1_antigo(
    temp_db: Path, tmp_path: Path
) -> None:
    """Garante que backups .json antigos importam sem erro."""
    dados_antigos = {
        "versao": 1,
        "exportado_em": "2026-01-10T10:00:00",
        "tr": [
            {
                "id": 1,
                "ano": 2026,
                "numero": 1,
                "data_inicio": "2026-01-01",
                "data_fim": "2026-02-28",
                "meta_min": 800,
                "meta_max": 1000,
            }
        ],
        "producao": [
            {
                "id": 1,
                "data": "2026-01-05",
                "tr_id": 1,
                "quantidade": 30,
                "motivo_id": None,
                "observacao": "Dia normal",
                "criado_em": "2026-01-05T12:00:00",
                "atualizado_em": "2026-01-05T12:00:00",
            }
        ],
        "evento": [],
        "motivo": [{"id": 1, "nome": "Chuva", "ativo": 1}],
    }
    arq = tmp_path / "backup_legado.json"
    arq.write_text(json.dumps(dados_antigos), encoding="utf-8")

    resumo = backup_service.importar_de_arquivo(arq, substituir=True)
    assert resumo["tr"] == 1
    assert producao_service.producao_do_dia(date(2026, 1, 5)) == 30
    assert len(bairro_service.listar_ativos()) >= 17


def test_banco_horas_parse_e_validacao(temp_db: Path) -> None:
    assert banco_horas_service.parse_horas("08:30") == 8.5
    assert banco_horas_service.parse_horas("27:00:00") == 27.0
    assert banco_horas_service.parse_horas(time(4, 15)) == 4.25
    assert banco_horas_service.parse_horas(timedelta(hours=12, minutes=30)) == 12.5

    banco_horas_service.adicionar(date(2026, 2, 1), 8.0, "trabalhada")
    movs = banco_horas_service.listar_todos()
    assert len(movs) == 1

    with pytest.raises(banco_horas_service.BancoHorasErro):
        banco_horas_service.atualizar(
            movs[0]["id"], date(2026, 2, 1), 0, "trabalhada"
        )
    with pytest.raises(banco_horas_service.BancoHorasErro):
        banco_horas_service.atualizar(
            movs[0]["id"], date(2026, 2, 1), -2.0, "trabalhada"
        )


def test_importacao_csv_producao(temp_db: Path, tmp_path: Path) -> None:
    csv_path = tmp_path / "planilha.csv"
    csv_path.write_text(
        "Data;Total T;Bairro;Atividade;Fechados;Resgates;Recusas;Observações\n"
        "10/03/2026;28;Bairro Novo CSV;pe;4;2;1;Teste CSV\n",
        encoding="utf-8",
    )
    linhas = import_service.ler_planilha(csv_path)
    assert len(linhas) == 1
    assert linhas[0]["atividade"] == "P.E. (Ponto Estratégico)"

    res = import_service.importar_linhas(linhas)
    assert res["inseridos"] == 1
    assert "Bairro Novo CSV" in res["bairros_criados"]

    prod = producao_service.producao_completa_do_dia(date(2026, 3, 10))
    assert prod is not None
    assert prod["quantidade"] == 28
    assert prod["fechados"] == 4


def test_pdf_escapa_caracteres_especiais_e_relatorio_inclui_bairros_inativos(
    temp_db: Path, tmp_path: Path
) -> None:
    tr1 = tr_service.listar_trs(2026)[0]
    b_id = bairro_service.criar("Bairro <Especial> & Cia")
    bairro_service.alternar_ativo(b_id, False)

    producao_service.registrar_producao(
        date(2026, 1, 20),
        tr1.id,
        quantidade=22,
        bairro_id=b_id,
        atividade=atividade_service.normalizar("Tratamento"),
        obs="Obs com <tags> & comerciais",
    )
    recuperacao_service.adicionar(
        tr1.id, "1", "Lado 1", "Rua A & B <C>", "10", "Obs <1> & 2"
    )

    dados_ano = relatorio_service.dados_do_ano(2026)
    prods_tr1 = dados_ano["trs"][0]["producoes"]
    assert prods_tr1[0]["bairro_nome"] == "Bairro <Especial> & Cia"

    pdf_hist = tmp_path / "hist.pdf"
    pdf_rec = tmp_path / "rec.pdf"
    pdf_anual = tmp_path / "anual.pdf"

    bairros_map = {b["id"]: b for b in bairro_service.listar_todos()}
    pdf_service.exportar_historico_pdf(
        pdf_hist,
        tr1,
        producao_service.listar_producoes_do_tr(tr1.id),
        [],
        bairros_map,
    )
    pdf_service.exportar_recuperacao_pdf(
        pdf_rec, tr1, recuperacao_service.listar_por_tr(tr1.id)
    )
    pdf_service.exportar_relatorio_anual_pdf(pdf_anual, dados_ano)

    assert pdf_hist.exists() and pdf_hist.stat().st_size > 0
    assert pdf_rec.exists() and pdf_rec.stat().st_size > 0
    assert pdf_anual.exists() and pdf_anual.stat().st_size > 0
