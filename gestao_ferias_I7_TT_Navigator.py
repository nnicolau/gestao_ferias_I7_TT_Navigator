import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
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

# --- Configuração Inicial ---
st.set_page_config(page_title=t("titulo"), layout="wide")

# --- Conexão com Supabase ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Sistema de Atualização em Tempo Real Alternativo ---
class StateManager:
    def __init__(self, supabase_client):
        self.supabase = supabase_client
        self.last_update = None
    
    def get_last_update(self):
        try:
            res = self.supabase.table("ultima_atualizacao").select("timestamp").eq("id", 1).execute()
            return pd.to_datetime(res.data[0]['timestamp']) if res.data else None
        except Exception as e:
            st.error(f"Erro ao obter última atualização: {str(e)}")
            return None
    
    def mark_update(self):
        try:
            self.supabase.table("ultima_atualizacao").upsert({
                "id": 1,
                "timestamp": datetime.now().isoformat()
            }).execute()
            return True
        except Exception as e:
            st.error(f"Erro ao marcar atualização: {str(e)}")
            return False

state_manager = StateManager(supabase)

# --- Autenticação ---
def check_password():
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    
    if st.session_state.authenticated:
        return True
        
    password = st.text_input(t("senha_acesso"), type="password", key="pw_input")
    if password and bcrypt.checkpw(password.encode(), os.getenv('PASSWORD_HASH').encode()):
        st.session_state.authenticated = True
        st.session_state.last_update = state_manager.get_last_update()
        st.rerun()
    elif password:
        st.error(t("senha_incorreta"))
    return False

if not check_password():
    st.stop()

# --- Layout Principal ---
col1, col2 = st.columns([1, 4])
with col1:
    st.image("logo2.png", width=400)
with col2:
    st.image("Logotipo.png", width=100)

st.title(t("titulo"))

# --- Sidebar ---
with st.sidebar:
    st.header(t("configuracoes"))
    
    # Seleção de idioma
    lang = st.selectbox("🌐 Língua / Language", ["pt", "en"], index=0 if st.session_state.get("lang", "pt") == "pt" else 1)
    if lang != st.session_state.get("lang"):
        st.session_state.lang = lang
        st.rerun()
    
    # Configuração máxima de férias
    res = supabase.table("configuracoes").select("max_ferias_simultaneas").eq("id", 1).single().execute()
    max_atual = res.data['max_ferias_simultaneas']
    novo_max = st.number_input(t("max_ferias_simultaneas"), min_value=1, value=max_atual)
    
    if novo_max != max_atual:
        supabase.table("configuracoes").update({"max_ferias_simultaneas": novo_max}).eq("id", 1).execute()
        if state_manager.mark_update():
            st.success(t("config_atualizada"))
            time.sleep(1)
            st.rerun()

# --- Funções Auxiliares ---
def calcular_dias_uteis(inicio, fim):
    inicio = pd.to_datetime(inicio)
    fim = pd.to_datetime(fim)
    return len(pd.bdate_range(start=inicio, end=fim))

def verificar_limite_ferias(inicio, fim, funcionario_id):
    inicio = pd.to_datetime(inicio)
    fim = pd.to_datetime(fim)
    
    res = supabase.table("configuracoes").select("max_ferias_simultaneas").eq("id", 1).single().execute()
    max_simultaneas = res.data['max_ferias_simultaneas']
    
    ferias = supabase.table("ferias").select("*").neq("funcionario_id", funcionario_id).execute().data
    
    calendario = pd.Series(0, index=pd.bdate_range(start=inicio, end=fim))
    
    for f in ferias:
        f_inicio = pd.to_datetime(f['data_inicio'])
        f_fim = pd.to_datetime(f['data_fim'])
        
        periodo = pd.bdate_range(
            start=max(f_inicio, inicio),
            end=min(f_fim, fim)
        )
        calendario.loc[periodo] += 1
    
    conflito = calendario[calendario >= max_simultaneas]
    return (True, None) if conflito.empty else (False, conflito.index[0].strftime('%d/%m/%Y'))

