from __future__ import annotations;

import calendar;
import secrets;
import threading;
from dataclasses import dataclass;
from datetime import date, datetime;
from typing import Callable, Optional;

import regras;
from erros import ErroDeNegocio;
from modelos import (
    Alternativa, Cliente, DataEvento, Espaco, HistoricoReserva, Mapa, MapaEspaco, MotivoAtendimento,
    Origem, Reserva, ResultadoSolicitacao, SolicitacaoReserva, StatusReserva, TipoData, TipoMapa,
    TipoNotificacao, TipoResultado, UsuarioAdmin,
);
from notificacoes import avisoSpam, contatoAtendimento, CaixaDeSaidaEmMemoria;
from repositorio import Armazem;

fuso = regras.fuso;

ocupaLugar = {StatusReserva.confirmada};


def agoraBrasilia() -> datetime:
    return datetime.now(fuso);


@dataclass
class DiaCalendario:
    data: date;
    tipo: str;
    hoje: bool = False;
    hojeEncerrado: bool = False;
    atracao: str = "";
    horarioLimite: str = "";


@dataclass
class OcupacaoArea:
    espacoId: int;
    nome: str;
    usados: int;
    capacidade: int;

    @property
    def vagas(self) -> int:
        return max(self.capacidade - self.usados, 0);


