# Diário ACE

Aplicativo mobile para agentes de combate a endemias registrarem produção
diária, controlarem metas por ciclo (TR), organizarem listas de recuperação
de imóveis fechados e gerarem relatórios em PDF.

Desenvolvido em Python com [Flet](https://flet.dev), roda offline no Android
e foi pensado para o uso real de campo: rápido, simples e sem depender de
internet.

---

## Funcionalidades

- **Produção diária** — registro de imóveis trabalhados, fechados, resgatados
  e recusados por dia, com bairro e tipo de atividade.
- **Metas por TR** — 6 ciclos de 2 meses por ano, com meta mínima e máxima
  configuráveis. Cálculo automático da meta diária necessária, considerando
  fins de semana, feriados e eventos.
- **Calendário de eventos** — férias, atestado, reunião, capacitação, folga,
  chuva, deslocamento, compensação e outros. Cada evento ajusta o peso do dia
  no cálculo da meta.
- **Histórico** — consulta por ano e TR, edição e exclusão de lançamentos,
  visão diária ou semanal.
- **Lista de recuperação** — cadastro de imóveis fechados com quarteirão,
  lado, rua e número, controle de status (fechado, atendido, abandonado,
  recusado) e filtros por status e quarteirão.
- **Relatórios em PDF** — histórico detalhado do TR e relatório anual com
  consolidado por bairro, por atividade e por TR, em modo paisagem.
- **Importação de planilha** — leitura de arquivos `.xlsx` e `.csv` com o
  formato de produção usado pelos supervisores.
- **Banco de horas** — controle de horas extras trabalhadas e compensações,
  com saldo em horas e conversão em dias de folga.
- **Backup automático** — exportação diária em JSON, com pasta pública
  opcional para sincronização via Google Drive.
- **Tema claro, escuro ou sistema**, com preferência salva.

---

## Tecnologias

| Camada | Tecnologia |
|---|---|
| Interface | [Flet](https://flet.dev) 1.x (baseado em Flutter) |
| Banco de dados | SQLite |
| Geração de PDF | ReportLab |
| Leitura de planilhas | openpyxl |
| Empacotamento | `flet build apk` |

---

## Como rodar localmente

Requer **Python 3.11+**.

```bash
git clone https://github.com/ryandevbr/diario-ace.git
cd diario-ace
python -m venv .venv
.venv\Scripts\activate     # Windows
# source .venv/bin/activate  # Linux/macOS
pip install -r requirements.txt
cd app
flet run main.py
```

O banco de dados SQLite é criado automaticamente em `data/controle_ace.db`
na primeira execução.

---

## Como gerar o APK

Requer o **Flutter SDK**, **JDK 17+** e o **Android SDK** instalados.

```bash
cd app
flet build apk
```

O APK fica em `app/build/apk/app-release.apk`.

> Se você atualizar um APK por cima de outro, os dados do app são preservados
> desde que o `app_id` em `pyproject.toml` não mude.

---

## Estrutura do projeto

```
diario-ace/
├── app/
│   ├── main.py              # Ponto de entrada
│   ├── database.py          # Schema e migrações do SQLite
│   ├── models.py            # Dataclasses
│   ├── components/          # Widgets reutilizáveis
│   ├── services/            # Lógica de negócio
│   ├── utils/               # Helpers (datas, arquivos, compartilhamento)
│   ├── views/               # Telas (Hoje, Meu TR, Calendário, ...)
│   └── assets/              # Ícone e imagens
├── tests/                   # Testes
├── conftest.py              # Configuração do pytest
├── requirements.txt
└── README.md
```

---

## Banco de dados

O banco fica em `data/controle_ace.db` (desktop) ou no diretório privado do
app (Android). Como o SQLite no Android é inacessível por gerenciadores de
arquivos comuns, use a função **Exportar backup** em Configurações para
gerar um JSON com todos os dados e guardar em local seguro.

Há também um **backup automático** a cada 24 horas, salvo em
`data/backups/` e, no Android, em `Documents/BackupACE/`.

---

## Licença

[MIT](LICENSE)