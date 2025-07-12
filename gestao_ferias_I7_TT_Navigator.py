import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
from supabase import create_client, Client
import bcrypt
import os
import toml
import time

# --- Carregar traduções ---
with open("traducao.toml", "r", encoding="utf-8") as f:
    traducoes = toml.load(f)

# --- Função de tradução ---
def t(chave):
    lang = st.session_state.get("lang", "pt")
    return traducoes.get(lang, {}).get(chave, chave)

# --- Seleção de idioma ---
if "lang" not in st.session_state:
    st.session_state.lang = "pt"

st.sidebar.selectbox("\U0001F310 Língua / Language", ["pt", "en"], index=0 if st.session_state.lang == "pt" else 1, key="lang")

# --- Carregar variáveis de ambiente ---
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

# --- Atualização automática ---
AUTO_REFRESH_INTERVAL = 15
with st.sidebar:
    auto_refresh = st.checkbox("\U0001F504 Atualização automática", value=False, key="auto_refresh")

if st.session_state.get("auto_refresh", False):
    if 'last_refresh' not in st.session_state:
        st.session_state.last_refresh = time.time()
    if time.time() - st.session_state.last_refresh > AUTO_REFRESH_INTERVAL:
        st.session_state.last_refresh = time.time()
        st.experimental_rerun()

# --- Configuração da página ---
st.set_page_config(page_title=t("titulo"), layout="wide")
col1, col2 = st.columns([1, 4])
with col1:
    st.image("logo2.png", width=400)
with col2:
    st.image("Logotipo.png", width=100)

st.title(t("titulo"))

# --- Sidebar: configurações ---
with st.sidebar:
    st.header(t("configuracoes"))     
    res = supabase.table("configuracoes").select("max_ferias_simultaneas").eq("id", 1).single().execute()
    max_atual = res.data['max_ferias_simultaneas']
    novo_max = st.number_input(t("max_ferias_simultaneas"), min_value=1, value=max_atual)
    if novo_max != max_atual:
        supabase.table("configuracoes").update({"max_ferias_simultaneas": novo_max}).eq("id", 1).execute()
        st.success(t("config_atualizada"))

# --- Tabs com atualização ---
tabs = st.tabs([t("gestao_funcionarios"), t("gestao_ferias"), t("relatorios_ferias")])
tab_labels = ["gestao_funcionarios", "gestao_ferias", "relatorios_ferias"]

for i, tab in enumerate(tabs):
    if st.session_state.get("selected_tab") != tab_labels[i]:
        st.session_state.selected_tab = tab_labels[i]
        st.experimental_rerun()
    break

# --- Funções auxiliares ---
@st.cache_data(ttl=10)
def obter_funcionarios():
    return pd.DataFrame(supabase.table("funcionarios").select("*").order("id").execute().data)

def calcular_dias_uteis(inicio, fim):
    return len(pd.bdate_range(start=inicio, end=fim))

# --- Aba 1: Gestão de Funcionários ---
with tabs[0]:
    st.subheader(t("gestao_funcionarios"))
    funcionarios = obter_funcionarios()

    with st.form("form_funcionario", clear_on_submit=True):
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
            st.cache_data.clear()
            st.rerun()

    if not funcionarios.empty:
        st.dataframe(funcionarios[['id', 'nome', 'data_admissao', 'dias_ferias']])

