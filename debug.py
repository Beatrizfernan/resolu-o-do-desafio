import pytest
import sys
import os

from mundo.testes.test_dominancia_de_armazenagem import _operar, _ordem_de_entrega, SORTIMENTO
from mundo.api.dependencias import instancia_do_mundo

def test_debug():
    entrega = _ordem_de_entrega()
    liquido = _operar(list(reversed(entrega)), entrega)
    
    motor = instancia_do_mundo.obter_motor()
    for e in motor.eventos.consultar_eventos():
        print(e)
    
if __name__ == "__main__":
    pytest.main(["-s", "debug.py"])
