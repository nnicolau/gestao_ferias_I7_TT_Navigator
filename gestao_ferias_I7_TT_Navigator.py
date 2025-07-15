import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
from supabase import create_client, Client
import bcrypt
import os
import toml

# --- Tradução ---
with open("traducao.toml", "r", encoding="utf-8") as f:
    traducoes = toml.load(f)

def t(chave):
    lang = st.session_state.get("lang", "pt")
    return traducoes.get(lang, {}).get(chave, chave)

# --- Seleção de idioma ---
if "lang" not in st.session_state:
    st.session_state.lang = "pt"

st.sidebar.selectbox("🌐 Língua / Language", ["pt", "en"], index=0 if st.session_state.lang == "pt" else 1, key="lang")

# --- Variáveis ambiente ---
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    st.warning("dotenv não está instalado. Usando variáveis padrão.")

SECRET_KEY = os.getenv('SECRET_KEY', 'fallback-secret-key-123')
PASSWORD_HASH = os.getenv('PASSWORD_HASH', '')
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Autenticação ---
def check_password():
    if 'authenticated' in st.session_state and st.session_state.authenticated:
        return True
    password = st.text_input(t("senha_acesso"), type="password", key="password_input")
    if password:
        if bcrypt.checkpw(password.encode(), PASSWORD_HASH.encode()):
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error(t("senha_incorreta"))
    return False

if not check_password():
    st.stop()

# --- Página ---
st.set_page_config(page_title=t("titulo"), layout="wide")
st.title(t("titulo"))

# --- Abas ---
tab1, tab2, tab3 = st.tabs([t("gestao_funcionarios"), t("gestao_ferias"), t("relatorios_ferias")])

# --- Aba 1: Gestão de Funcionários ---
with tab1:
    st.subheader(t("gestao_funcionarios"))
    funcionarios = pd.DataFrame(supabase.table("funcionarios").select("*").order("id").execute().data)

    with st.form("adicionar_funcionario", clear_on_submit=True):
        nome = st.text_input(t("nome"))
        data_admissao = st.date_input(t("data_admissao"))
        dias_ferias = st.number_input(t("dias_ferias_ano"), min_value=1, value=22)
        if st.form_submit_button(t("adicionar")):
            supabase.table("funcionarios").insert({
                "nome": nome,
                "data_admissao": data_admissao.isoformat(),
                "dias_ferias": dias_ferias
            }).execute()
            st.success(t("funcionario_adicionado"))
            st.experimental_rerun()

    st.dataframe(funcionarios)

    for _, row in funcionarios.iterrows():
        with st.expander(f"{row['nome']}"):
            with st.form(f"editar_{row['id']}"):
                novo_nome = st.text_input(t("nome"), value=row['nome'])
                nova_data = st.date_input(t("data_admissao"), value=pd.to_datetime(row['data_admissao']))
                novos_dias = st.number_input(t("dias_ferias_ano"), min_value=1, value=row['dias_ferias'])
                col1, col2 = st.columns(2)
                with col1:
                    if st.form_submit_button(t("atualizar")):
                        supabase.table("funcionarios").update({
                            "nome": novo_nome,
                            "data_admissao": nova_data.isoformat(),
                            "dias_ferias": novos_dias
                        }).eq("id", row['id']).execute()
                        st.success(t("atualizado"))
                        st.experimental_rerun()
                with col2:
                    if st.form_submit_button(t("apagar")):
                        supabase.table("funcionarios").delete().eq("id", row['id']).execute()
                        st.warning(t("removido"))
                        st.experimental_rerun()

# --- Aba 2: Gestão de Férias ---
with tab2:
    st.subheader(t("gestao_ferias"))
    funcionarios_ferias = pd.DataFrame(supabase.table("funcionarios").select("id", "nome", "dias_ferias").execute().data)
    ferias = pd.DataFrame(supabase.table("ferias").select("*", "funcionarios(nome)").order("data_inicio", desc=True).execute().data)

    if not funcionarios_ferias.empty:
        with st.form("marcar_ferias", clear_on_submit=True):
            funcionario_id = st.selectbox(
                t("nome"),
                funcionarios_ferias['id'],
                format_func=lambda x: funcionarios_ferias.loc[funcionarios_ferias['id'] == x, 'nome'].values[0]
            )
            data_inicio = st.date_input(t("inicio"))
            data_fim = st.date_input(t("fim"))
            if st.form_submit_button(t("marcar")):
                supabase.table("ferias").insert({
                    "funcionario_id": funcionario_id,
                    "data_inicio": data_inicio.isoformat(),
                    "data_fim": data_fim.isoformat()
                }).execute()
                st.success(t("ferias_marcadas"))
                st.experimental_rerun()

    st.dataframe(ferias)

    for _, row in ferias.iterrows():
        with st.expander(f"{row['funcionarios']['nome']} {row['data_inicio']} - {row['data_fim']}"):
            with st.form(f"editar_ferias_{row['id']}"):
                novo_inicio = st.date_input(t("inicio"), value=pd.to_datetime(row['data_inicio']))
                novo_fim = st.date_input(t("fim"), value=pd.to_datetime(row['data_fim']))
                col1, col2 = st.columns(2)
                with col1:
                    if st.form_submit_button(t("atualizar")):
                        supabase.table("ferias").update({
                            "data_inicio": novo_inicio.isoformat(),
                            "data_fim": novo_fim.isoformat()
                        }).eq("id", row['id']).execute()
                        st.success(t("ferias_atualizadas"))
                        st.experimental_rerun()
                with col2:
                    if st.form_submit_button(t("apagar")):
                        supabase.table("ferias").delete().eq("id", row['id']).execute()
                        st.warning(t("ferias_removidas"))
                        st.experimental_rerun()

# --- Aba 3: Relatórios ---
with tab3:
    st.subheader(t("relatorios_ferias"))
    dados_ferias = pd.DataFrame(supabase.table("ferias").select("*", "funcionarios(id, nome)").execute().data)

    if not dados_ferias.empty:
        dados_ferias['data_inicio'] = pd.to_datetime(dados_ferias['data_inicio']).dt.date
        dados_ferias['data_fim'] = pd.to_datetime(dados_ferias['data_fim']).dt.date
        dados_ferias['funcionario'] = dados_ferias['funcionarios'].apply(lambda x: x.get('nome', '') if isinstance(x, dict) else '')

        st.subheader(t("ferias_marcadas_titulo"))
        st.dataframe(dados_ferias[['funcionario', 'data_inicio', 'data_fim']])

        fig, ax = plt.subplots(figsize=(14, 6))
        all_dates = pd.date_range(start=dados_ferias['data_inicio'].min(), end=dados_ferias['data_fim'].max())
        congestion = pd.Series(0, index=all_dates)
        for _, row in dados_ferias.iterrows():
            inicio = pd.to_datetime(row['data_inicio'])
            fim = pd.to_datetime(row['data_fim'])
            mask = (all_dates >= inicio) & (all_dates <= fim)
            congestion[mask] += 1
        ax.plot(congestion.index, congestion.values, label="Sobreposição", color='red')
        ax.set_title("Gráfico de Sobreposição de Férias")
        ax.set_xlabel("Data")
        ax.set_ylabel("Número de Funcionários de Férias")
        ax.legend()
        ax.grid()
        st.pyplot(fig)
    else:
        st.info(t("nenhuma_ferias"))

# --- Footer ---
with st.sidebar:
    st.markdown("""
        <div style='height:300px;'></div>
        <div style='font-size:10px; text-align:center;'>
            Powered by NN ®
        </div>
    """, unsafe_allow_html=True)
