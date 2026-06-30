import imaplib
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime
import datetime
import os
import re
import io
import requests
import base64
import pdfplumber

from pecas import processar_pecas
from tubos import processar_tubos

def decodificar_texto(texto):
    """Decodifica cabeçalhos de e-mail codificados (MIME)."""
    if not texto:
        return ""
    partes_decodificadas = decode_header(texto)
    resultado = []
    for dado, codificacao in partes_decodificadas:
        if isinstance(dado, bytes):
            resultado.append(dado.decode(codificacao or "utf-8", errors="ignore"))
        else:
            resultado.append(str(dado))
    return "".join(resultado)

def extrair_xmls_dos_pdfs(anexos):
    """Lê PDFs, extrai a chave de acesso e busca o XML. Retorna (xmls, logs)."""
    xmls_extraidos = []
    logs_danfe = []
    
    for anexo in anexos:
        if anexo["filename"].lower().endswith(".pdf"):
            log_item = {"arquivo": anexo["filename"], "chave": "Não encontrada", "status": "Não consultado", "sucesso": False}
            try:
                with pdfplumber.open(io.BytesIO(anexo["content"])) as pdf:
                    texto_pagina = pdf.pages[0].extract_text()
                    
                    if texto_pagina:
                        texto_limpo = texto_pagina.replace(" ", "").replace("\n", "")
                        match = re.search(r'\b\d{44}\b', texto_limpo)
                        
                        if match:
                            chave = match.group(0)
                            log_item["chave"] = chave
                            
                            res = requests.post(
                                'https://consultadanfe.com/api/v1/consulta',
                                json={'chave': chave},
                                headers={'Content-Type': 'application/json'},
                                timeout=15
                            )
                            
                            log_item["status"] = res.status_code
                            if res.status_code == 200:
                                base64_xml = res.text
                                b64_str = re.sub(r'[^A-Za-z0-9+/]', '', base64_xml)
                                padding = len(b64_str) % 4
                                if padding:
                                    b64_str += '=' * (4 - padding)
                                
                                xml_decodificado = base64.b64decode(b64_str).decode('utf-8', errors='ignore')
                                xmls_extraidos.append(xml_decodificado)
                                log_item["sucesso"] = True
                            else:
                                log_item["erro"] = res.text
            except Exception as e:
                log_item["status"] = "Erro interno"
                log_item["erro"] = str(e)
            
            logs_danfe.append(log_item)
                
    return xmls_extraidos, logs_danfe

def parse_emails(username, password, start_date, end_date):
    IMAP_SERVER = "email-ssl.com.br"
    PORT = 993
    
    mail = imaplib.IMAP4_SSL(IMAP_SERVER, PORT)
    mail.login(username, password)
    mail.select("INBOX")
    
    imap_start = start_date.strftime("%d-%b-%Y")
    imap_end = (end_date + datetime.timedelta(days=1)).strftime("%d-%b-%Y")
    
    search_criterion = f'(SINCE "{imap_start}" BEFORE "{imap_end}")'
    status, messages = mail.search(None, search_criterion)
    
    relatorio_processamento = []
    
    if status != "OK" or not messages[0]:
        mail.logout()
        return relatorio_processamento
        
    email_ids = messages[0].split()
    
    for e_id in reversed(email_ids):
        res, data = mail.fetch(e_id, "(RFC822)")
        if res != "OK":
            continue
            
        for response_part in data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                
                assunto = decodificar_texto(msg["Subject"])
                remetente = decodificar_texto(msg["From"])
                
                data_header = msg.get("Date")
                try:
                    data_recebimento = parsedate_to_datetime(data_header)
                except:
                    data_recebimento = datetime.datetime.now()
                
                is_pecas = any(palavra in assunto.upper() for palavra in ["PEÇAS", "PECAS"])
                is_tubos = "TUBOS" in assunto.upper()
                
                if not is_pecas and not is_tubos:
                    break
                
                corpo = ""
                anexos = []
                
                if msg.is_multipart():
                    for part in msg.walk():
                        content_type = part.get_content_type()
                        content_disposition = str(part.get("Content-Disposition"))
                        
                        if content_type == "text/plain" and "attachment" not in content_disposition:
                            try:
                                charset = part.get_content_charset() or "utf-8"
                                corpo += part.get_payload(decode=True).decode(charset, errors="ignore")
                            except:
                                pass
                        
                        elif "attachment" in content_disposition or part.get_filename():
                            nome_arquivo = decodificar_texto(part.get_filename())
                            if nome_arquivo:
                                dados_anexo = part.get_payload(decode=True)
                                anexos.append({
                                    "filename": nome_arquivo,
                                    "content": dados_anexo
                                })
                else:
                    try:
                        charset = msg.get_content_charset() or "utf-8"
                        corpo = msg.get_payload(decode=True).decode(charset, errors="ignore")
                    except:
                        pass
                
                # Centraliza a extração dos XMLs e obtém os logs da consulta
                xmls_nfe, logs_danfe = extrair_xmls_dos_pdfs(anexos)
                
                dados_email = {
                    "assunto": assunto,
                    "remetente": remetente,
                    "data_recebimento": data_recebimento,
                    "logs_danfe": logs_danfe
                }
                
                if is_pecas:
                    resultado_detalhado = processar_pecas(data_recebimento, assunto, remetente, corpo, anexos, xmls_nfe)
                    dados_email.update(resultado_detalhado)
                    relatorio_processamento.append(dados_email)
                elif is_tubos:
                    # Exemplo simples adaptado para retornar estrutura compatível
                    resultado_detalhado = {"tipo": "Tubos", "status_umov": "Pendente de Implementação", "xml_enviado": "", "remessa": "", "nfs": [], "peso_total": 0.0}
                    dados_email.update(resultado_detalhado)
                    relatorio_processamento.append(dados_email)
                    
    mail.logout()
    return relatorio_processamento