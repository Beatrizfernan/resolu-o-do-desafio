from mundo.dominio.robos import EstadoDoRobo, UnidadeMineradora, UnidadeTransportadora


def test_unidade_mineradora_inicia_disponivel():
    unidade = UnidadeMineradora(
        identificador="m1", estado=EstadoDoRobo.DISPONIVEL,
        energia_necessaria=2, desgaste=0.0, localizacao="base", capacidade=50.0,
    )
    assert unidade.estado == EstadoDoRobo.DISPONIVEL


def test_unidade_transportadora_possui_viagens_disponiveis():
    unidade = UnidadeTransportadora(
        identificador="t1", estado=EstadoDoRobo.DISPONIVEL,
        energia_necessaria=3, desgaste=0.0, localizacao="base", capacidade=100.0,
        viagens_disponiveis=5,
    )
    assert unidade.viagens_disponiveis == 5


def test_estado_do_robo_pode_ser_alterado():
    unidade = UnidadeMineradora(
        identificador="m1", estado=EstadoDoRobo.DISPONIVEL,
        energia_necessaria=2, desgaste=0.0, localizacao="base", capacidade=50.0,
    )
    unidade.estado = EstadoDoRobo.EXECUTANDO
    assert unidade.estado == EstadoDoRobo.EXECUTANDO
