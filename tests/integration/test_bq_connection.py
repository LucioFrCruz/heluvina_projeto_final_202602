import os
from google.cloud import bigquery
from google.api_core.exceptions import Conflict
import json

def run_smoke_test():
    from dotenv import load_dotenv
    load_dotenv()
    
    credential_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    project_id = os.environ.get("GCP_PROJECT_ID")
    
    if not credential_path or not os.path.exists(credential_path):
        print(f"❌ GOOGLE_APPLICATION_CREDENTIALS não configurada ou arquivo não encontrado: {credential_path}")
        return
        
    if not project_id:
        print("❌ GCP_PROJECT_ID não configurado no .env")
        return

    print(f"✅ Autenticando com a conta de serviço no projeto: {project_id}")
    
    # Inicializa o cliente do BigQuery
    client = bigquery.Client(project=project_id)
    
    # 1. Criação do Dataset
    dataset_id = f"{project_id}.ipb_staging"
    dataset = bigquery.Dataset(dataset_id)
    dataset.location = "US"  # Conforme exigência do projeto (Free Tier)
    
    try:
        dataset = client.create_dataset(dataset, timeout=30)
        print(f"✅ Dataset {dataset_id} criado com sucesso na região {dataset.location}.")
    except Conflict:
        print(f"⚠️ Dataset {dataset_id} já existe na região US.")
    except Exception as e:
        print(f"❌ Erro ao criar o dataset: {e}")
        return

    # 2. Criação da Tabela Temporária
    table_id = f"{dataset_id}.tabela_teste_temporaria"
    schema = [
        bigquery.SchemaField("id", "INTEGER", mode="REQUIRED"),
        bigquery.SchemaField("mensagem", "STRING", mode="REQUIRED"),
    ]
    table = bigquery.Table(table_id, schema=schema)
    
    print(f"⏳ Criando tabela de teste: {table_id}...")
    try:
        table = client.create_table(table)
        print("✅ Tabela criada com sucesso.")
    except Conflict:
        print("⚠️ Tabela já existia. Recriando...")
        client.delete_table(table_id)
        table = client.create_table(table)
    except Exception as e:
        print(f"❌ Erro ao criar tabela: {e}")
        return

    # 3. Inserção de uma linha (Teste de Escrita)
    rows_to_insert = [
        {"id": 1, "mensagem": "Smoke test funcionando perfeitamente!"}
    ]
    print("⏳ Inserindo dados na tabela...")
    errors = client.insert_rows_json(table_id, rows_to_insert)
    if not errors:
        print("✅ Nova linha inserida com sucesso.")
    else:
        print(f"❌ Erro ao inserir linha: {errors}")
        return
        
    # 4. Leitura da linha inserida (Teste de Leitura) via Query
    print("⏳ Lendo dados da tabela via Query...")
    query = f"SELECT * FROM `{table_id}`"
    query_job = client.query(query)
    
    results = list(query_job.result())
    print("\n--- Resultado da Query ---")
    for row in results:
        print(f"ID: {row.id} | Mensagem: {row.mensagem}")
    print("--------------------------\n")
    
    # 5. Limpeza (Deletando a tabela de teste)
    print(f"⏳ Removendo tabela temporária {table_id}...")
    client.delete_table(table_id, not_found_ok=True)
    print("✅ Limpeza concluída. Smoke test finalizado com SUCESSO!")

if __name__ == "__main__":
    run_smoke_test()
