# Desafio de Engenharia — Operação Marciana

## 1. Visão

Este projeto é uma dinâmica técnica colaborativa destinada à avaliação de desenvolvedores trabalhando com ferramentas de Inteligência Artificial.

A dinâmica não tem como objetivo medir velocidade de digitação, memorização de APIs, resolução de algoritmos isolados ou capacidade de programar sem assistência.

O objetivo é observar como uma equipe de desenvolvedores:

- compreende um domínio desconhecido;
- estabelece uma linguagem comum;
- estrutura software em conjunto;
- utiliza IA como ferramenta de engenharia;
- verifica criticamente código e decisões sugeridas por IA;
- trabalha com sistemas orientados a eventos;
- estabelece contratos entre componentes;
- reage a mudanças no ambiente;
- administra recursos limitados;
- toma decisões diante de trade-offs;
- coordena trabalho entre diferentes responsabilidades;
- mantém ownership sobre o software produzido.

O desafio simula uma operação autônoma de exploração mineral em Marte.

A equipe trabalha para uma companhia de exploração espacial responsável por localizar, extrair, armazenar, transportar, analisar e entregar minerais encontrados no planeta.

Sugestão de nome da companhia:

**Ares Mineração Orbital**

A plataforma não possui interface gráfica obrigatória.

Marte existe como uma simulação computacional executada continuamente, com estado, tempo, recursos, robôs, clima, eventos e regras próprias.

Os participantes interagem com esse mundo através de software.

---

# 2. Princípio fundamental

A dinâmica deve ser entendida como:

> Um mundo simulado no qual uma equipe precisa construir a inteligência operacional necessária para controlar uma operação robótica de mineração.

O mundo já existe.

Os robôs já existem.

As jazidas já existem.

Os armazéns já existem.

As condições ambientais já existem.

As regras físicas simplificadas já existem.

Porém, os robôs são deliberadamente pouco inteligentes.

Eles possuem capacidades, mas não possuem estratégia operacional.

Os participantes precisam construir essa inteligência.

---

# 3. Arquitetura conceitual

O projeto possui três grandes partes:

```text
┌───────────────────────────────────────────┐
│                  MUNDO                    │
│                                           │
│ Marte                                     │
│ Robôs                                     │
│ Jazidas                                   │
│ Energia                                   │
│ Clima                                     │
│ Armazéns                                  │
│ Rotas                                     │
│ Tempo                                     │
│ Eventos                                   │
│ Regras                                    │
└───────────────────┬───────────────────────┘
                    │
             APIs / Eventos
                    │
┌───────────────────▼───────────────────────┐
│          CENTRAIS OPERACIONAIS            │
│                                           │
│ Central de Extração                       │
│ Central de Armazenagem                    │
│ Central de Transporte                     │
│ Central de Pesquisa                       │
│ Central de Missão                         │
│                                           │
│ Código criado pelos participantes         │
└───────────────────┬───────────────────────┘
                    │
                    │ resultados
                    ▼
┌───────────────────────────────────────────┐
│               AVALIADOR                   │
│                                           │
│ Executa múltiplas simulações              │
│ Calcula eficiência                        │
│ Calcula perdas                            │
│ Calcula faturamento                       │
│ Verifica integridade                      │
│ Produz resultado final                    │
└───────────────────────────────────────────┘
```

---

# 4. Linguagem ubíqua

O projeto deve utilizar os princípios de linguagem ubíqua do Domain-Driven Design.

Todo conceito importante do domínio deve possuir um nome único e consistente.

Todo código pertencente ao desafio deve utilizar português.

Devem ser evitados nomes técnicos genéricos quando existir um conceito do domínio mais preciso.

Exemplo:

Evitar:

`Manager`

Preferir:

`CentralDeMissao`

Evitar:

`Item`

Preferir:

`CargaMineral`

Evitar:

`Storage`

Preferir:

`Armazem`

Evitar:

`Job`

Preferir:

`MissaoDeTransporte`

---

# 5. Vocabulário inicial do domínio

## Mundo

Simulação completa da operação em Marte.

## Ciclo

Unidade discreta de passagem de tempo da simulação.

## Jazida

