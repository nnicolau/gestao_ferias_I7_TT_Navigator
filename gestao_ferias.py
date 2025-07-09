import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
from supabase import create_client, Client
import bcrypt
import os
import toml

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

st.sidebar.selectbox("🌐 Língua / Language", ["pt", "en"], index=0 if st.session_state.lang == "pt" else 1, key="lang")

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

# --- Configuração da página ---
st.set_page_config(page_title=t("titulo"), layout="wide")
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


# Funções auxiliares
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
            # Sobreposição encontrada
            return False, ini.strftime('%d/%m/%Y'), fim.strftime('%d/%m/%Y')

    return True, None, None

# Abas
aba1, aba2, aba3 = st.tabs([t("gestao_funcionarios"), t("gestao_ferias"), t("relatorios_ferias")])

# Verificar se a aba mudou
if 'current_tab' not in st.session_state:
    st.session_state.current_tab = None

# Determinar qual aba está ativa
current_tab_active = None
if aba1:
    current_tab_active = "gestao_funcionarios"
elif aba2:
    current_tab_active = "gestao_ferias"
elif aba3:
    current_tab_active = "relatorios_ferias"

# Se a aba mudou, atualizar os dados
if st.session_state.current_tab != current_tab_active:
    st.session_state.current_tab = current_tab_active
    st.rerun()

with aba1:
    st.subheader(t("gestao_funcionarios"))

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

        with st.expander(f"{t('editar_apagar_ferias')} (Funcionários)"):
            for _, row in funcionarios.iterrows():
                with st.form(f"edit_func_{row['id']}"):
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
                            st.rerun()
                    with col2:
                        if st.form_submit_button(t("apagar")):
                            supabase.table("funcionarios").delete().eq("id", row['id']).execute()
                            st.warning(t("removido"))
                            st.rerun()

with aba2:
    st.subheader(t("gestao_ferias"))
    funcionarios = pd.DataFrame(supabase.table("funcionarios").select("id", "nome", "dias_ferias").execute().data)

    if not funcionarios.empty:
        with st.form("marcar_ferias", clear_on_submit=True):
            funcionario_id = st.selectbox(
                t("nome"),
                funcionarios['id'],
                format_func=lambda x: funcionarios.loc[funcionarios['id'] == x, 'nome'].values[0]
            )
            col1, col2, col3 = st.columns(3)
            with col1:
                data_inicio = st.date_input(t("inicio"))
            with col2:
                data_fim = st.date_input(t("fim"))
            with col3:
                ano_ferias = st.number_input(t("ano_ferias"), min_value=2000, max_value=datetime.now().year + 1, value=datetime.now().year)

            if st.form_submit_button(t("marcar")):
                if pd.to_datetime(data_fim) < pd.to_datetime(data_inicio):
                    st.error(t("erro_data_final"))
                else:
                    dias = calcular_dias_uteis(data_inicio, data_fim)
                    if dias == 0:
                        st.error(t("erro_sem_dias_uteis"))
                    else:
                        # Verificar duplicidade para o mesmo funcionário
                        ok_dup, inicio_dup, fim_dup = verificar_duplicidade_ferias(data_inicio, data_fim, funcionario_id)
                        if not ok_dup:
                            st.error(t("erro_duplicado").format(inicio=inicio_dup, fim=fim_dup))
                        else:
                            ok, dia_conflito = verificar_limite_ferias(data_inicio, data_fim, funcionario_id)
                            if not ok:
                                st.error(t("erro_excesso_pessoas").format(dia=dia_conflito))
                            else:
                                # Verificar limite anual de dias por funcionário
                                ferias_ano = supabase.table("ferias").select("dias").eq("funcionario_id", funcionario_id).eq("ano", ano_ferias).execute().data
                                usado_ano = sum([f['dias'] for f in ferias_ano])
                                dias_disponiveis = funcionarios.loc[funcionarios['id'] == funcionario_id, 'dias_ferias'].values[0]
                                if usado_ano + dias > dias_disponiveis:
                                    st.error(t("erro_dias_excedidos").format(usado=usado_ano, disponivel=dias_disponiveis, ano=ano_ferias))
                                else:
                                    supabase.table("ferias").insert({
                                        "funcionario_id": funcionario_id,
                                        "data_inicio": data_inicio.isoformat(),
                                        "data_fim": data_fim.isoformat(),
                                        "dias": dias,
                                        "ano": ano_ferias
                                    }).execute()
                                    st.success(t("ferias_marcadas"))
                                    st.rerun()

        ferias_data = supabase.table("ferias").select("*", "funcionarios(nome)").order("data_inicio", desc=True).execute().data
        ferias = pd.DataFrame(ferias_data)

        if not ferias.empty:
            ferias['nome'] = ferias['funcionarios'].apply(lambda f: f['nome'] if isinstance(f, dict) else '')
            st.dataframe(ferias[['nome', 'data_inicio', 'data_fim', 'dias']])

            with st.expander(t("editar_apagar_ferias")):
                for _, row in ferias.iterrows():
                    with st.form(f"editar_ferias_{row['id']}"):
                        st.markdown(f"**{row['nome']}**")
                        novo_inicio = st.date_input(t("inicio"), value=pd.to_datetime(row['data_inicio']), key=f"inicio_{row['id']}")
                        novo_fim = st.date_input(t("fim"), value=pd.to_datetime(row['data_fim']), key=f"fim_{row['id']}")
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.form_submit_button(t("atualizar")):
                                if novo_fim < novo_inicio:
                                    st.error(t("erro_data_final"))
                                else:
                                    dias = calcular_dias_uteis(novo_inicio, novo_fim)
                                    if dias == 0:
                                        st.error(t("erro_sem_dias_uteis"))
                                    else:
                                        ok_dup, inicio_dup, fim_dup = verificar_duplicidade_ferias(novo_inicio, novo_fim, row['funcionario_id'], ignorar_id=row['id'])
                                        if not ok_dup:
                                            st.error(t("erro_duplicado").format(inicio=inicio_dup, fim=fim_dup))
                                        else:
                                            ok, dia_conflito = verificar_limite_ferias(novo_inicio, novo_fim, row['funcionario_id'])
                                            if not ok:
                                                st.error(t("conflito_ferias").format(dia=dia_conflito))
                                            else:
                                                supabase.table("ferias").update({
                                                    "data_inicio": novo_inicio.isoformat(),
                                                    "data_fim": novo_fim.isoformat(),
                                                    "dias": dias
                                                }).eq("id", row['id']).execute()
                                                st.success(t("ferias_atualizadas"))
                                                st.rerun()
                        with col2:
                            if st.form_submit_button(t("apagar")):
                                supabase.table("ferias").delete().eq("id", row['id']).execute()
                                st.warning(t("ferias_removidas"))
                                st.rerun()

