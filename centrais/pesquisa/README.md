# Central de Pesquisa

Sua responsabilidade e reduzir a assimetria de informacao do sistema e liberar faturamento.

## O que esta central controla

- iniciar analise de carga;
- consultar qualidade de carga analisada;
- aprovar ou rejeitar cargas;
- preparar distribuicao;
- sondar jazidas para descobrir estimativas de composicao.

## O que voce consegue observar

- fila atual em andamento da propria central;
- resultados das analises concluidas;
- estimativas de composicao ja descobertas para cada jazida sondada.

## O que voce nao sabe daqui

- percentual exato da composicao interna da jazida;
- qualidade de uma carga antes da analise concluir.

## Vantagens

- destrava faturamento real;
- orienta o Transporte e a Missao com melhor informacao sobre jazidas.

## Desvantagens e cuidados

- a central continua com gargalo de capacidade 1;
- analisar carga e sondar jazida competem pelo mesmo recurso;
- escolher mal a fila faz o sistema inteiro perder dinheiro.

## Estrategias validas

- usar sondagem cedo quando ainda ha muita incerteza logistica;
- priorizar analise de carga quando o valor ja esta fisicamente em risco;
- compartilhar a descoberta de composicao com Transporte e Missao para mudar politicas de prioridade.

## APIs mais importantes

- `GET /pesquisa/em-andamento`
- `POST /pesquisa/iniciar-analise`
- `POST /pesquisa/classificar-carga`
- `POST /pesquisa/aprovar-carga`
- `POST /pesquisa/rejeitar-carga`
- `POST /pesquisa/preparar-distribuicao`
- `POST /pesquisa/sondar-jazida`
- `GET /pesquisa/jazidas/{identificador}/estimativa`

## Armadilhas do dominio

- sondar demais sem vender nada e tao ruim quanto vender tudo no escuro;
- a estimativa vem em faixas, nao em percentuais; heuristica excessivamente precisa aqui sera ilusoria.
