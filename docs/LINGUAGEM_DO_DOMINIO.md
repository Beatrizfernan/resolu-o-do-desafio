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

## Modo de Operação

Parâmetro opcional de uma ação que escolhe um ponto no trade-off entre energia, tempo, qualidade e desperdício. Extração aceita `cuidadoso`, `normal` e `agressivo`; transporte aceita `economico`, `normal` e `rapido`. O default é sempre `normal`. Nenhum modo é globalmente superior: cada um vence em algum cenário, e a suíte de dominância existe para garantir isso.

O desgaste incide sobre todos os modos, não só sobre os extremos. Um modo isento viraria a escolha universal e a decisão deixaria de existir — não é hipótese: uma calibração anterior deste sub-projeto produziu exatamente isso, com `normal` virando o modo mais barato, e teve de ser corrigida.

## Perfil de Modo

Conjunto de multiplicadores que define um modo, carregado de `mundo/config/modos.json`. Multiplicam os valores base da ação — nunca os substituem — para que modificadores futuros possam compor sobre eles.

## Desperdício

Minério consumido da jazida além do que a carga recebe. Extração agressiva debita `quantidade × fator_desperdicio` da jazida e entrega apenas `quantidade`. A diferença some do mundo permanentemente: é o custo global de uma otimização local. O motor debita sempre o valor base; a ponderação estratégica pela raridade existe na métrica de dominância: uma jazida finita é insubstituível, então a perda de um mineral raro custa quase o dobro do valor tabelado na avaliação de qualidade de estratégia, enquanto desperdiçar um mineral abundante custa praticamente só o valor de face. Por isso extração cuidadosa vence em minerais raros e agressiva em abundantes.

## Local da Carga

Onde a carga está: `em_jazida` (exposta, sem proteção), `em_armazem`, `em_transito` ou `entregue`. Determina qual sensibilidade do mineral governa a degradação e qual multiplicador de contexto se aplica.

## Degradação por Ciclo

Perda de qualidade aplicada a toda carga a cada ciclo:

`taxa_degradacao do mineral × sensibilidade do local × fator de localização × fator do modo`

O `fator de localização` (`modos.json`'s `multiplicador_por_local`) depende do estado da carga: 2.0 exposta na jazida, 1.0 em armazém ou em trânsito, 0.0 entregue. O `fator do modo` é o `mult_degradacao` do modo de transporte ativo (1.0 para `normal`, 0.5 para `rapido`, 2.5 para `economico`), aplicado enquanto a carga viaja. Minerais estáveis como a hematita quase não perdem qualidade parados; o gelo de água perde rápido. Urgência é propriedade do mineral, não regra especial.

## Desgaste

Acúmulo em `Robo.desgaste` provocado por operar. Cada operação soma `taxa_de_desgaste / perfil.mult_duracao` (1.0 e os multiplicadores de duração em `modos.json`), logo após o débito de energia, tanto em `mundo/api/extracao.py` quanto em `mundo/api/transporte.py`. O desgaste segue o **ritmo** da operação, não a energia gasta nela: modos mais rápidos concluem mais operações na mesma janela e por isso acumulam mais depressa. Nunca fica negativo.

## Recuperação

Alívio automático do desgaste: a cada ciclo o motor subtrai `recuperacao_de_desgaste_por_ciclo` (0.15) do desgaste de todo robô em `DISPONIVEL`, com piso em zero. Não há ação de manutenção nem endpoint — o custo de recuperar é o tempo ocioso, que já é um custo real porque ciclos e energia são finitos. Pausar é decisão pura de escalonamento.

## Fator de Desgaste

`1.0 + desgaste × sensibilidade_ao_desgaste` (0.65), multiplicado no custo de energia da operação seguinte, no mesmo ponto de composição onde já entram o multiplicador do modo e o fator de escassez. Não há teto nem parada forçada: a pressão para pausar é econômica, não proibitiva.

O efeito é que o modo mais barato depende de por quanto tempo a operação é sustentada: `normal` vence em rajadas curtas, `cuidadoso` assume a partir de aproximadamente 70 ciclos de operação contínua, e `agressivo` nunca é o mais barato por unidade útil embora sempre entregue o maior volume bruto. Não existe modo universalmente correto — a decisão real que o mecanismo cria é *quando pausar*, não *qual modo escolher*. Fixado por `test_lideranca_de_custo_gira_conforme_a_janela_de_operacao`.
