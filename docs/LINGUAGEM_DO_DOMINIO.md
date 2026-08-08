# Linguagem do Domínio — Operação Marciana

Fonte de verdade terminológica do projeto (`SPEC_INICIAL.md` §43). Todo código de domínio deve usar estes termos.

## Mundo

Simulação completa da operação em Marte. Fonte de verdade sobre todo estado; Centrais não alteram esse estado diretamente, apenas enviam comandos.

## Ciclo

Unidade discreta de tempo simulado (`ciclo_atual`). Avança via `avancar_ciclo`, disparado por um loop em tempo real ou manualmente (testes/Avaliador).

## Comando

Intenção de ação enviada por uma Central via API. Entra em uma `FilaDeComandos` e só é aplicado ao estado no próximo ciclo processado — nunca na hora da chamada HTTP.

## Efeito Agendado

Consequência de um comando que não é instantânea (ex.: extração leva N ciclos). Registrado com um `ciclo_alvo` e disparado quando o motor atinge esse ciclo.

## Evento do Mundo

Alteração relevante do estado do ambiente, publicada pelo `BarramentoDeEventos`. Possui `identificador`, `tipo`, `ciclo`, `dados`. Entregue por polling (`consultar_eventos`) e opcionalmente por webhook (fire-and-forget, sem garantia de entrega).

## Autorização

Permissão emitida pela Central de Missão (`id_autorizacao`) exigida por operações que dependem de coordenação entre Centrais (ex.: `iniciar_viagem`, `preparar_distribuicao`). Uso único.

## Jazida

Local conhecido contendo quantidade finita de um mineral. Estados: `desconhecida → identificada → disponivel → interditada/esgotada`. Jazida esgotada nunca regenera.

## Mineral

Recurso extraível com valor econômico fixo durante toda a simulação (sem flutuação de mercado). Atributos: `valor_por_unidade`, `raridade`, `custo_extracao`, `massa`, `taxa_degradacao`, `sensibilidade_temperatura`, `sensibilidade_transporte`, `sensibilidade_armazenagem`.

## Carga Mineral

Quantidade de material extraído em trânsito entre extração, armazenagem, transporte e pesquisa. Possui `qualidade` (0–100, sempre limitada a esse intervalo) que pode degradar por espera, armazenagem inadequada, transporte ou eventos ambientais.

## Valor Efetivo

Valor econômico realmente entregue por uma carga: `quantidade * valor_por_unidade * (qualidade / 100)`. Só é contabilizado no `faturamento_total` quando a carga passa por `preparar_distribuicao` com autorização válida da Missão.

## Unidade Mineradora

Robô capaz de extrair minerais de jazidas. Não possui estratégia própria — só executa comandos válidos.

## Unidade Transportadora

Robô capaz de transportar cargas entre localizações, com `viagens_disponiveis` finitas.

## Armazém

Estrutura com `capacidade`, `ocupacao` e `compatibilidades` de mineral. Reservar espaço além da capacidade lança `CapacidadeExcedidaError`. Receber mineral incompatível gera evento `carga_contaminada`.

## Rota

Caminho entre localizações com `distancia`, `tempo_base`, `risco` e `condicao` (`livre`/`interditada`).

## Central

Um dos cinco serviços operacionais controlados pelos participantes: Extração, Armazenagem, Transporte, Pesquisa, Missão. Toda comunicação entre Centrais operacionais passa pela Central de Missão — imposta por contrato de autorização, não por isolamento de rede.

## Energia

Recurso global finito (`energia_total = 1000`). Cada Central inicia com 10 unidades; a reserva estratégica (950) é controlada exclusivamente pela Central de Missão. Não há geração de energia durante a simulação — o pool nunca regenera.

## Reserva Estratégica

Saldo de energia controlado pela Central de Missão, origem obrigatória de toda alocação de energia (`alocar_energia`).

## Semente

Valor inteiro (`semente`) que inicializa o gerador de números aleatórios (`random.Random`) do motor. Mesma semente + mesmas ações via ciclo manual produzem o mesmo estado final e a mesma sequência de eventos.

## Faturamento

Soma dos valores efetivos de todas as cargas que passaram por `preparar_distribuicao` com sucesso (`motor.faturamento_total`).
