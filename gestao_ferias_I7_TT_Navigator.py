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

# --- Configuração da página ---
st.set_page_config(page_title=t("titulo"), layout="wide")
col1, col2 = st.columns([1, 4])
with col1:
    st.image("logo2.png", width=400)
with col2:
    st.image("Logotipo.png", width=100)

st.title(t("titulo"))

# --- Sidebar: Configurações ---
with st.sidebar:
    st.header(t("configuracoes"))     
    res = supabase.table("configuracoes").select("max_ferias_simultaneas").eq("id", 1).single().execute()
    max_atual = res.data['max_ferias_simultaneas']
    novo_max = st.number_input(t("max_ferias_simultaneas"), min_value=1, value=max_atual)
    if novo_max != max_atual:
        supabase.table("configuracoes").update({"max_ferias_simultaneas": novo_max}).eq("id", 1).execute()
        st.success(t("config_atualizada"))

# --- Funções auxiliares ---
def calcular_dias_uteis(inicio, fim):
    inicio = pd.to_datetime(inicio)
    fim = pd.to_datetime(fim)
    dias_uteis = pd.bdate_range(start=inicio, end=fim)
    return len(dias_uteis)

def verificar_limite_ferias(nova_inicio, nova_fim, funcionario_id):
    nova_inicio = pd.to_datetime(nova_inicio)
    nova_fim = pd.to_datetime(nova_fim)
    res = supabase.table("configuracoes").select("max_ferias_simultaneas").eq("id", 1).single().execute()
    max_simultaneas = res.data['max_ferias_simultaneas']
    ferias_todas = supabase.table("ferias").select("*").neq("funcionario_id", funcionario_id).execute().data
    calendario = pd.Series(0, index=pd.bdate_range(start=nova_inicio, end=nova_fim))
    for f in ferias_todas:
        ini = pd.to_datetime(f['data_inicio'])
        fim = pd.to_datetime(f['data_fim'])
        inter_inicio = max(ini, nova_inicio)
        inter_fim = min(fim, nova_fim)
        if inter_inicio <= inter_fim:
            periodo = pd.bdate_range(start=inter_inicio, end=inter_fim)
            calendario.loc[periodo] += 1
    conflito = calendario[calendario >= max_simultaneas]
    if not conflito.empty:
        return False, conflito.index[0].strftime('%d/%m/%Y')
    return True, None

def verificar_duplicidade_ferias(nova_inicio, nova_fim, funcionario_id, ignorar_id=None):
    nova_inicio = pd.to_datetime(nova_inicio)
    nova_fim = pd.to_datetime(nova_fim)
    query = supabase.table("ferias").select("id", "data_inicio", "data_fim").eq("funcionario_id", funcionario_id)
    ferias_funcionario = query.execute().data
    for f in ferias_funcionario:
        if ignorar_id is not None and f['id'] == ignorar_id:
            continue
        ini = pd.to_datetime(f['data_inicio'])
        fim = pd.to_datetime(f['data_fim'])
        if not (nova_fim < ini or nova_inicio > fim):
            return False, ini.strftime('%d/%m/%Y'), fim.strftime('%d/%m/%Y')
    return True, None, None

# --- Abas ---
tab1, tab2, tab3 = st.tabs([t("gestao_funcionarios"), t("gestao_ferias"), t("relatorios_ferias")])

# --- Aba 1: Funcionários ---
with tab1:
    st.subheader(t("gestao_funcionarios"))
    funcionarios = supabase.table("funcionarios").select("*").order("id").execute().data
    st.dataframe(pd.DataFrame(funcionarios))

# --- Aba 2: Gestão de Férias ---
with tab2:
    st.subheader(t("gestao_ferias"))
    ferias = supabase.table("ferias").select("*", "funcionarios(nome)").order("data_inicio", desc=True).execute().data
    st.dataframe(pd.DataFrame(ferias))

# --- Aba 3: Relatórios ---
with tab3:
    st.subheader(t("relatorios_ferias"))
    dados_ferias = supabase.table("ferias").select("*", "funcionarios(id, nome, dias_ferias)").execute().data
    st.dataframe(pd.DataFrame(dados_ferias))

# --- Footer ---
with st.sidebar:
    st.markdown("""
        <div style='height:300px;'></div>
        <div style='font-size:10px; text-align:center;'>
            Powered by NN ®
        </div>
    """, unsafe_allow_html=True)
