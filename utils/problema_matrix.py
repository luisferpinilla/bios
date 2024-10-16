import pandas as pd
import numpy as np
from utils.asignador_capacidad import AsignadorCapacidad
from utils.objetivo_inventario import obtener_objetivo_inventario
from tqdm import tqdm
from datetime import datetime, timedelta


def _generar_dataframe_plantas(matriz: list) -> pd.DataFrame:

    fixed_columns = ['planta', 'ingrediente', 'variable']

    df = pd.DataFrame(matriz).fillna(0.0)

    per = [x for x in df.drop(columns=fixed_columns).columns]

    per = sorted(per)

    sorted_colums = fixed_columns + per

    df = df.groupby(fixed_columns)[per].sum().reset_index()

    df = df[sorted_colums]

    df. sort_values(fixed_columns, inplace=True)

    return df


def leer_archivo(bios_input_file: str) -> dict:

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


def __generar_periodos(dataframes: pd.DataFrame) -> list():

    print('generando periodos')

    consumo_df = dataframes['consumo_proyectado'].copy()

    periodos = [datetime.strptime(
        x, '%d/%m/%Y') for x in consumo_df.drop(columns=['planta', 'ingrediente']).columns]

    return periodos


def __generar_consumo(dataframes: pd.DataFrame, periodos: list) -> list():

    print('generando consumo')

    matriz = list()

    consumo_df = dataframes['consumo_proyectado'].copy()

    renamers = {x: datetime.strptime(
        x, '%d/%m/%Y') for x in consumo_df.drop(columns=['planta', 'ingrediente']).columns}

    consumo_df.rename(columns=renamers, inplace=True)

    consumo_df = consumo_df.groupby(['planta', 'ingrediente'])[
        periodos].sum().reset_index()

    for i in tqdm(consumo_df.index):
        dato = dict()

        dato['planta'] = consumo_df.loc[i]['planta']
        dato['ingrediente'] = consumo_df.loc[i]['ingrediente']
        dato['variable'] = 'consumo'

        for periodo in periodos:
            dato[periodo] = consumo_df.loc[i][periodo]

        matriz.append(dato)

    return matriz


def __generar_capacidad_recepcion(dataframes: pd.DataFrame, periodos: list, matriz: list) -> list():

    print('generando capacidad recepcion')

    capacidad_df = dataframes['plantas'].copy()

    ingredientes = list(capacidad_df.drop(columns=[
                        'planta', 'empresa', 'operacion_minutos', 'minutos_limpieza', 'plataformas']).columns)

    for i in tqdm(capacidad_df.index):
        total = dict()

        total['planta'] = capacidad_df.loc[i]['planta']
        total['ingrediente'] = "total"
        total['variable'] = 'capacidad_total_minutos_dia'

        limpieza = dict()
        limpieza['planta'] = capacidad_df.loc[i]['planta']
        limpieza['ingrediente'] = "total"
        limpieza['variable'] = 'minutos_limpieza'

        for periodo in periodos:
            total[periodo] = float(
                capacidad_df.loc[i]['operacion_minutos']*capacidad_df.loc[i]['plataformas'])
            limpieza[periodo] = float(capacidad_df.loc[i]['minutos_limpieza'])

        matriz.append(total)
        matriz.append(limpieza)

        for ingrediente in ingredientes:

            por_ingrediente = dict()
            por_ingrediente['planta'] = capacidad_df.loc[i]['planta']
            por_ingrediente['ingrediente'] = ingrediente
            por_ingrediente['variable'] = 'minutos_por_ingrediente'

            for periodo in periodos:
                por_ingrediente[periodo] = float(
                    capacidad_df.loc[i][ingrediente])

            matriz.append(por_ingrediente)


