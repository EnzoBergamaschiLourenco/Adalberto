import streamlit as st
import pandas as pd
import requests
import base64
import socket
import ssl
from datetime import date, timedelta
from email_parser import parse_emails
from dictionaries import MOTORISTA_TRANSPORTADORA, CNPJ_SERVICELOCAL

st.set_page_config(page_title="Parser de E-mails XpertPlan", layout="wide")

# --- FUNÇÕES AUXILIARES ---
def dict_to_df(d):
    """Converte dicionário para DataFrame editável."""
    return pd.DataFrame(list(d.items()), columns=["Chave", "Valor"])

def df_to_dict(df):
    """Converte DataFrame de volta para dicionário garantindo formato string."""
    d = {}
    for _, row in df.iterrows():
        k = str(row['Chave']).strip() if pd.notna(row['Chave']) else ""
        v = str(row['Valor']).strip() if pd.notna(row['Valor']) else ""
        if k: # Impede chaves vazias
            d[k] = v
    return d

def commit_to_github(new_content):
    """Envia o novo conteúdo do arquivo para o GitHub via API."""
    try:
        token = st.secrets["github"]["token"]
        repo_owner = st.secrets["github"]["repo_owner"]
        repo_name = st.secrets["github"]["repo_name"]
    except KeyError:
        st.error("Credenciais do GitHub não encontradas nos secrets do Streamlit.")
        return False

    file_path = "dictionaries.py"
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/contents/{file_path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # 1. Pegar o SHA atual do arquivo (necessário para atualizar)
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        sha = response.json()['sha']
    else:
        st.error(f"Erro ao acessar o repositório: {response.text}")
        return False
        
    # 2. Enviar a atualização codificada em Base64
    encoded_content = base64.b64encode(new_content.encode('utf-8')).decode('utf-8')
    data = {
        "message": "Atualizando dicionários via Streamlit",
        "content": encoded_content,
        "sha": sha
    }
    
    put_response = requests.put(url, headers=headers, json=data)
    return put_response.status_code == 200

# --- LAYOUT PRINCIPAL ---
# Dividindo a tela: col_esq (Dicionários) e col_dir (Parser + Diagnóstico)
col_esq, col_dir = st.columns([6, 4], gap="large")

# ==========================================
# COLUNA ESQUERDA: Edição de Dicionários
# ==========================================
with col_esq:
    st.subheader("Configuração de Dicionários")
    st.markdown("Edite, adicione ou remova itens nas tabelas abaixo.")
    
    # Cards lado a lado para os dicionários
    col_dict1, col_dict2 = st.columns(2)
    
    with col_dict1:
        st.markdown("**Motorista ➔ Transportadora**")
        df_motorista = dict_to_df(MOTORISTA_TRANSPORTADORA)
        edited_df_motorista = st.data_editor(df_motorista, num_rows="dynamic", use_container_width=True, key="ed_mot")
        
    with col_dict2:
        st.markdown("**CNPJ ➔ ServiceLocal**")
        df_cnpj = dict_to_df(CNPJ_SERVICELOCAL)
        edited_df_cnpj = st.data_editor(df_cnpj, num_rows="dynamic", use_container_width=True, key="ed_cnpj")
        
    st.write("") # Espaçamento
    if st.button("💾 Salvar Dicionários no Repositório", type="primary"):
        new_motorista = df_to_dict(edited_df_motorista)
        new_cnpj = df_to_dict(edited_df_cnpj)
        
        new_file_content = "MOTORISTA_TRANSPORTADORA = {\n"
        for k, v in new_motorista.items():
            new_file_content += f'    "{k}": "{v}",\n'
        new_file_content += "}\n\n"
        
        new_file_content += "CNPJ_SERVICELOCAL = {\n"
        for k, v in new_cnpj.items():
            new_file_content += f'    "{k}": "{v}",\n'
        new_file_content += "}\n"
        
        with st.spinner("Realizando commit no GitHub..."):
            sucesso = commit_to_github(new_file_content)
            if sucesso:
                st.success("✅ Dicionários atualizados! A aplicação deve reiniciar automaticamente em alguns segundos.")
            else:
                st.error("Falha ao salvar. Verifique o log e as permissões do token.")

# ==========================================
# COLUNA DIREITA: Parser de E-mails & Diagnóstico
# ==========================================
with col_dir:
    st.title("Parser de E-mails 📧")
    
    email_padrao = "adalberto@xpertplan.com.br"
    email_input = st.text_input("E-mail", value=email_padrao)
    password = st.text_input("Senha", type="password")
    
    st.markdown("---")
    st.subheader("Configurações do Processamento")
    
    hoje = date.today()
    data_inicial_padrao = hoje - timedelta(days=7)
    
    date_range = st.date_input(
        "Selecione o intervalo de datas",
        value=(data_inicial_padrao, hoje),
        max_value=hoje
    )
    
    # Seção de Diagnósticos de Conexão na Interface
    with st.expander("🔍 Testar Conectividade com o Servidor de E-mail"):
        host_teste = st.text_input("Host IMAP para teste", value="imap.uhserver.com")
        if st.button("Executar Teste de Diagnóstico"):
            with st.spinner("Testando conexão de rede e SSL..."):
                # Teste 1: DNS e Socket TCP
                try:
                    ip_resolvido = socket.gethostbyname(host_teste)
                    st.info(f"🌐 IP resolvido para **{host_teste}**: `{ip_resolvido}`")
                except Exception as e:
                    st.error(f"❌ Falha no DNS: {repr(e)}")

                try:
                    socket.create_connection((host_teste, 993), timeout=10)
                    st.success("✅ Conexão TCP com a porta 993 estabelecida com sucesso!")
                except Exception as e:
                    st.error(f"❌ Falha na conexão TCP (Timeout/Bloqueio): {repr(e)}")

                # Teste 2: Handshake SSL
                ctx = ssl.create_default_context()
                try:
                    with socket.create_connection((host_teste, 993), timeout=10) as sock:
                        with ctx.wrap_socket(sock, server_hostname=host_teste) as ssock:
                            versao_tls = ssock.version()
                            st.success(f"🔒 Handshake SSL/TLS bem-sucedido! Versão: `{versao_tls}`")
                except Exception as e:
                    st.error(f"❌ Falha no SSL/TLS: {repr(e)}")

    relatorios = []
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
        
        if st.button("▶ Processar", type="primary", use_container_width=True):
            if not email_input or not password:
                st.warning("Preencha o e-mail e a senha para continuar.")
            else:
                with st.spinner("Conectando ao webmail e triando mensagens..."):
                    try:
                        relatorios = parse_emails(email_input, password, start_date, end_date)           
                    except Exception as e:
                        st.error(f"Erro durante o processamento: {e}")
    else:
        st.info("Selecione a data de início e fim no calendário.")
        
    if relatorios:
        st.success(f"Concluído! {len(relatorios)} e-mail(s) processados.")
        
        st.markdown("### 📋 Auditoria")
        for idx, rel in enumerate(relatorios):
            titulo_aba = f"[{rel.get('tipo', 'N/A')}] {rel['assunto']}"
            
            with st.expander(titulo_aba):
                st.write(f"**Remetente:** {rel['remetente']}")
                st.write(f"**ID Transportadora:** {rel.get('service_local_id', 'Não identificado')}")
                
                if rel.get("logs_danfe"):
                    st.markdown("**Consulta DANFE:**")
                    for log_df in rel["logs_danfe"]:
                        st.caption(f"Status: {log_df['status']} | Chave: {log_df['chave']}")
                        
                if rel.get("resposta_umov"):
                    st.markdown("**Retorno Umov.me:**")
                    resp = str(rel["resposta_umov"])
                    st.caption(resp[:200] + "..." if len(resp) > 200 else resp)
    elif 'date_range' in locals() and isinstance(date_range, tuple):
        # Evita exibir a mensagem de "nenhum e-mail" antes de o botão ser acionado
        pass