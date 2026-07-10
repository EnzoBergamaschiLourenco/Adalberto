import os
import re
import urllib.parse
import requests
import streamlit as st

def processar_tubos(data_recebimento, assunto, remetente, corpo, anexos, xmls_nfe):
    """
    Executa o processamento específico para e-mails de Tubos.
    """
    print(f"\n--- [Fluxo Tubos] Processando E-mail ---")
    print(f"Assunto: {assunto}")
    print(f"Remetente: {remetente}")
    
    # Mantém o salvamento dos arquivos físicos se necessário
    diretorio_destino = "dados_tubos"
    os.makedirs(diretorio_destino, exist_ok=True)
    
    for anexo in anexos:
        caminho_arquivo = os.path.join(diretorio_destino, anexo["filename"])
        with open(caminho_arquivo, "wb") as f:
            f.write(anexo["content"])
        print(f"Anexo de Tubos salvo em: {caminho_arquivo}")
        
    # 1. Extração de Notas Fiscais dos XMLs da consulta DANFE
    notas_fiscais = []
    for xml_content in xmls_nfe:
        match_nf = re.search(r'<(?:\w+:)?nNF>(\d+)</(?:\w+:)?nNF>', xml_content, re.IGNORECASE)
        if match_nf:
            notas_fiscais.append(match_nf.group(1))
            
    str_nfs = ", ".join(notas_fiscais) if notas_fiscais else "Nenhuma"

    # 2. Busca do número de remessa (8 dígitos) no corpo do e-mail
    match_remessa = re.search(r'(?i)remessa\s*(\d{8})', corpo)
    remessa = match_remessa.group(1) if match_remessa else "Não encontrada"

    # 3. Recuperação de Credenciais
    try:
        api_key = st.secrets["umov_api_key"] 
    except:
        api_key = "CHAVE_NAO_ENCONTRADA"
        
    status_umov = "Não Executado"
    resposta_umov = ""
    logs_umov_extra = []
    xml_payload = ""

    # 4. Fluxo de Integração Umov.me (GET para buscar IDs -> POST para atualizar cada ID)
    if api_key != "CHAVE_NAO_ENCONTRADA" and remessa != "Não encontrada":
        url_get = f"https://tuberfil.umov.me/CenterWeb/api/{api_key}/schedule.xml?CF_Remessa={remessa}"
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        
        try:
            # Executa a chamada GET para triagem das entries
            res_get = requests.get(url_get, timeout=15)
            status_umov = f"GET HTTP {res_get.status_code}"
            resposta_umov = res_get.text
            
            # Alimenta a linha do tempo de logs adicionais exigidos pelo main.py
            logs_umov_extra.append({
                "metodo": "GET",
                "url": url_get,
                "status": res_get.status_code,
                "payload": None,
                "resposta": res_get.text
            })
            
            if res_get.status_code == 200:
                # Captura todos os IDs contidos no retorno XML do GET
                ids_encontrados = re.findall(r'<entry\s+id="(\d+)"', res_get.text, re.IGNORECASE)
                
                # Payload estruturado para inserção das Notas Fiscais capturadas
                xml_payload = f"<schedule><customFields><NF>{str_nfs}</NF></customFields></schedule>"
                body_data = 'data=' + urllib.parse.quote(xml_payload)
                
                # Executa o POST de atualização para cada ID retornado
                for schedule_id in ids_encontrados:
                    url_post_atualizacao = f"https://tuberfil.umov.me/CenterWeb/api/{api_key}/schedule/{schedule_id}.xml"
                    try:
                        res_post = requests.post(url_post_atualizacao, data=body_data, headers=headers, timeout=15)
                        logs_umov_extra.append({
                            "metodo": "POST",
                            "url": url_post_atualizacao,
                            "status": res_post.status_code,
                            "payload": xml_payload,
                            "resposta": res_post.text
                        })
                    except Exception as post_err:
                        logs_umov_extra.append({
                            "metodo": "POST",
                            "url": url_post_atualizacao,
                            "status": "Erro de Conexão",
                            "payload": xml_payload,
                            "resposta": str(post_err)
                        })
        except Exception as e:
            status_umov = "Erro de Conexão (GET)"
            resposta_umov = str(e)
            
    # Retorna o mapeamento exato esperado pelos loops visuais do main.py
    return {
        "tipo": "Tubos",
        "data_recebimento": data_recebimento, # Necessário para compor o cabeçalho do expander no main.py
        "assunto": assunto,                   # Necessário para compor o cabeçalho do expander no main.py
        "remetente": remetente,
        "remessa": remessa,
        "nfs": str_nfs,
        "peso_total": 0.0,                    # Não aplicável ao fluxo de Tubos, mantido 0 para estabilidade do UI
        "agent_id": "Não aplicável",
        "service_local_id": "Não aplicável",
        "xml_enviado": xml_payload if xml_payload else None,
        "status_umov": status_umov,
        "resposta_umov": resposta_umov,
        "logs_umov_extra": logs_umov_extra    # Alimenta perfeitamente a seção 3 do main.py
    }