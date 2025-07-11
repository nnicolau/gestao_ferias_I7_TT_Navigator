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

# --- Configuração Inicial ---
st.set_page_config(layout="wide")

# --- Carregar Traduções ---
with open("traducao.toml", "r", encoding="utf-8") as f:
    traducoes = toml.load(f)

def t(chave):
    lang = st.session_state.get("lang", "pt")
    return traducoes.get(lang, {}).get(chave, chave)



supabase = init_supabase()

# --- Autenticação ---
def check_auth():
    if 'auth' not in st.session_state:
        st.session_state.auth = False
        
    if st.session_state.auth:
        return True
        
    password = st.text_input(t("senha_acesso"), type="password")
    if password and bcrypt.checkpw(password.encode(), os.getenv('PASSWORD_HASH').encode()):
        st.session_state.auth = True
        st.rerun()
    elif password:
        st.error(t("senha_incorreta"))
    return False

if not check_auth():
    st.stop()

# --- Gerenciamento de Estado ---
class StateManager:
    def get_last_update(self):
        try:
            res = supabase.table("ultima_atualizacao").select("timestamp").eq("id", 1).execute()
            return pd.to_datetime(res.data[0]['timestamp']) if res.data else None
        except Exception as e:
            st.error(f"Erro ao verificar atualizações: {str(e)}")
            return None
    
    def mark_update(self):
        try:
            supabase.table("ultima_atualizacao").upsert({"id": 1, "timestamp": datetime.now().isoformat()}).execute()
            return True
        except Exception as e:
            st.error(f"Erro ao registrar atualização: {str(e)}")
            return False

state = StateManager()

# --- Interface Principal ---
st.title(t("titulo"))
st.sidebar.header(t("configuracoes"))

# Controle de Idioma
lang = st.sidebar.selectbox("🌐 Idioma", ["pt", "en"], index=0 if st.session_state.get("lang", "pt") == "pt" else 1)
if lang != st.session_state.get("lang"):
    st.session_state.lang = lang
    st.rerun()

# Configuração Máxima de Férias
try:
    config = supabase.table("configuracoes").select("*").eq("id", 1).execute().data[0]
    max_ferias = st.sidebar.number_input(t("max_ferias_simultaneas"), value=config['max_ferias_simultaneas'], min_value=1)
    
    if max_ferias != config['max_ferias_simultaneas']:
        supabase.table("configuracoes").update({"max_ferias_simultaneas": max_ferias}).eq("id", 1).execute()
        state.mark_update()
        st.sidebar.success(t("config_atualizada"))
except Exception as e:
    st.error(f"Erro nas configurações: {str(e)}")

# --- Funções Principais ---
def calcular_dias_uteis(inicio, fim):
    try:
        return len(pd.bdate_range(start=inicio, end=fim))
    except Exception:
        return 0

def verificar_disponibilidade(inicio, fim, funcionario_id):
    try:
        # Verifica conflitos com outros funcionários
        res = supabase.table("configuracoes").select("max_ferias_simultaneas").eq("id", 1).execute()
        limite = res.data[0]['max_ferias_simultaneas']
        
        ferias = supabase.table("ferias").select("*").neq("funcionario_id", funcionario_id).execute().data
        
        periodo = pd.date_range(start=inicio, end=fim)
        sobreposicao = pd.Series(0, index=periodo)
        
        for f in ferias:
            f_inicio = pd.to_datetime(f['data_inicio'])
            f_fim = pd.to_datetime(f['data_fim'])
            dias = pd.date_range(start=max(f_inicio, inicio), end=min(f_fim, fim))
            sobreposicao.loc[dias] += 1
        
        conflito = sobreposicao[sobreposicao >= limite]
        return (True, None) if conflito.empty else (False, conflito.index[0].strftime('%d/%m/%Y'))
    except Exception:
        return (False, "Erro na verificação")

# --- Abas Principais ---
tab1, tab2, tab3 = st.tabs([t("gestao_funcionarios"), t("gestao_ferias"), t("relatorios")])

with tab1:
    st.subheader(t("funcionarios"))
    
    # Adicionar Funcionário
    with st.form("novo_funcionario"):
        nome = st.text_input(t("nome"))
        data_admissao = st.date_input(t("data_admissao"))
        dias_base = st.number_input(t("dias_base"), min_value=1, value=22)
        
        if st.form_submit_button(t("adicionar")):
            try:
                supabase.table("funcionarios").insert({
                    "nome": nome,
                    "data_admissao": data_admissao.isoformat(),
                    "dias_ferias": dias_base
                }).execute()
                state.mark_update()
                st.success(t("funcionario_adicionado"))
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"Erro: {str(e)}")
    
    # Lista de Funcionários
    try:
        funcionarios = pd.DataFrame(supabase.table("funcionarios").select("*").execute().data)
        
        if not funcionarios.empty:
            for _, func in funcionarios.iterrows():
                with st.expander(f"📝 {func['nome']}"):
                    with st.form(f"editar_{func['id']}"):
                        novo_nome = st.text_input("Nome", value=func['nome'])
                        nova_data = st.date_input("Admissão", value=pd.to_datetime(func['data_admissao']))
                        novos_dias = st.number_input("Dias Base", value=func['dias_ferias'], min_value=1)
                        
                        if st.form_submit_button("Atualizar"):
                            try:
                                supabase.table("funcionarios").update({
                                    "nome": novo_nome,
                                    "data_admissao": nova_data.isoformat(),
                                    "dias_ferias": novos_dias
                                }).eq("id", func['id']).execute()
                                state.mark_update()
                                st.success("Atualizado!")
                                time.sleep(1)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro: {str(e)}")
                        
                        if st.form_submit_button("Remover"):
                            try:
                                supabase.table("funcionarios").delete().eq("id", func['id']).execute()
                                state.mark_update()
                                st.success("Removido!")
                                time.sleep(1)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro: {str(e)}")
    except Exception as e:
        st.error(f"Erro ao carregar funcionários: {str(e)}")

