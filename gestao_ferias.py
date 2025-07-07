# Requisitos: pip install streamlit pandas matplotlib python-dotenv supabase

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
SUPABASE_URL = os.getenv("https://sykrunsjlkxptxphlmnx.supabase.co")
SUPABASE_KEY = os.getenv("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InN5a3J1bnNqbGt4cHR4cGhsbW54Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTE5MjIyNDksImV4cCI6MjA2NzQ5ODI0OX0.scfVJFpCLed7db7LGmzlKmsjkFbjxEUWyGyU9LuJujA")
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
    return len(pd.bdate_range(start=inicio, end=fim))

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

    funcionarios = pd.DataFrame(supabase.table("funcionarios").select("*").execute().data)
    if not funcionarios.empty:
        st.dataframe(funcionarios)
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
                            st.experimental_rerun()
                    with col2:
                        if st.form_submit_button("Apagar"):
                            supabase.table("funcionarios").delete().eq("id", row['id']).execute()
                            st.warning("Funcionário removido.")
                            st.experimental_rerun()

with aba2:
    st.subheader("Gestão de Férias")
    funcionarios = pd.DataFrame(supabase.table("funcionarios").select("id", "nome").execute().data)
    if not funcionarios.empty:
        with st.form("marcar_ferias", clear_on_submit=True):
            funcionario_id = st.selectbox("Funcionário", funcionarios['id'],
                format_func=lambda x: funcionarios.loc[funcionarios['id'] == x, 'nome'].values[0])
            col1, col2 = st.columns(2)
            with col1:
                data_inicio = st.date_input("Início")
            with col2:
                data_fim = st.date_input("Fim")
            if st.form_submit_button("Marcar"):
                if data_fim <= data_inicio:
                    st.error("Data final deve ser posterior à inicial.")
                else:
                    dias = calcular_dias_uteis(data_inicio, data_fim)
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

        ferias = pd.DataFrame(supabase.table("ferias").select("*", "funcionarios(nome)").order("data_inicio", desc=True).execute().data)
        if not ferias.empty:
            ferias['nome'] = ferias['funcionarios']['nome']
            st.dataframe(ferias)
            # Editar / Apagar (igual à lógica de cima - podes copiar/adaptar)

with aba3:
    st.subheader("📊 Relatórios de Férias")
    ferias_df = pd.DataFrame(supabase.table("ferias").select("*", "funcionarios(nome,dias_ferias)").execute().data)

    if not ferias_df.empty:
        ferias_df['data_inicio'] = pd.to_datetime(ferias_df['data_inicio']).dt.date
        ferias_df['data_fim'] = pd.to_datetime(ferias_df['data_fim']).dt.date
        ferias_df['funcionario'] = ferias_df['funcionarios'].apply(lambda x: x['nome'])

        st.subheader("📋 Férias Marcadas")
        st.dataframe(ferias_df[['funcionario', 'data_inicio', 'data_fim', 'dias']])

        hoje = datetime.now().date()
        proximas = ferias_df[ferias_df['data_inicio'] >= hoje]
        st.subheader("🗕 Próximas Férias")
        st.dataframe(proximas[['funcionario', 'data_inicio', 'data_fim']])

        resumo = ferias_df.groupby('funcionario').agg(Usado=('dias', 'sum')).reset_index()
        resumo['Disponível'] = ferias_df['funcionarios'].apply(lambda x: x['dias_ferias'])
        resumo['Restante'] = resumo['Disponível'] - resumo['Usado']
        st.subheader("Resumo por Funcionário")
        st.dataframe(resumo)

        st.subheader("📈 Sobreposição de Férias")
        ferias_df['data_inicio'] = pd.to_datetime(ferias_df['data_inicio'])
        ferias_df['data_fim'] = pd.to_datetime(ferias_df['data_fim'])

        fig, ax = plt.subplots(figsize=(14, 6))
        all_dates = pd.date_range(start=ferias_df['data_inicio'].min(), end=ferias_df['data_fim'].max())
        congestion = pd.Series(0, index=all_dates)
        for _, row in ferias_df.iterrows():
            mask = (all_dates >= row['data_inicio']) & (all_dates <= row['data_fim'])
            congestion[mask] += 1

        for _, row in ferias_df.iterrows():
            overlap_days = congestion.loc[row['data_inicio']:row['data_fim']]
            avg_overlap = overlap_days.mean()
            color = 'green' if avg_overlap < 1.5 else 'goldenrod' if avg_overlap < 2.5 else 'red'
            ax.barh(y=row['funcionario'], width=(row['data_fim'] - row['data_inicio']).days,
                    left=row['data_inicio'], color=color, edgecolor='black', alpha=0.7)
            if avg_overlap > 1:
                ax.text(row['data_inicio'] + (row['data_fim'] - row['data_inicio'])/2, row['funcionario'],
                        f"{int(round(avg_overlap))}", va='center', ha='center', fontsize=10,
                        bbox=dict(facecolor='white', alpha=0.8))

        high_congestion = congestion[congestion >= 3]
        for date in high_congestion.index:
            ax.axvline(x=date, color='darkred', alpha=0.3, linestyle='--')

        ax.set_xlabel('Data')
        ax.set_ylabel('Funcionário')
        ax.set_title('Períodos de Férias - Sobreposições Destacadas', pad=15)
        ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
        plt.xticks(rotation=45)

        legend_elements = [
            plt.Rectangle((0,0),1,1, color='green', label='Sem sobreposição'),
            plt.Rectangle((0,0),1,1, color='goldenrod', label='2 pessoas'),
            plt.Rectangle((0,0),1,1, color='red', label='3+ pessoas')
        ]
        ax.legend(handles=legend_elements, loc='upper right', title="Sobreposições")
        plt.tight_layout()
        st.pyplot(fig)
    else:
        st.info("Nenhuma férias marcada para mostrar.")
