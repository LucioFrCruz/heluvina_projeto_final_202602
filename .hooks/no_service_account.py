#!/usr/bin/env python3
"""Bloqueia commit de JSONs de service account (GCP) e materiais sensíveis.

Diretriz 0.5 do AGENTS.md: zero secrets no Git. O pre-commit passa os arquivos
staged como argumentos; qualquer conteúdo com marcador de service account do GCP
("private_key" / "service_account") aborta o commit.
"""
import re
import sys

PADROES = [
    re.compile(r'"private_key"\s*:'),
    re.compile(r'"type"\s*:\s*"service_account"'),
    re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH |PGP |DSA )?PRIVATE KEY-----'),
]

def main() -> int:
    offenders = []
    for path in sys.argv[1:]:
        try:
            with open(path, encoding="utf-8", errors="ignore") as fh:
                conteudo = fh.read()
        except OSError:
            continue
        if any(p.search(conteudo) for p in PADROES):
            offenders.append(path)
    if offenders:
        print("BLOQUEADO: possível credencial (service account / chave privada) detectada:")
        for path in offenders:
            print(f"  - {path}")
        print("Remova o arquivo do commit ou revogue a credencial. Ver Diretriz 0.5 do AGENTS.md.")
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
