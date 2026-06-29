import streamlit as st
from datetime import date, timedelta
from email_parser import parse_emails

st.set_page_config(page_title="Parser de E-mails XpertPlan", layout="centered")
st.title("Parser de E-mails 📧")

# Campos de Autenticação
email_padrao = "adalberto@xpertplan.com.br"
email = st.text_input("E-mail", value=email_padrao)
password = st.text_input("Senha", type="password")

# Condicional: Só mostra o restante da tela se o e-mail e a senha estiverem preenchidos
if email and password:
    st.markdown("---")
    st.subheader("Configurações do Processamento")
    
    # Campo de range de datas (Padrão: últimos 7 dias até hoje)
    hoje = date.today()
    data_inicial_padrao = hoje - timedelta(days=7)
    
    date_range = st.date_input(
        "Selecione o intervalo de datas",
        value=(data_inicial_padrao, hoje),
        max_value=hoje
    )
    
    # Valida se o usuário selecionou ambas as datas (Início e Fim)
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
        
        if st.button("Processar", type="primary"):
            with st.spinner("Conectando ao webmail Locaweb e buscando mensagens..."):
                try:
                    total_processado = parse_emails(email, password, start_date, end_date)
                    st.success(f"Processamento concluído com sucesso! {total_processado} e-mail(s) triados.")
                except Exception as e:
                    st.error(f"Ocorreu um erro durante o processamento: {e}")
    else:
        st.info("Por favor, selecione a data de início e a data de fim no calendário.")