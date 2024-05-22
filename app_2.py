import streamlit as st
import pandas as pd
from bios_utils.asignador_capacidad import AsignadorCapacidad
from bios_utils.problema import get_inventario_capacidad_planta
from tqdm import tqdm


def leer_archivo(bios_input_file:str) -> dict:

    print('Leyendo archivo')

    # Leer el archivo de excel
    sheets = ['ingredientes', 'plantas', 'safety_stock', 'consumo_proyectado', 'tto_puerto',
              'tto_plantas', 'inventario_puerto',
              'costos_almacenamiento_cargas', 'costos_operacion_portuaria',
              'fletes_cop_per_kg', 'venta_entre_empresas']

    data_frames = dict()

    asignador = AsignadorCapacidad(bios_input_file)

    data_frames['unidades_almacenamiento_df'] = asignador.obtener_unidades_almacenamiento()

    for sheet in tqdm(sheets):
        data_frames[sheet] = pd.read_excel(
            io=bios_input_file, sheet_name=sheet)

    return data_frames


st.write('Seleccione un archivo para trabajar')

uploaded_file = st.file_uploader("Seleccione un archivo para trabajar")

if uploaded_file is not None:

    with st.spinner(text='Espere un momento por favor, se esta cargando el archivo'):

        dataframes = leer_archivo(uploaded_file)
        fletes_df = dataframes['fletes_cop_per_kg']

        inventario_planta_df = get_inventario_capacidad_planta(bios_input_file=uploaded_file)

    st.dataframe(data=inventario_planta_df)