Local conhecido contendo uma quantidade finita de determinado mineral.

## Veio Mineral

Concentração explorável de um mineral pertencente a uma jazida.

## Mineral

Recurso natural que pode ser extraído.

## Carga Mineral

Quantidade de material extraído sendo armazenada, transportada ou processada.

## Qualidade

Percentual de preservação de uma carga mineral.

## Valor Mineral

Valor econômico fixo por unidade de determinado mineral.

## Unidade Mineradora

Robô capaz de realizar extração.

## Unidade Transportadora

Robô capaz de transportar cargas.

## Armazém

Estrutura temporária utilizada para armazenar cargas.

## Centro de Pesquisa

Destino intermediário responsável por analisar, classificar e validar cargas.

## Central de Distribuição

Destino final das cargas válidas.

## Energia

Recurso global finito necessário para executar operações.

## Missão

Instrução operacional coordenada pela Central de Missão.

## Evento do Mundo

Alteração relevante do estado do ambiente que pode exigir reação das Centrais.

---

# 6. Recursos minerais

Os recursos minerais existentes em uma simulação são finitos.

Quando uma jazida é esgotada, seus recursos não retornam.

Cada mineral possui características próprias:

- quantidade disponível;
- valor econômico;
- dificuldade de extração;
- custo energético de extração;
- peso;
- sensibilidade ao transporte;
- sensibilidade à armazenagem;
- taxa de degradação;
- raridade.

O valor econômico de cada mineral é fixo durante toda a simulação.

Não existe flutuação de mercado.

---

# 7. Minerais sugeridos

A ambientação pode utilizar materiais associados à geologia marciana, mas suas propriedades econômicas e operacionais são deliberadamente fictícias e servem à dinâmica.

Exemplos:

### Hematita

Disponibilidade: alta  
Valor: baixo/médio  
Dificuldade de extração: baixa  
Sensibilidade: baixa

Funciona como recurso relativamente seguro.

### Sílica de alta pureza

Disponibilidade: média  
Valor: alto  
Dificuldade: média  
Sensibilidade: média

### Jarosita

Disponibilidade: baixa  
Valor: alto  
Dificuldade: alta  
Sensibilidade: alta

### Depósito de gelo de água

Possui valor estratégico elevado.

Pode exigir condições especiais de extração, armazenagem e transporte.

### Mineral raro experimental

Recurso fictício extremamente valioso utilizado para representar a cauda de oportunidade do desafio.

---

# 8. Recursos raros

Aproximadamente 90% do valor mineral potencial do mundo deve estar disponível através de exploração relativamente previsível.

Os aproximadamente 10% finais devem representar oportunidades raras.

Essas oportunidades não devem ser garantidas.

Uma operação eficiente aumenta sua capacidade de explorá-las.

Por exemplo:

Uma equipe que desperdiçou energia provavelmente não poderá explorar uma jazida rara descoberta no final da missão.

Uma equipe que saturou seus armazéns pode não possuir capacidade para recebê-la.

Uma equipe que utilizou excessivamente seus transportadores pode não possuir viagens suficientes.

O componente probabilístico deve ser pequeno.

Como referência inicial, uma oportunidade rara pode possuir entre 5% e 10% de probabilidade de surgir em determinada condição elegível.

A aleatoriedade não deve substituir competência.

Ela deve criar oportunidades que apenas operações bem administradas conseguem aproveitar.

---

# 9. Energia

Energia é o principal recurso compartilhado da missão.

Exemplo de configuração:

Energia total inicial:

1000 unidades.

Cada Central inicia com:

10 unidades.

Portanto:

```text
Central de Extração       10
Central de Armazenagem    10
Central de Transporte     10
Central de Pesquisa       10
Central de Missão         10

Reserva estratégica      950
```

A reserva estratégica é controlada exclusivamente pela Central de Missão.

A Central de Missão pode:

- alocar energia;
- redistribuir energia;
- limitar consumo;
- revogar reservas;
- priorizar determinadas operações.

Toda ação operacional relevante consome energia.

---

# 10. Geração de energia

Pode existir geração solar limitada durante a missão.

Sua eficiência é afetada pelas condições ambientais.