# --- Aba 2: Gestão de Férias ---
with tabs[1]:
    st.subheader(t("gestao_ferias"))
    funcionarios = obter_funcionarios()

    with st.form("form_ferias", clear_on_submit=True):
        funcionario_id = st.selectbox(
            t("nome"),
            funcionarios['id'],
            format_func=lambda x: funcionarios.loc[funcionarios['id'] == x, 'nome'].values[0]
        )
        col1, col2 = st.columns(2)
        with col1:
            data_inicio = st.date_input(t("inicio"))
        with col2:
            data_fim = st.date_input(t("fim"))

        if st.form_submit_button(t("marcar")):
            if data_fim < data_inicio:
                st.error(t("erro_data_final"))
            else:
                dias = calcular_dias_uteis(data_inicio, data_fim)
                supabase.table("ferias").insert({
                    "funcionario_id": funcionario_id,
                    "data_inicio": data_inicio.isoformat(),
                    "data_fim": data_fim.isoformat(),
                    "dias": dias,
                    "ano": data_inicio.year
                }).execute()
                st.success(t("ferias_marcadas"))
                st.cache_data.clear()
                st.rerun()

    ferias = pd.DataFrame(
        supabase.table("ferias").select("*", "funcionarios(nome)").order("data_inicio", desc=True).execute().data
    )

    if not ferias.empty:
        ferias['nome'] = ferias['funcionarios'].apply(lambda f: f['nome'] if isinstance(f, dict) else '')
        st.dataframe(ferias[['nome', 'data_inicio', 'data_fim', 'dias']])

# --- Aba 3: Relatórios de Férias ---
with tabs[2]:
    st.subheader(t("relatorios_ferias"))
    dados_ferias = pd.DataFrame(
        supabase.table("ferias").select("*", "funcionarios(id, nome, dias_ferias)").execute().data
    )

    if not dados_ferias.empty:
        dados_ferias['data_inicio'] = pd.to_datetime(dados_ferias['data_inicio'])
        dados_ferias['data_fim'] = pd.to_datetime(dados_ferias['data_fim'])
        dados_ferias['funcionario'] = dados_ferias['funcionarios'].apply(lambda x: x.get('nome', '') if isinstance(x, dict) else '')

        st.subheader(t("grafico_sobreposicao"))
        fig, ax = plt.subplots(figsize=(14, 6))
        all_dates = pd.date_range(start=dados_ferias['data_inicio'].min(), end=dados_ferias['data_fim'].max())

        congestion = pd.Series(0, index=all_dates)
        for _, row in dados_ferias.iterrows():
            mask = (all_dates >= row['data_inicio']) & (all_dates <= row['data_fim'])
            congestion[mask] += 1

        for _, row in dados_ferias.iterrows():
            avg_overlap = congestion.loc[row['data_inicio']:row['data_fim']].mean()
            color = 'green' if avg_overlap < 1.5 else 'goldenrod' if avg_overlap < 2.5 else 'red'
            ax.barh(
                y=row['funcionario'],
                width=(row['data_fim'] - row['data_inicio']).days,
                left=row['data_inicio'],
                color=color,
                edgecolor='black',
                alpha=0.7
            )
            if avg_overlap > 1:
                ax.text(
                    x=row['data_inicio'] + (row['data_fim'] - row['data_inicio']) / 2,
                    y=row['funcionario'],
                    s=f"{int(round(avg_overlap))}",
                    va='center',
                    ha='center',
                    fontsize=10,
                    bbox=dict(facecolor='white', alpha=0.8)
                )

        for date in congestion[congestion >= 3].index:
            ax.axvline(x=date, color='darkred', alpha=0.3, linestyle='--')

        ax.set_xlabel(t("data"))
        ax.set_ylabel(t("nome"))
        ax.set_title(t("titulo_grafico"), pad=15)
        ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
        plt.xticks(rotation=45)

        legend_elements = [
            plt.Rectangle((0, 0), 1, 1, color='green', label=t("sem_sobreposicao")),
            plt.Rectangle((0, 0), 1, 1, color='goldenrod', label=t("duas_pessoas")),
            plt.Rectangle((0, 0), 1, 1, color='red', label=t("tres_pessoas"))
        ]
        ax.legend(handles=legend_elements, loc='upper right', title=t("sobreposicao"))

        plt.tight_layout()
        st.pyplot(fig)

# --- Footer na sidebar ---
with st.sidebar:
    st.markdown("""
        <div style='height:300px;'></div>
        <div style='font-size:10px; text-align:center;'>
            Powered by NN ®
        </div>
    """, unsafe_allow_html=True)
