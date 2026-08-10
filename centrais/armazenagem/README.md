# Central de Armazenagem

Sua responsabilidade e estabilizar cargas e organizar a pilha sem transformar cada retirada em prejuizo.

## O que esta central controla

- recebimento de carga;
- ordem de empilhamento;
- retirada de carga quando outra central precisa usar o material.

## O que voce consegue observar

- ocupacao do armazem;
- ordem atual da pilha;
- custos implicitos de desenterrar cargas mais antigas.

## O que voce nao sabe daqui

- qualidade exata da carga antes da analise;
- valor final de uma carga ainda nao distribuida.

## Vantagens

- reduz a degradacao comparada ao material largado fora do armazem;
- permite segurar cargas ate a Pesquisa ou o Transporte terem capacidade.

## Desvantagens e cuidados

- a estrutura e LIFO estrita;
- reorganizar errado custa energia e movimentos;
- manter muito volume guardado tambem cobra manutencao.

## Estrategias validas

- empilhar prevendo ordem futura de saida;
- deixar mais acessivel o que tende a degradar primeiro ou o que ja foi priorizado pela Pesquisa;
- evitar usar o armazem como deposito sem criterio.

## APIs mais importantes

- endpoints da Central de Armazenagem do mundo;
- eventos de capacidade, ocupacao e entrega de carga.

## Armadilhas do dominio

- guardar tudo pode ser tao ruim quanto nao guardar nada;
- retirar o item errado da base da pilha transforma uma boa carga em passivo energetico.
