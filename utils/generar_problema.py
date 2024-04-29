import pandas as pd
from utils.asignador_capacidad import AsignadorCapacidad
from tqdm import tqdm
from datetime import datetime, timedelta




def leer_archivo(bios_input_file: str) -> dict:
    # Leer el archivo de excel
    sheets = ['ingredientes', 'plantas', 'safety_stock', 'consumo_proyectado', 'tto_puerto',
              'tto_plantas', 'inventario_puerto',
              'costos_almacenamiento_cargas', 'costos_operacion_portuaria',
              'fletes_cop_per_kg', 'venta_entre_empresas']

    data_frames = dict()

    for sheet in sheets:
        data_frames[sheet] = pd.read_excel(
            io=bios_input_file, sheet_name=sheet)

    asignador = AsignadorCapacidad(bios_input_file)

    data_frames['unidades_almacenamiento_df'] = asignador.obtener_unidades_almacenamiento()

    return data_frames




def generar_periodos(problema: dict, dataframes: pd.DataFrame):

    # Obtener el conjunto de periodos
    fechas = [datetime.strptime(x, '%d/%m/%Y')
              for x in dataframes['consumo_proyectado'].drop(columns=['planta', 'ingrediente']).columns]

    periodos = [int(x.strftime('%Y%m%d')) for x in fechas]

    periodo_anterior = fechas[0] - timedelta(days=1)
    periodo_anterior = int(periodo_anterior.strftime('%Y%m%d'))

    print('Hoy: ', periodo_anterior,  ', Periodo inicial: ',
          periodos[0], ', Periodo final', periodos[-1])

    problema['Tiempo'] = {
        'periodo_anterior': periodo_anterior,
        'periodo_inicial': periodos[0],
        'periodo_final': periodos[-1],
        'fechas': fechas,
        'periodos': periodos}


def generar_productos(problema: dict, dataframes: pd.DataFrame):

    problema['productos'] = list(dataframes['ingredientes']['nombre'].unique())


def generar_plantas(problema: dict, dataframes: pd.DataFrame):
    # Generar plantas
    problema['plantas'] = dict()

    for j in dataframes['plantas'].index:
        planta = dataframes['plantas'].loc[j]['planta']
        empresa = dataframes['plantas'].loc[j]['empresa']
        operacion_minutos = dataframes['plantas'].loc[j]['operacion_minutos'] * \
            dataframes['plantas'].loc[j]['plataformas']
        problema['plantas'][planta] = dict()
        problema['plantas'][planta]['empresa'] = empresa
        problema['plantas'][planta]['tiempo_total'] = operacion_minutos
        problema['plantas'][planta]['tiempo_ingrediente'] = dict()
        problema['plantas'][planta]['llegadas_puerto'] = dict()

        for p in problema['productos']:
            t_ingrediente = dataframes['plantas'].loc[j][p]
            problema['plantas'][planta]['tiempo_ingrediente'][p] = t_ingrediente
            problema['plantas'][planta]['llegadas_puerto'][p] = {
                t: list() for t in problema['Tiempo']['periodos']}


def generar_unidades_almacenamiento(problema: dict, dataframes: pd.DataFrame):

    unidades_almacenamiento_df = dataframes['unidades_almacenamiento_df']
    unidades_almacenamiento_df['capacidad'] = unidades_almacenamiento_df.apply(
        lambda x: x[x['ingrediente_actual']], axis=1)
    unidades_almacenamiento_df.drop(
        columns=problema['productos'], inplace=True)
    unidades_almacenamiento_df = unidades_almacenamiento_df.groupby(
        ['planta', 'ingrediente_actual'])[['cantidad_actual', 'capacidad']].sum().reset_index()

    # Agregando la informacion de safety stock
    unidades_almacenamiento_df = pd.merge(left=unidades_almacenamiento_df,
                                          right=dataframes['safety_stock'],
                                          left_on=[
                                              'planta', 'ingrediente_actual'],
                                          right_on=['planta', 'ingrediente'],
                                          how='left').drop(columns='ingrediente')

    # Generar un diccionario para renombrar las columnas de tiempo en consumo proyectado
    consumo_proyectado_renamer = {x: datetime.strptime(x, '%d/%m/%Y').strftime(
        '%Y%m%d') for x in dataframes['consumo_proyectado'].drop(columns=['planta', 'ingrediente']).columns}
    # Efectuar el cambio de nombre
    consumo_proyectado_df.rename(
        columns=consumo_proyectado_renamer, inplace=True)
    # Unir con el consumo proyectado
    unidades_almacenamiento_df = pd.merge(left=unidades_almacenamiento_df,
                                          right=consumo_proyectado_df,
                                          left_on=[
                                              'planta', 'ingrediente_actual'],
                                          right_on=['planta', 'ingrediente'],
                                          how='left').drop(columns=['ingrediente']).rename(columns={'ingrediente_actual': 'ingrediente', 'cantidad_actual': 'cantidad'}).fillna(0.0)

    print(unidades_almacenamiento_df.shape)
    unidades_almacenamiento_df.head()