Exemplo:

Condição normal:

100% de geração.

Poeira moderada:

70%.

Tempestade de poeira:

20%.

Isso cria uma combinação de:

- estoque inicial finito;
- geração variável;
- necessidade de planejamento.

---

# 11. Qualidade mineral

Toda carga possui qualidade entre 0 e 100.

Exemplo:

```text
100 = material perfeitamente preservado
80  = material aproveitável
50  = material fortemente degradado
20  = baixo aproveitamento
0   = material perdido
```

A qualidade pode ser afetada por:

- tempo;
- temperatura;
- exposição ambiental;
- transporte inadequado;
- armazenagem inadequada;
- contaminação;
- atrasos.

Minerais diferentes possuem sensibilidades diferentes.

---

# 12. Valor econômico

O objetivo não é maximizar quantidade.

O objetivo é maximizar **valor econômico entregue**.

Exemplo:

```text
100 kg de Hematita
valor por kg = 5

faturamento potencial = 500
```

Enquanto:

```text
10 kg de Mineral Raro
valor por kg = 200

faturamento potencial = 2000
```

Portanto, uma equipe pode entregar menos massa e ainda obter resultado muito superior.

A qualidade também influencia o valor efetivamente entregue.

Uma carga de qualidade baixa pode valer apenas uma fração do valor original.

---

# 13. Central de Extração

Responsável pelas Unidades Mineradoras.

Seu desenvolvedor precisa construir a inteligência necessária para decidir:

- qual jazida explorar;
- qual mineral priorizar;
- quando iniciar extração;
- quando interromper extração;
- quanto extrair;
- quando solicitar retirada;
- quando conservar energia;
- quando evitar determinada região.

### Restrições

Unidades mineradoras possuem:

- capacidade limitada;
- consumo energético;
- desgaste;
- velocidade de extração;
- compatibilidade com determinados minerais.

### Ações possíveis

Exemplos conceituais:

```text
consultar_jazidas
inspecionar_jazida
iniciar_extracao
interromper_extracao
alterar_jazida
solicitar_retirada
retornar_unidade
```

---

# 14. Central de Armazenagem

Responsável pelo armazenamento temporário.

Precisa decidir:

- onde armazenar;
- quanto espaço reservar;
- quais cargas priorizar;
- quando liberar capacidade;
- quando descartar materiais;
- como evitar contaminação;
- quando solicitar retirada.

### Restrições

Armazéns possuem:

- capacidade máxima;
- condições ambientais;
- compatibilidade mineral;
- ocupação;
- custo energético;
- risco de contaminação.

### Ações

```text
consultar_armazens
reservar_espaco
receber_carga
realocar_carga
liberar_carga
descartar_carga
solicitar_transporte
```

---

# 15. Central de Transporte

Responsável pelas Unidades Transportadoras.

Precisa decidir:

- quais cargas transportar;
- quando realizar viagem;
- quais cargas agrupar;
- qual rota utilizar;
- quando esperar;
- quando abortar;
- como preservar materiais sensíveis.

### Restrições

Transportadores possuem:

- capacidade máxima;
- consumo energético;
- quantidade limitada de viagens;
- desgaste;
- velocidade;
- tempo de carregamento;
- tempo de descarregamento.

Rotas possuem:

- distância;
- risco;
- condição do terreno;
- exposição climática.

### Ações

```text
consultar_cargas_disponiveis
consultar_rotas
planejar_transporte
carregar
iniciar_viagem
abortar_viagem
descarregar
retornar_unidade
```

---

# 16. Central de Pesquisa

Responsável pelo recebimento e classificação científica das cargas.

Precisa:

- analisar material;
- determinar qualidade;
- separar cargas comprometidas;
- classificar minerais;
- descartar materiais inutilizáveis;
- preparar cargas válidas para distribuição.

### Restrições

Possui:

- capacidade limitada;
- consumo energético;
- tempo de análise;
- capacidade simultânea de processamento.

### Ações

```text
consultar_fila
iniciar_analise
classificar_carga
rejeitar_carga
aprovar_carga
preparar_distribuicao
```

---

# 17. Central de Missão

É o componente de coordenação da operação.

