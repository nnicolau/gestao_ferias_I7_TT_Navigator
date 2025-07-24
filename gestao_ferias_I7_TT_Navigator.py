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
st.sidebar.selectbox("🌐 Língua / Language", ["pt", "en"],
                    index=0 if st.session_state.lang == "pt" else 1, key="lang")

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
    if st.session_state.get("authenticated", False):
        return True

    with st.form("login_form"):
        password = st.text_input(t("senha_acesso"), type="password")
        submit = st.form_submit_button(t("entrar"))

        if submit:
            if bcrypt.checkpw(password.encode(), PASSWORD_HASH.encode()):
                st.session_state.authenticated = True
                st.success(t("autenticado"))
                st.rerun()
            else:
                st.error(t("senha_incorreta"))

    return False

if not check_password():
    st.stop()

# --- Página ---
st.set_page_config(page_title=t("titulo"), layout="wide")
st.title(t("titulo"))

# --- Controle de abas ---
tabs = {
    "funcionarios": t("gestao_funcionarios"),
    "ferias": t("gestao_ferias"),
    "relatorios": t("relatorios_ferias")
}

aba_selecionada = st.selectbox("Menu", options=list(tabs.keys()), format_func=lambda x: tabs[x], key="aba_atual")

# --- Flags para recarregar dados ---
for flag in ["reload_funcionarios", "reload_ferias", "reload_config"]:
    if flag not in st.session_state:
        st.session_state[flag] = True

# --- Funções de carregamento ---
def carregar_funcionarios():
    return pd.DataFrame(supabase.table("funcionarios").select("*").order("id").execute().data)

def carregar_ferias():
    return pd.DataFrame(supabase.table("ferias").select("*", "funcionarios(nome)").order("data_inicio", desc=True).execute().data)

def carregar_config():
    res = supabase.table("configuracoes").select("max_ferias_simultaneas").eq("id", 1).single().execute()
    return res.data['max_ferias_simultaneas'] if res.data else 5

# --- Sidebar Configurações ---
with st.sidebar:
    st.header(t("configuracoes"))
    if st.session_state.reload_config:
        st.session_state.max_ferias_simultaneas = carregar_config()
        st.session_state.reload_config = False

    novo_max = st.number_input(t("max_ferias_simultaneas"), min_value=1, value=st.session_state.max_ferias_simultaneas)
    if novo_max != st.session_state.max_ferias_simultaneas:
        supabase.table("configuracoes").update({"max_ferias_simultaneas": novo_max}).eq("id", 1).execute()
        st.success(t("config_atualizada"))
        st.session_state.max_ferias_simultaneas = novo_max
        st.session_state.reload_config = True

# --- Aba Funcionários ---
if aba_selecionada == "funcionarios":
    st.subheader(t("gestao_funcionarios"))
    if st.session_state.reload_funcionarios:
        st.session_state.funcionarios = carregar_funcionarios()
        st.session_state.reload_funcionarios = False
    funcionarios = st.session_state.funcionarios

    with st.form("form_adicionar_funcionario", clear_on_submit=True):
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
            st.session_state.reload_funcionarios = True

    st.dataframe(funcionarios)

    for _, row in funcionarios.iterrows():
        with st.expander(row["nome"]):
            with st.form(f"form_editar_{row['id']}"):
                novo_nome = st.text_input(t("nome"), value=row["nome"])
                nova_data = st.date_input(t("data_admissao"), value=pd.to_datetime(row["data_admissao"]))
                novos_dias = st.number_input(t("dias_ferias_ano"), min_value=1, value=row["dias_ferias"])
                col1, col2 = st.columns(2)
                with col1:
                    if st.form_submit_button(t("atualizar")):
                        supabase.table("funcionarios").update({
                            "nome": novo_nome,
                            "data_admissao": nova_data.isoformat(),
                            "dias_ferias": novos_dias
                        }).eq("id", row["id"]).execute()
                        st.success(t("atualizado"))
                        st.session_state.reload_funcionarios = True
                with col2:
                    if st.form_submit_button(t("apagar")):
                        supabase.table("funcionarios").delete().eq("id", row["id"]).execute()
                        st.warning(t("removido"))
                        st.session_state.reload_funcionarios = True

