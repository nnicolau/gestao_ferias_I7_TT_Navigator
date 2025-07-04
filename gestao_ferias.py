import streamlit as st
import pandas as pd
from datetime import datetime
import sqlite3
from sqlite3 import Error
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# Configuração inicial
st.set_page_config(page_title="Gestão de Férias", layout="wide")
st.image("Logotipo.png", width=50)
st.title("🗕️ Sistema de Gestão de Férias - INDICA7")

# Função para criar/conectar ao banco de dados
def criar_conexao():
    try:
        return sqlite3.connect('ferias.db')
    except Error as e:
        st.error(f"Erro ao conectar ao banco de dados: {e}")
        return None

# Criar tabelas se não existirem
def criar_tabelas(conn):
    try:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS funcionarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            data_admissao TEXT NOT NULL,
            dias_ferias INTEGER NOT NULL)''')

        cursor.execute('''CREATE TABLE IF NOT EXISTS ferias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            funcionario_id INTEGER NOT NULL,
            data_inicio TEXT NOT NULL,
            data_fim TEXT NOT NULL,
            dias INTEGER NOT NULL,
            FOREIGN KEY (funcionario_id) REFERENCES funcionarios (id))''')

        cursor.execute('''CREATE TABLE IF NOT EXISTS configuracoes (
            id INTEGER PRIMARY KEY,
            max_ferias_simultaneas INTEGER NOT NULL)''')

        cursor.execute('SELECT 1 FROM configuracoes WHERE id = 1')
        if not cursor.fetchone():
            cursor.execute('INSERT INTO configuracoes (id, max_ferias_simultaneas) VALUES (1, 2)')

        conn.commit()
    except Error as e:
        st.error(f"Erro ao criar tabelas: {e}")

# Funções auxiliares
def calcular_dias_uteis(inicio, fim):
    return len(pd.bdate_range(start=inicio, end=fim))

def verificar_limite_ferias(conn, nova_inicio, nova_fim, funcionario_id):
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT max_ferias_simultaneas FROM configuracoes WHERE id = 1')
        max_simultaneas = cursor.fetchone()[0]

        nova_inicio = pd.to_datetime(nova_inicio).date()
        nova_fim = pd.to_datetime(nova_fim).date()

        cursor.execute('''SELECT f.data_inicio, f.data_fim FROM ferias f
            WHERE f.funcionario_id != ?
            AND ((f.data_inicio BETWEEN ? AND ?) OR
                 (f.data_fim BETWEEN ? AND ?) OR
                 (? BETWEEN f.data_inicio AND f.data_fim) OR
                 (? BETWEEN f.data_inicio AND f.data_fim))''',
            (funcionario_id, nova_inicio, nova_fim, nova_inicio, nova_fim, nova_inicio, nova_fim))

        ferias_conflitantes = cursor.fetchall()
        calendario = pd.DataFrame(columns=['Data', 'Pessoas'])

        for inicio, fim in ferias_conflitantes:
            dias = pd.bdate_range(start=max(pd.to_datetime(inicio).date(), nova_inicio),
                                  end=min(pd.to_datetime(fim).date(), nova_fim))
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

# Inicializar banco de dados
conn = criar_conexao()
if conn:
    criar_tabelas(conn)

# Sidebar
with st.sidebar:
    st.header("Configurações")
    if conn:
        cursor = conn.cursor()
        cursor.execute('SELECT max_ferias_simultaneas FROM configuracoes WHERE id = 1')
        max_atual = cursor.fetchone()[0]
        novo_max = st.number_input("Máximo em férias simultâneas", min_value=1, value=max_atual)
        if novo_max != max_atual:
            cursor.execute('UPDATE configuracoes SET max_ferias_simultaneas = ? WHERE id = 1', (novo_max,))
            conn.commit()
            st.success("Configuração atualizada!")

# (restante do código permanece o mesmo...)
