# Design — Desgaste por Intensidade

## 1. O problema que isto resolve

O sub-projeto B introduziu três modos de extração (`cuidadoso`, `normal`, `agressivo`) cujo propósito é criar uma decisão estratégica real. A suíte de dominância prova que cada modo vence em algum cenário — mas ela mede *valor por energia com o desperdício ponderado pela raridade*, e o motor não cobra nada por desperdício. O retorno que um participante de fato enfrenta é `qualidade_inicial / mult_energia`:

| modo | qualidade | mult_energia | retorno no motor |
|---|---|---|---|
| cuidadoso | 100 | 1.80 | 55.6 |
| normal | 92 | 1.00 | 92.0 |
| agressivo | 78 | 0.45 | **173.3** |

`agressivo` vence por 1,88× em todos os minerais. A decisão que o sub-projeto existia para criar não existe na simulação.

O fator de escassez adicionado depois encarece extrair de jazida esvaziada, o que é desejável por si só, mas incide igualmente sobre os três modos e portanto cancela na comparação — a razão entre eles não muda.

Simulando o esgotamento completo de uma jazida de 100 unidades em lotes de 5:

| modo | entregue | energia | valor/energia |
|---|---|---|---|
| cuidadoso | 100.0 | 609 | 0.16 |
| normal | 73.6 | 210 | 0.35 |
| agressivo | 54.6 | 89 | **0.61** |

Cuidadoso extrai quase o dobro de valor da mesma jazida gastando sete vezes mais energia. A escolha certa depende de qual recurso é o gargalo — mas enquanto a métrica for valor por energia, agressivo domina.

## 2. O mecanismo

Operar continuamente desgasta o robô, e o desgaste encarece as operações seguintes. Pausar recupera.

Isso ataca a assimetria certa. Agressivo dura 3 ciclos e cuidadoso 7, então no mesmo intervalo agressivo executa 2,33× mais operações. Se o desgaste acumula por operação, agressivo acumula 2,33× mais rápido, e sua vantagem de 1,88× é superada quando `k × (n_agressivo − n_cuidadoso) > ln(1,88) = 0,63`. Ao longo de 100 ciclos qualquer `k > 0,033` já inverte a ordem — margem folgada.

O efeito colateral é o mais valioso: pausar vira decisão. Se agressivo precisa de aproximadamente 4 ciclos de pausa para não acumular, seu ciclo efetivo passa a 3+4=7, igual ao cuidadoso — mas desperdiçando mais e entregando qualidade pior. Cuidadoso passa a ganhar por mérito, não por calibração forçada.

### Por que a fadiga incide sobre todos os modos

Uma versão anterior desta ideia puniria o uso contínuo de `agressivo` com fadiga e o de `cuidadoso` com queda de rendimento. Isso deixaria exatamente um modo sem punição e trocaria "agressivo domina" por "normal domina" — o mesmo defeito com outro rótulo, e mais difícil de enxergar porque dois mecanismos o mascarariam.

O desgaste acumula proporcional à **intensidade** da operação e incide sobre todos. `normal` não tem refúgio. A decisão deixa de ser "qual modo escolho" e passa a ser "qual sequência de modos e pausas ao longo da missão" — escalonamento sob restrição de recuperação, que é o tipo de problema que o desafio quer fazer emergir sem nomeá-lo.

## 3. Decisões tomadas

- **O desgaste vive em `Robo.desgaste`**, campo que já existe no domínio, é inicializado em `0.0` na geração do mundo e nunca é lido nem escrito por código nenhum. Nenhuma entidade nova.
- **Acumula proporcional à energia gasta na operação**, que é o proxy natural de intensidade e já está calculada no ponto onde o débito acontece.
- **Efeito: multiplica o custo de energia das operações seguintes**, no mesmo ponto de composição onde já entram o modo e a escassez. Isso preserva o seam único que a revisão final pediu para que os eventos ambientais possam compor ali depois.
- **Recuperação automática por ciclo enquanto o robô está `DISPONIVEL`.** O custo de recuperar é o tempo ocioso, que já é um custo real porque ciclos e energia são finitos. Sem endpoint novo, sem comando novo — decisão pura de escalonamento, coerente com o princípio de "poucas ações" do projeto.
- **Sem teto que force parada.** O custo cresce continuamente; o robô nunca é bloqueado. A pressão para pausar é econômica, não proibitiva: o participante escolhe quando pausa. O estado `INDISPONIVEL` permanece sem uso.