def __generar_capacidad_almacenamiento(matriz: list, periodos: list, dataframes: pd.DataFrame):

    print('trabajando con unidades de almacenamiento')

    unidades_almacenamiento_df = dataframes['unidades_almacenamiento_df'].copy(
    )

    unidades_almacenamiento_df['capacidad_max'] = unidades_almacenamiento_df.apply(
        lambda x: x[x['ingrediente_actual']], axis=1)

    unidades_almacenamiento_df = unidades_almacenamiento_df.groupby(
        ['planta', 'ingrediente_actual'])[['cantidad_actual', 'capacidad_max']].sum().reset_index()

    for i in tqdm(unidades_almacenamiento_df.index):

        # Incluir capacidad
        dato = dict()
        dato['planta'] = unidades_almacenamiento_df.loc[i]['planta']
        dato['ingrediente'] = unidades_almacenamiento_df.loc[i]['ingrediente_actual']
        dato['variable'] = 'capacidad_max'

        for periodo in periodos:
            dato[periodo] = unidades_almacenamiento_df.loc[i]['capacidad_max']

        matriz.append(dato)

        # Agregar inventario inicial
        dato = dict()
        dato['planta'] = unidades_almacenamiento_df.loc[i]['planta']
        dato['ingrediente'] = unidades_almacenamiento_df.loc[i]['ingrediente_actual']
        dato['variable'] = 'inventario'

        periodo_anterior = periodos[0] - timedelta(days=1)

        dato[periodo_anterior] = unidades_almacenamiento_df.loc[i]['cantidad_actual']

        matriz.append(dato)


def __generar_llegadas_ya_planeadas(matriz: list, periodos: list, dataframes: pd.DataFrame):

    print('trabajando con llegadas planeadas a planta')

    tto_plantas = dataframes['tto_plantas'].copy()

    tto_plantas = tto_plantas.groupby(['planta', 'ingrediente', 'fecha_llegada'])[
        ['cantidad']].sum().reset_index()

    for i in tqdm(tto_plantas.index):

        dato = dict()

        dato['planta'] = tto_plantas.loc[i]['planta']
        dato['ingrediente'] = tto_plantas.loc[i]['ingrediente']
        dato['variable'] = 'llegadas_planeadas'

        periodo = tto_plantas.loc[i]['fecha_llegada']
        dato[periodo] = tto_plantas.loc[i]['cantidad']

        if periodo in periodos:
            matriz.append(dato)


def __generar_safety_stock(matriz: list, periodos: list, dataframes: pd.DataFrame):

    print('trabajando con safety stock en planta')

    safety_stock = dataframes['safety_stock'].copy()

    consumo_proyectado = dataframes['consumo_proyectado'].copy()

    renamers = {x: datetime.strptime(
        x, '%d/%m/%Y') for x in consumo_proyectado.drop(columns=['planta', 'ingrediente']).columns}

    consumo_proyectado.rename(columns=renamers, inplace=True)

    for i in tqdm(safety_stock.index):
        planta = safety_stock.loc[i]['planta']
        ingrediente = safety_stock.loc[i]['ingrediente']
        dias_ss = int(safety_stock.loc[i]['dias_ss'])
        consumo = consumo_proyectado[(consumo_proyectado['planta'] == planta) & (
            consumo_proyectado['ingrediente'] == ingrediente)]

        if consumo.shape[0] > 0:

            for periodo in periodos:

                periodo_inicial = list(consumo.columns).index(periodo)
                periodo_final = periodo + timedelta(days=dias_ss)

                if periodo_final in list(consumo.columns):
                    ss_kg = np.sum(consumo.iloc[0][periodo_inicial:list(
                        consumo.columns).index(periodo_final)])
                else:
                    ss_kg = np.mean(consumo.iloc[0][periodo_inicial:])*dias_ss

                dato = dict()

                dato['planta'] = planta
                dato['ingrediente'] = ingrediente
                dato['variable'] = 'safety_stock'
                dato[periodo] = ss_kg

                matriz.append(dato)


