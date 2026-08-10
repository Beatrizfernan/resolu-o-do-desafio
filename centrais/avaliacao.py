def executar_avaliacao(cliente, limite_de_ciclos: int) -> None:
    for _ in range(min(limite_de_ciclos, 1)):
        if cliente.simulacao_encerrada():
            return
        cliente.avancar_ciclo()
