# Central de Transporte

Sua responsabilidade e mover cargas da jazida ate a base escolhendo o modo que preserva mais valor liquido.

## O que esta central controla

- qual transportadora usar;
- para onde enviar cada carga;
- qual modo de transporte escolher.

## O que voce consegue observar

- cargas prontas para transporte;
- estado das unidades transportadoras;
- modo disponivel para cada viagem;
- eventos de conclusao e falha;
- estimativa de composicao das jazidas que a Pesquisa ja sondou.

## O que voce nao sabe daqui

- qualidade exata da carga antes de a Pesquisa analisa-la;
- se a Missao vai continuar abastecendo sua central depois desta viagem.

## Vantagens

- define o tempo que a carga passa exposta;
- pode capturar muito valor ao usar modo urgente no lugar certo.

## Desvantagens e cuidados

- transporte rapido custa mais;
- transporte lento degrada mais a carga;
- excesso de viagens mal escolhidas consome sua frota sem retorno proporcional.

## Estrategias validas

- usar a estimativa de composicao da jazida de origem para inferir potencial economico esperado;
- tratar `alta` ou `media` presenca de minerais raros como sinal de prioridade maior;
- aceitar modo economico quando a composicao estimada indicar baixo potencial ou quando o gargalo real estiver na Pesquisa.

## APIs e informacoes mais importantes

- endpoints da Central de Transporte do mundo;
- eventos `extracao_concluida`, `transporte_concluido` e `operacao_invalida`;
- `GET /pesquisa/jazidas/{identificador}/estimativa` para conhecer a jazida de origem quando a sondagem existir.

## Armadilhas do dominio

- um algoritmo que sempre escolhe `urgente` quebra a economia da operacao;
- um algoritmo que sempre escolhe `economico` pode destruir o valor do raro antes da analise;
- sem integrar com Pesquisa e Missao, o Transporte vira um otimizador local ruim.
