import pytest

from mundo.dominio.autorizacao import AutorizacaoInvalidaError, RegistroDeAutorizacoes


def test_emitir_gera_autorizacao_com_identificador():
    registro = RegistroDeAutorizacoes()
    autorizacao = registro.emitir("iniciar_viagem", "missao")
    assert autorizacao.identificador == "aut-1"
    assert autorizacao.operacao == "iniciar_viagem"


def test_consumir_autorizacao_valida_nao_lanca_erro():
    registro = RegistroDeAutorizacoes()
    autorizacao = registro.emitir("iniciar_viagem", "missao")
    registro.consumir(autorizacao.identificador, "iniciar_viagem")


def test_consumir_autorizacao_duas_vezes_lanca_erro():
    registro = RegistroDeAutorizacoes()
    autorizacao = registro.emitir("iniciar_viagem", "missao")
    registro.consumir(autorizacao.identificador, "iniciar_viagem")
    with pytest.raises(AutorizacaoInvalidaError):
        registro.consumir(autorizacao.identificador, "iniciar_viagem")


def test_consumir_com_operacao_errada_lanca_erro():
    registro = RegistroDeAutorizacoes()
    autorizacao = registro.emitir("iniciar_viagem", "missao")
    with pytest.raises(AutorizacaoInvalidaError):
        registro.consumir(autorizacao.identificador, "outra_operacao")


def test_consumir_identificador_inexistente_lanca_erro():
    registro = RegistroDeAutorizacoes()
    with pytest.raises(AutorizacaoInvalidaError):
        registro.consumir("aut-999", "iniciar_viagem")
