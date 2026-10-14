import os
import sqlite3
from pathlib import Path
from datetime import datetime

import sys

def _default_db_dir() -> Path:
    # No mobile, o Flet expõe FLET_APP_STORAGE_DATA
    if sys.platform in ("android", "ios") or "ANDROID_ARGUMENT" in os.environ:
        env = os.getenv("FLET_APP_STORAGE_DATA")
        if env:
            return Path(env)
    # Em desktop, usa ./data
    return Path(__file__).resolve().parent.parent / "data"

DB_PATH = _default_db_dir() / "controle_ace.db"

def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db() -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS tr (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ano INTEGER NOT NULL,
        numero INTEGER NOT NULL,
        data_inicio TEXT NOT NULL,
        data_fim TEXT NOT NULL,
        meta_min INTEGER NOT NULL DEFAULT 800,
        meta_max INTEGER NOT NULL DEFAULT 1000,
        producao_inicial INTEGER NOT NULL DEFAULT 0,
        UNIQUE(ano, numero)
    );

    CREATE TABLE IF NOT EXISTS banco_horas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data TEXT NOT NULL,
        horas REAL NOT NULL,
        tipo TEXT NOT NULL,
        descricao TEXT,
        criado_em TEXT NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_banco_horas_data ON banco_horas(data);

    CREATE TABLE IF NOT EXISTS bairro (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL UNIQUE,
        ativo INTEGER NOT NULL DEFAULT 1,
        criado_em TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS producao (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data TEXT NOT NULL,
        tr_id INTEGER NOT NULL,
        bairro_id INTEGER,
        atividade TEXT,
        quantidade INTEGER NOT NULL DEFAULT 0,
        fechados INTEGER NOT NULL DEFAULT 0,
        resgatados INTEGER NOT NULL DEFAULT 0,
        recusados INTEGER NOT NULL DEFAULT 0,
        pendencia TEXT,
        motivo_id INTEGER,
        observacao TEXT,
        criado_em TEXT NOT NULL,
        atualizado_em TEXT NOT NULL,
        FOREIGN KEY (tr_id) REFERENCES tr(id),
        FOREIGN KEY (bairro_id) REFERENCES bairro(id),
        FOREIGN KEY (motivo_id) REFERENCES motivo(id)
    );

    CREATE TABLE IF NOT EXISTS evento (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data TEXT NOT NULL,
        tipo TEXT NOT NULL,
        fracao REAL NOT NULL,
        observacao TEXT,
        criado_em TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS motivo (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL UNIQUE,
        ativo INTEGER NOT NULL DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS recuperacao (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tr_id INTEGER NOT NULL,
        quarteirao TEXT,
        lado TEXT,
        rua TEXT NOT NULL,
        numero TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'fechado',
        observacao TEXT,
        criado_em TEXT NOT NULL,
        atualizado_em TEXT NOT NULL,
        FOREIGN KEY (tr_id) REFERENCES tr(id)
    );

    CREATE TABLE IF NOT EXISTS config (
        chave TEXT PRIMARY KEY,
        valor TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_producao_data ON producao(data);
    CREATE INDEX IF NOT EXISTS idx_evento_data ON evento(data);
    CREATE INDEX IF NOT EXISTS idx_recuperacao_tr ON recuperacao(tr_id);
    CREATE INDEX IF NOT EXISTS idx_recuperacao_status ON recuperacao(tr_id, status);
    CREATE INDEX IF NOT EXISTS idx_bairro_ativo ON bairro(ativo);
    """)

    # Motivos padrão
    cur.executemany(
        "INSERT OR IGNORE INTO motivo (nome) VALUES (?)",
        [("Reunião",), ("Chuva",), ("Falta de transporte",),
         ("Capacitação",), ("Problema no imóvel",), ("Outro",)],
    )
    conn.commit()

    # ---------- Migrações incrementais ----------
    # Garante que a tabela producao tenha todas as colunas (para quem já tinha banco)
    cur.execute("PRAGMA table_info(producao)")
    colunas_prod = {r[1] for r in cur.fetchall()}
    novas_colunas = {
        "bairro_id": "INTEGER",
        "atividade": "TEXT",
        "fechados": "INTEGER NOT NULL DEFAULT 0",
        "resgatados": "INTEGER NOT NULL DEFAULT 0",
        "recusados": "INTEGER NOT NULL DEFAULT 0",
        "pendencia": "TEXT",
    }
    for coluna, tipo in novas_colunas.items():
        if coluna not in colunas_prod:
            cur.execute(f"ALTER TABLE producao ADD COLUMN {coluna} {tipo}")

    # ---------- Bairros padrão (pré-cadastro) ----------
    bairros_padrao = [
        "Cachoeira do Vale",
        "Petrópolis",
        "Timirim",
        "Vila dos Técnicos",
        "Bairro dos Vieiras",
        "Recanto Verde",
        "Santa Rita",
        "Novo Horizonte",
        "Eldorado",
        "Serenata",
        "Garapa",
        "Santa Maria",
        "Quitandinha",
        "Olaria",
        "Cruzeirinho",
        "Ana Moura",
        "Nossa Senhora das Graças",
    ]
    agora = datetime.now().isoformat()
    for nome in bairros_padrao:
        cur.execute(
            "INSERT OR IGNORE INTO bairro (nome, ativo, criado_em) VALUES (?, 1, ?)",
            (nome, agora),
        )
        conn.commit()

    conn.close()