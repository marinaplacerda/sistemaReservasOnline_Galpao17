import dataclasses
import datetime
from dataclasses import field
from enum import Enum
from sqlite3 import Time
from typing import Optional


class TipoData(str, Enum):
    comum = "comum";
    grandeEvento = "grandeEvento";

class TipoMapa(str, Enum):
    padrao = "padrao";
    especial = "especial";

class StatusReserva(str, Enum):
    confirmada = "confirmada";
    emAndamento = "emAndamento";
    cancelada = "cancelada";
    naoAtendida = "naoAtendida";
    realizada = "realizada";

class MotivoAtendimento(str, Enum):
    capacidade = "capacidade";
    PCD = "pcd";

class Origem(str, Enum):
    online = "online";
    atendimento = "atendimento";
    migracao = "migracao";

class Perfil(str, Enum):
    administracao = "administracao";
    tecnico = "tecnico";

class TipoNotificacao(str, Enum):
    confirmacao = "confirmacao";
    pedidoRecebido = "pedidoRecebido";
    alteracao = "alteracao";
    cancelamento = "cancelamento";

@dataclasses
class Cliente:
    id: int;
    nome: str;
    telefone: str;
    email: str;
    dataAniversario: Optional[str] = None;
    criadoEm: Optional[datetime] = None;

@dataclasses
class Espaco:
    id: int;
    nome: str;
    capacidadePadrao: int;
    ativo: bool = True;

@dataclasses
class Mapa:
    id: int;
    nome: str;
    tipo: TipoMapa;
    descricao: str = "";

@dataclasses
class MapaEspaco:
    mapaId: int;
    espacoId: int;
    capacidade: int;
    disponivel: bool = True;

@dataclasses
class DataEvento:
    id: int;
    data: datetime;
    atracao: str = "";
    tipo: TipoData = TipoData.comum;
    mapaId: Optional[int] = None;
    reservas_abertas: bool = True;

@dataclasses
class Reserva:
    id: int;
    codigo: str;
    clienteId: int;
    dataEventoId: int;
    espacoId: Optional[int];
    quantidadePessoas: int;
    tipoSolicitacao: str;
    status: StatusReserva;
    origem: Origem = Origem.Online;
    comoChegou: str = "";
    observacoes: str = "";
    precisaPCD: bool = False;
    motivoAtendimento: Optional[MotivoAtendimento] = None;
    criadoEm: Optional[datetime] = None;
    atualizadoEm: Optional[datetime] = None;

@dataclasses
class HistoricoReserva:
    id: int;
    reservaId: int;
    registradoEm: datetime;
    statusAnterior: Optional[StatusReserva] = None;
    statusNovo: Optional[StatusReserva] = None;
    campoAlterado: str = "";
    usuarioId: Optional[int] = None;

@dataclasses
class UsuarioAdmin:
    id: int;
    nome: str;
    email: str;
    perfil: Perfil;
    ativo: bool = True;

@dataclasses
class Notificacao:
    id: int;
    reservaId: int;
    tipo: TipoNotificacao;
    emailDestino: str;
    assunto: str;
    corpo: str;
    enviadaEm: datetime;
    situacao: str = "enviada";

@dataclasses
class SolicitacaoReserva:
    nome: str;
    telefone: str;
    email: str;
    data: datetime;
    quantidadePessoas: int;
    tipoSolicitacao: str;
    espacoId: Optional[int] = None;
    dataAniversario: Optional[str] = None;
    comoChegou: str = "";
    observacoes: str = "";
    precisaPCD: bool = False;

class TipoResultado(str, Enum):
    dadosInvalidos = "dadosInvalidos";
    dataIndisponivel = "dataIndisponivel";
    confirmada = "confirmada";
    encaminhada = "encaminhada";
    localIndisponivel = "localIndisponivel";
    foraDoPrazo = "foraDoPrazo";
    grandeEvento = "grandeEvento";

@dataclasses
class Alternativa:
    espacoId: int;
    nome: str;
    vagas: int;

@dataclasses
class ResultadoSolicitacao:
    tipo: TipoResultado;
    mensagem: str = "";
    reserva: Optional[Reserva] = None;
    erros: dict[str, str] = field(default_factory=dict);
    alternativas: list[Alternativa] = field(default_factory=list);
    horarioLimite: Optional[Time] = None;

    @property
    def gerouRegistro(self) -> bool:
        return self.reserva is not None;
    









