# 🎶 Sistema de Reservas Online — Galpão 17

Sistema de reservas online do **Galpão 17**, casa de eventos e shows. O projeto digitaliza e centraliza o processo de reservas, 
que hoje é feito por **formulário e planilha**: o cliente faz o pedido de forma simples e a equipe ganha uma visão consolidada 
para acompanhar e administrar as reservas.

🚧 **Status: em desenvolvimento.** 
Projeto do meu estágio de TI no Galpão 17. Nesta etapa, o foco é a **camada de regras de negócio em Python**, com os dados guardados 
em memória (ainda sem banco de dados nem interface).

---

## ✨ Funcionalidades

### Para o cliente (formulário, sem login)
- **Calendário de eventos** com as datas, atrações e horário limite para reservar
- **Solicitação de reserva** por quantidade de pessoas e local de preferência
- **Validação dos dados** do formulário: nome, telefone com DDD, e-mail, data de aniversário (dd/mm) e limites de tamanho dos campos
- **Confirmação automática** quando o local está disponível e todas as regras são atendidas, com código de reserva no formato `G17-XXXXXX`
- **Sugestão de locais alternativos** quando o local escolhido está lotado ou indisponível
- **Notificações por e-mail** de confirmação, pedido recebido, alteração e cancelamento (hoje simuladas em uma caixa de saída em memória)

### Para a equipe (painel administrativo)
- Lista das **reservas do dia**, com filtro por status e busca, e **resumo de ocupação** por área
- **Fila de atendimento humano**: pedidos PCD e grupos acima da capacidade entram na fila e a equipe pode confirmar ou recusar
- **Alteração e cancelamento** de reservas feitos pelo atendimento, reaplicando as validações de disponibilidade, capacidade e prazo
- **Histórico** de cada reserva: status anterior e novo, campos alterados e usuário responsável
- **Gestão da programação**: cadastrar datas, marcar **grande evento**, criar **mapa especial**, definir o mapa da data e abrir as reservas
- **Gestão de espaços**: capacidade e disponibilidade de cada área

---

## 📏 Principais regras de negócio

| Regra | Comportamento |
|---|---|
| **Prazo** | Terça a quinta: reservas até **15h** do próprio dia. Sexta e sábado: até **12h** |
| **Capacidade** | A reserva é por **quantidade de pessoas**, não por mesa. Se o grupo passa da capacidade da área, o pedido vai para o **atendimento humano** |
| **Grande evento** | Não há reserva online de lugares. Só pedidos **PCD** são aceitos e seguem para o atendimento |
| **Atendimento PCD** | Sempre encaminhado para o atendimento humano, fora da confirmação automática |
| **Mapas** | **Mapa padrão** nos dias comuns. **Mapa especial** quando o layout muda, definido antes de abrir as reservas |
| **Alteração e cancelamento** | Sem autoatendimento: o cliente fala com a equipe, que faz a mudança no painel |
| **Fuso horário** | Prazos calculados no horário de Brasília |

---

## 👥 Perfis de acesso

| Perfil | Permissões |
|---|---|
| **Técnico/Gerência** | Acesso total: confirmar, alterar e cancelar reservas, gerenciar datas, mapas e espaços |
| **Administração** | Apenas visualização das reservas |
| **Cliente** | Sem login: usa apenas o formulário de reserva |

---

## 🧱 Arquitetura

O código é organizado em camadas, separando dados, regras e casos de uso:

```
sistemaReservasOnline_Galpao17/
├── modelos.py        # Entidades (Cliente, Espaco, Mapa, DataEvento, Reserva, Historico...) e enums de status
├── regras.py         # Regras puras: prazos, fuso de Brasília, validação do formulário e permissões
├── repositorio.py    # Armazém em memória e consultas (por data, código, contato...)
├── servicos.py       # SistemaReservas: fluxo de reserva, painel e gestão de datas/mapas/espaços
├── notificacoes.py   # Montagem e envio (em memória) dos e-mails ao cliente
└── erros.py          # Exceções do sistema (negócio, permissão negada, não encontrado)
```

**Fluxo de uma solicitação de reserva** (`SistemaReservas.solicitarReserva`):

1. Confere se a data existe e se as reservas estão abertas
2. Se for **grande evento**, aceita apenas pedido PCD
3. Valida os dados do formulário
4. Verifica o **prazo** do próprio dia
5. Encaminha pedidos **PCD** para o atendimento
6. Verifica **disponibilidade e capacidade** do local e sugere alternativas
7. Tudo certo: **confirma automaticamente** e envia o e-mail

---

## 🛠️ Tecnologias

- **Python 3** (dataclasses, enums, type hints, `zoneinfo`)
- Armazenamento **em memória** nesta fase
- **PyCharm** como IDE

---

## ▶️ Como executar

```bash
git clone https://github.com/marinaplacerda/sistemaReservasOnline_Galpao17.git
cd sistemaReservasOnline_Galpao17
python -m venv .venv
# Windows: .venv\Scripts\activate  |  Linux/macOS: source .venv/bin/activate
```

O projeto ainda não tem interface. Por enquanto, as funcionalidades são usadas pela classe `SistemaReservas`, em `servicos.py`.

---

## 🗺️ Próximos passos

- [ ] API com **FastAPI**
- [ ] Banco de dados em nuvem
- [ ] Interface web responsiva (formulário, calendário, confirmação e painel)
- [ ] Envio real de e-mails
- [ ] Testes automatizados
- [ ] Migração do histórico da planilha atual
- [ ] Piloto com usuários e lançamento

---

## 👩‍💻 Autora

**Marina Lacerda**, estagiária de TI no Galpão 17 e estudante de Análise e Desenvolvimento de Sistemas na Fatec Campinas.

[![LinkedIn](https://img.shields.io/badge/LinkedIn-0A66C2?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/marinaplacerda/)
[![GitHub](https://img.shields.io/badge/GitHub-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/marinaplacerda)
