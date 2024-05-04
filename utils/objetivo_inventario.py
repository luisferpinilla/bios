# %%
from datetime import datetime, timedelta
from utils.asignador_capacidad import AsignadorCapacidad
from sklearn.cluster import KMeans
import numpy as np
import pandas as pd
pd.options.display.max_columns = None


def obtener_objetivo_inventario(bios_input_file: str, cap_camion=34000, cap_descarge=5000000) -> dict:
    # Leer el archivo de excel
    productos_df = pd.read_excel(io=bios_input_file, sheet_name='ingredientes')
    plantas_df = pd.read_excel(io=bios_input_file, sheet_name='plantas')
    asignador = AsignadorCapacidad(bios_input_file)
    unidades_almacenamiento_df = asignador.obtener_unidades_almacenamiento()
    safety_stock_df = pd.read_excel(
        io=bios_input_file, sheet_name='safety_stock')
    consumo_proyectado_df = pd.read_excel(
        io=bios_input_file, sheet_name='consumo_proyectado')
    transitos_puerto_df = pd.read_excel(
        io=bios_input_file, sheet_name='tto_puerto')
    transitos_planta_df = pd.read_excel(
        io=bios_input_file, sheet_name='tto_plantas')
    inventario_puerto_df = pd.read_excel(
        io=bios_input_file, sheet_name='inventario_puerto')
    costos_almacenamiento_df = pd.read_excel(
        io=bios_input_file, sheet_name='costos_almacenamiento_cargas')
    operaciones_portuarias_df = pd.read_excel(
        io=bios_input_file, sheet_name='costos_operacion_portuaria')
    fletes_df = pd.read_excel(
        io=bios_input_file, sheet_name='fletes_cop_per_kg')
    intercompany_df = pd.read_excel(
        io=bios_input_file, sheet_name='venta_entre_empresas')

    # %% [markdown]
    # ## Armando el dataset

    # %%
    # Generar un dataset con las combinaciones de ingredientes y plantas
    objetivo = list()

    for planta in list(plantas_df['planta']):
        for ingrediente in list(productos_df['nombre']):
            objetivo.append({'planta': planta, 'ingrediente': ingrediente})
    objetivo_df = pd.DataFrame(objetivo)

    # Generar un mapeo para empresas
    empresas_map = {plantas_df.loc[i]['planta']                    : plantas_df.loc[i]['empresa'] for i in plantas_df.index}
    objetivo_df['empresa'] = objetivo_df['planta'].map(empresas_map)

    # Agregar el dato del consumo medio
    temp_df = consumo_proyectado_df[['planta', 'ingrediente']].copy()
    temp_df['consumo_medio'] = consumo_proyectado_df.drop(
        columns=['planta', 'ingrediente']).mean(axis=1)

    objetivo_df = pd.merge(left=objetivo_df,
                           right=temp_df,
                           left_on=['planta', 'ingrediente'],
                           right_on=['planta', 'ingrediente'],
                           how='left').fillna(0.0)

    objetivo_df.head()

    # %%
    # Calcular la capacidad
    unidades_almacenamiento_df['Capacidad'] = unidades_almacenamiento_df.apply(
        lambda x: x[x['ingrediente_actual']], axis=1)

    # Obtener la capacidad de almacenamiento por planta e ingrediente
    temp_df = unidades_almacenamiento_df.groupby(by=['planta', 'ingrediente_actual'])[
        ['Capacidad']].sum().reset_index().rename(columns={'ingrediente_actual': 'ingrediente', 'Capacidad': 'capacidad_kg'})

    # Agregar la capacidad de almacenamiento
    objetivo_df = pd.merge(left=objetivo_df,
                           right=temp_df,
                           left_on=['planta', 'ingrediente'],
                           right_on=['planta', 'ingrediente'],
                           how='left')

    objetivo_df.head()

    # %%
    # Colocando el inventario actual
    temp_df = unidades_almacenamiento_df.groupby(by=['planta', 'ingrediente_actual'])[
        ['cantidad_actual']].sum().reset_index().rename(columns={'ingrediente_actual': 'ingrediente',
                                                                 'cantidad_actual': 'inventario_kg'})

    objetivo_df = pd.merge(left=objetivo_df,
                           right=temp_df,
                           left_on=['planta', 'ingrediente'],
                           right_on=['planta', 'ingrediente'],
                           how='left').fillna(0.0)

    objetivo_df.head()

    # %%
    # Colocar los transitos ya planeados
    temp_df = transitos_planta_df.groupby(by=['planta', 'ingrediente'])[
        ['cantidad']].sum().reset_index().rename(columns={'cantidad': 'transito_kg'})

    objetivo_df = pd.merge(left=objetivo_df,
                           right=temp_df,
                           left_on=['planta', 'ingrediente'],
                           right_on=['planta', 'ingrediente'],
                           how='left').fillna(0.0)

    # Safety Stock
    objetivo_df = pd.merge(left=objetivo_df,
                           right=safety_stock_df[[
                               'planta', 'ingrediente', 'dias_ss']],
                           left_on=['planta', 'ingrediente'],
                           right_on=['planta', 'ingrediente'],
                           how='left')

    objetivo_df.head()

    # %%
    # Calcular indicadores
    objetivo_df['capacidad_dio'] = objetivo_df.apply(
        lambda x: x['capacidad_kg']/x['consumo_medio'] if x['consumo_medio'] > 0 else 0.0 if x['capacidad_kg'] == 0.0 else 365, axis=1)

    objetivo_df['inventario_dio'] = objetivo_df.apply(
        lambda x: x['inventario_kg']/x['consumo_medio'] if x['consumo_medio'] > 0 else 0.0 if x['inventario_kg'] == 0.0 else 365, axis=1)

    objetivo_df['transito_dio'] = objetivo_df.apply(
        lambda x: x['transito_kg']/x['consumo_medio'] if x['consumo_medio'] > 0 else 0.0 if x['transito_kg'] == 0.0 else 365, axis=1)

    objetivo_df['aporte_camion_dio'] = objetivo_df.apply(
        lambda x: cap_camion/x['consumo_medio'] if x['consumo_medio'] > 0 else 365, axis=1)

    objetivo_df.head()

    # %% [markdown]
    # ## Calculando costo de despacho

    # %%
    # Costos de fletes por importacion, producto y planta por cada camion
    costos_transporte_df = fletes_df.melt(id_vars=['puerto', 'operador', 'ingrediente'],
                                          value_vars=fletes_df.drop(
        columns=['puerto', 'operador', 'ingrediente']).columns,
        var_name='planta',
        value_name='costo_kg')

    costos_transporte_df['flete_camion'] = cap_camion * \
        costos_transporte_df['costo_kg']

    costos_transporte_df.drop(columns=['costo_kg'], inplace=True)

    # Agregar Costos de operaciones portuarias
    temp_df = operaciones_portuarias_df[operaciones_portuarias_df['tipo_operacion'] == 'directo'].drop(columns=[
        'tipo_operacion'])
    temp_df['despacho_directo'] = cap_camion*temp_df['valor_kg']
    temp_df.drop(columns=['valor_kg'], inplace=True)

    # Unir a costos de transporte
    join_field_list = ['puerto', 'operador', 'ingrediente']
    costos_transporte_df = pd.merge(left=costos_transporte_df,
                                    right=temp_df,
                                    left_on=join_field_list,
                                    right_on=join_field_list,
                                    how='left')

    # Adicionar empresa de destino
    costos_transporte_df['empresa_destino'] = costos_transporte_df['planta'].map(
        empresas_map)

    costos_transporte_df.head()

    # %%
    print('Fletes sin costos portuarios de despacho directo asociados')
    costos_transporte_df[costos_transporte_df['despacho_directo'].isnull()]

    # %% [markdown]
    # ## Obteniendo cargas

    # %%
    # obtener valores de cargas en tránsito a puerto
    cargas_df = transitos_puerto_df.rename(
        columns={'valor_kg': 'valor_cif_kg'}).copy()

    # Agregar status
    cargas_df['status'] = ['transito' for i in cargas_df.index]

    # Obtener el inventario en puerto
    temp_df = inventario_puerto_df.copy()

    temp_df['status'] = ['bodega' for i in temp_df.index]

    # Concatenar cargas
    cargas_df = pd.concat([cargas_df, temp_df])

    # Renombrar empresa
    cargas_df.rename(columns={'empresa': 'empresa_origen'}, inplace=True)

    # %%
    cargas_df.head()

    # %%
    join_field_list = ['puerto', 'operador', 'ingrediente']
    costos_transporte_df = pd.merge(left=cargas_df,
                                    right=costos_transporte_df,
                                    left_on=join_field_list,
                                    right_on=join_field_list,
                                    how='left')

    # %%
    print('Cargas que no tienen fletes relacionados')
    costos_transporte_df[costos_transporte_df['planta'].isna()]

    # %%
    # Costos intercompany
    temp_df = intercompany_df.melt(id_vars='origen', value_vars=['contegral', 'finca'], var_name='destino', value_name='valor_intercompany').rename(
        columns={'origen': 'empresa_origen', 'destino': 'empresa_destino'})

    join_field_list = ['empresa_origen', 'empresa_destino']
    costos_transporte_df = pd.merge(left=costos_transporte_df,
                                    right=temp_df,
                                    left_on=join_field_list,
                                    right_on=join_field_list,
                                    how='inner')

    # %%
    costos_transporte_df.head()

    # %%
    costos_transporte_df['costo_intercompany_camion'] = cap_camion * \
        costos_transporte_df['valor_cif_kg'] * \
        costos_transporte_df['valor_intercompany']
    costos_transporte_df['costo_transporte_camion_directo'] = costos_transporte_df['flete_camion'] + \
        costos_transporte_df['despacho_directo'] + \
        costos_transporte_df['costo_intercompany_camion']
    costos_transporte_df['costo_transporte_camion_indirecto'] = costos_transporte_df['flete_camion'] + \
        costos_transporte_df['costo_intercompany_camion']

    # %%
    costos_transporte_df.head()

    # %%
    fields_to_melt = ['costo_transporte_camion_directo',
                      'costo_transporte_camion_indirecto']
    fields_to_keep = costos_transporte_df.drop(columns=fields_to_melt).columns

    # %%
    costos_transporte_df = costos_transporte_df.melt(id_vars=fields_to_keep,
                                                     value_vars=fields_to_melt,
                                                     var_name='tipo_transporte',
                                                     value_name='costo_total_por_camion')

    # %%
    costos_transporte_df['tipo_transporte'] = costos_transporte_df['tipo_transporte'].apply(
        lambda x: str(x).replace('costo_transporte_camion_', ''))

    # %%
    costos_transporte_df.pivot_table(values='costo_total_por_camion',
                                     columns='planta',
                                     index=['puerto', 'tipo_transporte'],
                                     aggfunc='mean')

    # %%

    def asignar_etiquetas(df: pd.DataFrame, column_name: str, n_clusters=3):
        # Copiamos el DataFrame para no modificar el original
        df_resultado = df.copy()

        # Instanciar el modelo KMeans
        kmeans = KMeans(n_clusters=3,
                        init='random',
                        n_init=10,
                        max_iter=300,
                        random_state=0)

        # Ajustar el modelo a los datos
        kmeans.fit(np.array(df[column_name]).reshape(-1, 1))

        # Obtener las etiquetas de los clusters
        labels = kmeans.labels_

        # Agregar las etiquetas al DataFrame
        df_resultado['cluster'] = labels

        # Calcular los centroides
        centroids = kmeans.cluster_centers_

        # Calcular los límites de los clusters
        limits = [df[labels == i].describe() for i in range(n_clusters)]

        # Asignar etiquetas de 'alto', 'medio' y 'bajo'
        for i in range(n_clusters):
            df_resultado.loc[df_resultado['cluster'] == i, 'etiqueta'] = (
                'alto' if centroids[i] == max(centroids) else
                'bajo' if centroids[i] == min(centroids) else
                'medio'
            )

        return df_resultado

    # %%
    costos_transporte_df

    # %%

    asignar_etiquetas(df=costos_transporte_df,
                      column_name='costo_total_por_camion')

    # %%
    list_clusters = list()
    for planta in list(plantas_df['planta']):
        # for importacion in list(costos_transporte_df['importacion'].unique()):
        df = costos_transporte_df[costos_transporte_df['planta']
                                  == planta]
        list_clusters.append(asignar_etiquetas(
            df=df, column_name='costo_total_por_camion'))
    costos_transporte_df = pd.concat(list_clusters)

    # %%
    costos_transporte_df.pivot_table(values='etiqueta',
                                     columns='planta',
                                     index=['puerto', 'importacion',
                                            'tipo_transporte', 'cantidad_kg'],
                                     aggfunc=list)

    # %%
    costos_almacenamiento_df['corte'] = costos_almacenamiento_df.apply(
        lambda x: (x['fecha_corte'], x['valor_kg']), axis=1)

    # %%
    costos_almacenamiento_df

    # %%
    cargas_df['importacion'] = cargas_df['importacion'].apply(
        lambda x: str(x).replace(' ', ''))

    # %%
    importaciones = list(costos_almacenamiento_df['importacion'].apply(
        lambda x: str(x).replace(' ', '')))

    # %%
    cargas_df[~cargas_df['importacion'].isin(importaciones)]

    # %%
    cantidad_periodos = len(consumo_proyectado_df.drop(
        columns=['planta', 'ingrediente']).columns)
    temp_df = pd.merge(left=cargas_df.groupby(by=['ingrediente'])[['cantidad_kg']].sum().rename(columns={'cantidad_kg': 'inventario_puerto_kg'}).reset_index(),
                       right=objetivo_df.groupby('ingrediente')[
        ['consumo_medio', 'inventario_kg', 'transito_kg']].sum().reset_index(),
        left_on='ingrediente',
        right_on='ingrediente',
        how='left')

    temp_df['inventario_total'] = temp_df['inventario_puerto_kg'] + \
        temp_df['inventario_kg'] + temp_df['transito_kg']
    temp_df['inventario_menos_consumo'] = temp_df['inventario_total'] - \
        cantidad_periodos*temp_df['consumo_medio']
    temp_df['objetivo_dio_general'] = temp_df['inventario_menos_consumo'] / \
        temp_df['consumo_medio']

    # %%
    objetivo_df = pd.merge(left=objetivo_df,
                           right=temp_df[['ingrediente',
                                          'objetivo_dio_general']],
                           left_on=['ingrediente'],
                           right_on=['ingrediente'],
                           how='left')

    # %%

    def objetivo_ajustado(x) -> float:

        if x['objetivo_dio_general'] > 0 and x['consumo_medio'] > 0:
            objetivo = x['capacidad_dio'] - 2*x['aporte_camion_dio']

            return min(x['objetivo_dio_general'], objetivo)

        return 0

    # %%
    objetivo_df['objetivo_dio'] = objetivo_df.apply(objetivo_ajustado, axis=1)

    # %%
    objetivo_df['objetivo_kg'] = objetivo_df['objetivo_dio'] * \
        objetivo_df['consumo_medio']

    # %%
    objetivo_df[objetivo_df['ingrediente'] == 'destilado']

    # %%
    response_dict = dict()
    response_dict['costos_transporte'] = costos_transporte_df
    response_dict['objetivo_inventario'] = objetivo_df
    response_dict['datos_cargas'] = cargas_df

    return response_dict
