import requests

def search_agregados(keyword):
    url = "https://servicodados.ibge.gov.br/api/v3/agregados"
    response = requests.get(url)
    data = response.json()
    
    results = []
    for pesquisa in data:
        for agregado in pesquisa['agregados']:
            if keyword.lower() in agregado['nome'].lower() or keyword.lower() in pesquisa['nome'].lower():
                results.append(f"Pesquisa: {pesquisa['nome']} | Tabela {agregado['id']}: {agregado['nome']}")
    return results[:20]

print("=== Populacao ===")
for r in search_agregados("população residente"):
    if "2022" in r or "Censo" in r:
        print(r)

