from mundo.motor.comandos import Comando, FilaDeComandos


def test_drenar_retorna_comandos_na_ordem_de_chegada_e_esvazia_fila():
    fila = FilaDeComandos()
    execucoes = []
    fila.enfileirar(Comando("a", "extracao", {}, lambda: execucoes.append("a")))
    fila.enfileirar(Comando("b", "transporte", {}, lambda: execucoes.append("b")))

    comandos = fila.drenar()

    assert [c.tipo for c in comandos] == ["a", "b"]
    assert fila.drenar() == []
