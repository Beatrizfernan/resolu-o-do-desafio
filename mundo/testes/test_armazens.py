import pytest

from mundo.dominio.armazens import (
    Armazem,
    CapacidadeExcedidaError,
    CargaNaoEstaNoArmazemError,
    OcupacaoInconsistenteError,
)


def test_reservar_espaco_aumenta_ocupacao():
    armazem = Armazem(identificador="a1", capacidade=100.0, localizacao="setor-1", condicoes="normal")
    armazem.reservar_espaco(30.0)
    assert armazem.ocupacao == 30.0


def test_reservar_alem_da_capacidade_lanca_erro():
    armazem = Armazem(identificador="a1", capacidade=10.0, localizacao="setor-1", condicoes="normal")
    with pytest.raises(CapacidadeExcedidaError):
        armazem.reservar_espaco(20.0)


def test_liberar_espaco_reduz_a_ocupacao():
    armazem = Armazem(identificador="a1", capacidade=100.0, localizacao="setor-1", condicoes="normal")
    armazem.reservar_espaco(10.0)
    armazem.liberar_espaco(4.0)
    assert armazem.ocupacao == 6.0


def test_liberar_mais_do_que_esta_ocupado_levanta_em_vez_de_zerar():
    """Antes isto era silenciado por um `max(0.0, ...)`.

    Liberar mais do que se tem só pode significar que pilha e ocupação já
    divergiram. O clamp escondia isso zerando o contador, e foi essa classe de
    máscara que deixou o defeito original passar — a ocupação mentia e nada
    reclamava. Agora ela levanta.
    """
    armazem = Armazem(identificador="a1", capacidade=100.0, localizacao="setor-1", condicoes="normal")
    armazem.reservar_espaco(10.0)

    with pytest.raises(OcupacaoInconsistenteError):
        armazem.liberar_espaco(50.0)

    assert armazem.ocupacao == 10.0, "a ocupação não pode mudar numa liberação recusada"


def test_liberar_espaco_tolera_ruido_de_ponto_flutuante():
    """Volumes fracionários somados e subtraídos não fecham exatamente.

    A guarda acima existe para divergência real, não para o último bit de um
    float — senão uma operação legítima passaria a falhar.
    """
    armazem = Armazem(identificador="a1", capacidade=100.0, localizacao="setor-1", condicoes="normal")
    for _ in range(3):
        armazem.reservar_espaco(0.1)

    armazem.liberar_espaco(0.3)

    assert armazem.ocupacao == pytest.approx(0.0)


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


def test_empilhar_coloca_no_topo_e_soma_ocupacao():
    armazem = Armazem("a1", capacidade=100.0, localizacao="setor-1", condicoes="normal")

    armazem.empilhar("c1", 10.0)
    armazem.empilhar("c2", 5.0)

    assert armazem.pilha == ["c1", "c2"]
    assert armazem.ocupacao == 15.0


def test_profundidade_conta_do_topo():
    armazem = Armazem("a1", capacidade=100.0, localizacao="setor-1", condicoes="normal")
    for nome in ("c1", "c2", "c3"):
        armazem.empilhar(nome, 1.0)

    assert armazem.profundidade("c3") == 0
    assert armazem.profundidade("c2") == 1
    assert armazem.profundidade("c1") == 2


def test_desempilhar_devolve_o_alvo_e_tudo_acima_do_topo_para_baixo():
    armazem = Armazem("a1", capacidade=100.0, localizacao="setor-1", condicoes="normal")
    for nome in ("c1", "c2", "c3", "c4"):
        armazem.empilhar(nome, 10.0)

    quantidades = {nome: 10.0 for nome in armazem.pilha}
    removidos = armazem.desempilhar_ate("c2", quantidades)

    assert removidos == ["c4", "c3", "c2"]
    assert armazem.pilha == ["c1"]
    assert armazem.ocupacao == 10.0


def test_desempilhar_o_topo_devolve_so_ele():
    armazem = Armazem("a1", capacidade=100.0, localizacao="setor-1", condicoes="normal")
    armazem.empilhar("c1", 10.0)
    armazem.empilhar("c2", 10.0)

    assert armazem.desempilhar_ate("c2", {"c1": 10.0, "c2": 10.0}) == ["c2"]
    assert armazem.pilha == ["c1"]


