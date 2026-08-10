IMAGEM_AVALIADOR ?= operacao-marte-avaliador
SEEDS ?= 1,2,3,4,5
LIMITE_DE_CICLOS ?= 100
RELATORIO ?= docs/relatorios/avaliacao-container.md
MANIFESTO_TEMPORARIO ?= /tmp/manifesto-avaliacao.json

.PHONY: avaliar-container docker-build

docker-build:
	docker build -t $(IMAGEM_AVALIADOR) .

avaliar-container: docker-build
	mkdir -p $(dir $(RELATORIO))
	docker run --rm \
		-v "$(PWD)/docs/relatorios:/app/docs/relatorios" \
		$(IMAGEM_AVALIADOR) \
		sh -lc 'python -c "from pathlib import Path; from integridade.manifesto import gerar_manifesto; gerar_manifesto(Path(\"/app\"), Path(\"$(MANIFESTO_TEMPORARIO)\"))" && python -m avaliador.cli --seeds "$(SEEDS)" --limite-de-ciclos "$(LIMITE_DE_CICLOS)" --manifesto "$(MANIFESTO_TEMPORARIO)" --saida "$(RELATORIO)" --mostrar-relatorio'
