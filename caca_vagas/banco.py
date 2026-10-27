"""Acesso ao banco do site (Cloudflare D1) pela API HTTP, para o que roda fora do Worker."""

import os

import httpx

BANCO_ID = "860b0c40-6e57-4bf4-8057-4c5ea08cc27d"


def d1(sql: str, params: list | None = None) -> list[dict]:
    conta = os.environ["CLOUDFLARE_ACCOUNT_ID"]
    resposta = httpx.post(
        f"https://api.cloudflare.com/client/v4/accounts/{conta}/d1/database/{BANCO_ID}/query",
        headers={"Authorization": f"Bearer {os.environ['CLOUDFLARE_API_TOKEN']}"},
        json={"sql": sql, "params": params or []},
        timeout=30,
    )
    resposta.raise_for_status()
    return resposta.json()["result"][0]["results"]
