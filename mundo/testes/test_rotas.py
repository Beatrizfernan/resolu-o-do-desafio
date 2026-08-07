from mundo.dominio.rotas import CondicaoDaRota, Rota


def test_rota_inicia_livre_por_padrao():
    rota = Rota(identificador="r1", origem="setor-1", destino="central-distribuicao",
                 distancia=10.0, tempo_base=5, risco=0.1)
    assert rota.condicao == CondicaoDaRota.LIVRE


def test_rota_pode_ser_interditada():
    rota = Rota(identificador="r1", origem="setor-1", destino="central-distribuicao",
                 distancia=10.0, tempo_base=5, risco=0.1)
    rota.condicao = CondicaoDaRota.INTERDITADA
    assert rota.condicao == CondicaoDaRota.INTERDITADA