def __completar_inventario_planta(matriz: list):

    print('calculando inventarios')

    df = _generar_dataframe_plantas(matriz)

    fixed_columns = ['planta', 'ingrediente', 'variable']

    per = [x for x in df.drop(columns=fixed_columns).columns]

    per = sorted(per)

    # Llenar el inventario inicial

    plantas = list(df['planta'].unique())

    ingredientes = list(df['ingrediente'].unique())

    for planta in tqdm(plantas):
        for ingrediente in ingredientes:

            consumo = df[(df['planta'] == planta) & (
                df['ingrediente'] == ingrediente) & (df['variable'] == 'consumo')].copy()
            llegadas_planeadas = df[(df['planta'] == planta) & (
                df['ingrediente'] == ingrediente) & (df['variable'] == 'llegadas_planeadas')].copy()
            inventario = df[(df['planta'] == planta) & (
                df['ingrediente'] == ingrediente) & (df['variable'] == 'inventario')].copy()

            # Si hay datos de inventario vas a calcula los inventarios en el tiempo
            if inventario.shape[0] > 0:
                inventario_t = inventario.iloc[0][per[0]]

                for periodo in per[1:]:

                    if consumo.shape[0] > 0:
                        consumo_t = consumo.iloc[0][periodo]
                    else:
                        consumo_t = 0.0

                    if llegadas_planeadas.shape[0] > 0:
                        llegadas_t = llegadas_planeadas.iloc[0][periodo]
                    else:
                        llegadas_t = 0.0

                    inventario_t = inventario_t + llegadas_t - consumo_t

                    if inventario_t >= 0:
                        backorder_t = 0.0
                    else:
                        backorder_t = -1*inventario_t
                        inventario_t = 0.0

                    dato = {
                        'planta': planta,
                        'ingrediente': ingrediente,
                        'variable': 'inventario',
                        periodo: inventario_t
                    }
                    matriz.append(dato)

                    dato = {
                        'planta': planta,
                        'ingrediente': ingrediente,
                        'variable': 'backorder',
                        periodo: backorder_t
                    }

                    matriz.append(dato)

            else:  # Si no tienes inventarios, vas a llenar inventarios en el tiempo en cero.
                for periodo in per:

                    dato = {
                        'planta': planta,
                        'ingrediente': ingrediente,
                        'variable': 'inventario',
                        periodo: 0.0
                    }
                    matriz.append(dato)

                    dato = {
                        'planta': planta,
                        'ingrediente': ingrediente,
                        'variable': 'backorder',
                        periodo: 0.0
                    }

                    matriz.append(dato)


def validar_capacidad_almacenamiento(df: pd.DataFrame, periodos: list):

    df = df[df['variable'].isin(
        ['consumo', 'capacidad_max', 'safety_stock'])].copy()

    id_vars = ['planta', 'ingrediente', 'variable']

    value_vars = list(df.drop(columns=id_vars).columns)

    df = df.melt(id_vars=id_vars, value_vars=value_vars,
                 var_name='periodo', value_name='valor').copy()
    df = df[df['periodo'].isin(periodos)]

    df = df.pivot_table(
        index=['planta', 'ingrediente', 'periodo'], columns='variable', values='valor')
    df = df.groupby(['planta', 'ingrediente']).agg(
        {'capacidad_max': 'mean', 'consumo': 'mean', 'safety_stock': 'mean'}).fillna(0.0)

    df['camiones_consumo'] = df['consumo'].apply(
        lambda x: 34000/x if x > 0.0 else 0.0)

    def validate(x):

        validaciones = list()

        consumo = x['consumo']
        capacidad = x['capacidad_max']
        safety_stock = x['safety_stock']
        consumo_total = consumo*len(periodos)

        if consumo < 0 and safety_stock > 0:
            validaciones.append(
                ('bajo', 'se ha definido safety stock en días con consumos de 0'))

        if consumo > 0 and capacidad <= 0:
            validaciones.append(
                ('alto', 'existen consumos definidos pero no existe capacidad de almacenamiento'))

        if consumo > 0:
            if capacidad < safety_stock + 34000:
                validaciones.append(
                    ('alto', 'La capacidad definida y el SS no permiten recibir al menos un camiones'))

        return validaciones

    df['validaciones'] = df.apply(validate, axis=1)


def __obtener_matriz_objetivo_inventario(matriz: list, periodos: list, estadisticas: dict):

    objetivo_inventario_df = estadisticas['objetivo_inventario'].copy()

    objetivo_inventario_df.set_index(['planta', 'ingrediente'], inplace=True)

    for i in objetivo_inventario_df.index:

        dato = {
            'planta': i[0],
            'ingrediente': i[1],
            'variable': 'objetivo_inventario',
            periodos[-1]: objetivo_inventario_df.loc[i]['objetivo_kg']
        }
        matriz.append(dato)