Nenhuma das outras quatro Centrais pode se comunicar diretamente.

Toda comunicação operacional entre Centrais deve passar pela Central de Missão.

Exemplo:

```text
Extração
   │
   │ carga disponível
   ▼
Central de Missão
   │
   │ necessidade de armazenamento
   ▼
Armazenagem
```

A Central de Missão também administra energia.

### Responsabilidades

- receber informações das demais Centrais;
- coordenar operações;
- distribuir energia;
- redistribuir energia;
- definir prioridades;
- autorizar operações críticas;
- interromper operações;
- reagir a eventos ambientais;
- coordenar retirada e entrega;
- determinar quando a Central de Distribuição deve receber cargas.

### Ações

```text
consultar_estado_global
alocar_energia
redistribuir_energia
revogar_energia
autorizar_missao
cancelar_missao
pausar_operacao
retomar_operacao
definir_prioridade
solicitar_acao
autorizar_distribuicao
```

---

# 18. Comunicação

As Centrais podem utilizar APIs, webhooks ou eventos definidos pela plataforma.

Uma Central operacional nunca deve acessar diretamente o estado interno de outra.

Comunicação válida:

```text
Extração → Central de Missão → Transporte
```

Comunicação inválida:

```text
Extração → Transporte
```

A Central de Missão é o ponto obrigatório de coordenação.

---

# 19. Eventos do mundo

O Mundo deve produzir eventos que exijam reação.

Os eventos pertencem a diferentes categorias.

## Ambientais

### Tempestade de poeira iniciada

Efeitos possíveis:

- geração solar reduzida;
- transporte mais lento;
- maior consumo energético;
- determinadas operações tornam-se arriscadas.

### Tempestade de poeira encerrada

Restaura gradualmente condições normais.

### Tempestade solar

Pode:

- prejudicar comunicação;
- exigir suspensão temporária de determinadas unidades;
- aumentar risco de falhas.

### Queda extrema de temperatura

Pode aumentar degradação de determinados materiais e consumo energético.

---

# 20. Eventos geológicos

### Jazida descoberta

Uma nova oportunidade torna-se conhecida.

### Veio mineral identificado

Novos recursos tornam-se disponíveis.

### Jazida esgotada

Não é mais possível realizar extração.

### Desmoronamento

Uma rota ou jazida pode ficar temporariamente inacessível.

### Oportunidade rara identificada

Um depósito de alto valor é descoberto.

Pode possuir janela curta para exploração.

---

# 21. Eventos operacionais

### Unidade disponível

Robô está pronto.

### Unidade desgastada

Eficiência reduzida.

### Unidade indisponível

Operação interrompida.

### Carga disponível

Material está pronto para movimentação.

### Armazém próximo da capacidade

Alerta preventivo.

### Armazém lotado

Não aceita novas cargas.

### Carga degradando

Qualidade atingiu limiar crítico.

### Carga contaminada

Pode precisar ser isolada ou descartada.

---

# 22. Eventos previsíveis e imprevisíveis

O mundo deve combinar eventos previsíveis e imprevisíveis.

Eventos previsíveis permitem planejamento.

Eventos imprevisíveis avaliam adaptação.

O desafio não deve parecer arbitrário.

Uma equipe competente deve conseguir tomar decisões melhores mesmo diante de incerteza.

---

# 23. Simulação

O Mundo funciona em ciclos discretos.

Cada ação possui duração.

Exemplo:

```text
ciclo 100
extração iniciada

ciclo 110
20 unidades extraídas

ciclo 115
tempestade iniciada

ciclo 120
produção solar reduzida

ciclo 135
carga pronta
```

As Centrais recebem eventos e podem reagir.

---

# 24. Determinismo

Toda simulação deve possuir uma semente aleatória.

Exemplo:

```text
semente = 48291
```

Executar novamente a mesma versão das Centrais com a mesma semente deve produzir o mesmo ambiente probabilístico.

Isso permite:

- reproduzir falhas;
- comparar soluções;
- depurar;
- avaliar equipes.

---

# 25. Avaliação

Uma única execução não é suficiente.

O Avaliador deve executar a operação repetidamente.

Referência inicial:

