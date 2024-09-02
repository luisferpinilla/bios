import streamlit as st
import pandas as pd
from code.client.loader import Loader

# # Modelo de base de datos



@st.cache_data
def convert_df(df):
    # IMPORTANT: Cache the conversion to prevent computation on every rerun
    return df.to_csv().encode("utf-8")


st.set_page_config(layout="wide")

st.button(label='call_back')

st.title('Optimizador BIOS. V2.01')

if 'resultado' not in st.session_state:

    st.write('Seleccione un archivo para trabajar')

    uploaded_file = st.file_uploader("Seleccione un archivo para trabajar")

    if uploaded_file is not None:

        with st.spinner(text='Espere un momento por favor, se esta cargando el archivo'):

            loader = Loader(input_file=uploaded_file)
            loader.load_data()

        with st.spinner(text='Espere un momento por favor, se esta ejecutando el modelo'):    
            loader.gen_solucion_fase_01()
            loader.gen_solucion_fase_02()

            plantas_df, puertos_df, despachos_df = loader.save_reports()
            reportes_dict = {
                "puerto":puertos_df,
                "despacho":despachos_df,
                "planta":plantas_df
            }
            
        st.session_state['resultado'] = reportes_dict

else:

    reportes_dict = st.session_state['resultado']
    puerto = convert_df(reportes_dict['puerto'])
    despachos = convert_df(reportes_dict['despacho'])
    plantas = convert_df(reportes_dict['planta'])
    puertos_tab, despachos_tab, plantas_tab = st.tabs(
        tabs=['Puerto', 'Despachos', 'Plantas'])
    with puertos_tab:
        st.dataframe(reportes_dict['puerto'])
        st.download_button(
            label="Descargar reporte de Puertos",
            data=puerto,
            file_name="reporte_puerto.csv",
            mime="text/csv",
        )
    with despachos_tab:
        st.dataframe(reportes_dict['despacho'])
        st.download_button(
            label="Descargar reporte de Despachos",
            data=despachos,
            file_name="reporte_despachos.csv",
            mime="text/csv",
        )
    with plantas_tab:
        st.dataframe(reportes_dict['planta'])
        st.download_button(
            label="Descargar reporte de Plantas",
            data=plantas,
            file_name="reporte_plantas.csv",
            mime="text/csv",
        )