def obtener_matriz_plantas(dataframes: dict, periodos: list, estadisticas) -> pd.DataFrame:

    matriz = __generar_consumo(dataframes, periodos)

    __generar_capacidad_almacenamiento(matriz, periodos, dataframes)

    __generar_capacidad_recepcion(dataframes, periodos, matriz)

    __generar_llegadas_ya_planeadas(matriz, periodos, dataframes)

    __generar_safety_stock(matriz, periodos, dataframes)

    __obtener_matriz_objetivo_inventario(matriz, periodos, estadisticas)

    __completar_inventario_planta(matriz)

    df = _generar_dataframe_plantas(matriz)

    return df


###################
# Informacion sobre cargas
###################


def _generar_dataframe_cargas(matriz: list, periodos: list) -> pd.DataFrame:

    fixed_columns = ['ingrediente', 'importacion',
                     'empresa', 'puerto', 'operador', 'variable']

    df = pd.DataFrame(matriz).fillna(0.0)

    periodo_anterior = periodos[0] - timedelta(days=1)

    horizonte = [periodo_anterior] + periodos

    per = [x for x in df.drop(columns=fixed_columns).columns if x in horizonte]

    per = sorted(per)

    sorted_colums = fixed_columns + per

    df = df.groupby(fixed_columns)[per].sum().reset_index()

    df = df[sorted_colums]

    df. sort_values(fixed_columns, inplace=True)

    return df


def _obtener_inventarios_puerto(periodos: list, dataframes: dict):

    print('obtener inventarios en puerto')

    periodo_anterior = periodos[0] - timedelta(days=1)

    inventario_puerto = dataframes['inventario_puerto'].copy()

    matriz = list()

    for i in tqdm(inventario_puerto.index):

        ingrediente = inventario_puerto.loc[i]['ingrediente']
        importacion = inventario_puerto.loc[i]['importacion']
        empresa = inventario_puerto.loc[i]['empresa']
        puerto = inventario_puerto.loc[i]['puerto']
        operador = inventario_puerto.loc[i]['operador']
        valor_cif = inventario_puerto.loc[i]['valor_cif_kg']
        cantidad_kg = inventario_puerto.loc[i]['cantidad_kg']

        cif = dict()
        cif['ingrediente'] = ingrediente
        cif['importacion'] = importacion
        cif['empresa'] = empresa
        cif['puerto'] = puerto
        cif['operador'] = operador
        cif['variable'] = 'valor_cif'

        for periodo in periodos:
            cif[periodo] = valor_cif

        matriz.append(cif)

        dato = dict()

        dato['ingrediente'] = ingrediente
        dato['importacion'] = importacion
        dato['empresa'] = empresa
        dato['puerto'] = puerto
        dato['operador'] = operador
        dato['variable'] = 'inventario'
        dato[periodo_anterior] = cantidad_kg

        matriz.append(dato)

    return matriz