with aba3:
    st.subheader(t("relatorios_ferias"))

    dados_ferias = supabase.table("ferias").select("*", "funcionarios(id, nome, dias_ferias)").execute().data
    ferias_df = pd.DataFrame(dados_ferias)

    if not ferias_df.empty:
        ferias_df['data_inicio'] = pd.to_datetime(ferias_df['data_inicio']).dt.date
        ferias_df['data_fim'] = pd.to_datetime(ferias_df['data_fim']).dt.date
        ferias_df['funcionario'] = ferias_df['funcionarios'].apply(lambda x: x.get('nome', '') if isinstance(x, dict) else '')
        ferias_df['funcionario_id'] = ferias_df['funcionarios'].apply(lambda x: x.get('id', None) if isinstance(x, dict) else None)
        ferias_df['dias_ferias'] = ferias_df['funcionarios'].apply(lambda x: x.get('dias_ferias', 0) if isinstance(x, dict) else 0)

        st.subheader(t("ferias_marcadas_titulo"))
        st.dataframe(ferias_df[['funcionario', 'data_inicio', 'data_fim', 'dias', 'ano']])

        hoje = datetime.now().date()
        proximas = ferias_df[ferias_df['data_inicio'] >= hoje].sort_values(by='data_inicio')
        st.subheader(t("proximas_ferias"))
        st.dataframe(proximas[['funcionario', 'data_inicio', 'data_fim', 'ano']])

        # Férias passadas - sombrear com style
        ferias_df_sorted = ferias_df.sort_values(by='data_inicio')
        def highlight_passadas(row):
            return ['background-color: #f0f0f0' if row['data_fim'] < hoje else '' for _ in row]

        st.subheader(t("historico_futuras"))
        st.dataframe(
            ferias_df_sorted[['funcionario', 'data_inicio', 'data_fim', 'dias', 'ano']]
            .style.apply(highlight_passadas, axis=1)
        )

        st.subheader(t("resumo_funcionario"))
        resumo = ferias_df.groupby(['funcionario', 'funcionario_id', 'ano', 'dias_ferias']).agg(
            Usado=('dias', 'sum')
        ).reset_index()
        resumo['Disponivel'] = resumo['dias_ferias']
        resumo['Restante'] = resumo['Disponivel'] - resumo['Usado']
        resumo.rename(columns={
            'funcionario': t("nome"),
            'ano': t("ano_ferias"),
            'Usado': t("usado"),
            'Disponivel': t("disponivel"),
            'Restante': t("restante")
        }, inplace=True)

        st.dataframe(resumo[[
            t("nome"),
            t("ano_ferias"),
            t("usado"),
            t("disponivel"),
            t("restante")
        ]])

        st.subheader(t("sobreposicao"))
        ferias_df['data_inicio'] = pd.to_datetime(ferias_df['data_inicio'])
        ferias_df['data_fim'] = pd.to_datetime(ferias_df['data_fim'])

        fig, ax = plt.subplots(figsize=(14, 6))
        all_dates = pd.date_range(
            start=ferias_df['data_inicio'].min(),
            end=ferias_df['data_fim'].max()
        )

        congestion = pd.Series(0, index=all_dates)
        for _, row in ferias_df.iterrows():
            mask = (all_dates >= row['data_inicio']) & (all_dates <= row['data_fim'])
            congestion[mask] += 1

        for _, row in ferias_df.iterrows():
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
    else:
        st.info(t("nenhuma_ferias"))

with st.sidebar:
    st.markdown("""
        <div style='height:300px;'></div>
        <div style='font-size:10px; text-align:center;'>
            Powered by NN ®
        </div>
    """, unsafe_allow_html=True)
