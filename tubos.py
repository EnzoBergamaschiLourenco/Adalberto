import os

def processar_tubos(assunto: str, remetente: str, corpo: str, anexos: list):
    """
    Executa o processamento específico para e-mails de Tubos.
    anexos: lista de dicionários contendo {'filename': str, 'content': bytes}
    """
    print(f"\n--- [Fluxo Tubos] Processando E-mail ---")
    print(f"Assunto: {assunto}")
    print(f"Remetente: {remetente}")
    
    diretorio_destino = "dados_tubos"
    os.makedirs(diretorio_destino, exist_ok=True)
    
    for anexo in anexos:
        caminho_arquivo = os.path.join(diretorio_destino, anexo["filename"])
        with open(caminho_arquivo, "wb") as f:
            f.write(anexo["content"])
        print(f"Anexo de Tubos salvo em: {caminho_arquivo}")
        
    # TODO: Incluir aqui as regras de negócio ou chamadas de extração de dados