def _obtener_transitos_a_puerto(matriz: list, periodos: list, dataframes: dict, capacidad_recepcion=5000000):

    print('obtener transitos a puerto')

    transitos = dataframes['tto_puerto'].copy()

    costos_portuarios = dataframes['costos_operacion_portuaria'].copy()

    transitos['fecha_llegada'] = pd.to_datetime(transitos['fecha_llegada'])

    for i in tqdm(transitos.index):

        ingrediente = transitos.loc[i]['ingrediente']
        importacion = transitos.loc[i]['importacion']
        empresa = transitos.loc[i]['empresa']
        puerto = transitos.loc[i]['puerto']
        operador = transitos.loc[i]['operador']
        valor_cif = transitos.loc[i]['valor_kg']
        arrival_date = transitos.loc[i]['fecha_llegada']
        cantidad_llegada = float(transitos.loc[i]['cantidad_kg'])

        costo_bodegaje_df = costos_portuarios[(costos_portuarios['puerto'] == puerto) & (costos_portuarios['operador'] == operador) & (
            costos_portuarios['ingrediente'] == ingrediente) & (costos_portuarios['tipo_operacion'] == 'bodega')]

        costo_directo_df = costos_portuarios[(costos_portuarios['puerto'] == puerto) & (costos_portuarios['operador'] == operador) & (
            costos_portuarios['ingrediente'] == ingrediente) & (costos_portuarios['tipo_operacion'] == 'directo')]

        if costo_bodegaje_df.shape[0] > 0:
            costo_bodegaje = costo_bodegaje_df.iloc[0]['valor_kg']
        else:
            costo_bodegaje = 0.0

        if costo_directo_df.shape[0] > 0:
            costo_directo = costo_directo_df.iloc[0]['valor_kg']
        else:
            costo_directo = 0.0

        llegadas = dict()

        llegadas['ingrediente'] = ingrediente
        llegadas['importacion'] = importacion
        llegadas['empresa'] = empresa
        llegadas['puerto'] = puerto
        llegadas['operador'] = operador
        llegadas['variable'] = 'llegadas'

        inventario = dict()
        inventario['ingrediente'] = ingrediente
        inventario['importacion'] = importacion
        inventario['empresa'] = empresa
        inventario['puerto'] = puerto
        inventario['operador'] = operador
        inventario['variable'] = 'inventario'
        cant_inventario = 0.0

        directo = dict()
        directo['ingrediente'] = ingrediente
        directo['importacion'] = importacion
        directo['empresa'] = empresa
        directo['puerto'] = puerto
        directo['operador'] = operador
        directo['variable'] = 'costo_directo_por_kg'

        cif = dict()
        cif['ingrediente'] = ingrediente
        cif['importacion'] = importacion
        cif['empresa'] = empresa
        cif['puerto'] = puerto
        cif['operador'] = operador
        cif['variable'] = 'valor_cif'

        for periodo in periodos:
            cif[periodo] = valor_cif

        matriz.append(cif)

        while cantidad_llegada > capacidad_recepcion:

            llegadas[arrival_date] = capacidad_recepcion

            cant_inventario += capacidad_recepcion
            inventario[arrival_date] = cant_inventario

            directo[arrival_date] = costo_directo

            cantidad_llegada -= capacidad_recepcion
            arrival_date = arrival_date + timedelta(days=1)

        if cantidad_llegada > 0:

            llegadas[arrival_date] = cantidad_llegada

            cant_inventario += cantidad_llegada
            inventario[arrival_date] = cant_inventario

        matriz.append(llegadas)
        matriz.append(inventario)

        # Agregar costo de bodegaje

        costo_bodegaje_por_kg = dict()

        costo_bodegaje_por_kg['ingrediente'] = ingrediente
        costo_bodegaje_por_kg['importacion'] = importacion
        costo_bodegaje_por_kg['empresa'] = empresa
        costo_bodegaje_por_kg['puerto'] = puerto
        costo_bodegaje_por_kg['operador'] = operador
        costo_bodegaje_por_kg['variable'] = 'costo_bodegaje_por_kg'
        costo_bodegaje_por_kg[arrival_date] = costo_bodegaje

        matriz.append(costo_bodegaje_por_kg)

        directo['variable'] = 'costo_directo_por_kg'
        directo[arrival_date] = costo_directo

        matriz.append(directo)


def _obtener_costos_corte_almacenamiento(matriz: list, periodos: list, dataframes: dict):

    print('obtener costos de almacenamiento')

    costos_almacenamiento_df = dataframes['costos_almacenamiento_cargas'].copy(
    )

    costos_almacenamiento_df['fecha_corte'] = pd.to_datetime(
        costos_almacenamiento_df['fecha_corte'])

    for i in tqdm(costos_almacenamiento_df.index):

        ingrediente = costos_almacenamiento_df.loc[i]['ingrediente']
        importacion = costos_almacenamiento_df.loc[i]['importacion']
        empresa = costos_almacenamiento_df.loc[i]['empresa']
        puerto = costos_almacenamiento_df.loc[i]['puerto']
        operador = costos_almacenamiento_df.loc[i]['operador']
        fecha_corte = costos_almacenamiento_df.loc[i]['fecha_corte']
        costo = costos_almacenamiento_df.loc[i]['valor_kg']

        costo_almacenamiento_por_kg = dict()

        costo_almacenamiento_por_kg['ingrediente'] = ingrediente
        costo_almacenamiento_por_kg['importacion'] = importacion
        costo_almacenamiento_por_kg['empresa'] = empresa
        costo_almacenamiento_por_kg['puerto'] = puerto
        costo_almacenamiento_por_kg['operador'] = operador
        costo_almacenamiento_por_kg['variable'] = 'costo_almacenamiento_por_kg'
        costo_almacenamiento_por_kg[fecha_corte] = costo

        matriz.append(costo_almacenamiento_por_kg)