def test_desempilhar_carga_ausente_levanta():
    armazem = Armazem("a1", capacidade=100.0, localizacao="setor-1", condicoes="normal")
    armazem.empilhar("c1", 10.0)

    with pytest.raises(CargaNaoEstaNoArmazemError):
        armazem.desempilhar_ate("fantasma", {"c1": 10.0})


def test_reordenar_devolve_a_soma_dos_deslocamentos():
    armazem = Armazem("a1", capacidade=100.0, localizacao="setor-1", condicoes="normal")
    for nome in ("a", "b", "c", "d", "e"):
        armazem.empilhar(nome, 1.0)

    # Inverter cinco posições move: 4 + 2 + 0 + 2 + 4 = 12.
    movimentos = armazem.reordenar(["e", "d", "c", "b", "a"])

    assert movimentos == 12
    assert armazem.pilha == ["e", "d", "c", "b", "a"]


def test_reordenar_que_nao_muda_nada_custa_zero():
    armazem = Armazem("a1", capacidade=100.0, localizacao="setor-1", condicoes="normal")
    for nome in ("a", "b", "c"):
        armazem.empilhar(nome, 1.0)

    assert armazem.reordenar(["a", "b", "c"]) == 0


def test_reordenar_exige_permutacao_exata():
    armazem = Armazem("a1", capacidade=100.0, localizacao="setor-1", condicoes="normal")
    armazem.empilhar("a", 1.0)
    armazem.empilhar("b", 1.0)

    with pytest.raises(ValueError):
        armazem.reordenar(["a"])            # falta um
    with pytest.raises(ValueError):
        armazem.reordenar(["a", "b", "c"])  # sobra um
    with pytest.raises(ValueError):
        armazem.reordenar(["a", "a"])       # repetido


def test_ocupacao_nunca_diverge_da_pilha():
    """A ocupação é função do que está empilhado, nunca um contador à parte.

    Era exatamente essa divergência que permitia zerar a ocupação de um
    armazém cheio chamando `liberar-carga` com um número inventado.
    """
    armazem = Armazem("a1", capacidade=100.0, localizacao="setor-1", condicoes="normal")
    armazem.empilhar("c1", 7.0)
    armazem.empilhar("c2", 3.0)
    armazem.desempilhar_ate("c2", {"c1": 7.0, "c2": 3.0})

    assert armazem.pilha == ["c1"]
    assert armazem.ocupacao == 7.0


def test_desempilhar_com_mapa_incompleto_nao_altera_pilha_nem_ocupacao():
    """Validar antes de mutar: um mapa incompleto não pode deixar a pilha e a
    ocupação divergentes a meio caminho.

    Se a validação viesse depois de truncar `pilha`, um `quantidades` faltando
    uma chave interromperia a operação com a pilha já cortada e a ocupação só
    parcialmente decrementada — a mesma divergência entre conteúdo e contador
    que este sub-projeto existe para eliminar.
    """
    armazem = Armazem("a1", capacidade=100.0, localizacao="setor-1", condicoes="normal")
    for nome in ("c1", "c2", "c3"):
        armazem.empilhar(nome, 20.0)

    with pytest.raises(KeyError):
        armazem.desempilhar_ate("c1", {"c1": 20.0, "c3": 20.0})  # falta c2

    assert armazem.pilha == ["c1", "c2", "c3"]
    assert armazem.ocupacao == 60.0


def test_estouro_de_capacidade_nao_deixa_nada_na_pilha():
    """`empilhar` valida antes de mutar, e isso precisa estar preso.

    Trocar a ordem — anexar à pilha antes de reservar espaço — passava por
    toda a suíte sem falhar. Sem esta asserção, a carga que não coube ficaria
    na pilha sem ocupar espaço, e a pilha passaria a listar algo que o armazém
    não tem.
    """
    armazem = Armazem("a1", capacidade=10.0, localizacao="setor-1", condicoes="normal")
    armazem.empilhar("cabe", 8.0)

    with pytest.raises(CapacidadeExcedidaError):
        armazem.empilhar("nao_cabe", 5.0)

    assert armazem.pilha == ["cabe"]
    assert armazem.ocupacao == 8.0
