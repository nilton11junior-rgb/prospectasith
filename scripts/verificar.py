#!/usr/bin/env python3
"""Verificação única do Prospecta: sintaxe, testes, JavaScript da tela, tamanho de arquivo e segredos no git.

Não liga serviços, não fala com WhatsApp, Google ou IA e não altera arquivos.

    python -X utf8 scripts/verificar.py
"""
import os, shutil, subprocess, sys

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
LIMITE_LINHAS = 400  # referência do toolkit: 350; acima de 400 vira aviso para dividir por responsabilidade
IGNORAR = {".git", "engine", "dados", "__pycache__", "node_modules", ".venv"}
PROIBIDOS_NO_GIT = (".env", "painel/dados/")  # dados pessoais e segredos nunca vão para o repositório

falhas, avisos = [], []


def arquivos(ext):
    for raiz, dirs, nomes in os.walk(RAIZ):
        dirs[:] = [d for d in dirs if d not in IGNORAR]
        for n in nomes:
            if n.endswith(ext):
                yield os.path.join(raiz, n)


def rel(p):
    return os.path.relpath(p, RAIZ).replace(os.sep, "/")


def etapa(nome, ok, detalhe=""):
    print(f"{'✓' if ok else '✗'} {nome}{(' — ' + detalhe) if detalhe else ''}")
    if not ok:
        falhas.append(nome)


def main():
    # 1) sintaxe Python
    erros = []
    for p in arquivos(".py"):
        try:  # compila em memória: não grava .pyc
            with open(p, encoding="utf-8") as f:
                compile(f.read(), p, "exec")
        except SyntaxError as e:
            erros.append(f"{rel(p)}:{e.lineno}: {e.msg}")
    etapa("Sintaxe Python", not erros, "; ".join(erros))

    # 2) testes (scripts/ e painel/)
    for pasta in ("scripts", "painel"):
        r = subprocess.run([sys.executable, "-X", "utf8", "-m", "unittest", "discover", "-s", pasta, "-p", "test_*.py"],
                           cwd=RAIZ, capture_output=True, text=True, encoding="utf-8")
        resumo = [l for l in (r.stderr or "").splitlines() if l.startswith(("Ran ", "OK", "FAILED"))]
        etapa(f"Testes {pasta}/", r.returncode == 0, " ".join(resumo) or r.stderr[-300:])

    # 3) JavaScript da tela (precisa do Node; sem ele, avisa e segue)
    node = shutil.which("node")
    if node:
        erros = []
        for p in arquivos(".js"):
            r = subprocess.run([node, "--check", p], capture_output=True, text=True)
            if r.returncode:
                msg = next((l for l in r.stderr.splitlines() if "Error" in l), "erro de sintaxe")
                erros.append(f"{rel(p)}: {msg.strip()}")
        etapa("Sintaxe JavaScript", not erros, "; ".join(erros))
    else:
        avisos.append("Node não encontrado: sintaxe do JavaScript não verificada")

    # 4) tamanho de arquivo (aviso, não falha)
    for ext in (".py", ".js", ".css", ".html"):
        for p in arquivos(ext):
            with open(p, encoding="utf-8", errors="replace") as f:
                n = sum(1 for _ in f)
            if n > LIMITE_LINHAS and not rel(p).startswith(("docs/",)):
                avisos.append(f"{rel(p)} tem {n} linhas (referência {LIMITE_LINHAS})")

    # 5) segredos e dados pessoais fora do git
    if shutil.which("git") and os.path.isdir(os.path.join(RAIZ, ".git")):
        r = subprocess.run(["git", "ls-files"], cwd=RAIZ, capture_output=True, text=True, encoding="utf-8")
        vazados = [f for f in r.stdout.splitlines() if f == ".env" or f.startswith(PROIBIDOS_NO_GIT[1])]
        etapa("Segredos e dados fora do git", not vazados, ", ".join(vazados))
    else:
        avisos.append("Sem git: checagem de segredos versionados não rodou")

    for a in avisos:
        print(f"! {a}")
    print("\nResultado:", "OK" if not falhas else f"FALHOU ({', '.join(falhas)})")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