## 4. Modelo

`Robo` ganha nada — `desgaste: float` já existe. O que muda é que ele passa a ser lido e escrito.

Fórmula de acumulação, aplicada quando uma operação é debitada:

```
robo.desgaste += energia_da_operacao × taxa_de_desgaste
```

Fórmula de recuperação, aplicada a cada ciclo pelo motor, para todo robô em `DISPONIVEL`:

```
robo.desgaste = max(0.0, robo.desgaste − recuperacao_por_ciclo)
```

Fator aplicado ao custo das operações:

```
fator_desgaste = 1.0 + robo.desgaste × sensibilidade_ao_desgaste
```

O custo de extração passa a ser:

```
custo = mineral.custo_extracao
      × quantidade
      × fator_base_de_energia
      × perfil.mult_energia
      × fator_de_escassez(jazida.fracao_restante)
      × fator_desgaste(unidade)
```

O transporte compõe o mesmo `fator_desgaste` sobre seu custo.

`taxa_de_desgaste`, `recuperacao_por_ciclo` e `sensibilidade_ao_desgaste` ficam em `mundo/config/modos.json`, expostos por `CatalogoDeModos`, seguindo o padrão de `fator_base_de_energia` e `fator_escassez_maximo`.

## 5. Recalibração

Introduzir o desgaste muda o equilíbrio dos seis modos, então `mundo/config/modos.json` precisa ser recalibrado e a suíte de dominância revalidada. Além do critério existente — cada modo vence em algum cenário sob a métrica de valor por energia com raridade — o alvo passa a incluir:

**Nenhum modo domina sob uso contínuo.** Uma simulação de operação sustentada (extrações consecutivas sem pausa, ao longo de uma janela de ciclos representativa) deve mostrar que a ordem entre os modos se inverte conforme o desgaste acumula. Se `agressivo` continuar vencendo indefinidamente sob uso contínuo, a calibração falhou e é ela que muda.

## 6. Testes

Além dos testes de comportamento (desgaste acumula ao operar, recupera ao ficar disponível, encarece a operação seguinte, nunca fica negativo):

- **Teste de inversão**: sob uso contínuo, o custo acumulado de `agressivo` ultrapassa o de `cuidadoso` dentro de uma janela de ciclos razoável — provando que o mecanismo faz o que se propõe.
- **Teste de refúgio**: `normal` também acumula desgaste sob uso contínuo. Este é o teste que impede a dominância invertida e deve ser escrito explicitamente com esse nome e essa intenção.
- A suíte de dominância existente continua verde após a recalibração.

## 7. Ressalva sobre validação

Toda a calibração aqui é algébrica, não medida. O **Avaliador** — que executaria N simulações e compararia médias — ainda não existe, e enquanto não existir nenhuma afirmação sobre "estratégia melhor produz vantagem estatisticamente observável" pode ser verificada empiricamente. A suíte de dominância e o teste de inversão são análise de cenário: provam que o trade-off existe no papel, não que ele distribui as estratégias como se espera na prática.

Isto é uma limitação conhecida e aceita para este sub-projeto. A recalibração empírica é trabalho do ciclo em que o Avaliador for construído.

## 8. Fora de escopo

- Ação explícita de manutenção (avaliada e descartada em favor da recuperação automática).
- Teto de desgaste levando a `INDISPONIVEL` (avaliado e descartado em favor de custo crescente sem bloqueio).
- Desgaste afetando velocidade, qualidade ou capacidade — apenas o custo de energia, para manter um único eixo de efeito.
- O Avaliador.
- Eventos ambientais, regiões e exploração, armazenagem posicional, missões — sub-projetos próprios.