# --- Aba Férias ---
elif aba_selecionada == "ferias":
    st.subheader(t("gestao_ferias"))
    if st.session_state.reload_funcionarios:
        st.session_state.funcionarios = carregar_funcionarios()
        st.session_state.reload_funcionarios = False
    funcionarios_ferias = st.session_state.funcionarios

    if st.session_state.reload_ferias:
        st.session_state.ferias = carregar_ferias()
        st.session_state.reload_ferias = False
    ferias = st.session_state.ferias

    if not funcionarios_ferias.empty:
        with st.form("form_marcar_ferias", clear_on_submit=True):
            funcionario_id = st.selectbox(
                t("nome"),
                funcionarios_ferias["id"],
                format_func=lambda x: funcionarios_ferias.loc[funcionarios_ferias["id"] == x, "nome"].values[0]
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
                st.session_state.reload_ferias = True

    st.dataframe(ferias)

    for _, row in ferias.iterrows():
        with st.expander(f"{row['funcionarios']['nome']} {row['data_inicio']} - {row['data_fim']}"):
            with st.form(f"form_editar_ferias_{row['id']}"):
                novo_inicio = st.date_input(t("inicio"), value=pd.to_datetime(row["data_inicio"]))
                novo_fim = st.date_input(t("fim"), value=pd.to_datetime(row["data_fim"]))
                col1, col2 = st.columns(2)
                with col1:
                    if st.form_submit_button(t("atualizar")):
                        supabase.table("ferias").update({
                            "data_inicio": novo_inicio.isoformat(),
                            "data_fim": novo_fim.isoformat()
                        }).eq("id", row["id"]).execute()
                        st.success(t("ferias_atualizadas"))
                        st.session_state.reload_ferias = True
                with col2:
                    if st.form_submit_button(t("apagar")):
                        supabase.table("ferias").delete().eq("id", row["id"]).execute()
                        st.warning(t("ferias_removidas"))
                        st.session_state.reload_ferias = True

# --- Aba Relatórios ---
elif aba_selecionada == "relatorios":
    st.subheader(t("relatorios_ferias"))
    if st.session_state.reload_ferias:
        st.session_state.ferias = carregar_ferias()
        st.session_state.reload_ferias = False
    ferias = st.session_state.ferias

    if not ferias.empty:
        ferias["data_inicio"] = pd.to_datetime(ferias["data_inicio"])
        ferias["data_fim"] = pd.to_datetime(ferias["data_fim"])
        ferias["funcionario"] = ferias["funcionarios"].apply(lambda x: x.get("nome", "") if isinstance(x, dict) else "")

        st.subheader(t("ferias_marcadas_titulo"))
        st.dataframe(ferias[["funcionario", "data_inicio", "data_fim"]])

        fig, ax = plt.subplots(figsize=(14, 6))
        all_dates = pd.date_range(start=ferias["data_inicio"].min(), end=ferias["data_fim"].max())
        congestion = pd.Series(0, index=all_dates)
        for _, row in ferias.iterrows():
            inicio = row["data_inicio"]
            fim = row["data_fim"]
            congestion[(all_dates >= inicio) & (all_dates <= fim)] += 1

        ax.plot(congestion.index, congestion.values, label=t("sobreposicao"), color="red")
        ax.set_title(t("titulo_grafico"))
        ax.set_xlabel(t("data"))
        ax.set_ylabel(t("numero_funcionarios_ferias"))
        ax.legend()
        ax.grid()
        st.pyplot(fig)
    else:
        st.info(t("nenhuma_ferias"))

# --- Footer ---
with st.sidebar:
    st.markdown(
        """
        <div style='height:300px;'></div>
        <div style='font-size:10px; text-align:center;'>
            Powered by NN ®
        </div>
        """,
        unsafe_allow_html=True
    )
