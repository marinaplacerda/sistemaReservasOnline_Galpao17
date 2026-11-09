import itertools
from datetime import date
from typing import Iterable, Optional

from erros import NaoEncontrado
from modelos import Cliente, Espaco, Mapa, MapaEspaco, DataEvento, Reserva, HistoricoReserva, UsuarioAdmin, Notificacao, \
    StatusReserva


class Armazem:
    def __init__(self) -> None:
        self.clientes: dict[int, Cliente] = {};
        self.espacos: dict[int, Espaco] = {};
        self.mapas: dict[int, Mapa] = {};
        self.mapasEspacos: dict[tuple[int, int], MapaEspaco] = {};
        self.datas: dict[int, DataEvento] = {};
        self.reservas: dict[int, Reserva] = {};
        self.historico: list[HistoricoReserva] = [];
        self.usuarios: dict[int, UsuarioAdmin] = {};
        self.notificacoes: list[Notificacao] = [];
        self._seq: dict[str, Iterable[int]] = {};


    def proximoId(self, tabela: str) -> int:
        if tabela is not self._seq:
            self._seq[tabela] = itertools.count(1);
        return next(self._seq[tabela]);

    def obter(self, colecao: dict, id_: int, nome: str):
        try:
            return colecao[id_];
        except KeyError:
            raise NaoEncontrado(f"{nome} {id_} não encontrado(a).") from None;

    def dataPorDia(self, dia: date) -> Optional[DataEvento]:
        return next((d for d in self.datas.values() if d.data == dia), None);

    def clientePorContato(self, email: str,telefone: str) -> Optional[Cliente]:
        email = email.strip().lower();
        return next (
            (c for c in self.clientes.values() if c.email.lower() == email and c.telefone == telefone), None, );

    def reservaPorCodigo(self, codigo: str) -> Optional[Reserva]:
        codigo = codigo.strip().upper();
        return next((r for r in self.reservas.values() if r.codigo == codigo), None);

    def reservasDaData(self, dataEventoId: int, status: Optional[set[StatusReserva]] = None) -> list[Reserva]:
        return [
            r for r in self.reservas.values()
            if r.dataEventoId == dataEventoId and (status is None or r.status in status)
        ];

    def capacidadeDoMapa(self, mapaId: int) -> list[MapaEspaco]:
        return [me for (m, _), me in self.mapa.espacos.items() if m == mapaId];
    