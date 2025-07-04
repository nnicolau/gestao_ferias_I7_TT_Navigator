import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import numpy as np
from collections import defaultdict

# Configuração inicial
st.set_page_config(page_title="Gestão de Férias", layout="wide")

# Funções auxiliares
def calcular_dias_uteis(inicio, fim):
    dias = pd.bdate_range(start=inicio, end=fim)
    return len(dias)

def verificar_sobreposicao(ferias, nova_feria):
    inicio_novo = nova_feria['Início']
    fim_novo = nova_feria['Fim']
    for f in ferias:
        if f['Funcionário'] == nova_feria['Funcionário']:
            inicio_existente = f['Início']
            fim_existente = f['Fim']
            if not (fim_novo < inicio_existente or inicio_novo > fim_existente):
                return True
    return False

def verificar_limite_pessoas(ferias, nova_feria, limite):
    inicio_novo = nova_feria['Início']
    fim_novo = nova_feria['Fim']
    
    # Criar um dicionário para contar pessoas por dia
    dias = pd.bdate_range(start=inicio_novo, end=fim_novo)
    contagem_dias = {dia: 0 for dia in dias}
    
    # Contar férias existentes
    for f in ferias:
        if f['ID'] != nova_feria['ID']:  # Ignorar a própria férias se já estiver na lista
            inicio_existente = f['Início']
            fim_existente = f['Fim']
            dias_existentes = pd.bdate_range(start=inicio_existente, end=fim_existente)
            
            for dia in dias_existentes:
                if dia in contagem_dias:
                    contagem_dias[dia] += 1
    
    # Adicionar a nova férias
    for dia in dias:
        contagem_dias[dia] += 1
    
    # Verificar se algum dia excede o limite
    for dia, count in contagem_dias.items():
        if count > limite:
            return False, dia
    return True, None

# Inicialização do estado da sessão
if 'funcionarios' not in st.session_state:
    st.session_state.funcionarios = []
    
if 'ferias' not in st.session_state:
    st.session_state.ferias = []
    
if 'ferias_id_counter' not in st.session_state:
    st.session_state.ferias_id_counter = 1

if 'dias_ferias_por_ano' not in st.session_state:
    st.session_state.dias_ferias_por_ano = 22
    
if 'limite_pessoas_ferias' not in st.session_state:
    st.session_state.limite_pessoas_ferias = 2

# Interface Streamlit
st.title("📅 Sistema de Gestão de Férias")

# Menu lateral
with st.sidebar:
    st.header("Configurações")
    st.session_state.dias_ferias_por_ano = st.number_input(
        "Dias de férias por ano por funcionário", 
        min_value=1, 
        max_value=60, 
        value=st.session_state.dias_ferias_por_ano
    )
    
    st.session_state.limite_pessoas_ferias = st.number_input(
        "Número máximo de pessoas em férias simultâneas", 
        min_value=1, 
        max_value=20, 
        value=st.session_state.limite_pessoas_ferias
    )
    
    st.markdown("---")
    st.markdown("**Desenvolvido por**")
    st.markdown("Sistema de Gestão de Férias v1.0")

# Abas principais
tab1, tab2, tab3, tab4 = st.tabs(["Funcionários", "Marcar Férias", "Visualizar Férias", "Relatórios"])

with tab1:
    st.header("Gestão de Funcionários")
    
    col1, col2 = st.columns(2)
    
    with col1:
        with st.form("novo_funcionario"):
            st.subheader("Adicionar Novo Funcionário")
            nome = st.text_input("Nome completo")
            data_admissao = st.date_input("Data de admissão", datetime.today())
            dias_ferias = st.number_input(
                "Dias de férias disponíveis", 
                min_value=0, 
                max_value=60, 
                value=st.session_state.dias_ferias_por_ano
            )
            
            if st.form_submit_button("Adicionar Funcionário"):
                novo_funcionario = {
                    "Nome": nome,
                    "Data Admissão": data_admissao,
                    "Dias Férias Disponíveis": dias_ferias,
                    "Dias Férias Usados": 0
                }
                st.session_state.funcionarios.append(novo_funcionario)
                st.success(f"Funcionário {nome} adicionado com sucesso!")
    
    with col2:
        st.subheader("Lista de Funcionários")
        if not st.session_state.funcionarios:
            st.info("Nenhum funcionário cadastrado ainda.")
        else:
            funcionarios_df = pd.DataFrame(st.session_state.funcionarios)
            st.dataframe(funcionarios_df, hide_index=True)

with tab2:
    st.header("Marcar Férias")
    
    if not st.session_state.funcionarios:
        st.warning("Cadastre funcionários antes de marcar férias.")
    else:
        with st.form("marcar_ferias"):
            funcionario = st.selectbox(
                "Funcionário",
                [f["Nome"] for f in st.session_state.funcionarios]
            )
            
            col1, col2 = st.columns(2)
            with col1:
                data_inicio = st.date_input("Data de início")
            with col2:
                data_fim = st.date_input("Data de fim")
            
            if st.form_submit_button("Marcar Férias"):
                # Verificar se data fim é maior que data início
                if data_fim <= data_inicio:
                    st.error("A data de fim deve ser posterior à data de início.")
                else:
                    # Encontrar funcionário
                    func_idx = next(i for i, f in enumerate(st.session_state.funcionarios) if f["Nome"] == funcionario)
                    funcionario_data = st.session_state.funcionarios[func_idx]
                    
                    # Calcular dias úteis
                    dias_ferias = calcular_dias_uteis(data_inicio, data_fim)
                    
                    # Verificar dias disponíveis
                    dias_disponiveis = funcionario_data["Dias Férias Disponíveis"] - funcionario_data["Dias Férias Usados"]
                    if dias_ferias > dias_disponiveis:
                        st.error(f"Funcionário só tem {dias_disponiveis} dias de férias disponíveis.")
                    else:
                        nova_feria = {
                            "ID": st.session_state.ferias_id_counter,
                            "Funcionário": funcionario,
                            "Início": data_inicio,
                            "Fim": data_fim,
                            "Dias": dias_ferias,
                            "Status": "Pendente"
                        }
                        
                        # Verificar sobreposição
                        if verificar_sobreposicao(st.session_state.ferias, nova_feria):
                            st.error("Este funcionário já tem férias marcadas nesse período.")
                        else:
                            # Verificar limite de pessoas
                            limite_ok, dia_problema = verificar_limite_pessoas(
                                st.session_state.ferias, 
                                nova_feria, 
                                st.session_state.limite_pessoas_ferias
                            )
                            
                            if not limite_ok:
                                st.error(f"Limite de pessoas em férias excedido no dia {dia_problema.strftime('%d/%m/%Y')}.")
                            else:
                                st.session_state.ferias.append(nova_feria)
                                st.session_state.funcionarios[func_idx]["Dias Férias Usados"] += dias_ferias
                                st.session_state.ferias_id_counter += 1
                                st.success("Férias marcadas com sucesso!")

