import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
from supabase import create_client, Client
import bcrypt
import os

# Carregar variáveis de ambiente
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    st.warning("dotenv não está instalado. Usando variáveis padrão.")

# Configuração de segurança
SECRET_KEY = os.getenv('SECRET_KEY', 'fallback-secret-key-123')
PASSWORD_HASH = os.getenv('PASSWORD_HASH', '')

# Configuração do Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Função de autenticação
def check_password():
    if 'authenticated' in st.session_state and st.session_state.authenticated:
        return True

    password = st.text_input("Senha de acesso", type="password", key="password_input")

    if password:
        if bcrypt.checkpw(password.encode(), PASSWORD_HASH.encode()):
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Senha incorreta")

    return False

if not check_password():
    st.stop()

st.set_page_config(page_title="Gestão de Férias", layout="wide")
st.image("Logotipo.png", width=100)
st.title("🗕 Sistema de Gestão de Férias - INDICA7")

# Sidebar
with st.sidebar:
    st.header("Configurações")
    res = supabase.table("configuracoes").select("max_ferias_simultaneas").eq("id", 1).single().execute()
    max_atual = res.data['max_ferias_simultaneas']
    novo_max = st.number_input("Máximo em férias simultâneas", min_value=1, value=max_atual)
    if novo_max != max_atual:
        supabase.table("configuracoes").update({"max_ferias_simultaneas": novo_max}).eq("id", 1).execute()
        st.success("Configuração atualizada!")

# Funções auxiliares
def calcular_dias_uteis(inicio, fim):
    inicio = pd.to_datetime(inicio)
    fim = pd.to_datetime(fim)
    dias_uteis = pd.bdate_range(start=inicio, end=fim)
    return len(dias_uteis)

def verificar_limite_ferias(nova_inicio, nova_fim, funcionario_id):
    res = supabase.table("configuracoes").select("max_ferias_simultaneas").eq("id", 1).single().execute()
    max_simultaneas = res.data['max_ferias_simultaneas']

    ferias_todas = supabase.table("ferias").select("*").neq("funcionario_id", funcionario_id).execute().data
    calendario = pd.DataFrame(columns=['Data', 'Pessoas'])

    nova_inicio = pd.to_datetime(nova_inicio).date()
    nova_fim = pd.to_datetime(nova_fim).date()

    for f in ferias_todas:
        ini = pd.to_datetime(f['data_inicio']).date()
        fim = pd.to_datetime(f['data_fim']).date()
        if ini <= nova_fim and fim >= nova_inicio:
            dias = pd.bdate_range(start=max(ini, nova_inicio), end=min(fim, nova_fim))
            for dia in dias:
                calendario.loc[len(calendario)] = [dia, 1]

    if not calendario.empty:
        contagem = calendario.groupby('Data').sum()
        dias_problema = contagem[contagem['Pessoas'] >= max_simultaneas]
        if not dias_problema.empty:
            return False, dias_problema.index[0].strftime('%d/%m/%Y')

    return True, None

# Abas
aba1, aba2, aba3 = st.tabs(["Funcionários", "Férias", "Relatórios"])

with aba1:
    st.subheader("Gestão de Funcionários")

    with st.form("form_funcionario", clear_on_submit=True):
        nome = st.text_input("Nome")
        data_admissao = st.date_input("Data de admissão")
        dias_ferias = st.number_input("Dias de férias/ano", min_value=1, value=22)
        if st.form_submit_button("Adicionar"):
            supabase.table("funcionarios").insert({
                "nome": nome,
                "data_admissao": data_admissao.isoformat(),
                "dias_ferias": dias_ferias
            }).execute()
            st.success("Funcionário adicionado.")
            st.rerun()

    funcionarios = pd.DataFrame(
        supabase.table("funcionarios")
        .select("*")
        .order("id")
        .execute()
        .data
    )

    if not funcionarios.empty:
        st.dataframe(funcionarios[['id', 'nome', 'data_admissao', 'dias_ferias']])

        with st.expander("Editar / Apagar Funcionários"):
            for _, row in funcionarios.iterrows():
                with st.form(f"edit_func_{row['id']}"):
                    novo_nome = st.text_input("Nome", value=row['nome'])
                    nova_data = st.date_input("Data de admissão", value=pd.to_datetime(row['data_admissao']))
                    novos_dias = st.number_input("Dias de férias", min_value=1, value=row['dias_ferias'])
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.form_submit_button("Atualizar"):
                            supabase.table("funcionarios").update({
                                "nome": novo_nome,
                                "data_admissao": nova_data.isoformat(),
                                "dias_ferias": novos_dias
                            }).eq("id", row['id']).execute()
                            st.success("Atualizado.")
                            st.rerun()
                    with col2:
                        if st.form_submit_button("Apagar"):
                            supabase.table("funcionarios").delete().eq("id", row['id']).execute()
                            st.warning("Funcionário removido.")
                            st.rerun()

