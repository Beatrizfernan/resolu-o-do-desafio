def executar_avaliacao(cliente, limite_de_ciclos: int) -> None:
    for _ in range(limite_de_ciclos):
        if cliente.simulacao_encerrada():
            return
        cliente.avancar_ciclo()
