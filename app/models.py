from dataclasses import dataclass
from datetime import date


@dataclass
class TR:
    id: int
    ano: int
    numero: int
    data_inicio: date
    data_fim: date
    meta_min: int
    meta_max: int
    producao_inicial: int = 0


@dataclass
class Producao:
    id: int
    data: date
    tr_id: int
    quantidade: int
    motivo_id: int | None = None
    observacao: str | None = None
    bairro_id: int | None = None
    atividade: str | None = None
    fechados: int = 0
    resgatados: int = 0
    recusados: int = 0
    pendencia: str | None = None


@dataclass
class Evento:
    id: int
    data: date
    tipo: str
    fracao: float
    observacao: str | None = None
