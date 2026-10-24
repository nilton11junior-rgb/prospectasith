#!/usr/bin/env python3
"""Liga o Prospecta inteiro no Windows, sem Docker: motor de busca, WhatsApp (WAHA) e painel.

Cada serviço só sobe se a porta dele ainda estiver livre, então rodar de novo não duplica nada.
Logs em painel/dados/logs/. Ctrl+C (ou fechar a janela) desliga o que este script ligou.

    python scripts/iniciar.py [--sem-navegador]
"""
import os, secrets, shutil, socket, subprocess, sys, time, webbrowser

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
DADOS = os.path.join(RAIZ, "painel", "dados")
LOGS = os.path.join(DADOS, "logs")
os.makedirs(LOGS, exist_ok=True)
SEM_JANELA = getattr(subprocess, "CREATE_NO_WINDOW", 0)
# PATH pode não ter o Docker logo após instalar: cai no caminho padrão do Docker Desktop
DOCKER = shutil.which("docker") or os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Docker", "Docker", "resources", "bin", "docker.exe")


def segredo(nome):
    caminho = os.path.join(DADOS, nome)
    if not os.path.exists(caminho) or not open(caminho, encoding="utf-8").read().strip():
        with open(caminho, "w", encoding="utf-8") as f:
            f.write(secrets.token_hex(32))
    return open(caminho, encoding="utf-8").read().strip()


def porta_ocupada(p):
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", p)) == 0


def espera_porta(p, nome, seg=90):
    for _ in range(seg * 2):
        if porta_ocupada(p):
            return True
        time.sleep(0.5)
    print(f"  ⚠ {nome} não respondeu na porta {p} — veja painel/dados/logs/")
    return False


def docker_ok():
    # "docker info" pode levar quase 1 min numa máquina ocupada; a lista de pipes responde na hora
    # (os.path.exists não enxerga named pipes no Windows)
    try:
        return "dockerDesktopLinuxEngine" in os.listdir(r"\\.\pipe" + "\\")
    except OSError:
        return False


def liga_docker():
    """Abre o Docker Desktop se preciso e espera o daemon (até 5 min)."""
    if docker_ok():
        return True
    exe = os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Docker", "Docker", "Docker Desktop.exe")
    if not os.path.exists(exe):
        print("• WhatsApp: Docker Desktop não instalado (o WhatsApp interno não vai funcionar)")
        return False
    print("• Docker Desktop: abrindo (pode levar alguns minutos)…")
    os.startfile(exe)  # igual a dois cliques: o Docker continua aberto mesmo se esta janela fechar
    for _ in range(150):
        time.sleep(2)
        if docker_ok():
            return True
    print("  ⚠ Docker não ficou pronto em 5 min. Abra o Docker Desktop e rode o Prospeccao.cmd de novo.")
    return False


filhos = []

def sobe(nome, porta, cmd, cwd=RAIZ, env=None):
    if porta_ocupada(porta):
        print(f"• {nome}: já está rodando (porta {porta})")
        return
    print(f"• {nome}: ligando…")
    log = open(os.path.join(LOGS, f"{nome.lower().split()[0]}.log"), "a", encoding="utf-8")
    p = subprocess.Popen(cmd, cwd=cwd, env={**os.environ, **(env or {})}, stdout=log, stderr=subprocess.STDOUT,
                         creationflags=SEM_JANELA)
    filhos.append((nome, p))
    if espera_porta(porta, nome):
        print(f"  ✓ {nome} pronto em http://127.0.0.1:{porta}")


def main():
    py = sys.executable
    # 1) motor de busca do Google Maps (binário nativo)
    motor = os.path.join(RAIZ, "engine", "google-maps-scraper.exe")
    if os.path.exists(motor):
        sobe("Motor de busca", 8080, [motor, "-web", "-addr", "127.0.0.1:8080", "-data-folder", os.path.join(RAIZ, "engine", "gmapsdata")])
    else:
        print("• Motor de busca: engine/google-maps-scraper.exe não encontrado (buscas não vão rodar)")

    # 2) WhatsApp (WAHA no Docker Desktop)
    if porta_ocupada(3000):
        print("• WhatsApp WAHA: já está rodando (porta 3000)")
    elif liga_docker():
        print("• WhatsApp WAHA: ligando container…")
        for tentativa in range(4):  # logo após abrir, o Docker pode recusar por alguns segundos
            r = subprocess.run([DOCKER, "compose", "-f", os.path.join(RAIZ, "whatsapp", "docker-compose.yml"), "up", "-d"],
                               env={**os.environ, "WAHA_API_KEY": segredo("waha_key")}, capture_output=True, text=True,
                               creationflags=SEM_JANELA)
            if not r.returncode:
                break
            time.sleep(15)
        if r.returncode:
            print("  ⚠ docker compose falhou:", (r.stderr or r.stdout)[-400:])
        elif espera_porta(3000, "WhatsApp WAHA", 180):
            print("  ✓ WhatsApp WAHA pronto em http://127.0.0.1:3000")

    # 3) painel
    sobe("Painel", 8090, [py, "-X", "utf8", os.path.join(RAIZ, "painel", "server.py"), "--sem-navegador"])
    print("\nProspecta no ar: http://localhost:8090   (feche esta janela para desligar)")
    if "--sem-navegador" not in sys.argv:
        webbrowser.open("http://localhost:8090")
    try:
        while True:
            time.sleep(5)
            for nome, p in filhos:
                if p.poll() is not None:
                    print(f"⚠ {nome} parou (código {p.returncode}). Veja painel/dados/logs/.")
                    filhos.remove((nome, p))
                    break
    except KeyboardInterrupt:
        pass
    finally:
        for nome, p in filhos:
            p.terminate()


if __name__ == "__main__":
    main()
