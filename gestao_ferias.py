import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
try:
    import matplotlib.pyplot as plt
except ImportError:
    st.error("A biblioteca matplotlib não está instalada. Por favor, instale com: pip install matplotlib")
    st.stop()
from collections import defaultdict

# Configuração inicial
st.set_page_config(page_title="Gestão de Férias", layout="wide")

# Funções auxiliares
def calcular_dias_uteis(inicio, fim):
    try:
        dias = pd.bdate_range(start=inicio, end=fim)
        return len(dias)
    except Exception as e:
        st.error(f"Erro ao calcular dias úteis: {e}")
        return 0

def verificar_sobreposicao(ferias, nova_feria):
    try:
        inicio_novo = nova_feria['Início']
        fim_novo = nova_feria['Fim']
        for f in ferias:
            if f['Funcionário'] == nova_feria['Funcionário']:
                inicio_existente = f['Início']
                fim_existente = f['Fim']
                if not (fim_novo < inicio_existente or inicio_novo > fim_existente):
                    return True
        return False
    except Exception as e:
        st.error(f"Erro ao verificar sobreposição: {e}")
        return True

def verificar_limite_pessoas(ferias, nova_feria, limite):
    try:
        inicio_novo = nova_feria['Início']
        fim_novo = nova_feria['Fim']
        
        dias = pd.bdate_range(start=inicio_novo, end=fim_novo)
        contagem_dias = {dia: 0 for dia in dias}
        
        for f in ferias:
            if f['ID'] != nova_feria['ID']:
                inicio_existente = f['Início']
                fim_existente = f['Fim']
                dias_existentes = pd.bdate_range(start=inicio_existente, end=fim_existente)
                
                for dia in dias_existentes:
                    if dia in contagem_dias:
                        contagem_dias[dia] += 1
        
        for dia in dias:
            contagem_dias[dia] += 1
        
        for dia, count in contagem_dias.items():
            if count > limite:
                return False, dia
        return True, None
    except Exception as e:
        st.error(f"Erro ao verificar limite de pessoas: {e}")
        return False, None

# Restante do código permanece igual...
