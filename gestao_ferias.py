import streamlit as st
import pandas as pd
from datetime import datetime
import sqlite3
from sqlite3 import Error
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# Configuração inicial
st.set_page_config(page_title="Gestão de Férias", layout="wide")
st.title("📅 Sistema de Gestão de Férias")

# Função para criar/conectar ao banco de dados
def criar_conexao():
    conn = None
    try:
        conn = sqlite3.connect('ferias.db')
        return conn
    except Error as e:
        st.error(f"Erro ao conectar ao banco de dados: {e}")
    return conn

# Criar tabelas se não existirem
def criar_tabelas(conn):
    try:
        cursor = conn.cursor()
        
        # Tabela de funcionários
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS funcionarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            data_admissao TEXT NOT NULL,
            dias_ferias INTEGER NOT NULL
        )''')
        
        # Tabela de férias
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ferias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            funcionario_id INTEGER NOT NULL,
            data_inicio TEXT NOT NULL,
            data_fim TEXT NOT NULL,
            dias INTEGER NOT NULL,
            FOREIGN KEY (funcionario_id) REFERENCES funcionarios (id)
        )''')
        
        # Tabela de configurações
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS configuracoes (
            id INTEGER PRIMARY KEY,
            max_ferias_simultaneas INTEGER NOT NULL
        )''')
        
        # Inserir configuração padrão se não existir
        cursor.execute('SELECT 1 FROM configuracoes WHERE id = 1')
        if not cursor.fetchone():
            cursor.execute('INSERT INTO configuracoes (id, max_ferias_simultaneas) VALUES (1, 2)')
        
        conn.commit()
    except Error as e:
        st.error(f"Erro ao criar tabelas: {e}")

# Inicializar banco de dados
conn = criar_conexao()
if conn:
    criar_tabelas(conn)

# Funções auxiliares
def calcular_dias_uteis(inicio, fim):
    dias = pd.bdate_range(start=inicio, end=fim)
    return len(dias)

def verificar_limite_ferias(conn, nova_inicio, nova_fim, funcionario_id):
    try:
        cursor = conn.cursor()
        
        # Obter o limite máximo
        cursor.execute('SELECT max_ferias_simultaneas FROM configuracoes WHERE id = 1')
        max_simultaneas = cursor.fetchone()[0]
        
        # Converter para objetos date para comparação
        nova_inicio = pd.to_datetime(nova_inicio).date()
        nova_fim = pd.to_datetime(nova_fim).date()
        
        # Obter todas as férias que se sobrepõem ao novo período
        cursor.execute('''
        SELECT f.data_inicio, f.data_fim, fu.nome 
        FROM ferias f
        JOIN funcionarios fu ON f.funcionario_id = fu.id
        WHERE f.funcionario_id != ?
        AND (
            (f.data_inicio BETWEEN ? AND ?) OR
            (f.data_fim BETWEEN ? AND ?) OR
            (? BETWEEN f.data_inicio AND f.data_fim) OR
            (? BETWEEN f.data_inicio AND f.data_fim)
        )
        ''', (funcionario_id, nova_inicio, nova_fim, nova_inicio, nova_fim, nova_inicio, nova_fim))
        
        ferias_conflitantes = cursor.fetchall()
        
        # Verificar dias com mais férias que o permitido
        calendario = pd.DataFrame(columns=['Data', 'Pessoas'])
        
        for ferias in ferias_conflitantes:
            inicio = pd.to_datetime(ferias[0]).date()
            fim = pd.to_datetime(ferias[1]).date()
            
            dias = pd.bdate_range(start=max(inicio, nova_inicio), 
                                end=min(fim, nova_fim))
            
            for dia in dias:
                calendario.loc[len(calendario)] = [dia, 1]
        
        if not calendario.empty:
            contagem = calendario.groupby('Data').sum()
            dias_problema = contagem[contagem['Pessoas'] >= max_simultaneas]
            
            if not dias_problema.empty:
                return False, dias_problema.index[0].strftime('%d/%m/%Y')
        
        return True, None
        
    except Error as e:
        st.error(f"Erro ao verificar limite de férias: {e}")
        return False, None

# Menu lateral
with st.sidebar:
    st.header("Configurações")
    
    if conn:
        cursor = conn.cursor()
        cursor.execute('SELECT max_ferias_simultaneas FROM configuracoes WHERE id = 1')
        max_atual = cursor.fetchone()[0]
        
        novo_max = st.number_input(
            "Máximo em férias simultâneas", 
            min_value=1, 
            value=max_atual,
            key="max_ferias"
        )
        
        if novo_max != max_atual:
            cursor.execute('UPDATE configuracoes SET max_ferias_simultaneas = ? WHERE id = 1', (novo_max,))
            conn.commit()
            st.success("Configuração atualizada!")

# Abas principais
tab1, tab2, tab3  = st.tabs(["Funcionários", "Marcar Férias", "Consultas"])

with tab1:
    st.header("Gestão de Funcionários")
    
    with st.form("novo_funcionario", clear_on_submit=True):
        nome = st.text_input("Nome completo", key="nome_func")
        data_admissao = st.date_input("Data de admissão", key="data_adm")
        dias_ferias = st.number_input("Dias de férias por ano", min_value=1, value=22, key="dias_ferias")
        
        if st.form_submit_button("Cadastrar Funcionário"):
            if conn:
                try:
                    cursor = conn.cursor()
                    cursor.execute(
                        'INSERT INTO funcionarios (nome, data_admissao, dias_ferias) VALUES (?, ?, ?)',
                        (nome, data_admissao.isoformat(), dias_ferias)
                    )
                    conn.commit()
                    st.success("Funcionário cadastrado com sucesso!")
                except Error as e:
                    st.error(f"Erro ao cadastrar funcionário: {e}")
            else:
                st.error("Não foi possível conectar ao banco de dados")
    
    if conn:
        funcionarios = pd.read_sql('SELECT * FROM funcionarios', conn)
        if not funcionarios.empty:
            st.subheader("Funcionários Cadastrados")
            st.dataframe(funcionarios)

with tab2:
    st.header("Marcação de Férias")
    
    if conn:
        funcionarios = pd.read_sql('SELECT id, nome FROM funcionarios', conn)
        
        if not funcionarios.empty:
            with st.form("marcar_ferias", clear_on_submit=True):
                funcionario_id = st.selectbox(
                    "Funcionário",
                    funcionarios['id'],
                    format_func=lambda x: funcionarios.loc[funcionarios['id'] == x, 'nome'].values[0]
                )
                
                col1, col2 = st.columns(2)
                with col1:
                    data_inicio = st.date_input("Data de início")
                with col2:
                    data_fim = st.date_input("Data de fim")
                
                if st.form_submit_button("Marcar Férias"):
                    if data_fim <= data_inicio:
                        st.error("A data final deve ser posterior à data inicial!")
                    else:
                        dias = calcular_dias_uteis(data_inicio, data_fim)
                        
                        # Verificar limite de pessoas em férias
                        limite_ok, dia_problema = verificar_limite_ferias(
                            conn, data_inicio, data_fim, funcionario_id
                        )
                        
                        if not limite_ok:
                            st.error(f"Limite de férias simultâneas excedido no dia {dia_problema}!")
                        else:
                            try:
                                cursor = conn.cursor()
                                cursor.execute(
                                    'INSERT INTO ferias (funcionario_id, data_inicio, data_fim, dias) VALUES (?, ?, ?, ?)',
                                    (funcionario_id, data_inicio.isoformat(), data_fim.isoformat(), dias)
                                )
                                conn.commit()
                                st.success(f"Férias marcadas com sucesso! Total de dias: {dias}")
                            except Error as e:
                                st.error(f"Erro ao marcar férias: {e}")
        else:
            st.warning("Nenhum funcionário cadastrado. Cadastre funcionários primeiro.")

with tab3:
    st.header("Consultas e Relatórios")
    
    if conn:
        st.subheader("Férias Marcadas")
        ferias = pd.read_sql('''
        SELECT f.id, fu.nome as Funcionário, f.data_inicio as Início, f.data_fim as Fim, f.dias as Dias
        FROM ferias f
        JOIN funcionarios fu ON f.funcionario_id = fu.id
        ORDER BY f.data_inicio
        ''', conn)
        
        if not ferias.empty:
            st.dataframe(ferias)
            
            st.subheader("Resumo por Funcionário")
            resumo = pd.read_sql('''
            SELECT 
                fu.nome as Funcionário,
                fu.dias_ferias as "Dias Disponíveis",
                COALESCE(SUM(f.dias), 0) as "Dias Usados",
                (fu.dias_ferias - COALESCE(SUM(f.dias), 0)) as "Dias Restantes"
            FROM funcionarios fu
            LEFT JOIN ferias f ON fu.id = f.funcionario_id
            GROUP BY fu.id, fu.nome, fu.dias_ferias
            ''', conn)
            st.dataframe(resumo)
            
            st.subheader("Próximas Férias")
            hoje = datetime.now().date().isoformat()
            proximas = pd.read_sql(f'''
            SELECT fu.nome as Funcionário, f.data_inicio as Início, f.data_fim as Fim
            FROM ferias f
            JOIN funcionarios fu ON f.funcionario_id = fu.id
            WHERE f.data_inicio >= '{hoje}'
            ORDER BY f.data_inicio
            LIMIT 5
            ''', conn)
            st.dataframe(proximas)
            
            # Gráfico de Gantt melhorado para destacar sobreposições
            st.subheader("Linha do Tempo das Férias (Sobreposições Destacadas)")
            
            # Preparar os dados
            ferias['Início'] = pd.to_datetime(ferias['Início'])
            ferias['Fim'] = pd.to_datetime(ferias['Fim'])
            
            # Criar figura maior para melhor visualização
            fig, ax = plt.subplots(figsize=(14, 8))
            
            # Verificar sobreposições
            dates_range = pd.date_range(
                start=ferias['Início'].min(),
                end=ferias['Fim'].max()
            )
            
            # Calcular congestionamento por dia
            congestionamento = pd.DataFrame(index=dates_range, columns=['count'])
            congestionamento['count'] = 0
            
            for _, row in ferias.iterrows():
                mask = (dates_range >= row['Início']) & (dates_range <= row['Fim'])
                congestionamento.loc[mask, 'count'] += 1
            
            # Mapear cores baseado no nível de sobreposição
            max_overlap = congestionamento['count'].max()
            cmap = plt.get_cmap('RdYlGn_r')  # Vermelho para muitas sobreposições, verde para poucas
            norm = plt.Normalize(1, max_overlap)
            
            # Plotar cada período de férias
            for i, (_, row) in enumerate(ferias.iterrows()):
                # Calcular nível médio de sobreposição para este período
                mask = (dates_range >= row['Início']) & (dates_range <= row['Fim'])
                avg_overlap = congestionamento.loc[mask, 'count'].mean()
                
                # Escolher cor baseada no nível de sobreposição
                color = cmap(norm(avg_overlap))
                
                ax.barh(
                    y=row['Funcionário'],
                    width=(row['Fim'] - row['Início']).days,
                    left=row['Início'],
                    color=color,
                    edgecolor='black',
                    alpha=0.7,
                    label=f"{row['Funcionário']} ({row['Dias']} dias)"
                )
                
                # Adicionar texto com número de sobreposições
                ax.text(
                    x=row['Início'] + (row['Fim'] - row['Início'])/2,
                    y=row['Funcionário'],
                    s=f"{int(avg_overlap)} {'pessoas' if avg_overlap > 1 else 'pessoa'}",
                    va='center',
                    ha='center',
                    color='black',
                    fontweight='bold'
                )
            
            # Adicionar barra de cores para a sobreposição
            sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
            sm.set_array([])
            cbar = plt.colorbar(sm, ax=ax, label='Nível de Sobreposição')
            cbar.set_ticks(range(1, max_overlap + 1))
            
            # Configurações do gráfico
            ax.set_xlabel('Data')
            ax.set_ylabel('Funcionário')
            ax.set_title('Períodos de Férias com Destaque para Sobreposições', pad=20)
            ax.grid(axis='x', linestyle='--', alpha=0.7)
            
            # Formatar datas
            ax.xaxis.set_major_locator(mdates.MonthLocator())
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m/%Y'))
            plt.xticks(rotation=45)
            
            # Adicionar legenda de cores
            handles = [plt.Rectangle((0,0),1,1, color=cmap(norm(i))) for i in range(1, max_overlap+1)]
            ax.legend(handles, [f'{i} sobreposição{"es" if i>1 else ""}' for i in range(1, max_overlap+1)],
                     title="Níveis de Sobreposição", bbox_to_anchor=(1.05, 1), loc='upper left')
            
            plt.tight_layout()
            st.pyplot(fig)
            
        else:
            st.info("Nenhuma férias marcada ainda.")
                
# Fechar conexão ao final
if conn:
    conn.close()
