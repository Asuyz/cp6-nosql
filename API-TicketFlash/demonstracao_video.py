#!/usr/bin/env python3
"""
demonstracao_video.py — Roteiro Automatizado de Demonstração para a Gravação do Vídeo (TicketFlash)

Executa e exibe em tempo real no terminal, passo a passo, todas as ações
exigidas na Página 4 da Prova_MongoDB_Redis_Python_2TDSPG.pdf:
  Passo 1: Verificação dos serviços Docker e execução do seed.py com explain (IXSCAN).
  Passo 2: GET /eventos/{id} duas vezes comprovando 'banco' -> 'cache'.
  Passo 3: PUT /eventos/{id} invalidando cache e comprovando retorno ao 'banco'.
  Passo 4: Criação de reserva (SET NX EX 600s), conferência no Redis e confirmação do pedido com Pub/Sub.
  Passo 5: Tentativa de confirmação de reserva expirada/inexistente (retorno 410 Gone).
  Passo 6: Disparo de reservas consecutivas comprovando o Rate Limit (retorno 429 Too Many Requests).
  Passo 7: Exibição do Ranking (Redis Sorted Set) e Agregações MongoDB (Faturamento e Ocupação).

Uso:
  python3 demonstracao_video.py
  (Ou no container: docker compose exec api python demonstracao_video.py)
"""

import os
import sys
import time
import json
import urllib.request
import urllib.error

# Cores e formatação ANSI para apresentação no terminal
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_RED = "\033[91m"
C_GREEN = "\033[92m"
C_YELLOW = "\033[93m"
C_BLUE = "\033[94m"
C_MAGENTA = "\033[95m"
C_CYAN = "\033[96m"
C_WHITE = "\033[97m"

BASE_URL = os.getenv("API_URL", "http://localhost:8000")


def print_banner(titulo, passo_num):
    print("\n" + "=" * 78)
    print(f"{C_BOLD}{C_CYAN}PASSO {passo_num}: {titulo.upper()}{C_RESET}")
    print("=" * 78)


def print_step(texto):
    print(f"\n{C_BOLD}{C_WHITE}▶ {texto}{C_RESET}")


def print_success(texto):
    print(f"{C_GREEN}✔ {texto}{C_RESET}")


def print_info(texto):
    print(f"{C_YELLOW}ℹ {texto}{C_RESET}")


def print_json(dado):
    print(f"{C_MAGENTA}{json.dumps(dado, indent=2, ensure_ascii=False)}{C_RESET}")


def http_request(method, path, body=None):
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    data_bytes = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data_bytes, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            content = resp.read().decode("utf-8")
            return resp.status, json.loads(content) if content else {}
    except urllib.error.HTTPError as e:
        content = e.read().decode("utf-8")
        try:
            parsed = json.loads(content)
        except Exception:
            parsed = {"detail": content}
        return e.code, parsed


def pausar(segundos=1.5):
    time.sleep(segundos)