def _obtener_matriz_fletes_intercompany(matriz: list, periodos: list, dataframes: dict, cap_camion=34000):

    print('obtener fletes y costos intercompany')

    fletes = dataframes['fletes_cop_per_kg'].copy()

    importaciones = [(i['ingrediente'], i['importacion'],
                      i['empresa'], i['puerto'], i['operador']) for i in matriz]

    importaciones = list(set(importaciones))

    empresas = dataframes['plantas'].copy()

    empresas = {empresas.loc[i]['planta']: empresas.loc[i]
                ['empresa'] for i in empresas.index}

    intercompanies = dataframes['venta_entre_empresas'].copy(
    ).set_index('origen')

    for importacion in tqdm(importaciones):

        flete = fletes[(fletes['ingrediente'] == importacion[0]) & (
            fletes['puerto'] == importacion[3]) & (fletes['operador'] == importacion[4])]

        if flete.shape[0] > 0:

            for planta in empresas.keys():

                flete_kg = dict()

                flete_kg['ingrediente'] = importacion[0]
                flete_kg['importacion'] = importacion[1]
                flete_kg['empresa'] = importacion[2]
                flete_kg['puerto'] = importacion[3]
                flete_kg['operador'] = importacion[4]
                flete_kg['variable'] = f'costo_flete_kg_{planta}'

                intercompany = dict()

                intercompany['ingrediente'] = importacion[0]
                intercompany['importacion'] = importacion[1]
                intercompany['empresa'] = importacion[2]
                intercompany['puerto'] = importacion[3]
                intercompany['operador'] = importacion[4]
                intercompany['variable'] = f'costo_intercompany_{planta}'

                for periodo in periodos:

                    flete_kg[periodo] = flete.iloc[0][planta]
                    
                    try:
                        intercompany[periodo] = intercompanies.loc[importacion[2]][empresas[planta]]
                    except:
                        intercompany[periodo] = 0.0

                matriz.append(flete_kg)
                matriz.append(intercompany)


def __completar_inventario_cargas(matriz: list, periodos: list):

    print('calculando inventarios de cargas')

    df = _generar_dataframe_cargas(matriz, periodos)

    fixed_columns = ['ingrediente', 'importacion',
                     'empresa', 'puerto', 'operador', 'variable']

    per = [x for x in df.drop(columns=fixed_columns).columns]

    per = sorted(per)

    # Llenar el inventario inicial
    importaciones = [(i['ingrediente'], i['importacion'],
                      i['empresa'], i['puerto'], i['operador']) for i in matriz]

    importaciones = list(set(importaciones))

    df.set_index(keys=fixed_columns, inplace=True)

    for importacion in tqdm(importaciones):

        inventario_index = (
            importacion[0], importacion[1], importacion[2], importacion[3], importacion[4], 'inventario')

        if inventario_index in df.index:

            inventario = df.loc[inventario_index].copy()

            periodo_anterior = periodos[0] - timedelta(days=1)

            inventario_anterior = inventario[periodo_anterior]

            for periodo in periodos:

                inventario_actual = inventario[periodo]

                if inventario_anterior >= inventario_actual:
                    if inventario_anterior > 0:

                        dato = {
                            'ingrediente': importacion[0],
                            'importacion': importacion[1],
                            'empresa': importacion[2],
                            'puerto': importacion[3],
                            'operador': importacion[4],
                            'variable': 'inventario',
                            periodo: inventario_anterior
                        }

                        # print(dato)
                        matriz.append(dato)

                else:

                    inventario_anterior = inventario_actual