# --- Verificação de Atualizações ---
def check_for_updates():
    if 'last_update' not in st.session_state:
        st.session_state.last_update = state_manager.get_last_update()
    
    current_update = state_manager.get_last_update()
    
    if current_update and st.session_state.last_update:
        if current_update > st.session_state.last_update:
            st.session_state.last_update = current_update
            st.rerun()
    elif current_update:
        st.session_state.last_update = current_update

# --- Abas Principais ---
tab1, tab2, tab3 = st.tabs([t("gestao_funcionarios"), t("gestao_ferias"), t("relatorios_ferias")])

# Aba 1: Gestão de Funcionários
with tab1:
    st.subheader(t("gestao_funcionarios"))
    
    # Formulário de adição
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
            if state_manager.mark_update():
                st.success(t("funcionario_adicionado"))
                time.sleep(1)
                st.rerun()
    
    # Lista de funcionários
    funcionarios = pd.DataFrame(
        supabase.table("funcionarios").select("*").order("id").execute().data
    )
    
    if not funcionarios.empty:
        st.dataframe(funcionarios)
        
        # Edição de funcionários
        with st.expander(t("editar_funcionarios")):
            for _, func in funcionarios.iterrows():
                with st.form(f"edit_func_{func['id']}"):
                    st.write(f"**{func['nome']}**")
                    novo_nome = st.text_input(t("nome"), value=func['nome'], key=f"nome_{func['id']}")
                    nova_data = st.date_input(t("data_admissao"), value=pd.to_datetime(func['data_admissao']), key=f"data_{func['id']}")
                    novos_dias = st.number_input(t("dias_ferias_ano"), min_value=1, value=func['dias_ferias'], key=f"dias_{func['id']}")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.form_submit_button(t("atualizar")):
                            supabase.table("funcionarios").update({
                                "nome": novo_nome,
                                "data_admissao": nova_data.isoformat(),
                                "dias_ferias": novos_dias
                            }).eq("id", func['id']).execute()
                            if state_manager.mark_update():
                                st.success(t("atualizado"))
                                time.sleep(1)
                                st.rerun()
                    with col2:
                        if st.form_submit_button(t("remover")):
                            supabase.table("funcionarios").delete().eq("id", func['id']).execute()
                            if state_manager.mark_update():
                                st.success(t("removido"))
                                time.sleep(1)
                                st.rerun()

