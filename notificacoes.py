from __future__ import annotations;

from datetime import datetime;
from typing import Optional;

from modelos import Cliente, DataEvento, Espaco, Notificacao, Reserva, TipoNotificacao;
from repositorio import Armazem;

avisoSpam = "Se não encontrar este e-mail, confira a caixa de spam.";
contatoAtendimento = "[CONTATO DO ATENDIMENTO]";  # pendente: definir


class CaixaDeSaidaEmMemoria:

    def __init__(self, armazem: Armazem) -> None:
        self.armazem = armazem;

    def enviar(self, tipo: TipoNotificacao, reserva: Reserva, cliente: Cliente,
               data: DataEvento, espaco: Optional[Espaco], agora: datetime, detalhe: str = "") -> Notificacao:
        assunto, corpo = self._montar(tipo, reserva, cliente, data, espaco, detalhe);
        n = Notificacao(
            id = self.armazem.proximoId("notificacao"),
            reservaId = reserva.id,
            tipo = tipo,
            emailDestino = cliente.email,
            assunto = assunto,
            corpo = corpo,
            enviadaEm = agora,
        );

        self.armazem.notificacoes.append(n);
        return n;

    @staticmethod
    def _montar(tipo, reserva, cliente, data, espaco, detalhe):
        dia = data.data.strftime("%d/%m/%Y");
        local = espaco.nome if espaco else "a definir com a equipe";
        resumo = f"Nº {reserva.codigo} · {dia} · {local} · {reserva.quantidadePessoas} pessoa(s)";
        if tipo is TipoNotificacao.confirmacao:
            return ("Sua reserva no Galpão 17 está confirmada",
                    f"Olá, {cliente.nome}! Seus lugares estão garantidos.\n{resumo}\n"
                    f"Para alterar ou cancelar, fale com o atendimento: {contatoAtendimento}.");
        if tipo is TipoNotificacao.pedidoRecebido:
            return ("Recebemos seu pedido de reserva",
                    f"Olá, {cliente.nome}! Ainda não é uma reserva confirmada: nossa equipe vai analisar "
                    f"e falar com você.\nPedido {resumo}");
        if tipo is TipoNotificacao.alteracao:
            return ("Sua reserva foi alterada",
                    f"Olá, {cliente.nome}! Sua reserva foi atualizada pelo atendimento.\n{detalhe}\n{resumo}");
        return ("Sua reserva foi cancelada",
                f"Olá, {cliente.nome}! A reserva {reserva.codigo} de {dia} foi cancelada.");