def __totalizar_valor_almacenamiento(matriz: list, periodos: list):

    print('totalizar el costo de almacenamiento para cada carga')

    df = _generar_dataframe_cargas(matriz, periodos)

    df = df[df['variable'].isin(
        ['costo_almacenamiento_por_kg', 'costo_bodegaje_por_kg'])].copy()

    fixed_columns = ['ingrediente', 'importacion',
                     'empresa', 'puerto', 'operador', 'variable']

    df = df[fixed_columns + periodos].copy()

    df = df.melt(id_vars=fixed_columns, value_vars=periodos,
                 var_name='periodo', value_name='valor').copy()

    df = df.pivot_table(values='valor',
                        index=['ingrediente', 'importacion', 'empresa',
                               'puerto', 'operador', 'periodo'],
                        columns='variable',
                        aggfunc='sum').fillna(0.0)

    # Calcular costo total de almacenamiento
    df['costo_total_almacenamiento'] = df['costo_almacenamiento_por_kg'] + \
        df['costo_bodegaje_por_kg']

    for importacion in tqdm(df.index):

        dato = {
            'ingrediente': importacion[0],
            'importacion': importacion[1],
            'empresa': importacion[2],
            'puerto': importacion[3],
            'operador': importacion[4],
            'variable': 'costo_total_almacenamiento',
            importacion[5]: df.loc[importacion]['costo_total_almacenamiento']
        }

        # print(dato)
        matriz.append(dato)


def __totalizar_valor_despacho_por_camion(matriz: list, periodos: list, dataframes: dict, cap_camion=34000):

    print('totalizar valor de despacho por camion')

    df = _generar_dataframe_cargas(matriz, periodos)

    # Extraer todos los posibles costos de transporte
    lista_costos = ['valor_cif', 'costo_directo_por_kg'] + [x for x in df['variable'].unique(
    ) if 'flete' in x] + [x for x in df['variable'].unique() if 'intercompany' in x]

    df = df[df['variable'].isin(lista_costos)].copy()

    # Llenar el inventario inicial
    importaciones = [(i['ingrediente'], i['importacion'],
                      i['empresa'], i['puerto'], i['operador']) for i in matriz]

    importaciones = list(set(importaciones))

    # Llenar lista de plantas

    empresas = dataframes['plantas'].copy()

    empresas = {empresas.loc[i]['planta']: empresas.loc[i]
                ['empresa'] for i in empresas.index}

    fixed_columns = ['ingrediente', 'importacion',
                     'empresa', 'puerto', 'operador', 'variable']

    df.set_index(keys=fixed_columns, inplace=True)

    for i in tqdm(importaciones):

        for planta, empresa in empresas.items():

            for periodo in periodos:

                # Costo total por camion = cap_camion * (flete + directo + valor_cif*intercompany)

                flete_index = (i[0], i[1], i[2], i[3], i[4],
                               f'costo_flete_kg_{planta}')
                flete = df.loc[flete_index][periodo]

                directo_index = (i[0], i[1], i[2], i[3],
                                 i[4], 'costo_directo_por_kg')
                if directo_index in df.index:
                    directo = df.loc[directo_index][periodo]
                else:
                    directo = 0.0

                valorcif_index = (i[0], i[1], i[2], i[3], i[4], 'valor_cif')
                valorcif = df.loc[valorcif_index][periodo]

                intercompany_index = (
                    i[0], i[1], i[2], i[3], i[4], f'costo_intercompany_{planta}')
                intercompany = df.loc[intercompany_index][periodo]

                costo_total = cap_camion * \
                    (flete + directo + valorcif*intercompany)

                dato = {
                    'ingrediente': i[0],
                    'importacion': i[1],
                    'empresa': i[2],
                    'puerto': i[3],
                    'operador': i[4],
                    'variable': f'costo_total_despacho_camion_{planta}',
                    periodo: costo_total
                }

                # print(dato)
                matriz.append(dato)


