import streamlit as st
import pandas as pd
from utils.modelo import generar_modelo
from utils.modelo import resolver_modelo
from utils.reporte import generar_reporte


@st.cache_data
def load_data(file: str):
    return generar_modelo(file)


st.set_page_config(layout="wide")

st.title('Optimizador BIOS')

st.write('Seleccione un archivo para trabajar')

uploaded_file = st.file_uploader("Seleccione un archivo para trabajar")

if uploaded_file is not None:

    with st.spinner(text='Espere un momento por favor, se esta cargando el archivo'):

        plantas_df, cargas_df, estadisticas, periodos, variables, validaciones = load_data(
            uploaded_file)

    with st.expander("ver validaciones"):
        for validacion in validaciones:
            if validacion['nivel'] == 'Advertencia':
                st.warning(body=validacion['Mensaje'], icon="⚠️")
            if validacion['nivel'] == 'Critico':
                archivo_es_ejecutable = False
                st.error(body=validacion['Mensaje'], icon="🚨")

    if not 'cargas' in st.session_state:
        if st.button("Ejecutar Modelo (20 minutos aprox)"):
            with st.spinner(text='Ejecutando'):
                resolver_modelo(variables, periodos, cargas_df, plantas_df)
                plantas_df, cargas_df = generar_reporte(
                    plantas_df, cargas_df, variables)
                # Poner en cache la respuesta
                st.session_state['cargas'] = cargas_df
                st.session_state['plantas'] = plantas_df

                st.button(label='Mostrar resultados')

    else:
        # Sacar del cache
        cargas_df = st.session_state['cargas']
        plantas_df = st.session_state['plantas']

        cargas_tab, plantas_tab = st.tabs(
            ['Visualizar Cargas', 'Visualizar Plantas'])

        with cargas_tab:
            st.dataframe(data=cargas_df, hide_index=True)

        with plantas_tab:

            ingrediente_col, planta_col = st.columns(2)

            with ingrediente_col:
                ingrediente = st.select_slider(
                    label='Seleccione un ingrediente',
                    options=plantas_df['ingrediente'].unique())
            with planta_col:
                planta = st.select_slider(
                    label='Seleccione una planta',
                    options=plantas_df['planta'].unique())

            st.dataframe(
                data=plantas_df[(plantas_df['planta'] == planta) & (
                    plantas_df['ingrediente'] == ingrediente)],
                hide_index=True)
