import streamlit as st
from datetime import date, timedelta
from email_parser import parse_emails

st.set_page_config(page_title="Parser de E-mails XpertPlan", layout="wide")
st.title("Parser de E-mails 📧")

# Campos de Autenticação
email_padrao = "adalberto@xpertplan.com.br"
email = st.text_input("E-mail", value=email_padrao)
password = st.text_input("Senha", type="password")

if email and password:
    st.markdown("---")
    st.subheader("Configurações do Processamento")
    
    hoje = date.today()
    data_inicial_padrao = hoje - timedelta(days=7)
    
    date_range = st.date_input(
        "Selecione o intervalo de datas",
        value=(data_inicial_padrao, hoje),
        max_value=hoje
    )
    
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
        
        if st.button("Processar", type="primary"):
            with st.spinner("Conectando ao webmail Locaweb e triando mensagens..."):
                try:
                    # Captura a lista detalhada de tudo que foi feito
                    relatorios = parse_emails(email, password, start_date, end_date)
                    
                    if not relatorios:
                        st.info("Nenhum e-mail de Peças ou Tubos encontrado no período selecionado.")
                    else:
                        st.success(f"Processamento concluído! {len(relatorios)} e-mail(s) triados.")
                        
                        st.markdown("### 📋 Detalhes e Auditoria do Processamento")
                        
                        # Loop gerando uma aba expandível para cada e-mail
                        for idx, rel in enumerate(relatorios):
                            titulo_aba = f"[{rel['tipo']}] {rel['assunto']} | Recebido em: {rel['data_recebimento'].strftime('%d/%m/%Y %H:%M')}"
                            
                            with st.expander(titulo_aba):
                                col1, col2 = st.columns(2)
                                
                                with col1:
                                    st.markdown("#### 🔍 Dados Extraídos")
                                    st.write(f"**Remetente:** {rel['remetente']}")
                                    st.write(f"**Nº Remessa:** {rel.get('remessa', 'N/A')}")
                                    st.write(f"**Notas Fiscais (NF):** {rel.get('nfs', 'N/A')}")
                                    st.write(f"**Peso Total:** {rel.get('peso_total', 0.0)} kg")
                                    st.write(f"**ID Motorista (Agent):** {rel.get('agent_id', 'Não identificado')}")
                                    st.write(f"**ID Transportadora (Local):** {rel.get('service_local_id', 'Não identificado')}")
                                
                                with col2:
                                    st.markdown("#### 🌐 Requisições e Integrações")
                                    
                                    st.markdown("**1. Consulta DANFE (PDF para XML):**")
                                    if not rel["logs_danfe"]:
                                        st.caption("Nenhum anexo PDF processado para este e-mail.")
                                    for log_df in rel["logs_danfe"]:
                                        status_cor = "green" if log_df["sucesso"] else "red"
                                        st.markdown(f"- Arquivo: `{log_df['arquivo']}`")
                                        st.markdown(f"  - Chave: `{log_df['chave']}`")
                                        st.markdown(f"  - Status API: :{status_cor}[{log_df['status']}]")
                                        
                                    st.markdown("---")
                                    st.markdown("**2. Envio Umov.me:**")
                                    st.write(f"**Status do Envio:** `{rel.get('status_umov', 'N/A')}`")
                                    
                                # Se houver payload XML gerado, exibe de forma limpa abaixo
                                if rel.get("xml_enviado"):
                                    st.markdown("#### 📄 XML Payload enviado ao Umov.me")
                                    st.code(rel["xml_enviado"], language="xml")
                                    
                                if rel.get("resposta_umov"):
                                    with st.get_container() if hasattr(st, "get_container") else st.container():
                                        st.caption("**Resposta brute do servidor Umov.me:**")
                                        st.text(rel["resposta_umov"][:500] + "..." if len(rel["resposta_umov"]) > 500 else rel["resposta_umov"])
                except Exception as e:
                    st.error(f"Ocorreu um erro durante o processamento: {e}")
    else:
        st.info("Por favor, selecione a data de início e a data de fim no calendário.")