# Central de Extracao

Sua responsabilidade e transformar jazidas em cargas exploraveis pelo restante da operacao.

## O que esta central controla

- escolha da unidade mineradora;
- escolha da jazida;
- quantidade a ser extraida;
- modo de extracao.

## O que voce consegue observar

- lista de jazidas e seus identificadores;
- mineral predominante de cada jazida;
- quantidade restante;
- dificuldade de extracao;
- risco da jazida;
- estado das unidades mineradoras.

## O que voce nao sabe daqui

- qualidade final da carga antes da Pesquisa analisar;
- estimativa de composicao da jazida antes de a Pesquisa sondar;
- se o Transporte vai conseguir preservar bem a carga depois.

## Vantagens

- e a porta de entrada do faturamento;
- permite acelerar ou segurar a producao conforme energia, desgaste e gargalos seguintes.

## Desvantagens e cuidados

- desgaste dos robos cresce com a operacao;
- modos mais agressivos podem custar mais energia e castigar mais a unidade;
- extrair demais sem coordenação pode saturar Pesquisa, Transporte ou Armazenagem.

## Estrategias validas

- modular o ritmo de extracao para nao inundar o sistema;
- priorizar jazidas cujo mineral predominante pareca compativel com a janela atual de energia e transporte;
- combinar o que a Missao sabe sobre saldo com o que a Pesquisa descobriu sobre composicao.

## APIs mais importantes

- `GET /extracao/jazidas`
- `GET /extracao/jazidas/{identificador}`
- `POST /extracao/iniciar-extracao`
- `POST /extracao/interromper-extracao`
- `POST /extracao/retornar-unidade`

## Armadilhas do dominio

- operacao invalida continua custando ciclo e coordenação;
- jazidas esvaziadas ficam mais caras de explorar indiretamente pela escassez;
- uma carga extraida no momento errado pode degradar antes de achar destino.
