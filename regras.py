from __future__ import annotations;

import re;
from datetime import date, datetime, time, timedelta, timezone;
from types import MappingProxyType;
from typing import Optional;
from zoneinfo import ZoneInfo;

from .erros import PermissaoNegada;
from .modelos import Perfil, SolicitacaoReserva, UsuarioAdmin;

try:
    fuso = ZoneInfo("America/Sao_Paulo");
except Exception:
    fuso = timezone(timedelta(hours=-3), "BRT");

def emBrasilia(agora: datetime) -> datetime:
    if agora.tzinfo is None:
        return agora.replace(tzinfo=fuso);
    return agora.astimezone(fuso);



horarioLimite = MappingProxyType({
    1: time(15, 0),  # terça
    2: time(15, 0),  # quarta
    3: time(15, 0),  # quinta
    4: time(12, 0),  # sexta
    5: time(12, 0),  # sábado
});


def horarioLimite(dia: date) -> Optional[time]:
    return horarioLimite.get(dia.weekday());


def dentroDoPrazo(dia: date, agora: datetime) -> bool:
    agora = emBrasilia(agora);
    hoje = agora.date();
    if dia > hoje:
        return True;
    if dia < hoje:
        return False;
    limite = horarioLimite(dia);
    return limite is not None and agora.time() < limite;

def soDigitos(texto: Optional[str]) -> str:
    return re.sub(r"\D", "", texto or "");

def normalizarTelefone(telefone: Optional[str]) -> str:
    "Deixa só os dígitos, sem o +55. Ex.: '+55 (61) 98765-4321' → '61987654321'.";
    d = soDigitos(telefone);
    if d.startswith("55") and len(d) in (12, 13):
        d = d[2:];
    return d;

def telefoneValido(telefone: Optional[str]) -> bool:
    d = normalizarTelefone(telefone);
    if len(d) not in (10, 11) or "0" in d[:2]:
        return False;
    numero = d[2:];
    if len(d) == 11:
        return numero[0] == "9";
    return numero[0] in "2345";

_RE_Email = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$");
_RE_Aniversario = re.compile(r"^(\d{2})/(\d{2})$");
_RE_Letra = re.compile(r"[^\W\d_]");

tamanhoMaximo = MappingProxyType [str, int] ({
   "nome": 120,
    "email": 254,
    "tipoSolicitacao": 100,
    "comoChegou": 100,
    "observacoes": 500,
});

quantidadeMaximaPessoas = 500;

def aniversarioValido(texto: str) -> bool:
    m = _RE_Aniversario.match(texto.strip());
    if not m:
        return False;
    dia, mes = int(m.group(1)), int(m.group(2));
    try:
        date(2024, mes, dia);
    except ValueError:
        return False;
    return True;

def _texto(valor) -> str:
    return valor.strip() if isinstance(valor, str) else "";

def _inteiro(valor) -> bool:
    return isinstance(valor, int) and not isinstance(valor, bool);

def validarSolicitacao (s:SolicitacaoReserva, exigeLocal: bool = True) -> dict[str, str]:
    erros: dict[str, str] = {};

    nome = _texto(s.nome);
    if len(nome) < 3 or not _RE_Letra.search(nome):
        erros["nome"] = "Informe seu nome completo.";

    if not telefoneValido(s.telefone):
        erros["telefone"] = "Inclua o DDD — ex.: (61) 98765-4321.";

    if not _RE_Email.match(_texto(s.email)):
        erros["email"] = "Confira o e-mail — ex.: nome@email.com.";

    if s.dataAniversario and not aniversarioValido(str(s.data_aniversario)):
        erros["dataAniversario"] = "Use o formato dd/mm com uma data que exista — ex.: 14/03.";

    if not _texto(s.tipoSolicitacao):
        erros["tipoSolicitacao"] = "Escolha o tipo de solicitação.";

    if not isinstance(s.data, date) or isinstance(s.data, datetime):
        erros["data"] = "Escolha a data no calendário.";

    if not _inteiro(s.quantidadePessoas) or s.quantidadePessoas < 1:
        erros["quantidadePessoas"] = "Informe quantas pessoas vêm (mínimo 1).";

    elif s.quantidadePessoas > quantidadeMaximaPessoas:
        erros["quantidadePessoas"] = f"Confira a quantidade: o máximo pelo formulário é {quantidadeMaximaPessoas} pessoas.";

    if exigeLocal and not _inteiro(s.espacoId):
        erros["espacoId"] = "Escolha um local.";

    for campo, limite in tamanhoMaximo.items():
        valor = getattr(s, campo, None);
        if isinstance(valor, str) and len(valor.strip()) > limite and campo not in erros:
            erros[campo] = f"Use no máximo {limite} caracteres.";
    return erros;

def exigirAcessoPainel(usuario: Optional[UsuarioAdmin]) -> None:
    if usuario is None:
        raise PermissaoNegada ("Entre no painel para continuar.");
    if not usuario.ativo:
        raise PermissaoNegada(f"O usuário {usuario.nome} está inativo.");

def exigirGestao(usuario: Optional[UsuarioAdmin]) -> None:
    exigirAcessoPainel(usuario);
    if usuario.perfil is not Perfil.TecnicoGerencia:
        raise PermissaoNegada(
            "O perfil Administração só visualiza as reservas."
        );