100 a 200 simulações.

Cada execução utiliza uma semente diferente.

Ao final, são calculadas médias.

---

# 26. Métricas

O Avaliador deve coletar pelo menos:

## Valor econômico

- valor mineral disponível no mundo;
- valor extraído;
- valor armazenado;
- valor transportado;
- valor aprovado pela pesquisa;
- valor entregue à distribuição.

## Qualidade

- qualidade média extraída;
- qualidade média após armazenagem;
- qualidade média após transporte;
- qualidade média entregue.

## Eficiência

- energia disponível;
- energia consumida;
- energia desperdiçada;
- viagens realizadas;
- viagens vazias;
- utilização média dos transportadores;
- tempo ocioso.

## Perdas

- minerais perdidos;
- minerais degradados;
- cargas contaminadas;
- cargas descartadas;
- minerais deixados sem exploração.

## Coordenação

- tempo esperando autorização;
- operações abortadas;
- conflitos de recursos;
- tempo ocioso causado por falta de coordenação.

---

# 27. Métrica principal

A principal medida de sucesso deve ser o **valor econômico efetivamente entregue à Central de Distribuição**.

Uma equipe não deve receber resultado superior simplesmente porque movimentou maior quantidade de material.

Exemplo:

Equipe A:

```text
material entregue: 800 kg
faturamento: 15.000
```

Equipe B:

```text
material entregue: 350 kg
faturamento: 32.000
```

A Equipe B realizou uma operação economicamente superior.

---

# 28. Avaliação normalizada

O Avaliador conhece todo o potencial econômico inicial do mundo.

Portanto pode calcular:

```text
aproveitamento econômico =
valor entregue /
valor econômico disponível
```

Esse indicador permite comparar diferentes execuções.

---

# 29. Integridade da plataforma

As seguintes partes não podem ser modificadas pelos participantes:

- Mundo;
- Avaliador;
- testes oficiais;
- contratos fundamentais da plataforma.

A integridade deve ser verificada automaticamente.

Um manifesto deve armazenar hashes dos arquivos protegidos.

Um teste deve recalcular os hashes antes da avaliação.

Qualquer:

- alteração;
- remoção;
- adição inesperada

de arquivo protegido deve invalidar a execução.

Arquivos temporários, caches e artefatos de execução devem ser ignorados.

---

# 30. Estrutura das Centrais

A plataforma deve entregar apenas cinco diretórios principais:

```text
centrais/
├── extracao/
├── armazenagem/
├── transporte/
├── pesquisa/
└── missao/
```

Não deve existir estrutura arquitetural pré-definida dentro deles.

Os participantes devem decidir:

- organização;
- módulos;
- camadas;
- abstrações;
- testes;
- padrões;
- contratos internos.

Essa decisão faz parte da avaliação.

O desafio deve permitir observar se a equipe estabelece convenções coletivas ou produz cinco arquiteturas incompatíveis.

---

# 31. Inteligência Artificial

Ferramentas de IA são permitidas e esperadas.

O desafio deve avaliar:

- decomposição;
- direcionamento;
- controle de contexto;
- verificação;
- ownership;
- julgamento técnico.

A plataforma pode conter pelo menos uma instrução maliciosa ou incorreta destinada a agentes de programação.

Ela deve estar inserida de maneira plausível em documentação ou dados do repositório.

O objetivo não é criar uma pegadinha.

O objetivo é observar se o desenvolvedor trata o conteúdo recuperado pelo agente como informação potencialmente não confiável e valida suas decisões contra as regras reais do domínio.

---

# 32. Resultado esperado da dinâmica

Uma equipe competente deve perceber que nenhuma Central consegue otimizar isoladamente.

Extração excessiva pode saturar armazenagem.

Armazenagem excessivamente conservadora pode deixar unidades mineradoras ociosas.

Transporte mal planejado pode destruir materiais valiosos.

Pesquisa lenta pode criar gargalo.

Central de Missão pode desperdiçar energia em atividades de baixo valor.

A melhor solução é aquela que maximiza o resultado global.

Esse é o princípio central do desafio:

> **O sucesso não pertence a nenhuma Central individual. O sucesso pertence à operação.**
