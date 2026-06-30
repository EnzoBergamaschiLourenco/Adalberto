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
    """Lê PDFs em anexo, extrai a chave de acesso e busca o XML na API."""
    xmls_extraidos = []
    
    for anexo in anexos:
        if anexo["filename"].lower().endswith(".pdf"):
            try:
                # Utiliza o pdfplumber com os bytes do anexo
                with pdfplumber.open(io.BytesIO(anexo["content"])) as pdf:
                    # Lê apenas a primeira página onde costuma ficar a chave
                    texto_pagina = pdf.pages[0].extract_text()
                    
                    if texto_pagina:
                        # Limpa espaços e quebras para achar a chave de 44 números
                        texto_limpo = texto_pagina.replace(" ", "").replace("\n", "")
                        match = re.search(r'\b\d{44}\b', texto_limpo)
                        
                        if match:
                            chave = match.group(0)
                            
                            # Faz a requisição POST para buscar a DANFE
                            res = requests.post(
                                'https://consultadanfe.com/api/v1/consulta',
                                json={'chave': chave},
                                headers={'Content-Type': 'application/json'},
                                timeout=15
                            )
                            
                            if res.status_code == 200:
                                base64_xml = res.text
                                
                                # Limpa os caracteres que não pertencem ao Base64 e ajusta o padding
                                b64_str = re.sub(r'[^A-Za-z0-9+/]', '', base64_xml)
                                padding = len(b64_str) % 4
                                if padding:
                                    b64_str += '=' * (4 - padding)
                                
                                # Decodifica o Base64 para string XML
                                xml_decodificado = base64.b64decode(b64_str).decode('utf-8', errors='ignore')
                                xmls_extraidos.append(xml_decodificado)
            except Exception as e:
                print(f"Erro ao processar PDF {anexo['filename']}: {e}")
                
    return xmls_extraidos

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
    
    if status != "OK" or not messages[0]:
        mail.logout()
        return 0
        
    email_ids = messages[0].split()
    contador_processados = 0
    
    for e_id in reversed(email_ids):
        res, data = mail.fetch(e_id, "(RFC822)")
        if res != "OK":
            continue
            
        for response_part in data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                
                assunto = decodificar_texto(msg["Subject"])
                remetente = decodificar_texto(msg["From"])
                
                # Extraindo a data exata do recebimento do email
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
                
                # Centraliza a extração dos XMLs aqui
                xmls_nfe = extrair_xmls_dos_pdfs(anexos)
                
                # Direcionamento com os novos parâmetros
                if is_pecas:
                    processar_pecas(data_recebimento, assunto, remetente, corpo, anexos, xmls_nfe)
                    contador_processados += 1
                elif is_tubos:
                    processar_tubos(data_recebimento, assunto, remetente, corpo, anexos, xmls_nfe)
                    contador_processados += 1
                    
    mail.logout()
    return contador_processados