class SistemaReservas:
    def __init__(self, armazem: Optional[Armazem] = None,
                 relogio: Callable[[], datetime] = agoraBrasilia,
                 caixaDeSaida: Optional[CaixaDeSaidaEmMemoria] = None) -> None:
        self.armazem = armazem or Armazem();
        self.relogio = relogio;
        self.caixa = caixaDeSaida or CaixaDeSaidaEmMemoria(self.armazem);
        self._trava = threading.RLock();

    def calendario(self, ano: int, mes: int) -> list[DiaCalendario]:
        agora = self.relogio();
        hoje = agora.date();
        dias = [];
        for n in range(1, calendar.monthrange(ano, mes)[1] + 1):
            dia = date(ano, mes, n);
            de = self.armazem.dataPorDia(dia);
            limite = regras.horarioLimite(dia);
            if dia < hoje:
                tipo = "passado";
            elif de is None or (de.tipo is TipoData.comum and (not de.reservas_abertas or limite is None)):
                tipo = "semProgramacao";
            elif de.tipo is TipoData.grandeEvento:
                tipo = "grandeEvento";
            elif self._mapaDaData(de).tipo is TipoMapa.especial:
                tipo = "mapaEspecial";
            else:
                tipo = "comum";
            dias.append(DiaCalendario(
                data = dia,
                tipo = tipo,
                hoje= dia == hoje,
                hojeEncerrado = dia == hoje and tipo in ("comum", "mapaEspecial") and not regras.dentroDoPrazo(dia, agora),
                atracao = de.atracao if de else "",
                horarioLimite=limite.strftime("%Hh") if limite and tipo in ("comum", "mapaEspecial") else "",
            ));
        return dias;

    def locaisDaData(self, dia: date) -> list[OcupacaoArea]:
        de = self._exigirData(dia);
        if de.tipo is TipoData.grandeEvento:
            return [];
        return self._ocupacao(de);

    def vagas(self, dia: date, espacoId: int) -> int:
        de = self._exigirData(dia);
        return next((o.vagas for o in self._ocupacao(de) if o.espacoId == espacoId), 0);

    def solicitarReserva(self, s: SolicitacaoReserva, usuario: Optional[UsuarioAdmin] = None) -> ResultadoSolicitacao:
        if usuario is not None:
            regras.exigirGestao(usuario);
        origem = Origem.atendimento if usuario else Origem.online;
        with self._trava:
            agora = self.relogio();

            if not isinstance(s.data, date) or isinstance(s.data, datetime):
                return ResultadoSolicitacao(TipoResultado.dadosInvalidos, "Revise 1 campo(s) para enviar.",
                                            erros={"data": "Escolha a data no calendário."});

            de = self.armazem.dataPorDia(s.data);

            # 1. A data existe e está aberta?
            if s.data < agora.date():
                return ResultadoSolicitacao(TipoResultado.dataIndisponivel,
                                            "Essa data já passou. Escolha outra data no calendário.");
            if de is None:
                return ResultadoSolicitacao(TipoResultado.dataIndisponivel,
                                            "Não há programação nesta data. Escolha outra data no calendário.");

            # 2. Grande evento: só pedido PCD
            if de.tipo is TipoData.grandeEvento and not s.precisaPCD:
                return ResultadoSolicitacao(
                    TipoResultado.grandeEvento,
                    "Esta data é um grande evento: não há reserva online de mesas nem assentos. "
                    "Se você precisa de atendimento PCD, envie o formulário marcando essa opção.");
            if de.tipo is TipoData.comum and (not de.reservas_abertas or regras.horarioLimite(de.data) is None):
                return ResultadoSolicitacao(TipoResultado.dataIndisponivel,
                                            "As reservas desta data ainda não estão abertas.");

            # 3. Dados do formulário
            exigeLocal = de.tipo is TipoData.comum;
            erros = regras.validarSolicitacao(s, exigeLocal = exigeLocal);
            if exigeLocal and s.espacoId is not None and "espacoId" not in erros:
                if self._mapaEspaco(de, s.espacoId) is None:
                    erros["espacoId"] = "Este local não existe no mapa desta data. Escolha outro.";
            if erros:
                return ResultadoSolicitacao(TipoResultado.dadosInvalidos, f"Revise {len(erros)} campo(s) para enviar.",erros = erros);

            # 4. Prazo do próprio dia (não vale para grande evento)
            if de.tipo is TipoData.comum and not regras.dentroDoPrazo(de.data, agora):
                limite = regras.horarioLimite(de.data);
                return ResultadoSolicitacao(
                    TipoResultado.foraDoPrazo,
                    f"As reservas para hoje encerraram às {limite:%H}h. Terça a quinta: até 15h; sexta e sábado: até 12h.",
                    horarioLimite = limite);

            # 5. PCD vai para o atendimento
            if s.precisaPCD:
                r = self._registrar(s, de, StatusReserva.emAndamento, origem, MotivoAtendimento.PCD, agora, usuario);
                return ResultadoSolicitacao(
                    TipoResultado.encaminhada,
                    "Recebemos seu pedido. Como você indicou atendimento PCD, nossa equipe vai combinar os detalhes com você. "
                    "Ainda não é uma reserva confirmada.", reserva=r);

            # 6. Local disponível e capacidade
            me = self._mapaEspaco(de, s.espacoId);
            espaco = self.armazem.espacos[s.espacoId];
            if not me.disponivel or not espaco.ativo:
                return self._localIndisponivel(de, espaco, s.quantidadePessoas,f"{espaco.nome} não está disponível nesta data.");
            if s.quantidadePessoas > me.capacidade:
                r = self._registrar(s, de, StatusReserva.emAndamento, origem, MotivoAtendimento.capacidade, agora,
                                    usuario);
                return ResultadoSolicitacao(TipoResultado.encaminhada,
                    f"Seu grupo de {s.quantidadePessoas} pessoas é maior que a capacidade de {espaco.nome} ({me.capacidade}). "
                    "O pedido foi para a nossa equipe, que vai falar com você. Ainda não é uma reserva confirmada.", reserva=r);
            livres = me.capacidade - self._usados(de, s.espacoId);
            if s.quantidadePessoas > livres:
                return self._localIndisponivel(de, espaco, s.quantidadePessoas,f"{espaco.nome} está lotado em {de.data:%d/%m}.");

            # 7. Tudo certo: confirmação automátic (RF-09, RN-03)
            r = self._registrar(s, de, StatusReserva.confirmada, origem, None, agora, usuario);
            return ResultadoSolicitacao(
                TipoResultado.confirmada,
                f"Reserva confirmada! Guarde o número {r.codigo}. A confirmação foi enviada para {s.email.strip()}. {avisoSpam}", reserva=r);

    # Pàinel Visualização - Perfis Técnico/Gerência e Administração
    def reservasDoDia(self, usuario: UsuarioAdmin, dia: date, status: Optional[StatusReserva] = None, busca: str = "") -> list[dict]:
        regras.exigirAcessoPainel(usuario);
        de = self.armazem.dataPorDia(dia);
        if de is None:
            return [];
        busca = busca.strip().lower();
        linhas = [];
        for r in sorted(self.armazem.reservasDaData(de.id), key=lambda r: r.id):
            c = self.armazem.clientes[r.clienteId];
            if status and r.status is not status:
                continue;
            if busca and busca not in f"{c.nome} {c.telefone} {r.codigo}".lower():
                continue;
            linhas.append({
                "id": r.id, "codigo": r.codigo, "cliente": c.nome, "telefone": c.telefone,
                "pessoas": r.quantidadePessoas, "local": self._nomeEspaco(r.espacoId),
                "origem": r.origem.value, "status": r.status.value, "pcd": r.precisaPCD,
            });
        return linhas;

    def filaAtendimento(self, usuario: UsuarioAdmin) -> list[dict]:
        regras.exigirAcessoPainel(usuario);
        fila = [r for r in self.armazem.reservas.values() if r.status is StatusReserva.emAndamento];
        return [{
            "id": r.id, "codigo": r.codigo, "cliente": self.armazem.clientes[r.clienteId].nome,
            "data": self.armazem.datas[r.dataEventoId].data, "pessoas": r.quantidadePessoas,
            "local": self._nomeEspaco(r.espacoId), "motivo": r.motivoAtendimento.value if r.motivoAtendimento else "",
        }
            for r in sorted(fila, key=lambda r: r.id)];

    def resumoDoDia(self, usuario: UsuarioAdmin, dia: date) -> dict:
        regras.exigirAcessoPainel(usuario);
        de = self._exigirData(dia);
        areas = [] if de.tipo is TipoData.grandeEvento else self._ocupacao(de);
        confirmadas = self.armazem.reservasDaData(de.id, ocupaLugar);
        capacidade = sum(a.capacidade for a in areas);
        pessoas = sum(r.quantidadePessoas for r in confirmadas);
        return {
            "data": de.data, "tipo": de.tipo.value,
            "reservasConfirmadas": len(confirmadas),
            "pessoasConfirmadas": pessoas,
            "capacidadeTotal": capacidade,
            "aguardandoAtendimento": len(self.armazem.reservasDaData(de.id, {StatusReserva.emAndamento})),
            "ocupacaoPercentual": round(100 * pessoas / capacidade) if capacidade else 0,
            "areas": areas,
        };

    def historico(self, usuario: UsuarioAdmin, reservaId: int) -> list[HistoricoReserva]:
        regras.exigirAcessoPainel(usuario);
        return [h for h in self.armazem.historico if h.reservaId == reservaId];


    # Painel ações do atendimento - Perfil Técnico/Gerência
    def confirmarPedido(self, usuario: UsuarioAdmin, reservaId: int, espacoId: Optional[int] = None,
                        quantidadePessoas: Optional[int] = None, usarMesasExtras: bool = False) -> Reserva:

        regras.exigirGestao(usuario);
        with self._trava:
            r = self._obterReserva(reservaId);
            if r.status is not StatusReserva.emAndamento:
                raise ErroDeNegocio(f"A reserva {r.codigo} não está na fila de atendimento ({r.status.value}).");
            de = self.armazem.datas[r.dataEventoId];
            novoEspaco = espacoId if espacoId is not None else r.espacoId;
            novaQuantidade = quantidadePessoas if quantidadePessoas is not None else r.quantidadePessoas;
            if de.tipo is TipoData.comum:
                if novoEspaco is None:
                    raise ErroDeNegocio("Escolha um local antes de confirmar.");
                self._checarVaga(de, novoEspaco, novaQuantidade, ignorar = r.id, permitirExtra = usarMesasExtras);
            mudou = self._diff(r, espacoId = novoEspaco, quantidadePessoas = novaQuantidade);
            r.espacoId, r.quantidadePessoas = novoEspaco, novaQuantidade;
            self._mudarStatus(r, StatusReserva.confirmada, usuario,
                              mudou + (" · mesas extras" if usarMesasExtras else ""));
            self._notificar(TipoNotificacao.confirmacao, r);
            return r;

    def naoAtender(self, usuario: UsuarioAdmin, reservaId: int, motivo: str = "") -> Reserva:
        regras.exigirGestao(usuario);
        with self._trava:
            r = self._obterReserva(reservaId);
            if r.status is not StatusReserva.emAndamento:
                raise ErroDeNegocio(f"A reserva {r.codigo} não está na fila de atendimento.");
            self._mudarStatus(r, StatusReserva.naoAtendida, usuario, motivo);
            return r;

    def alterarReserva(self, usuario: UsuarioAdmin, reservaId: int, novaData: Optional[date] = None,
                       espacoId: Optional[int] = None, quantidadePessoas: Optional[int] = None) -> Reserva:

        regras.exigirGestao(usuario);
        with self._trava:
            r = self._obterReserva(reservaId);
            if r.status is not StatusReserva.confirmada:
                raise ErroDeNegocio(
                    f"Só reservas confirmadas podem ser alteradas (a {r.codigo} está {r.status.value}).");
            de = self.armazem.datas[r.dataEventoId] if novaData is None else self._exigirData(novaData);
            novoEspaco = espacoId if espacoId is not None else r.espacoId;
            novaQuantidade = quantidadePessoas if quantidadePessoas is not None else r.quantidadePessoas;
            if de.tipo is TipoData.grandeEvento:
                raise ErroDeNegocio(f"{de.data:%d/%m} é um grande evento: não há reserva de lugares nessa data.");
            if not de.reservas_abertas:
                raise ErroDeNegocio(f"As reservas de {de.data:%d/%m} não estão abertas.");
            agora = self.relogio();
            if de.data < agora.date() or not regras.dentroDoPrazo(de.data, agora):
                raise ErroDeNegocio(f"Fora do prazo para {de.data:%d/%m} (RF-06).");
            self._checarVaga(de, novoEspaco, novaQuantidade, ignorar = r.id);
            mudou = self._diff(r, dataEventoId = de.id, espacoId = novoEspaco, quantidadePessoas = novaQuantidade);
            if not mudou:
                raise ErroDeNegocio("Nada foi alterado.");
            r.dataEventoId, r.espacoId, r.quantidadePessoas = de.id, novoEspaco, novaQuantidade;
            r.atualizadoEm = agora;
            self._registrarHistorico(r, None, None, mudou, usuario);
            self._notificar(TipoNotificacao.alteracao, r, detalhe = f"Alterado: {mudou}.");
            return r;

    def cancelarReserva(self, usuario: UsuarioAdmin, reservaId: int) -> Reserva:
        regras.exigirGestao(usuario);
        with self._trava:
            r = self._obterReserva(reservaId);
            if r.status is StatusReserva.cancelada:
                raise ErroDeNegocio(f"A reserva {r.codigo} já está cancelada; não há ação a realizar.");
            if r.status not in (StatusReserva.confirmada, StatusReserva.emAndamento):
                raise ErroDeNegocio(f"A reserva {r.codigo} está {r.status.value} e não pode ser cancelada.");
            self._mudarStatus(r, StatusReserva.cancelada, usuario, "pedido do cliente via atendimento");
            self._notificar(TipoNotificacao.cancelamento, r);
            return r;

    def marcarRealizadas(self) -> int:
        with self._trava:
            hoje = self.relogio().date();
            n = 0;
            for r in list(self.armazem.reservas.values()):
                if r.status is StatusReserva.confirmada and self.armazem.datas[r.dataEventoId].data < hoje:
                    self._mudarStatus(r, StatusReserva.realizada, None, "data passou");
                    n += 1;
            return n;

    # Painel datas, mapas e espaços - Perfis Técnico/Gerência
    def programarData(self, usuario: UsuarioAdmin, dia: date, atracao: str = "",
                      grandeEvento: bool = False, mapaId: Optional[int] = None) -> DataEvento:
        regras.exigirGestao(usuario);
        with self._trava:
            if self.armazem.dataPorDia(dia):
                raise ErroDeNegocio(f"Já existe programação em {dia:%d/%m/%Y}.");
            de = DataEvento(id = self.armazem.proximoId("data"), data = dia, atracao = atracao);
            self.armazem.datas[de.id] = de;
            if grandeEvento:
                self._aplicarGrandeEvento(de);
            else:
                self._aplicarMapa(de, mapaId or self.mapaPadrao().id);
            return de;

    def marcarGrandeEvento(self, usuario: UsuarioAdmin, dia: date, grandeEvento: bool = True) -> DataEvento:
        regras.exigirGestao(usuario);
        with self._trava:
            de = self._exigirData(dia);
            if grandeEvento:
                confirmadas = self.armazem.reservasDaData(de.id, ocupaLugar);
                if confirmadas:
                    raise ErroDeNegocio(f"Há {len(confirmadas)} reserva(s) confirmada(s) em {dia:%d/%m}. "
                        "Resolva-as com o atendimento antes de marcar grande evento.");
                self._aplicarGrandeEvento(de);
            else:
                de.tipo = TipoData.comum;
                self._aplicarMapa(de, self.mapaPadrao().id);
            return de;

    def criarMapaEspecial(self, usuario: UsuarioAdmin, nome: str, capacidades: dict[int, int], descricao: str = "") -> Mapa:
        regras.exigirGestao(usuario);
        with self._trava:
            m = Mapa(id = self.armazem.proximoId("mapa"), nome = nome, tipo = TipoMapa.especial, descricao = descricao);
            self.armazem.mapas[m.id] = m;
            for e in self.armazem.espacos.values():
                cap = capacidades.get(e.id, 0);
                self.armazem.mapasEspacos[(m.id, e.id)] = MapaEspaco(m.id, e.id, cap, disponivel = cap > 0);
            return m;

    def definirMapa(self, usuario: UsuarioAdmin, dia: date, mapaId: int) -> DataEvento:
        regras.exigirGestao(usuario);
        with self._trava:
            de = self._exigirData(dia);
            if de.tipo is TipoData.grandeEvento:
                raise ErroDeNegocio("Grande evento não usa mapa. Desmarque o grande evento primeiro.");
            self._aplicarMapa(de, mapaId);
            return de;

    def abrirReservas(self, usuario: UsuarioAdmin, dia: date) -> DataEvento:
        regras.exigirGestao(usuario);
        with self._trava:
            de = self._exigirData(dia);
            if de.tipo is TipoData.grandeEvento:
                raise ErroDeNegocio("Grande evento não tem reserva online.");
            if de.mapaId is None:
                raise ErroDeNegocio("Defina o mapa da data antes de abrir as reservas (RN-11).");
            de.reservas_abertas = True;
            return de;

    def atualizarEspaco(self, usuario: UsuarioAdmin, espacoId: int, capacidade: Optional[int] = None, ativo: Optional[bool] = None) -> Espaco:
        regras.exigirGestao(usuario);
        with self._trava:
            e = self.armazem.obter(self.armazem.espacos, espacoId, "Espaço");
            if capacidade is not None:
                if capacidade < 1:
                    raise ErroDeNegocio("A capacidade precisa ser de pelo menos 1 pessoa.");
                e.capacidadePadrao = capacidade;
                me = self.armazem.mapasEspacos.get((self.mapaPadrao().id, e.id));
                if me:
                    me.capacidade = capacidade;
            if ativo is not None:
                e.ativo = ativo;
            return e;

    def mapaPadrao(self) -> Mapa:
        m = next((m for m in self.armazem.mapas.values() if m.tipo is TipoMapa.padrao), None);
        if m is None:
            raise ErroDeNegocio("O mapa padrão não foi cadastrado.");
        return m;

    # Apoio interno
    def _exigirData(self, dia: date) -> DataEvento:
        de = self.armazem.dataPorDia(dia);
        if de is None:
            raise ErroDeNegocio(f"Não há programação em {dia:%d/%m/%Y}.");
        return de;

    def _obterReserva(self, reservaId: int) -> Reserva:
        return self.armazem.obter(self.armazem.reservas, reservaId, "Reserva");

    def _mapaDaData(self, de: DataEvento) -> Mapa:
        return self.armazem.mapas[de.mapaId] if de.mapaId else self.mapaPadrao();

    def _mapaEspaco(self, de: DataEvento, espacoId: Optional[int]) -> Optional[MapaEspaco]:
        if espacoId is None or de.mapaId is None:
            return None;
        return self.armazem.mapasEspacos.get((de.mapaId, espacoId));

    def _usados(self, de: DataEvento, espacoId: int, ignorar: Optional[int] = None) -> int:
        return sum(r.quantidadePessoas for r in self.armazem.reservasDaData(de.id, ocupaLugar)
                   if r.espacoId == espacoId and r.id != ignorar);

    def _ocupacao(self, de: DataEvento) -> list[OcupacaoArea]:
        if de.mapaId is None:
            return [];
        saida = [];
        for me in sorted(self.armazem.capacidadeDoMapa(de.mapaId), key=lambda m: m.espacoId):
            e = self.armazem.espacos[me.espacoId];
            if me.disponivel and e.ativo:
                saida.append(OcupacaoArea(e.id, e.nome, self._usados(de, e.id), me.capacidade));
        return saida;

    def _checarVaga(self, de: DataEvento, espacoId: Optional[int], quantidade: int, ignorar: Optional[int] = None,
                    permitirExtra: bool = False) -> None:
        me = self._mapaEspaco(de, espacoId);
        if me is None or not me.disponivel or not self.armazem.espacos[espacoId].ativo:
            raise ErroDeNegocio("Este local não está disponível nesta data.");
        if quantidade < 1:
            raise ErroDeNegocio("A reserva precisa ter pelo menos 1 pessoa.");
        if permitirExtra:
            return;
        nome = self.armazem.espacos[espacoId].nome;
        if quantidade > me.capacidade:
            raise ErroDeNegocio(f"{quantidade} pessoas passa da capacidade de {nome} ({me.capacidade}) — RN-19.");
        livres = me.capacidade - self._usados(de, espacoId, ignorar);
        if quantidade > livres:
            raise ErroDeNegocio(f"{nome} tem só {livres} lugar(es) livre(s) em {de.data:%d/%m}.");

    def _localIndisponivel(self, de: DataEvento, espaco: Espaco, quantidade: int, msg: str) -> ResultadoSolicitacao:
        alternativas = [Alternativa(o.espacoId, o.nome, o.vagas) for o in self._ocupacao(de)
                        if o.espacoId != espaco.id and o.vagas >= quantidade];
        complemento = (f" Estes locais ainda têm lugar para {quantidade} pessoa(s)." if alternativas
                       else " Nenhum local tem vaga para esse grupo nesta data. Escolha outra data.");
        return ResultadoSolicitacao(TipoResultado.localIndisponivel, msg + complemento, alternativas = alternativas);

    def _cliente(self, s: SolicitacaoReserva, agora: datetime) -> Cliente:
        tel = regras.normalizarTelefone(s.telefone);
        c = self.armazem.clientePorContato(s.email, tel);
        if c is None:
            c = Cliente(id = self.armazem.proximoId("cliente"), nome = s.nome.strip(), telefone = tel,
                        email = s.email.strip().lower(), dataAniversario = s.dataAniversario, criadoEm = agora);
            self.armazem.clientes[c.id] = c;
        else:
            c.nome = s.nome.strip();
            if s.dataAniversario:
                c.dataAniversario = s.dataAniversario;
        return c;

    def _novoCodigo(self) -> str:
        while True:
            codigo = "G17-" + "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(6));
            if self.armazem.reservaPorCodigo(codigo) is None:
                return codigo;

    def _registrar(self, s: SolicitacaoReserva, de: DataEvento, status: StatusReserva, origem: Origem,
                   motivo: Optional[MotivoAtendimento], agora: datetime, usuario: Optional[UsuarioAdmin]) -> Reserva:
        c = self._cliente(s, agora);
        r = Reserva(
            id = self.armazem.proximoId("reserva"),
            codigo = self._novoCodigo(),
            clienteId = c.id,
            dataEventoId = de.id,
            espacoId = s.espacoId,
            quantidadePessoas = s.quantidadePessoas,
            tipoSolicitacao = s.tipoSolicitacao.strip(),
            status = status,
            origem = origem,
            comoChegou = s.comoChegou,
            observacoes = s.observacoes,
            precisaPCD = s.precisaPCD,
            motivoAtendimento = motivo,
            criadoEm = agora,
            atualizadoEm = agora,
        );

        self.armazem.reservas[r.id] = r;
        self._registrarHistorico(r, None, status, "criada", usuario);
        self._notificar(
            TipoNotificacao.confirmacao if status is StatusReserva.confirmada else TipoNotificacao.pedidoRecebido, r);
        return r;

    def _mudarStatus(self, r: Reserva, novo: StatusReserva, usuario: Optional[UsuarioAdmin], nota: str = "") -> None:
        anterior = r.status;
        r.status = novo;
        r.atualizadoEm = self.relogio();
        self._registrarHistorico(r, anterior, novo, nota, usuario);

    def _registrarHistorico(self, r: Reserva, anterior, novo, campos: str, usuario: Optional[UsuarioAdmin]) -> None:
        self.armazem.historico.append(HistoricoReserva(
            id = self.armazem.proximoId("historico"),
            reservaId = r.id,
            registradoEm = self.relogio(),
            statusAnterior = anterior,
            statusNovo = novo,
            campoAlterado = campos,
            usuarioId = usuario.id if usuario else None,
        ));

    def _notificar(self, tipo: TipoNotificacao, r: Reserva, detalhe: str = "") -> None:
        c = self.armazem.clientes[r.clienteId];
        de = self.armazem.datas[r.dataEventoId];
        espaco = self.armazem.espacos.get(r.espacoId) if r.espacoId else None;
        self.caixa.enviar(tipo, r, c, de, espaco, self.relogio(), detalhe);

    def _diff(self, r: Reserva, **novos) -> str:
        nomes = {"dataEventoId": "data", "espacoId": "local", "quantidadePessoas": "pessoas"};
        partes = [];
        for campo, valor in novos.items():
            antigo = getattr(r, campo);
            if antigo != valor:
                if campo == "dataEventoId":
                    antigo, valor = (self.armazem.datas[x].data.strftime("%d/%m") for x in (antigo, valor));
                elif campo == "espacoId":
                    antigo, valor = self._nomeEspaco(antigo), self._nomeEspaco(valor);
                partes.append(f"{nomes[campo]}: {antigo} → {valor}");
        return "; ".join(partes);

    def _nomeEspaco(self, espacoId: Optional[int]) -> str:
        return self.armazem.espacos[espacoId].nome if espacoId else "a definir";

    def _aplicarGrandeEvento(self, de: DataEvento) -> None:
        de.tipo = TipoData.grandeEvento;
        de.mapaId = None;
        de.reservas_abertas = False;

    def _aplicarMapa(self, de: DataEvento, mapaId: int) -> None:
        m = self.armazem.obter(self.armazem.mapas, mapaId, "Mapa");
        de.mapaId = m.id;
        de.reservas_abertas = m.tipo is TipoMapa.padrao;


__all__ = ["SistemaReservas", "DiaCalendario", "OcupacaoArea", "agoraBrasilia", "fuso", "contatoAtendimento"];
