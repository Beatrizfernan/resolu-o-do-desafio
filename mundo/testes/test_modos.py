from pathlib import Path

import pytest

from mundo.dominio.modos import CatalogoDeModos, ModoDeExtracao, ModoDeTransporte

CAMINHO_MODOS = Path(__file__).parent.parent / "config" / "modos.json"


def _catalogo() -> CatalogoDeModos:
    return CatalogoDeModos.carregar_de_arquivo(CAMINHO_MODOS)


def test_carrega_os_tres_modos_de_extracao():
    catalogo = _catalogo()
    for modo in ModoDeExtracao:
        assert catalogo.obter_extracao(modo) is not None


def test_carrega_os_tres_modos_de_transporte():
    catalogo = _catalogo()
    for modo in ModoDeTransporte:
        assert catalogo.obter_transporte(modo) is not None


def test_perfil_de_extracao_agressivo_desperdica_mais_e_gasta_menos():
    catalogo = _catalogo()
    cuidadoso = catalogo.obter_extracao(ModoDeExtracao.CUIDADOSO)
    agressivo = catalogo.obter_extracao(ModoDeExtracao.AGRESSIVO)
    assert agressivo.fator_desperdicio > cuidadoso.fator_desperdicio
    assert agressivo.mult_energia < cuidadoso.mult_energia
    assert agressivo.qualidade_inicial < cuidadoso.qualidade_inicial
    assert agressivo.mult_duracao < cuidadoso.mult_duracao


def test_perfil_de_transporte_rapido_gasta_mais_e_degrada_menos():
    catalogo = _catalogo()
    economico = catalogo.obter_transporte(ModoDeTransporte.ECONOMICO)
    rapido = catalogo.obter_transporte(ModoDeTransporte.RAPIDO)
    assert rapido.mult_energia > economico.mult_energia
    assert rapido.mult_duracao < economico.mult_duracao
    assert rapido.mult_degradacao < economico.mult_degradacao


def test_multiplicador_por_local():
    catalogo = _catalogo()
    assert catalogo.mult_do_local("em_jazida") == 2.0
    assert catalogo.mult_do_local("em_armazem") == 1.0
    assert catalogo.mult_do_local("entregue") == 0.0


def test_fator_base_de_energia_disponivel():
    assert _catalogo().fator_base_de_energia == 0.2


def test_fator_de_escassez_cresce_conforme_a_jazida_esvazia():
    catalogo = _catalogo()
    assert catalogo.fator_de_escassez(1.0) == 1.0
    assert catalogo.fator_de_escassez(0.5) > catalogo.fator_de_escassez(1.0)
    assert catalogo.fator_de_escassez(0.1) > catalogo.fator_de_escassez(0.5)


def test_fator_de_escassez_e_sempre_positivo_e_finito():
    catalogo = _catalogo()
    for fracao in (0.0, 1e-12, 0.5, 1.0):
        fator = catalogo.fator_de_escassez(fracao)
        assert 1.0 <= fator <= catalogo.fator_escassez_maximo


def test_local_desconhecido_lanca_erro():
    with pytest.raises(ValueError):
        _catalogo().mult_do_local("inexistente")