def obtener_matriz_importaciones(dataframes: dict, periodos: list):

    matriz = _obtener_inventarios_puerto(periodos, dataframes)

    _obtener_transitos_a_puerto(matriz, periodos, dataframes)

    _obtener_costos_corte_almacenamiento(matriz, periodos, dataframes)

    _obtener_matriz_fletes_intercompany(matriz, periodos, dataframes)

    __completar_inventario_cargas(matriz, periodos)

    __totalizar_valor_almacenamiento(matriz, periodos)

    __totalizar_valor_despacho_por_camion(matriz, periodos, dataframes)

    df = _generar_dataframe_cargas(matriz, periodos)

    return df


def validacion_eliminar_cargas_sin_inventario(cargas_df: pd.DataFrame, validation_list: list) -> pd.DataFrame:

    df = cargas_df[cargas_df['variable'] == 'inventario'].copy()

    df.drop(columns=['variable'], inplace=True)

    df.set_index(['ingrediente', 'importacion', 'empresa',
                 'puerto', 'operador'], inplace=True)

    df['max'] = df.apply(np.max, axis=1)

    index_to_delete = df[df['max'] < 34000].index

    for i in index_to_delete:
        validation_list.append({"nivel": "Advertencia",
                                "Mensaje": f"la importacion {' '.join(i)} no tiene suficiente inventario para ser despachado."
                                })

    cargas_df['temp'] = [(cargas_df.loc[i]['ingrediente'], cargas_df.loc[i]['importacion'], cargas_df.loc[i]
                          ['empresa'], cargas_df.loc[i]['puerto'], cargas_df.loc[i]['operador']) for i in cargas_df.index]

    cargas_df = cargas_df[~cargas_df['temp'].isin(index_to_delete)].copy()

    cargas_df.drop(columns=['temp'], inplace=True)

    return cargas_df


def validacion_eliminar_ingredientes_sin_consumo(plantas_df: pd.DataFrame, validation_list: list) -> pd.DataFrame():

    df = plantas_df[plantas_df['variable'] == 'consumo'].copy()

    df.drop(columns=['variable'], inplace=True)

    df.set_index(['planta', 'ingrediente'], inplace=True)

    df['tot'] = df.apply(np.sum, axis=1)

    index_to_delete = df[df['tot'] <= 0].index

    for i in index_to_delete:
        validation_list.append({"nivel": "Advertencia",
                                "Mensaje": f"el manejo del ingrediente {i[1]} en la planta {i[0]} será ignorado por no tener consumo proyectado"
                                })

    plantas_df['temp'] = [(plantas_df.loc[i]['planta'],
                           plantas_df.loc[i]['ingrediente']) for i in plantas_df.index]

    plantas_df = plantas_df[~plantas_df['temp'].isin(index_to_delete)].copy()

    plantas_df.drop(columns=['temp'], inplace=True)

    return plantas_df

# Falta:
# Crear la capacidad de recepcion de material en cada planta
# Crear matriz de despachos cruzando importaciones con plantas y periodos
# Inicializar en 0 las varibles de transporte hacia planta
# Alimentar el modelo
# Resolver el modelo
# Crear visualizacion en streamlit


if __name__ == '__main__':

    bios_input_file = 'data/0_model_template_2204.xlsm'

    dataframes = leer_archivo(bios_input_file=bios_input_file)

    periodos = __generar_periodos(dataframes)

    estadisticas = obtener_objetivo_inventario(bios_input_file)

    plantas_df = obtener_matriz_plantas(dataframes, periodos, estadisticas)

    cargas_df = obtener_matriz_importaciones(dataframes, periodos)

    validation_list = list()

    cargas_df = validacion_eliminar_cargas_sin_inventario(
        cargas_df, validation_list)

    plantas_df = validacion_eliminar_ingredientes_sin_consumo(
        plantas_df, validation_list)

    bios_model_file = bios_input_file.replace('.xlsm', '_model.xlsx')

    with pd.ExcelWriter(path=bios_model_file) as writer:
        plantas_df.to_excel(writer, sheet_name='plantas', index=False)
        cargas_df.to_excel(writer, sheet_name='cargas', index=False)
        estadisticas['objetivo_inventario'].to_excel(
            writer, sheet_name='objetivo_inventario', index=False)

    print('finalizado')
