import imaplib
import email
from email.header import decode_header
import datetime
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

def parse_emails(username, password, start_date, end_date):
    # Configuração padrão do IMAP Locaweb
    IMAP_SERVER = "email-ssl.com.br"
    PORT = 993
    
    # Conexão segura SSL
    mail = imaplib.IMAP4_SSL(IMAP_SERVER, PORT)
    mail.login(username, password)
    mail.select("INBOX")
    
    # O IMAP usa formato "DD-Mon-YYYY" (Ex: 29-Jun-2026) e o critério BEFORE é exclusivo.
    # Adicionamos 1 dia na data final para cobrir o dia selecionado por completo.
    imap_start = start_date.strftime("%d-%b-%Y")
    imap_end = (end_date + datetime.timedelta(days=1)).strftime("%d-%b-%Y")
    
    # Busca por e-mails no intervalo de datas
    search_criterion = f'(SINCE "{imap_start}" BEFORE "{imap_end}")'
    status, messages = mail.search(None, search_criterion)
    
    if status != "OK" or not messages[0]:
        mail.logout()
        return 0
        
    email_ids = messages[0].split()
    contador_processados = 0
    
    # Iterar do mais recente para o mais antigo
    for e_id in reversed(email_ids):
        res, data = mail.fetch(e_id, "(RFC822)")
        if res != "OK":
            continue
            
        for response_part in data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                
                # Extração de Metadados
                assunto = decodificar_texto(msg["Subject"])
                remetente = decodificar_texto(msg["From"])
                
                is_pecas = "Peças" in assunto
                is_tubos = "Tubos" in assunto
                
                # Regra solicitada: se nenhum dos nomes for encontrado, interrompe a busca (break)
                # NOTA: Se preferir ignorar o atual e continuar avaliando os outros, altere para 'continue'.
                if not is_pecas and not is_tubos:
                    break
                
                # Extração de Corpo e Anexos
                corpo = ""
                anexos = []
                
                if msg.is_multipart():
                    for part in msg.walk():
                        content_type = part.get_content_type()
                        content_disposition = str(part.get("Content-Disposition"))
                        
                        # Extrai o texto plano do e-mail
                        if content_type == "text/plain" and "attachment" not in content_disposition:
                            try:
                                charset = part.get_content_charset() or "utf-8"
                                corpo += part.get_payload(decode=True).decode(charset, errors="ignore")
                            except:
                                pass
                        
                        # Captura anexos válidos
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
                
                # Direcionamento baseado na palavra-chave
                if is_pecas:
                    processar_pecas(assunto, remetente, corpo, anexos)
                    contador_processados += 1
                elif is_tubos:
                    processar_tubos(assunto, remetente, corpo, anexos)
                    contador_processados += 1
                    
    mail.logout()
    return contador_processados