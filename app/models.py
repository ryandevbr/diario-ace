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
    motivo_id: int | None
    observacao: str | None

@dataclass
class Evento:
    id: int
    data: date
    tipo: str          # feriado, ferias, atestado, reuniao, capacitacao, outro
    fracao: float      # 1.0 = dia todo, 0.5 = meio período, etc.
    observacao: str | None