import os
import re
import urllib.parse
from datetime import datetime, timedelta
import requests
import streamlit as st

from dictionaries import MOTORISTA_ID, MOTORISTA_TRANSPORTADORA

def processar_pecas(data_recebimento, assunto, remetente, corpo, anexos, xmls_nfe):
    """
    Executa o processamento e retorna um dicionário com os resultados obtidos.
    """
    agent_id = ""
    service_local_id = ""
    assunto_lower = assunto.lower()
    
    for motorista, m_id in MOTORISTA_ID.items():
        if motorista.lower() in assunto_lower:
            agent_id = m_id
            break
            
    for motorista, transp_id in MOTORISTA_TRANSPORTADORA.items():
        if motorista.lower() in assunto_lower:
            service_local_id = transp_id
            break

    match_remessa = re.search(r'(?i)remessas?\s*(\d{8})', corpo)
    remessa = match_remessa.group(1) if match_remessa else "Não encontrada"

    notas_fiscais = []
    peso_total = 0.0
    
    for xml_content in xmls_nfe:
        match_nf = re.search(r'<nNF>(\d+)</nNF>', xml_content)
        if match_nf:
            notas_fiscais.append(match_nf.group(1))
            
        match_peso = re.search(r'<pesoB>([\d\.]+)</pesoB>', xml_content)
        if match_peso:
            peso_total += float(match_peso.group(1))

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
        <situation><id>30</id></situation>
        <customFields>
            <Remessa>{remessa}</Remessa>
            <NF>{str_nfs}</NF>
            <Peso>{peso_total:.2f}</Peso>
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
        res = requests.post(url, data=body_data, headers=headers, timeout=60)
        status_umov = f"HTTP {res.status_code}"
        resposta_umov = res.text
    except Exception as e:
        status_umov = "Erro de Conexão"
        resposta_umov = str(e)
        
    # Retorna o compilado com todas as informações tratadas e respostas das APIs
    return {
        "tipo": "Peças",
        "remessa": remessa,
        "nfs": str_nfs,
        "peso_total": round(peso_total, 3),
        "agent_id": agent_id,
        "service_local_id": service_local_id,
        "xml_enviado": xml_payload,
        "status_umov": status_umov,
        "resposta_umov": resposta_umov
    }