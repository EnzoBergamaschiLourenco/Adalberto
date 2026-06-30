import os
import re
import urllib.parse
from datetime import datetime, timedelta
import requests
import streamlit as st

from dictionaries import MOTORISTA_ID, MOTORISTA_TRANSPORTADORA

def processar_pecas(data_recebimento, assunto, remetente, corpo, anexos, xmls_nfe):
    """
    Executa o processamento para e-mails de Peças com integração via API Umov.me.
    """
    print(f"\n--- [Fluxo Peças] Processando E-mail ---")
    print(f"Assunto: {assunto}")
    
    # 1. Mapeamento de Agent e ServiceLocal (Transportadora) pelo assunto
    agent_id = ""
    service_local_id = ""
    
    # Asseguramos o "lower()" para evitar falhas por letras maiúsculas/minúsculas
    assunto_lower = assunto.lower()
    
    for motorista, m_id in MOTORISTA_ID.items():
        if motorista.lower() in assunto_lower:
            agent_id = m_id
            break
            
    for motorista, transp_id in MOTORISTA_TRANSPORTADORA.items():
        if motorista.lower() in assunto_lower:
            service_local_id = transp_id
            break

    # 2. Extração da Remessa do Corpo do E-mail
    # Regex procura por "remessa(s)" ignorando caixa alta/baixa seguido de 8 números
    match_remessa = re.search(r'(?i)remessas?\s*(\d{8})', corpo)
    remessa = match_remessa.group(1) if match_remessa else ""

    # 3. Extração das NFs e Soma dos Pesos através da lista de XMLs lidos
    notas_fiscais = []
    peso_total = 0.0
    
    for xml_content in xmls_nfe:
        match_nf = re.search(r'<nNF>(\d+)</nNF>', xml_content)
        if match_nf:
            notas_fiscais.append(match_nf.group(1))
            
        match_peso = re.search(r'<pesoB>([\d\.]+)</pesoB>', xml_content)
        if match_peso:
            peso_total += float(match_peso.group(1))

    str_nfs = ", ".join(notas_fiscais)

    # 4. Tratamento de Tempo e Datas
    now = datetime.now()
    time_three_hours_ago = now - timedelta(hours=3)
    hour_formatted = time_three_hours_ago.strftime("%H:%M")
    
    data_formatada = data_recebimento.strftime("%d/%m/%Y")
    
    # Verifica se a data atual é maior que a data de recebimento do e-mail
    tag_baixa_manual = ""
    if now.date() > data_recebimento.date():
        # Inclui o registro customizado ou ajusta situação de campo para sinalizar baixa manual no sistema
        tag_baixa_manual = "<BaixaManual>Sim</BaixaManual>"

    # 5. Montagem do Payload XML
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

    # 6. Requisição HTTP - POST com URL Encode
    try:
        # Acessa a API key utilizando o gerenciamento de Secrets do Streamlit
        api_key = st.secrets["umov_api_key"] 
    except FileNotFoundError:
        # Fallback caso rode fora do ambiente st 
        api_key = "CHAVE_NAO_ENCONTRADA"
        
    url = f"https://tuberfil.umov.me/CenterWeb/api/{api_key}/schedule.xml"
    
    # O encoding para a chave 'data' sendo enviada no body form-urlencoded
    body_data = 'data=' + urllib.parse.quote(xml_payload)
    
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }

    try:
        res = requests.post(url, data=body_data, headers=headers, timeout=60)
        print(f"Umov.me Requisição finalizada. Status: {res.status_code}")
        # print(res.text) # Caso precise debugar o retorno do servidor deles
    except Exception as e:
        print(f"Erro ao enviar requisição para Umov.me: {e}")