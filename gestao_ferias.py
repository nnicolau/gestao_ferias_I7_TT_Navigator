import streamlit as st
import pandas as pd
from datetime import datetime

# Configuração inicial com verificação
try:
    st.set_page_config(page_title="Gestão de Férias", layout="wide")
    st.title("📅 Sistema de Gestão de Férias")
    
    # Verifica se as variáveis de sessão existem
    if 'funcionarios' not in st.session_state:
        st.session_state.funcionarios = []
    
    if 'ferias' not in st.session_state:
        st.session_state.ferias = []
    
    # Função para calcular dias úteis
    def calcular_dias_uteis(inicio, fim):
        dias = pd.bdate_range(start=inicio, end=fim)
        return len(dias)

    # Menu lateral
    with st.sidebar:
        st.header("Configurações")
        dias_ferias = st.number_input("Dias de férias por ano", min_value=1, value=22)
        limite_pessoas = st.number_input("Máximo em férias simultâneas", min_value=1, value=2)

    # Abas principais
    tab1, tab2 = st.tabs(["Funcionários", "Férias"])

    with tab1:
        st.header("Cadastro de Funcionários")
        
        with st.form("novo_funcionario"):
            nome = st.text_input("Nome completo")
            data_admissao = st.date_input("Data de admissão")
            if st.form_submit_button("Salvar"):
                st.session_state.funcionarios.append({
                    "Nome": nome,
                    "Admissão": data_admissao,
                    "Dias Disponíveis": dias_ferias
                })
                st.success("Funcionário cadastrado!")
        
        if st.session_state.funcionarios:
            st.dataframe(pd.DataFrame(st.session_state.funcionarios))

    with tab2:
        st.header("Marcação de Férias")
        
        if st.session_state.funcionarios:
            with st.form("marcar_ferias"):
                funcionario = st.selectbox("Funcionário", [f["Nome"] for f in st.session_state.funcionarios])
                data_inicio = st.date_input("Data de início")
                data_fim = st.date_input("Data de fim")
                
                if st.form_submit_button("Marcar Férias"):
                    if data_fim <= data_inicio:
                        st.error("Data final deve ser após a data inicial!")
                    else:
                        dias = calcular_dias_uteis(data_inicio, data_fim)
                        st.session_state.ferias.append({
                            "Funcionário": funcionario,
                            "Início": data_inicio,
                            "Fim": data_fim,
                            "Dias": dias
                        })
                        st.success(f"Férias marcadas! Total de dias: {dias}")
            
            if st.session_state.ferias:
                st.subheader("Férias Marcadas")
                st.dataframe(pd.DataFrame(st.session_state.ferias))
        else:
            st.warning("Cadastre funcionários primeiro")

except Exception as e:
    st.error(f"Ocorreu um erro: {str(e)}")
    st.error("Por favor, verifique o terminal para mais detalhes.")
