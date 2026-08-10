# Design — Central de Missão: consumo por ciclo e fim por esgotamento

## 1. O problema que isto resolve

A central de missão é a única decisão **global** da simulação. Tudo mais é otimização local: qual modo para esta extração, que ordem nesta pilha, qual rota para esta carga. Só a missão troca um eixo contra outro — energia para minerar contra energia para transportar contra energia para guardar.

E hoje ela não decide nada. Medido no código:

- `alocar-energia` move reserva → central sem custo, sem limite de quantas vezes, e sem rota de volta (`redistribuir_energia` e `revogar_energia` existem no domínio e não são expostas).
- `autorizar-missao` emite autorizações ilimitadas, sob demanda, para qualquer operação.
- Esperar para alocar não custa nada, e alocar cedo também não. Sem pressão nos dois sentidos, tanto "aloca tudo no ciclo 1" quanto "aloca no último instante" são ótimos — e ambos inertes.
- `duracao_maxima` existe em `ConfiguracaoDaSimulacao`, é passada em toda construção do motor, e **nenhuma lógica a lê**. O tick nunca para. Mesmo padrão de campo morto que `raridade` e `condicoes` tiveram.

Não há informação oculta no mundo: jazidas nascem `DISPONIVEL` com `quantidade_disponivel` exposta, e os estados `DESCONHECIDA` e `IDENTIFICADA` nunca são usados. Tudo que se sabe no ciclo 200 já se sabe no ciclo 1. Isso importa porque elimina uma família inteira de soluções: encarecer o compromisso só cria decisão se esperar revelar algo. Sem informação chegando, tornar a alocação irreversível vira imposto, não escolha.

## 2. O mecanismo

**Existir custa.** Cada uma das cinco centrais consome uma quantidade fixa de energia por ciclo, debitada do próprio saldo. A missão inclusive.

**Central sem saldo não opera.** Ela para de executar operações e para de pagar consumo — fica dormente.

**A missão pode ressuscitar as outras quatro.** Alocar para uma central seca a traz de volta. O erro é recuperável.

**A missão seca é irrecuperável.** Sem saldo ela não aloca, e sem alocação ninguém mais recebe energia. A reserva congela e as centrais restantes drenam até secar.

**A simulação acaba quando nenhuma central consegue pagar o próprio consumo.** No caminho normal isso é o esgotamento natural do orçamento. No caminho do deadlock é morte antecipada, com energia encalhada na reserva.

### Por que isto cria decisão

Duas decisões, e nenhuma delas precisa de informação oculta:

**Quanto comprometer, e quando.** Alocar é de mão única. Alocar cedo demais para a central errada é energia que não volta; alocar tarde demais é robô parado consumindo sem produzir. O ótimo depende da taxa de consumo real de cada central, que o participante só descobre observando os eventos que já existem.

**Manter a missão viva.** As centrais começam com 10 cada. O consumo da missão é calibrado para que esses 10 durem cerca de metade de uma execução típica. Quem alocar um pouco para ela no início nunca vê o problema; quem esquecer descobre no meio, e perde a cauda da execução.

Esta segunda não é punição por estratégia ruim — é armadilha por desatenção, e é detectável antes de disparar: `/missao/estado` mostra o saldo. A informação está lá desde o ciclo 1. A questão é se o participante olhou.

### Uma armadilha, não cinco

A assimetria é deliberada. Se qualquer central seca fosse definitiva, um erro de alocação em extração encerraria a mineração para sempre, e o mundo ficaria punitivo em cinco frentes. Concentrando a irreversibilidade na missão, existe exatamente um erro fatal, ele é barato de evitar, e é o erro que corresponde a ignorar a única decisão global do jogo.

## 3. Decisões tomadas

- **Sem janela de alocação.** Foi considerada e descartada: com o consumo por ciclo já penalizando a indecisão, limitar quanto se pode alocar por janela seria uma segunda restrição temporal fazendo trabalho parecido, puxando no sentido oposto. Restrições redundantes produzem decisão aparente.
- **Sem limite de ciclos.** `duracao_maxima` sai de `ConfiguracaoDaSimulacao`. O fim passa a ser consequência do esgotamento, não constante escolhida. A terminação é garantida porque a energia total só diminui: alocar move energia entre saldos, e o consumo sempre drena.
- **Autorizações custam energia**, debitadas da missão. Sem teto de contagem — a escassez é a própria energia.
- **Consumo debitado do saldo da própria central**, não da reserva. É o que faz "central seca" ser um estado observável e recuperável, em vez de um saldo global abstrato.
- **A reserva não paga consumo.** Ela só guarda. Isso é o que garante o encerramento: as cinco centrais drenam, e quando todas estão dormentes a simulação acaba mesmo com a reserva cheia — que é exatamente o desfecho do deadlock.
- **`redistribuir_energia` e `revogar_energia` permanecem sem rota.** Alocação é de mão única, e é isso que dá peso ao compromisso.

### Consequência aceita: o tamanho do lote volta a importar

O sub-projeto da armazenagem registrou que dividir minério em cargas pequenas virou estritamente pior, e que extrair no maior lote possível dominava. Com autorização custando energia, isso se inverte parcialmente: `receber-carga` aceita uma **lista**, então guardar cinco cargas numa chamada custa uma autorização e em cinco chamadas custa cinco.

