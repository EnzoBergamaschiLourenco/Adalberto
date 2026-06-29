import os

def processar_pecas(assunto: str, remetente: str, corpo: str, anexos: list):
    """
    Executa o processamento específico para e-mails de Peças.
    anexos: lista de dicionários contendo {'filename': str, 'content': bytes}
    """
    # Exemplo de processamento / Logs no terminal da aplicação
    print(f"\n--- [Fluxo Peças] Processando E-mail ---")
    print(f"Assunto: {assunto}")
    print(f"Remetente: {remetente}")
    
    # Criar pasta para salvar os arquivos de processamento, caso queira
    diretorio_destino = "dados_pecas"
    os.makedirs(diretorio_destino, exist_ok=True)
    
    # Salvando os anexos fisicamente
    for anexo in anexos:
        caminho_arquivo = os.path.join(diretorio_destino, anexo["filename"])
        with open(caminho_arquivo, "wb") as f:
            f.write(anexo["content"])
        print(f"Anexo de Peças salvo em: {caminho_arquivo}")
        
    # TODO: Incluir aqui as regras de negócio ou chamadas de extração de dados