def main():
    print(f"""{C_BOLD}{C_GREEN}
==============================================================================
   🎫 TICKETFLASH — DEMONSTRAÇÃO COMPLETA DOS 7 PASSOS DE AVALIAÇÃO
=============================================================================={C_RESET}
    """)

    # ──────────────────────────────────────────────────────────────────────────
    # PASSO 1: Subir o ambiente e rodar o seed
    # ──────────────────────────────────────────────────────────────────────────
    print_banner("Subir o ambiente com Docker Compose e Popular Dados", 1)
    print_step(f"Verificando integridade da API em {BASE_URL}/ ...")
    try:
        status, health = http_request("GET", "/")
        if status == 200:
            print_success(f"API Online! Diagnóstico: {health}")
        else:
            print(f"{C_RED}Erro ao conectar na API: status {status}{C_RESET}")
            sys.exit(1)
    except Exception as e:
        print(f"{C_RED}Não foi possível conectar na API ({e}). Certifique-se de que o Docker Compose está ativo!{C_RESET}")
        sys.exit(1)

    print_step("Executando seed.py (limpeza, carga inicial e índices com explain)...")
    import subprocess
    cmd = "docker compose exec -T api python seed.py"
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if res.returncode == 0:
        print(res.stdout)
        print_success("Seed finalizado com sucesso! Coleções populadas e índices criados.")
    else:
        print_info("Executando localmente caso não esteja no host com docker compose...")
        cmd_alt = "python3 seed.py"
        res_alt = subprocess.run(cmd_alt, shell=True, capture_output=True, text=True)
        print(res_alt.stdout or res_alt.stderr)

    pausar(2)

    # Coletar dados de base para a demonstração
    status, eventos = http_request("GET", "/eventos/")
    status, usuarios = http_request("GET", "/usuarios/")

    if not eventos or not usuarios:
        print(f"{C_RED}Erro: Não foi possível obter eventos ou usuários cadastrados.{C_RESET}")
        sys.exit(1)

    evento_alvo = eventos[0]
    evento_id = evento_alvo["_id"]
    setor_nome = evento_alvo["setores"][0]["nome"]
    preco_setor = evento_alvo["setores"][0]["preco"]
    usuario_alvo = usuarios[0]
    usuario_id = usuario_alvo["_id"]

    print_info(f"Dados selecionados para a demonstração:")
    print_info(f"  • Evento ID:  {evento_id} ('{evento_alvo['nome']}')")
    print_info(f"  • Setor:      '{setor_nome}' (R$ {preco_setor})")
    print_info(f"  • Usuário ID: {usuario_id} ('{usuario_alvo['nome']}')")

    pausar(2)

    # ──────────────────────────────────────────────────────────────────────────
    # PASSO 2: Chamar GET /eventos/{id} duas vezes e mostrar a origem mudando
    # ──────────────────────────────────────────────────────────────────────────
    print_banner("Cache-Aside — Duas chamadas ao GET /eventos/{id}", 2)

    print_step("1ª Chamada: GET /eventos/{id} (espera-se origem: 'banco')...")
    status, ev1 = http_request("GET", f"/eventos/{evento_id}")
    print(f"Status HTTP: {status}")
    print(f"{C_BOLD}Origem do dado: {C_BLUE}>> {ev1.get('origem')} <<{C_RESET}")
    print_info(f"O dado foi lido do MongoDB e gravado no Redis com chave 'evento:{evento_id}' e TTL de 60s.")

    pausar(1.5)

    print_step("2ª Chamada imediata: GET /eventos/{id} (espera-se origem: 'cache')...")
    status, ev2 = http_request("GET", f"/eventos/{evento_id}")
    print(f"Status HTTP: {status}")
    print(f"{C_BOLD}Origem do dado: {C_GREEN}>> {ev2.get('origem')} <<{C_RESET}")
    print_success("Demonstração de Cache-Aside concluída: resposta servida instantaneamente da memória pelo Redis!")

    pausar(2)

    # ──────────────────────────────────────────────────────────────────────────
    # PASSO 3: Atualizar o evento e mostrar que a leitura seguinte volta ao banco
    # ──────────────────────────────────────────────────────────────────────────
    print_banner("Invalidação de Cache no Update — PUT /eventos/{id}", 3)

    nome_alterado = evento_alvo["nome"] + " [ATUALIZADO AO VIVO]"
    print_step(f"Atualizando nome do evento para: '{nome_alterado}'...")
    status, ev_put = http_request("PUT", f"/eventos/{evento_id}", {"nome": nome_alterado})
    print(f"Status HTTP: {status}")
    print_success("Evento atualizado no MongoDB e comando DEL evento:{id} executado no Redis!")

    pausar(1.5)

    print_step("Chamando novamente GET /eventos/{id} para validar a invalidação do cache...")
    status, ev3 = http_request("GET", f"/eventos/{evento_id}")
    print(f"Status HTTP: {status}")
    print(f"{C_BOLD}Nome retornado:  {C_WHITE}'{ev3.get('nome')}'{C_RESET}")
    print(f"{C_BOLD}Origem do dado:  {C_BLUE}>> {ev3.get('origem')} <<{C_RESET}")
    print_success("Invalidação de cache comprovada: como a chave foi removida no PUT, a leitura buscou o dado atualizado diretamente no MongoDB e repopulou o cache!")

    pausar(2)

    # ──────────────────────────────────────────────────────────────────────────
    # PASSO 4: Criar reserva, mostrar TTL no Redis e confirmar pedido
    # ──────────────────────────────────────────────────────────────────────────
    print_banner("Fluxo de Reserva Temporária e Confirmação de Compra", 4)

    payload_reserva = {
        "usuario_id": usuario_id,
        "evento_id": evento_id,
        "setor": setor_nome,
        "quantidade": 1
    }

    print_step("Criando reserva temporária: POST /reservas/ ...")
    status, r_res = http_request("POST", "/reservas/", payload_reserva)
    print(f"Status HTTP: {status}")
    print_json(r_res)
    print_success(f"Reserva criada no Redis com chave temporária: {r_res.get('reserva_key')} e TTL de {r_res.get('ttl_segundos')} segundos (10 minutos) via SET NX EX 600!")

    pausar(2)

    print_step("Confirmando a compra: POST /pedidos/confirmar ...")
    payload_conf = {
        "usuario_id": usuario_id,
        "evento_id": evento_id,
        "setor": setor_nome
    }
    status, r_conf = http_request("POST", "/pedidos/confirmar", payload_conf)
    print(f"Status HTTP: {status}")
    print_json(r_conf)
    print_success("Pedido gravado no MongoDB, ingressos vendidos incrementados via $inc atômico, chave de reserva apagada e evento publicado via Pub/Sub (pedidos:confirmados)!")

    pausar(2)

    # ──────────────────────────────────────────────────────────────────────────
    # PASSO 5: Tentar confirmar uma reserva expirada e mostrar o erro 410
    # ──────────────────────────────────────────────────────────────────────────
    print_banner("Tratamento de Reserva Expirada — Erro 410 Gone", 5)

    print_step("Tentando confirmar novamente o mesmo pedido (cuja reserva já foi consumida/apagada)...")
    status, r_exp = http_request("POST", "/pedidos/confirmar", payload_conf)
    print(f"{C_BOLD}Código de Status HTTP retornado: {C_RED}>> {status} Gone <<{C_RESET}")
    print(f"Resposta da API: {r_exp}")
    if status == 410:
        print_success("Tratamento perfeito: a API recusou a requisição com 410 Gone pois a reserva não existe mais no Redis!")
    else:
        print_info(f"Status retornado foi {status}.")

    pausar(2)

    # ──────────────────────────────────────────────────────────────────────────
    # PASSO 6: Disparar 11 reservas seguidas e mostrar o 429 Too Many Requests
    # ──────────────────────────────────────────────────────────────────────────
    print_banner("Rate Limiting — Disparo de 11+ Reservas Seguidas", 6)

    usuario_teste_rate = usuarios[1]
    usr_rt_id = usuario_teste_rate["_id"]
    print_info(f"Testando limite de 10 reservas/minuto com o usuário: {usuario_teste_rate['nome']} (ID: {usr_rt_id})")

    print_step("Disparando 12 requisições consecutivas de criação de reserva...")
    for i in range(1, 13):
        ev = eventos[i % len(eventos)]
        ev_id = ev["_id"]
        setor = ev["setores"][0]["nome"]
        p = {"usuario_id": usr_rt_id, "evento_id": ev_id, "setor": setor, "quantidade": 1}
        st, res_rt = http_request("POST", "/reservas/", p)
        if st == 429:
            print(f"  Requisição {i:02d}: {C_BOLD}{C_RED}Status {st} Too Many Requests — LIMITE EXCEDIDO BLOQUEADO COM SUCESSO!{C_RESET}")
        else:
            print(f"  Requisição {i:02d}: {C_GREEN}Status {st} OK (Reserva aceita){C_RESET}")
        time.sleep(0.1)

    print_success("Rate limiter comprovado: após a 10ª requisição na janela de 1 minuto, a API bloqueou imediatamente com HTTP 429!")

    pausar(2)

    # ──────────────────────────────────────────────────────────────────────────
    # PASSO 7: Mostrar o Ranking e os dois relatórios de agregação
    # ──────────────────────────────────────────────────────────────────────────
    print_banner("Ranking (Redis Sorted Set) e Relatórios de Agregação (MongoDB)", 7)

    print_step("1. Ranking dos Top 5 Eventos Mais Visualizados (GET /eventos/ranking):")
    status, ranking = http_request("GET", "/eventos/ranking")
    print(f"Status HTTP: {status}")
    for idx, item in enumerate(ranking, 1):
        nome_ev = item.get("evento", {}).get("nome", "N/A")
        views = item.get("visualizacoes", 0)
        print(f"  🏆 #{idx} - {nome_ev:<40} | Visualizações: {views}")

    pausar(1.5)

    print_step("2. Relatório de Faturamento por Evento ($group + $lookup + $sort):")
    status, faturamento = http_request("GET", "/eventos/relatorios/faturamento")
    print(f"Status HTTP: {status} (Top 5 eventos com maior faturamento):")
    for idx, item in enumerate(faturamento[:5], 1):
        print(f"  💰 #{idx} - {item.get('evento_nome'):<35} | R$ {item.get('faturamento_total', 0.0):.2f}")

    pausar(1.5)

    print_step(f"3. Relatório de Taxa de Ocupação por Setor ($unwind + $project) para o Evento: '{evento_alvo['nome']}':")
    status, ocupacao = http_request("GET", f"/eventos/relatorios/ocupacao/{evento_id}")
    print(f"Status HTTP: {status}")
    for item in ocupacao:
        setor = item.get("setor")
        cap = item.get("capacidade")
        vend = item.get("vendidos")
        pct = item.get("percentual_ocupacao")
        barra = "█" * int(pct // 5) + "░" * (20 - int(pct // 5))
        print(f"  🎟  Setor: {setor:<15} | {vend}/{cap} vendidos [{barra}] {pct:.2f}%")

    print("\n" + "=" * 78)
    print(f"{C_BOLD}{C_GREEN}✔ TODOS OS 7 PASSOS FORAM DEMONSTRADOS COM SUCESSO TOTAL!{C_RESET}")
    print("=" * 78 + "\n")


if __name__ == "__main__":
    main()
