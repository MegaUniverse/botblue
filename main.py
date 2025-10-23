# main.py
import os
import time
import threading
import logging
from flask import Flask, jsonify
from atproto import Client

# -----------------------
# CONFIGURAÇÃO / VARS
# -----------------------
HANDLE = os.getenv('BLUESKY_HANDLE')                 # ex: themegamac.bsky.social
APP_PASSWORD = os.getenv('BLUESKY_APP_PASSWORD')     # App Password do Bluesky
PROFILE_URL = os.getenv('BLUESKY_PROFILE_URL')       # ex: https://bsky.app/profile/camarotedacpi.bsky.social
MAX_TO_FOLLOW = int(os.getenv('MAX_TO_FOLLOW', '100000'))

if not (HANDLE and APP_PASSWORD and PROFILE_URL):
    raise RuntimeError(
        "Faltam variáveis de ambiente. Defina BLUESKY_HANDLE, BLUESKY_APP_PASSWORD e BLUESKY_PROFILE_URL."
    )

TARGET_HANDLE = PROFILE_URL.rstrip('/').split('/')[-1]

# -----------------------
# LOGGING
# -----------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
log = logging.getLogger("bluesky-bot")

# -----------------------
# ESTADO COMPARTILHADO P/ STATUS HTTP
# -----------------------
state = {
    "logged_in_as": None,
    "target": TARGET_HANDLE,
    "total_followed": 0,
    "last_error": None,
    "last_cursor": None,
}

# -----------------------
# FLASK (mantém serviço vivo no Render Free)
# -----------------------
app = Flask(__name__)

@app.route("/")
def home():
    return jsonify({
        "status": "running",
        "logged_in_as": state["logged_in_as"],
        "target": state["target"],
        "total_followed": state["total_followed"],
        "last_error": state["last_error"],
        "last_cursor": state["last_cursor"],
    })

def run_web():
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)

# -----------------------
# LÓGICA DO BOT
# -----------------------
def login_with_retry(max_retries=5, delay=5):
    client = Client()
    for attempt in range(1, max_retries + 1):
        try:
            client.login(HANDLE, APP_PASSWORD)
            state["logged_in_as"] = HANDLE
            log.info(f"✅ Logado como: {HANDLE}")
            return client
        except Exception as e:
            state["last_error"] = str(e)
            log.error(f"Tentativa {attempt}/{max_retries} de login falhou: {e}")
            if attempt < max_retries:
                time.sleep(delay)
    raise RuntimeError("Não foi possível autenticar no Bluesky após múltiplas tentativas.")

def follow_loop():
    """
    Loop principal:
    - Pagina seguidores do TARGET_HANDLE
    - Segue cada um (respeitando delay)
    - Quando terminar a lista, aguarda e recomeça (para captar novos)
    """
    client = login_with_retry()
    limit_per_request = 100  # limite da API por requisição

    while True:
        try:
            total_followed = 0
            cursor = None

            while total_followed < MAX_TO_FOLLOW:
                params = {"actor": TARGET_HANDLE, "limit": limit_per_request}
                if cursor:
                    params["cursor"] = cursor

                response = client.app.bsky.graph.get_followers(params)
                followers = getattr(response, "followers", [])
                cursor = getattr(response, "cursor", None)
                state["last_cursor"] = cursor

                if not followers:
                    log.info("❌ Não há mais seguidores para buscar agora.")
                    break

                for follower in followers:
                    if total_followed >= MAX_TO_FOLLOW:
                        break

                    did = follower.did
                    handle = follower.handle
                    idx = state["total_followed"] + 1
                    log.info(f"[{idx}] ➕ Seguindo {handle} ({did})...")

                    try:
                        client.app.bsky.graph.follow.create(
                            repo=client.me.did,
                            record={
                                "subject": did,
                                "createdAt": client.get_current_time_iso(),
                            },
                        )
                        log.info(f"✅ Sucesso ao seguir {handle}")
                    except Exception as e:
                        state["last_error"] = str(e)
                        log.warning(f"❌ Erro ao seguir {handle}: {e}")

                    time.sleep(2)  # delay entre follows (ajuste se necessário)
                    total_followed += 1
                    state["total_followed"] += 1

                if not cursor:
                    log.info("✅ Chegou ao fim da lista de seguidores.")
                    break

            log.info(f"✅ Total seguido nesta rodada: {total_followed} | Total geral: {state['total_followed']}")
            # Aguarda antes de reiniciar uma nova varredura (capta novos seguidores no futuro)
            time.sleep(15 * 60)  # 15 minutos

        except Exception as e:
            state["last_error"] = str(e)
            log.error(f"❌ Erro no loop principal: {e}")
            # Reautentica após erro e segue
            time.sleep(10)
            try:
                client = login_with_retry()
            except Exception as e2:
                state["last_error"] = str(e2)
                log.error(f"Falha ao relogar: {e2}. Tentando novamente em 30s...")
                time.sleep(30)

# -----------------------
# ENTRADA
# -----------------------
if __name__ == "__main__":
    # Sobe o servidor web em uma thread (mantém o serviço vivo no Render Free)
    threading.Thread(target=run_web, daemon=True).start()
    # Roda o loop do bot na thread principal
    follow_loop()
