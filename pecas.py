import os
import re
import urllib.parse
from datetime import datetime, timedelta
import requests
import streamlit as st

from dictionaries import MOTORISTA_ID, MOTORISTA_TRANSPORTADORA, CNPJ_SERVICELOCAL

def processar_pecas(data_recebimento, assunto, remetente, corpo, anexos, xmls_nfe):
    """
    Executa o processamento e retorna um dicionário com os resultados obtidos.
    """
    agent_id = ""
    service_local_id = ""
    transportadora = ""
    assunto_lower = assunto.lower()
    
    # Identificação por assunto
    for motorista, m_id in MOTORISTA_ID.items():
        if motorista.lower() in assunto_lower:
            agent_id = m_id
            break
            
    for motorista, transp_id in MOTORISTA_TRANSPORTADORA.items():
        if motorista.lower() in assunto_lower:
            transportadora = transp_id
            break

    match_remessa = re.search(r'(?i)remessas?\s*(\d{8})', corpo)
    remessa = match_remessa.group(1) if match_remessa else "Não encontrada"

    notas_fiscais = []
    peso_total = 0.0
    
    for xml_content in xmls_nfe:
        # Pega notas fiscais ignorando namespaces e maiúsculas/minúsculas
        match_nf = re.search(r'<(?:\w+:)?nNF>(\d+)</(?:\w+:)?nNF>', xml_content, re.IGNORECASE)
        if match_nf:
            notas_fiscais.append(match_nf.group(1))
            
        # Pega peso ignorando namespaces
        match_peso = re.search(r'<(?:\w+:)?pesoB>([\d\.]+)</(?:\w+:)?pesoB>', xml_content, re.IGNORECASE)
        if match_peso:
            peso_total += float(match_peso.group(1))
            
        # NOVA ESTRATÉGIA CNPJ: Pega todos os CNPJs do XML e cruza com o dicionário
        todos_cnpjs = re.findall(
                r'<(?:\w+:)?CNPJ[^>]*>\s*([\d]+)\s*</(?:\w+:)?CNPJ>',
                xml_content,
                re.IGNORECASE | re.DOTALL
            )
        for cnpj in todos_cnpjs:
            cnpj = re.sub(r'\D', '', cnpj)
            cnpj_limpo = cnpj.lstrip("0")

            if cnpj in CNPJ_SERVICELOCAL:
                service_local_id = CNPJ_SERVICELOCAL[cnpj]
                break

            if cnpj_limpo in CNPJ_SERVICELOCAL:
                service_local_id = CNPJ_SERVICELOCAL[cnpj_limpo]
                break
                
        # NOVA ESTRATÉGIA TRANSPORTADORA: Ignora namespaces, atributos extras e case
        if not transportadora:
            match_transp = re.search(
                r'<(?:\w+:)?transporta[^>]*>.*?<(?:\w+:)?xNome[^>]*>(.*?)</(?:\w+:)?xNome>', 
                xml_content, 
                re.IGNORECASE | re.DOTALL
            )
            if match_transp:
                transportadora = match_transp.group(1).strip()

    str_nfs = ", ".join(notas_fiscais) if notas_fiscais else "Nenhuma"

    now = datetime.now()
    time_three_hours_ago = now - timedelta(hours=3)
    hour_formatted = time_three_hours_ago.strftime("%H:%M")
    data_formatada = data_recebimento.strftime("%Y-%m-%d")
    
    tag_baixa_manual = ""
    if now.date() > data_recebimento.date():
        tag_baixa_manual = "<BaixaManual>Sim</BaixaManual>"

    xml_payload = f"""<schedule>
        <agent><id>{agent_id}</id></agent>
        <serviceLocal><id>{service_local_id}</id></serviceLocal>
        <activitiesOrigin>7</activitiesOrigin>
        <date>{data_formatada}</date>
        <hour>{hour_formatted}</hour>
        <customFields>
            <CF_Remessa>{remessa}</CF_Remessa>
            <NF>{str_nfs}</NF>
            <Peso>{peso_total:.2f}</Peso>
            <transportadora>{transportadora}</transportadora>
            {tag_baixa_manual}
        </customFields>
        <scheduleType>
            <id>96897</id>
        </scheduleType>
    </schedule>""".strip()

    try:
        api_key = st.secrets["umov_api_key"] 
    except:
        api_key = "CHAVE_NAO_ENCONTRADA"
        
    url = f"https://tuberfil.umov.me/CenterWeb/api/{api_key}/schedule.xml"
    body_data = 'data=' + urllib.parse.quote(xml_payload)
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}

    status_umov = "Não Enviado"
    resposta_umov = ""
    
    try:
        res = requests.post(url, data=body_data, headers=headers, timeout=15)
        status_umov = f"HTTP {res.status_code}"
        resposta_umov = res.text
    except Exception as e:
        status_umov = "Erro de Conexão"
        resposta_umov = str(e)
        
    # =====================================================================
    # NOVA LÓGICA: Buscar e atualizar Schedules com BaixaManual=Sim
    # =====================================================================
    if api_key != "CHAVE_NAO_ENCONTRADA":
        url_get = f"https://tuberfil.umov.me/CenterWeb/api/{api_key}/schedule.xml?BaixaManual=Sim"
        try:
            # 1. Faz o GET para pegar os registros
            res_get = requests.get(url_get, timeout=15)
            
            if res_get.status_code == 200:
                # Extrai todos os IDs numéricos usando regex
                ids_encontrados = re.findall(r'<entry\s+id="(\d+)"', res_get.text, re.IGNORECASE)
                
                # Monta o payload de atualização apenas uma vez
                xml_atualizacao = """<schedule>\n<situation><id>50</id></situation>\n</schedule>"""
                body_atualizacao = 'data=' + urllib.parse.quote(xml_atualizacao)
                
                # 2. Faz o POST para cada ID encontrado
                for schedule_id in ids_encontrados:
                    url_post_atualizacao = f"https://tuberfil.umov.me/CenterWeb/api/{api_key}/schedule/{schedule_id}.xml"
                    requests.post(url_post_atualizacao, data=body_atualizacao, headers=headers, timeout=15)
                    
        except Exception as e:
            # Em caso de falha nesta rotina secundária, evitamos travar a execução principal.
            # O log de erro pode ser adicionado aqui, se necessário.
            pass
    # =====================================================================
    # FIM DA NOVA LÓGICA
    # =====================================================================
        
    return {
        "tipo": "Peças",
        "remessa": remessa,
        "nfs": str_nfs,
        "peso_total": round(peso_total, 3),
        "agent_id": agent_id,
        "service_local_id": service_local_id,
        "transportadora": transportadora,
        "xml_enviado": xml_payload,
        "status_umov": status_umov,
        "resposta_umov": resposta_umov
    }