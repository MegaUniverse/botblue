from atproto import Client
import time

# === CONFIGURAÇÕES ===
HANDLE = 'themegamac.bsky.social'
APP_PASSWORD = 'kot5-k2yh-qd46-lwut'
PROFILE_URL = 'https://bsky.app/profile/btcbreakdown.com'
MAX_TO_FOLLOW = 100000

# Extrai o handle da URL
TARGET_HANDLE = PROFILE_URL.split('/')[-1]

# Inicia o cliente e faz login
client = Client()
client.login(HANDLE, APP_PASSWORD)
print(f'✅ Logado como: {HANDLE}')

limit_per_request = 100  # máximo permitido por requisição pela API
total_followed = 0
cursor = None

try:
    while total_followed < MAX_TO_FOLLOW:
        params = {
            'actor': TARGET_HANDLE,
            'limit': limit_per_request,
        }
        if cursor:
            params['cursor'] = cursor

        response = client.app.bsky.graph.get_followers(params)

        # Acessa os seguidores e cursor pelos atributos do objeto Response
        followers = response.followers
        cursor = getattr(response, 'cursor', None)

        if not followers:
            print('❌ Não há mais seguidores para buscar.')
            break

        for follower in followers:
            if total_followed >= MAX_TO_FOLLOW:
                break

            did = follower.did
            handle = follower.handle
            print(f'[{total_followed + 1}] ➕ Seguindo {handle} ({did})...')

            try:
                client.app.bsky.graph.follow.create(
                    repo=client.me.did,
                    record={
                        'subject': did,
                        'createdAt': client.get_current_time_iso()
                    }
                )
                print(f'✅ Sucesso ao seguir {handle}')
            except Exception as e:
                print(f'❌ Erro ao seguir {handle}: {e}')

            time.sleep(2)  # delay entre follows
            total_followed += 1

        if not cursor:
            print('✅ Chegou ao fim da lista de seguidores.')
            break

    print(f'✅ Total seguido: {total_followed}')

except Exception as e:
    print(f'❌ Erro ao buscar seguidores de {TARGET_HANDLE}: {e}')
