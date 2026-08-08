from __future__ import annotations

from fastapi import APIRouter

from .dependencias import obter_motor

router = APIRouter(prefix="/missao", tags=["missao"])


@router.get("/estado")
def consultar_estado_global() -> dict:
    motor = obter_motor()
    return {"ciclo_atual": motor.ciclo_atual}
