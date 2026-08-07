import pytest

from mundo.dominio.armazens import Armazem, CapacidadeExcedidaError


def test_reservar_espaco_aumenta_ocupacao():
    armazem = Armazem(identificador="a1", capacidade=100.0, localizacao="setor-1", condicoes="normal")
    armazem.reservar_espaco(30.0)
    assert armazem.ocupacao == 30.0


def test_reservar_alem_da_capacidade_lanca_erro():
    armazem = Armazem(identificador="a1", capacidade=10.0, localizacao="setor-1", condicoes="normal")
    with pytest.raises(CapacidadeExcedidaError):
        armazem.reservar_espaco(20.0)


def test_liberar_espaco_reduz_ocupacao_sem_ir_negativo():
    armazem = Armazem(identificador="a1", capacidade=100.0, localizacao="setor-1", condicoes="normal")
    armazem.reservar_espaco(10.0)
    armazem.liberar_espaco(50.0)
    assert armazem.ocupacao == 0.0


def test_compativel_com_vazio_aceita_qualquer_mineral():
    armazem = Armazem(identificador="a1", capacidade=100.0, localizacao="setor-1", condicoes="normal")
    assert armazem.compativel_com("hematita") is True


def test_compativel_com_lista_restrita():
    armazem = Armazem(
        identificador="a1", capacidade=100.0, localizacao="setor-1", condicoes="normal",
        compatibilidades={"hematita"},
    )
    assert armazem.compativel_com("hematita") is True
    assert armazem.compativel_com("jarosita") is False