with tab3:
    st.header("Visualização de Férias")
    
    if not st.session_state.ferias:
        st.info("Nenhuma férias marcada ainda.")
    else:
        # Mostrar tabela de férias
        ferias_df = pd.DataFrame(st.session_state.ferias)
        st.dataframe(ferias_df, hide_index=True, column_order=["ID", "Funcionário", "Início", "Fim", "Dias", "Status"])
        
        # Gráfico de calendário
        st.subheader("Calendário de Férias")
        
        # Criar dataframe para o calendário
        todas_ferias = []
        for f in st.session_state.ferias:
            dias = pd.bdate_range(start=f['Início'], end=f['Fim'])
            for dia in dias:
                todas_ferias.append({
                    "Data": dia,
                    "Funcionário": f['Funcionário'],
                    "Dias": f['Dias']
                })
        
        if todas_ferias:
            calendario_df = pd.DataFrame(todas_ferias)
            
            # Agrupar por data e contar funcionários
            calendario_agrupado = calendario_df.groupby('Data')['Funcionário'].count().reset_index()
            calendario_agrupado.columns = ['Data', 'Pessoas de Férias']
            
            # Plotar gráfico
            fig, ax = plt.subplots(figsize=(12, 6))
            ax.plot(calendario_agrupado['Data'], calendario_agrupado['Pessoas de Férias'], marker='o')
            ax.axhline(y=st.session_state.limite_pessoas_ferias, color='r', linestyle='--', label='Limite')
            ax.set_title("Pessoas em Férias por Dia")
            ax.set_xlabel("Data")
            ax.set_ylabel("Número de Pessoas")
            ax.legend()
            ax.grid(True)
            plt.xticks(rotation=45)
            st.pyplot(fig)
            
            # Mostrar dias com limite excedido
            dias_excedidos = calendario_agrupado[calendario_agrupado['Pessoas de Férias'] > st.session_state.limite_pessoas_ferias]
            if not dias_excedidos.empty:
                st.warning("⚠️ Dias com limite de férias excedido:")
                st.dataframe(dias_excedidos, hide_index=True)

with tab4:
    st.header("Relatórios e Análises")
    
    if not st.session_state.ferias:
        st.info("Nenhuma férias marcada para gerar relatórios.")
    else:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Resumo por Funcionário")
            funcionarios_resumo = []
            for func in st.session_state.funcionarios:
                ferias_func = [f for f in st.session_state.ferias if f['Funcionário'] == func['Nome']]
                dias_usados = sum(f['Dias'] for f in ferias_func)
                funcionarios_resumo.append({
                    "Funcionário": func['Nome'],
                    "Dias Disponíveis": func['Dias Férias Disponíveis'],
                    "Dias Usados": dias_usados,
                    "Dias Restantes": func['Dias Férias Disponíveis'] - dias_usados
                })
            
            resumo_df = pd.DataFrame(funcionarios_resumo)
            st.dataframe(resumo_df, hide_index=True)
            
            # Gráfico de barras
            fig, ax = plt.subplots(figsize=(10, 6))
            resumo_df.set_index('Funcionário')[['Dias Usados', 'Dias Restantes']].plot(
                kind='bar', 
                stacked=True, 
                ax=ax,
                color=['#1f77b4', '#2ca02c']
            )
            ax.set_title("Dias de Férias por Funcionário")
            ax.set_ylabel("Dias")
            plt.xticks(rotation=45)
            st.pyplot(fig)
        
        with col2:
            st.subheader("Distribuição de Férias")
            
            # Total de dias por mês
            ferias_df = pd.DataFrame(st.session_state.ferias)
            ferias_df['Mês'] = ferias_df['Início'].apply(lambda x: x.strftime('%Y-%m'))
            dias_por_mes = ferias_df.groupby('Mês')['Dias'].sum().reset_index()
            
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.bar(dias_por_mes['Mês'], dias_por_mes['Dias'])
            ax.set_title("Total de Dias de Férias por Mês")
            ax.set_xlabel("Mês")
            ax.set_ylabel("Dias de Férias")
            plt.xticks(rotation=45)
            st.pyplot(fig)
            
            # Top funcionários com mais dias de férias
            st.subheader("Top Funcionários com Mais Dias de Férias")
            top_funcionarios = ferias_df.groupby('Funcionário')['Dias'].sum().nlargest(5).reset_index()
            st.dataframe(top_funcionarios, hide_index=True)

# Rodapé
st.markdown("---")
st.markdown("© 2023 Sistema de Gestão de Férias - Todos os direitos reservados")