# Aba 2: Gestão de Férias
with tab2:
    st.subheader(t("gestao_ferias"))
    
    # Carregar dados
    funcionarios = pd.DataFrame(
        supabase.table("funcionarios").select("id", "nome").execute().data
    )
    ferias = pd.DataFrame(
        supabase.table("ferias").select("*", "funcionarios(nome)").order("data_inicio", desc=True).execute().data
    )
    
    # Formulário de marcação de férias
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
        ano_ferias = st.number_input(t("ano_ferias"), min_value=2000, max_value=datetime.now().year + 1, value=datetime.now().year)
        
        if st.form_submit_button(t("marcar")):
            if data_fim < data_inicio:
                st.error(t("erro_data_final"))
            else:
                dias = calcular_dias_uteis(data_inicio, data_fim)
                if dias == 0:
                    st.error(t("erro_sem_dias_uteis"))
                else:
                    ok, dia = verificar_limite_ferias(data_inicio, data_fim, funcionario_id)
                    if not ok:
                        st.error(t("erro_excesso_pessoas").format(dia=dia))
                    else:
                        supabase.table("ferias").insert({
                            "funcionario_id": funcionario_id,
                            "data_inicio": data_inicio.isoformat(),
                            "data_fim": data_fim.isoformat(),
                            "dias": dias,
                            "ano": ano_ferias
                        }).execute()
                        if state_manager.mark_update():
                            st.success(t("ferias_marcadas"))
                            time.sleep(1)
                            st.rerun()
    
    # Lista de férias
    if not ferias.empty:
        ferias['nome'] = ferias['funcionarios'].apply(lambda x: x['nome'] if isinstance(x, dict) else '')
        st.dataframe(ferias[['nome', 'data_inicio', 'data_fim', 'dias', 'ano']])
        
        # Edição de férias
        with st.expander(t("editar_ferias")):
            for _, fer in ferias.iterrows():
                with st.form(f"edit_ferias_{fer['id']}"):
                    st.write(f"**{fer['nome']}**")
                    novo_inicio = st.date_input(t("inicio"), value=pd.to_datetime(fer['data_inicio']), key=f"inicio_{fer['id']}")
                    novo_fim = st.date_input(t("fim"), value=pd.to_datetime(fer['data_fim']), key=f"fim_{fer['id']}")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.form_submit_button(t("atualizar")):
                            if novo_fim < novo_inicio:
                                st.error(t("erro_data_final"))
                            else:
                                dias = calcular_dias_uteis(novo_inicio, novo_fim)
                                supabase.table("ferias").update({
                                    "data_inicio": novo_inicio.isoformat(),
                                    "data_fim": novo_fim.isoformat(),
                                    "dias": dias
                                }).eq("id", fer['id']).execute()
                                if state_manager.mark_update():
                                    st.success(t("ferias_atualizadas"))
                                    time.sleep(1)
                                    st.rerun()
                    with col2:
                        if st.form_submit_button(t("remover")):
                            supabase.table("ferias").delete().eq("id", fer['id']).execute()
                            if state_manager.mark_update():
                                st.success(t("ferias_removidas"))
                                time.sleep(1)
                                st.rerun()

# Aba 3: Relatórios de Férias
with tab3:
    st.subheader(t("relatorios_ferias"))
    
    dados = pd.DataFrame(
        supabase.table("ferias").select("*", "funcionarios(nome, dias_ferias)").execute().data
    )
    
    if not dados.empty:
        # Processar dados
        dados['data_inicio'] = pd.to_datetime(dados['data_inicio'])
        dados['data_fim'] = pd.to_datetime(dados['data_fim'])
        dados['nome'] = dados['funcionarios'].apply(lambda x: x['nome'] if isinstance(x, dict) else '')
        dados['dias_ferias'] = dados['funcionarios'].apply(lambda x: x.get('dias_ferias', 0) if isinstance(x, dict) else 0)
        
        # Relatório consolidado
        st.subheader(t("resumo_ferias"))
        hoje = datetime.now().date()
        
        # Férias futuras
        futuras = dados[dados['data_inicio'] >= hoje]
        if not futuras.empty:
            st.write(t("proximas_ferias"))
            st.dataframe(futuras[['nome', 'data_inicio', 'data_fim', 'dias']])
        
        # Consumo por funcionário
        st.subheader(t("consumo_ferias"))
        resumo = dados.groupby(['nome', 'ano']).agg(
            Usados=('dias', 'sum'),
            Disponíveis=('dias_ferias', 'first')
        ).reset_index()
        resumo['Restantes'] = resumo['Disponíveis'] - resumo['Usados']
        st.dataframe(resumo)
        
        # Gráfico de sobreposição
        st.subheader(t("sobreposicao_ferias"))
        fig, ax = plt.subplots(figsize=(10, 6))
        
        for _, row in dados.iterrows():
            ax.barh(
                y=row['nome'],
                width=(row['data_fim'] - row['data_inicio']).days,
                left=row['data_inicio'],
                alpha=0.6
            )
        
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
        plt.xticks(rotation=45)
        plt.tight_layout()
        st.pyplot(fig)
    else:
        st.info(t("nenhuma_ferias_registrada"))

# --- Sistema de Atualização Contínua ---
update_placeholder = st.empty()

while True:
    check_for_updates()
    time.sleep(5)  # Verifica a cada 5 segundos
    update_placeholder.empty()  # Limpa qualquer mensagem de atualização