with tab2:
    st.subheader(t("ferias"))
    
    try:
        # Seleção de Funcionário
        funcionarios = pd.DataFrame(supabase.table("funcionarios").select("id", "nome").execute().data)
        ferias = pd.DataFrame(supabase.table("ferias").select("*", "funcionarios(nome)").execute().data)
        
        # Marcador de Férias
        with st.form("marcar_ferias"):
            funcionario_id = st.selectbox(t("funcionario"), options=funcionarios['id'], 
                                        format_func=lambda x: funcionarios.loc[funcionarios['id'] == x, 'nome'].values[0])
            col1, col2 = st.columns(2)
            with col1:
                inicio = st.date_input(t("inicio"))
            with col2:
                fim = st.date_input(t("fim"))
            ano = st.number_input(t("ano"), min_value=2000, max_value=2100, value=datetime.now().year)
            
            if st.form_submit_button(t("marcar")):
                if fim < inicio:
                    st.error(t("erro_data"))
                else:
                    dias = calcular_dias_uteis(inicio, fim)
                    if dias == 0:
                        st.error(t("sem_dias_uteis"))
                    else:
                        disponivel, conflito = verificar_disponibilidade(inicio, fim, funcionario_id)
                        if disponivel:
                            try:
                                supabase.table("ferias").insert({
                                    "funcionario_id": funcionario_id,
                                    "data_inicio": inicio.isoformat(),
                                    "data_fim": fim.isoformat(),
                                    "dias": dias,
                                    "ano": ano
                                }).execute()
                                state.mark_update()
                                st.success(t("ferias_marcadas"))
                                time.sleep(1)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro: {str(e)}")
                        else:
                            st.error(f"Conflito em {conflito}")
        
        # Lista de Férias
        if not ferias.empty:
            ferias['nome'] = ferias['funcionarios'].apply(lambda x: x['nome'] if isinstance(x, dict) else 'Desconhecido')
            
            for _, fer in ferias.iterrows():
                with st.expander(f"🏖️ {fer['nome']} ({fer['data_inicio']} a {fer['data_fim']})"):
                    with st.form(f"editar_ferias_{fer['id']}"):
                        novo_inicio = st.date_input("Início", value=pd.to_datetime(fer['data_inicio']))
                        novo_fim = st.date_input("Fim", value=pd.to_datetime(fer['data_fim']))
                        
                        if st.form_submit_button("Atualizar"):
                            try:
                                supabase.table("ferias").update({
                                    "data_inicio": novo_inicio.isoformat(),
                                    "data_fim": novo_fim.isoformat(),
                                    "dias": calcular_dias_uteis(novo_inicio, novo_fim)
                                }).eq("id", fer['id']).execute()
                                state.mark_update()
                                st.success("Atualizado!")
                                time.sleep(1)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro: {str(e)}")
                        
                        if st.form_submit_button("Cancelar Férias"):
                            try:
                                supabase.table("ferias").delete().eq("id", fer['id']).execute()
                                state.mark_update()
                                st.success("Cancelado!")
                                time.sleep(1)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro: {str(e)}")
    except Exception as e:
        st.error(f"Erro ao carregar dados: {str(e)}")

with tab3:
    st.subheader(t("relatorios"))
    
    try:
        # Dados para relatórios
        dados = pd.DataFrame(supabase.table("ferias").select("*", "funcionarios(nome, dias_ferias)").execute().data)
        
        if not dados.empty:
            # Processamento dos dados
            dados['nome'] = dados['funcionarios'].apply(lambda x: x['nome'] if isinstance(x, dict) else '')
            dados['dias_base'] = dados['funcionarios'].apply(lambda x: x.get('dias_ferias', 0) if isinstance(x, dict) else 0)
            
            # Relatório de Utilização
            st.subheader("Utilização de Férias")
            resumo = dados.groupby(['nome', 'ano']).agg(
                Utilizados=('dias', 'sum'),
                Base=('dias_base', 'first')
            ).reset_index()
            resumo['Disponíveis'] = resumo['Base'] - resumo['Utilizados']
            st.dataframe(resumo)
            
            # Gráfico de Ocupação
            st.subheader("Ocupação por Período")
            fig, ax = plt.subplots(figsize=(12, 6))
            
            for _, row in dados.iterrows():
                ax.barh(
                    y=row['nome'],
                    width=(pd.to_datetime(row['data_fim']) - pd.to_datetime(row['data_inicio'])).days,
                    left=pd.to_datetime(row['data_inicio']),
                    alpha=0.6
                )
            
            ax.xaxis.set_major_locator(mdates.MonthLocator())
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
            plt.xticks(rotation=45)
            st.pyplot(fig)
        else:
            st.info("Nenhum dado disponível para relatórios")
    except Exception as e:
        st.error(f"Erro ao gerar relatórios: {str(e)}")

# --- Sistema de Atualização Automática ---
update_placeholder = st.empty()

if 'last_update' not in st.session_state:
    st.session_state.last_update = state.get_last_update()

while True:
    try:
        current_update = state.get_last_update()
        
        if current_update and st.session_state.last_update:
            if current_update > st.session_state.last_update:
                st.session_state.last_update = current_update
                update_placeholder.success("Atualizando dados...")
                time.sleep(1)
                st.rerun()
        
        time.sleep(5)
        update_placeholder.empty()
    except Exception as e:
        st.error(f"Erro no sistema de atualização: {str(e)}")
        time.sleep(10)
