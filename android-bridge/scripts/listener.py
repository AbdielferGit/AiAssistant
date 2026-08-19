"""
Corre dentro de Termux en el celular. Hace polling al bridge del
orchestrator y ejecuta acciones locales usando Termux:API.

Variables de entorno requeridas: PHONE_BRIDGE_URL, PHONE_BRIDGE_TOKEN.
"""
from __future__ import annotations

import os
import subprocess
import time

import httpx

PHONE_BRIDGE_URL = os.environ["PHONE_BRIDGE_URL"].rstrip("/")
PHONE_BRIDGE_TOKEN = os.environ["PHONE_BRIDGE_TOKEN"]
HEADERS = {"Authorization": f"Bearer {PHONE_BRIDGE_TOKEN}"}
POLL_INTERVAL_SEGUNDOS = 3


def ejecutar_accion(accion: str, parametros: dict) -> dict:
    if accion == "notificar":
        subprocess.run(
            ["termux-notification", "--title", parametros.get("titulo", "AiAsistant"),
             "--content", parametros.get("texto", "")],
            check=False,
        )
        return {"status": "ok"}

    if accion == "leer_bateria":
        salida = subprocess.run(["termux-battery-status"], capture_output=True, text=True)
        return {"status": "ok", "salida": salida.stdout}

    if accion == "hablar":
        subprocess.run(["termux-tts-speak", parametros.get("texto", "")], check=False)
        return {"status": "ok"}

    if accion == "disparar_tasker":
        tarea = parametros.get("tarea", "")
        subprocess.run(
            ["am", "broadcast", "--user", "0", "-a", "net.dinglisch.android.tasker.ACTION_TASK",
             "--es", "task_name", tarea],
            check=False,
        )
        return {"status": "ok", "tarea": tarea}

    return {"status": "error", "detalle": f"acción desconocida: {accion}"}


def loop() -> None:
    print(f"Escuchando comandos de {PHONE_BRIDGE_URL} ...")
    with httpx.Client(timeout=10) as client:
        while True:
            try:
                resp = client.get(f"{PHONE_BRIDGE_URL}/commands/next", headers=HEADERS)
                resp.raise_for_status()
                comando = resp.json().get("comando")
                if comando:
                    resultado = ejecutar_accion(comando["accion"], comando.get("parametros", {}))
                    client.post(
                        f"{PHONE_BRIDGE_URL}/commands/result",
                        headers=HEADERS,
                        json={"comando_id": comando["id"], "resultado": resultado},
                    )
            except httpx.HTTPError as e:
                print(f"Error de red, reintentando: {e}")
            time.sleep(POLL_INTERVAL_SEGUNDOS)


if __name__ == "__main__":
    loop()