with aba2:
    st.subheader("Gestão de Férias")
    funcionarios = pd.DataFrame(supabase.table("funcionarios").select("id", "nome").execute().data)

    if not funcionarios.empty:
        with st.form("marcar_ferias", clear_on_submit=True):
            funcionario_id = st.selectbox(
                "Funcionário",
                funcionarios['id'],
                format_func=lambda x: funcionarios.loc[funcionarios['id'] == x, 'nome'].values[0]
            )
            col1, col2 = st.columns(2)
            with col1:
                data_inicio = st.date_input("Início")
            with col2:
                data_fim = st.date_input("Fim")

            if st.form_submit_button("Marcar"):
                if pd.to_datetime(data_fim) < pd.to_datetime(data_inicio):
                    st.error("A data final não pode ser anterior à inicial.")
                else:
                    dias = calcular_dias_uteis(data_inicio, data_fim)
                    if dias == 0:
                        st.error("O período selecionado não contém dias úteis.")
                    else:
                        ok, dia_conflito = verificar_limite_ferias(data_inicio, data_fim, funcionario_id)
                        if not ok:
                            st.error(f"Excesso de pessoas em férias no dia {dia_conflito}.")
                        else:
                            supabase.table("ferias").insert({
                                "funcionario_id": funcionario_id,
                                "data_inicio": data_inicio.isoformat(),
                                "data_fim": data_fim.isoformat(),
                                "dias": dias
                            }).execute()
                            st.success("Férias marcadas.")
                            st.rerun()

        ferias_data = supabase.table("ferias").select("*", "funcionarios(nome)").order("data_inicio", desc=True).execute().data
        ferias = pd.DataFrame(ferias_data)

        if not ferias.empty:
            ferias['nome'] = ferias['funcionarios'].apply(lambda f: f['nome'] if isinstance(f, dict) else '')
            st.dataframe(ferias[['nome', 'data_inicio', 'data_fim', 'dias']])

            with st.expander("Editar / Apagar Férias"):
                for _, row in ferias.iterrows():
                    with st.form(f"editar_ferias_{row['id']}"):
                        st.markdown(f"**{row['nome']}**")
                        novo_inicio = st.date_input("Início", value=pd.to_datetime(row['data_inicio']), key=f"inicio_{row['id']}")
                        novo_fim = st.date_input("Fim", value=pd.to_datetime(row['data_fim']), key=f"fim_{row['id']}")
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.form_submit_button("Atualizar"):
                                if novo_fim < novo_inicio:
                                    st.error("Data final deve ser posterior à inicial.")
                                else:
                                    dias = calcular_dias_uteis(novo_inicio, novo_fim)
                                    if dias == 0:
                                        st.error("O período selecionado não contém dias úteis.")
                                    else:
                                        ok, dia_conflito = verificar_limite_ferias(novo_inicio, novo_fim, row['funcionario_id'])
                                        if not ok:
                                            st.error(f"Conflito de férias no dia {dia_conflito}.")
                                        else:
                                            supabase.table("ferias").update({
                                                "data_inicio": novo_inicio.isoformat(),
                                                "data_fim": novo_fim.isoformat(),
                                                "dias": dias
                                            }).eq("id", row['id']).execute()
                                            st.success("Férias atualizadas.")
                                            st.rerun()
                        with col2:
                            if st.form_submit_button("Apagar"):
                                supabase.table("ferias").delete().eq("id", row['id']).execute()
                                st.warning("Férias removidas.")
                                st.rerun()

# aba3 permanece igual, manter código existente
