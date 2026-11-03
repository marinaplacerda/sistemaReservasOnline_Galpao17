import datetime
import zoneinfo
from datetime import timedelta
from operator import and_
from time import timezone
from types import MappingProxyType
from typing import Mapping, Optional

try:
    Fuso = zoneinfo("America/Sao_Paulo");

except Exception:
    Fuso = timezone(timedelta(hours=-3), "BRT");

def emBrasilia(agora: datetime) -> datetime:
    if agora.tzinfo is None:
        return agora.replace(tzinfo=Fuso);
    return agora.astimezone(Fuso);

HorarioLimite = MappingProxyType({
    1: datetime.time(15, 0),
    2: datetime.time(15, 0),
    3: datetime.time(15, 0),
    4: datetime.time(12, 0),
    5: datetime.time(12, 0),
});

def horarioLimite(dia: datetime) -> Optional[datetime.time]:
    return horarioLimite.get(dia.weekday());

def dentroDoPrazo(dia: date, agora: datetime) -> bool:
    agora = emBrasilia(agora);
    hoje = agora.date();
    if dia > hoje:
        return True;
    if dia < hoje:
        return False;
    limite = horarioLimite(dia);
    return limite is not None and agora.time() <= limite;