Isso é reversão desejada de uma limitação registrada, não efeito colateral. Documentar como tal.

## 4. Modelo

`GerenciadorDeEnergia` ganha o conceito de central dormente:

```python
def esta_operante(self, central: str) -> bool
    """Uma central sem saldo não executa nem consome. Dormente, não morta."""
```

Novo arquivo `mundo/config/operacao.json`, seguindo o padrão de `modos.json` e `armazenagem.json`:

```json
{
  "consumo_por_ciclo_da_central": 0.05,
  "custo_de_autorizacao": 0.2
}
```

Carregado por `CatalogoDeOperacao` em `mundo/dominio/operacao.py`, exposto no motor como `motor.catalogo_de_operacao`.

`ConfiguracaoDaSimulacao` perde `duracao_maxima` e ganha nada. Isso é mudança de contrato de API: `POST /missao/resetar-mundo` hoje exige o campo, e `criar_app` o passa. Os dois deixam de mencioná-lo, e um pedido que ainda o envie deve ser aceito ignorando o campo — participantes que já escreveram clientes não podem quebrar por causa de um parâmetro que nunca fez nada. `MotorDeSimulacao` ganha:

```python
self.encerrada: bool = False
```

## 5. Números

| parâmetro | valor | justificativa |
|---|---|---|
| `consumo_por_ciclo_da_central` | 0.05 | Os 10 iniciais duram 200 ciclos sem nenhuma alocação — cerca de metade de uma execução típica, que é onde a armadilha deve disparar. |
| `custo_de_autorizacao` | 0.2 | Quatro ciclos de consumo por autorização. Alto o bastante para agrupar operações valer a pena, baixo o bastante para não dominar o orçamento: cem autorizações custam 20, contra 950 de reserva. |

Uma execução em que ninguém aloca nada termina por volta do ciclo 200, quando as cinco centrais secam. É o piso, e é o resultado que um participante que não olhou para a missão vai obter.

Estes números são ponto de partida por análise, não por medição. O que os protege é a suíte descrita adiante — e o Avaliador, quando existir, é quem os validará empiricamente.

## 6. Aplicação

**Novo passo no tick**, junto de `_degradar_cargas`, `_recuperar_desgaste` e `_cobrar_manutencao_dos_armazens`:

```
_cobrar_consumo_das_centrais()
```

Debita `consumo_por_ciclo_da_central` de cada central que ainda tenha saldo. Central sem saldo é pulada — não acumula dívida.

Em seguida, o motor verifica o fim: se nenhuma central consegue pagar o consumo, marca `encerrada` e publica `simulacao_encerrada` com o ciclo, o faturamento total e a energia encalhada. `avancar_ciclo` passa a ser no-op depois disso.

**Toda rota que executa operação** passa a exigir que sua central esteja operante. Uma central dormente rejeita com `operacao_invalida` e motivo explícito, antes de qualquer mutação — a mesma ordem que o sub-projeto da armazenagem estabeleceu.

**`autorizar-missao`** debita `custo_de_autorizacao` da missão antes de emitir. Missão dormente não emite.

**`alocar-energia`** exige missão operante. É esta linha que cria o deadlock, e ela é o mecanismo inteiro.

O handler de `alocar-energia` hoje muta de forma síncrona, fora de qualquer `Comando.executar()`, violando o invariante que o resto do projeto mantém. Corrigir junto: a alocação passa a ser comando enfileirado como todas as outras mutações.

## 7. Testes

Além dos de comportamento (consumo debita por ciclo, central seca não opera, central seca não acumula dívida, alocação ressuscita central seca):

- **Teste do deadlock**: sem nenhuma alocação para a missão, a simulação encerra por volta do ciclo 200 e a reserva fica encalhada. Prova que a armadilha existe.
- **Teste de recuperação**: alocar para a missão antes do ciclo 200 evita o deadlock por completo. Prova que ela é barata de evitar.
- **Teste de assimetria**: extração seca e depois ressuscitada volta a minerar; missão seca não volta de jeito nenhum. Prova que existe uma armadilha, não cinco.
- **Teste de terminação**: toda execução termina. É o que o Avaliador vai depender para rodar 100 simulações.
- **Teste de não-obrigatoriedade**: uma estratégia que aloca tudo no ciclo 1 e nunca mais mexe precisa continuar viável. Se alocar bem virar obrigatório para produzir qualquer coisa, o mecanismo virou pedágio e a calibração é que está errada.

O último é o guarda contra o defeito que este projeto já produziu cinco vezes num único sub-projeto: um mecanismo que, em vez de criar decisão, cria obrigação.

## 8. Fora de escopo

- **Informação oculta** — jazidas de qualidade desconhecida, custo de análise, exploração. É o sub-projeto A, e é o que daria valor a *esperar* antes de decidir. Sem ele, a decisão de alocação é sobre quantidade e destino, não sobre timing informacional.
- Janela de alocação (avaliada e descartada acima).
- Revogar ou redistribuir energia já alocada.
- Missões nomeadas com objetivo e prazo — a central de missão aqui só aloca e autoriza.
- Eventos ambientais: sub-projeto E.
- O Avaliador. Este sub-projeto entrega a terminação de que ele depende, mas não o implementa.
