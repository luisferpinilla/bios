# %% [markdown]
# # Modelo BIOS:

# %% [markdown]
# ## Importacion de Librerias

# %%
import pandas as pd
from datetime import datetime, timedelta
import pulp as pu
from utils.asignador_capacidad import AsignadorCapacidad
from utils.planta_loader import obtener_matriz_plantas
import os
import shutil
import json
import numpy as np
from sklearn.cluster import KMeans
from tqdm import tqdm

# %% [markdown]
# ## Parametros generales

# %%
bios_input_file = 'data/0_model_template_2204.xlsm'

# Tiempo máximo de detencion en minutos
t_limit_minutes = 60*6

# Cantidad CPU habilitadas para trabajar
cpu_count = max(1, os.cpu_count()-1)

# Gap en millones de pesos
gap = 5000000

# Capacidad de carga de un camion
cap_camion = 34000

# Capacidad de descarga en puerto por día
cap_descarge = 5000000

# Costo de no safety stock por día
costo_safety_stock = 50000

# Costo de backorder por dia
costo_backorder_dia = costo_safety_stock*5

# Costo exceso de inventario
costo_exceso_capacidad = costo_safety_stock*3

# Los transportes solo tienen sentido desde el periodo 3, es dificil tomar deciciones para el mismo día
periodo_administrativo = 1

# Asumimos qe todo despacho tarda 2 días desde el momento que se envía la carga hasta que esta disponible para el consumo en planta
lead_time = 2

# %% [markdown]
# ## Lectura de dataframes

# %%
data_plantas_df = obtener_matriz_plantas(bios_input_file=bios_input_file)

# %%
# Leer el archivo de excel
productos_df = pd.read_excel(io=bios_input_file, sheet_name='ingredientes')
plantas_df = pd.read_excel(io=bios_input_file, sheet_name='plantas')
asignador = AsignadorCapacidad(bios_input_file)
unidades_almacenamiento_df = asignador.obtener_unidades_almacenamiento()
safety_stock_df = pd.read_excel(io=bios_input_file, sheet_name='safety_stock')
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
operaciones_portuarias_df = operaciones_portuarias_df.set_index(
    ['tipo_operacion', 'operador', 'puerto', 'ingrediente'])
fletes_df = pd.read_excel(io=bios_input_file, sheet_name='fletes_cop_per_kg')
intercompany_df = pd.read_excel(
    io=bios_input_file, sheet_name='venta_entre_empresas')
objetivo_df = pd.read_excel(io='data/validaciones.xlsx', sheet_name='objetivo')

# %% [markdown]
# ## Creacion de parametros del problema

# %% [markdown]
# ### Tiempo

# %%
# Obtener el conjunto de periodos
fechas = [datetime.strptime(x, '%d/%m/%Y')
          for x in consumo_proyectado_df.drop(columns=['planta', 'ingrediente']).columns]

periodos = [int(x.strftime('%Y%m%d')) for x in fechas]

periodo_anterior = fechas[0] - timedelta(days=1)
periodo_anterior = int(periodo_anterior.strftime('%Y%m%d'))

print(periodo_anterior,  periodos[0], periodos[-1])

# %% [markdown]
# ### Productos

# %%
productos = [productos_df.loc[i]['nombre'] for i in productos_df.index]

# %% [markdown]
# ### Plantas

# %% [markdown]
# #### Tiempo de descarge de materiales

# %%
# Generar plantas
plantas = dict()

for j in plantas_df.index:
    planta = plantas_df.loc[j]['planta']
    empresa = plantas_df.loc[j]['empresa']
    operacion_minutos = plantas_df.loc[j]['operacion_minutos'] * \
        plantas_df.loc[j]['plataformas']
    plantas[planta] = dict()
    plantas[planta]['empresa'] = empresa
    plantas[planta]['tiempo_total'] = operacion_minutos
    plantas[planta]['tiempo_ingrediente'] = dict()
    plantas[planta]['llegadas_puerto'] = dict()

    for p in productos:
        t_ingrediente = plantas_df.loc[j][p]
        plantas[planta]['tiempo_ingrediente'][p] = t_ingrediente
        plantas[planta]['llegadas_puerto'][p] = {t: list() for t in periodos}

# %% [markdown]
# #### Inventario en Planta

# %%
unidades_almacenamiento_df['capacidad'] = unidades_almacenamiento_df.apply(
    lambda x: x[x['ingrediente_actual']], axis=1)
unidades_almacenamiento_df.drop(columns=productos, inplace=True)
unidades_almacenamiento_df = unidades_almacenamiento_df.groupby(
    ['planta', 'ingrediente_actual'])[['cantidad_actual', 'capacidad']].sum().reset_index()

# Agregando la informacion de safety stock
unidades_almacenamiento_df = pd.merge(left=unidades_almacenamiento_df,
                                      right=safety_stock_df,
                                      left_on=['planta', 'ingrediente_actual'],
                                      right_on=['planta', 'ingrediente'],
                                      how='left').drop(columns='ingrediente')

unidades_almacenamiento_df.head()

# %%
# Generar un diccionario para renombrar las columnas de tiempo en consumo proyectado
consumo_proyectado_renamer = {x: datetime.strptime(x, '%d/%m/%Y').strftime(
    '%Y%m%d') for x in consumo_proyectado_df.drop(columns=['planta', 'ingrediente']).columns}
# Efectuar el cambio de nombre
consumo_proyectado_df.rename(columns=consumo_proyectado_renamer, inplace=True)
# Unir con el consumo proyectado
unidades_almacenamiento_df = pd.merge(left=unidades_almacenamiento_df,
                                      right=consumo_proyectado_df,
                                      left_on=['planta', 'ingrediente_actual'],
                                      right_on=['planta', 'ingrediente'],
                                      how='left').drop(columns=['ingrediente']).rename(columns={'ingrediente_actual': 'ingrediente', 'cantidad_actual': 'cantidad'}).fillna(0.0)

print(unidades_almacenamiento_df.shape)
unidades_almacenamiento_df.head()

# %%
renamer = {x: int(x.strftime('%Y%m%d')) for x in data_plantas_df.drop(
    columns=['planta', 'ingrediente', 'variable']).columns}
data_plantas_df.rename(columns=renamer, inplace=True)

# %%
# Llenar la informacion de los inventarios
for i in tqdm(data_plantas_df.index):
    planta = data_plantas_df.loc[i]['planta']
    ingrediente = data_plantas_df.loc[i]['ingrediente']

    inventarios = data_plantas_df[(data_plantas_df['planta'] == planta) & (
        data_plantas_df['ingrediente'] == ingrediente) & (data_plantas_df['variable'] == 'inventario')]
    consumo_df = data_plantas_df[(data_plantas_df['planta'] == planta) & (
        data_plantas_df['ingrediente'] == ingrediente) & (data_plantas_df['variable'] == 'consumo')]
    safety_stock = data_plantas_df[(data_plantas_df['planta'] == planta) & (
        data_plantas_df['ingrediente'] == ingrediente) & (data_plantas_df['variable'] == 'safety_stock')]
    capacidad_df = data_plantas_df[(data_plantas_df['planta'] == planta) & (
        data_plantas_df['ingrediente'] == ingrediente) & (data_plantas_df['variable'] == 'capacidad_max')]
    backorder_df = data_plantas_df[(data_plantas_df['planta'] == planta) & (
        data_plantas_df['ingrediente'] == ingrediente) & (data_plantas_df['variable'] == 'backorder')]
    cantidad_inicial = data_plantas_df.iloc[0][periodo_anterior]

    if capacidad_df.shape[0] > 0:

        if consumo_df.shape[0] > 0:
            consumo_total = np.sum(consumo_df.drop(
                columns=['planta', 'ingrediente', 'variable']).iloc[0])
        else:
            consumo_total = 0.0
        # capacidad_almacenamiento = unidades_almacenamiento_df.loc[i]['capacidad']
        # safety_stock_dias = unidades_almacenamiento_df.loc[i]['dias_ss']

        if not 'inventarios' in plantas[planta].keys():
            plantas[planta]['inventarios'] = dict()

        if not ingrediente in plantas[planta]['inventarios'].keys():
            plantas[planta]['inventarios'][ingrediente] = dict()

        # if not 'capacidad' in plantas[planta]['inventarios'][ingrediente].keys():
        #    plantas[planta]['inventarios'][ingrediente]['capacidad'] = capacidad_almacenamiento

        if not 'inventario_final' in plantas[planta]['inventarios'][ingrediente].keys():
            plantas[planta]['inventarios'][ingrediente]['inventario_final'] = dict()

        if not 'llegadas' in plantas[planta]['inventarios'][ingrediente].keys():
            plantas[planta]['inventarios'][ingrediente]['llegadas'] = dict()

        if not 'consumo' in plantas[planta]['inventarios'][ingrediente].keys():
            plantas[planta]['inventarios'][ingrediente]['consumo'] = dict()

        if not 'backorder' in plantas[planta]['inventarios'][ingrediente].keys():
            plantas[planta]['inventarios'][ingrediente]['backorder'] = dict()

        if not 'safety_stock' in plantas[planta]['inventarios'][ingrediente].keys():
            plantas[planta]['inventarios'][ingrediente]['safety_stock'] = dict()

        if not 'exceso_capacidad' in plantas[planta]['inventarios'][ingrediente].keys():
            plantas[planta]['inventarios'][ingrediente]['exceso_capacidad'] = dict()

        plantas[planta]['inventarios'][ingrediente]['inventario_final'][periodo_anterior] = cantidad_inicial

        if consumo_total > 0:

            # safety_stock_dias
            plantas[planta]['inventarios'][ingrediente]['safety_stock_dias'] = 0.0

            # safety_stock_kg = consumo_total*safety_stock_dias/len(periodos)

            for periodo in periodos:

                if safety_stock.shape[0] > 0:
                    plantas[planta]['inventarios'][ingrediente]['safety_stock_kg'] = safety_stock.iloc[0][periodo]
                else:
                    plantas[planta]['inventarios'][ingrediente]['safety_stock_kg'] = 0.0

                # Obtener consumo
                consumo = consumo_df.iloc[0][periodo]

                # Maximo entre inventario proyectado y la capacidad
                capacidad_maxima = capacidad_df.iloc[0][periodo]
                inventario_proyectado = inventarios.iloc[0][periodo]
                capacidad_almacenamiento = max(
                    capacidad_maxima, inventario_proyectado)
                # Agregar las variables de inventario
                inventario_var_name = f'I_{planta}_{ingrediente}_{periodo}'
                inventario_var = pu.LpVariable(
                    name=inventario_var_name,
                    lowBound=0.0,
                    upBound=capacidad_almacenamiento, cat=pu.LpContinuous)
                inventario_var.setInitialValue(inventario_proyectado)
                plantas[planta]['inventarios'][ingrediente]['inventario_final'][periodo] = inventario_var

                # Agregar las listas a donde llegarán los transportes
                plantas[planta]['inventarios'][ingrediente]['llegadas'][periodo] = list()

                # Agregar las variables de backorder
                backorder = backorder_df.iloc[0][periodo]
                bak_var_name = f'B_{planta}_{ingrediente}_{periodo}'
                bak_var = pu.LpVariable(
                    name=bak_var_name,
                    lowBound=0.0,
                    # upBound=consumo,
                    cat=pu.LpContinuous)
                bak_var.setInitialValue(backorder)

                plantas[planta]['inventarios'][ingrediente]['backorder'][periodo] = bak_var

                # Agregar las variables de Safety Stock
                if safety_stock.shape[0] > 0:
                    safety_stock_kg = safety_stock.iloc[0][periodo]
                    if capacidad_almacenamiento > safety_stock_kg + 2*cap_camion:
                        ss_var_name = f'S_{planta}_{ingrediente}_{periodo}'
                        ss_var = pu.LpVariable(
                            name=ss_var_name, lowBound=0.0, upBound=safety_stock_kg, cat=pu.LpContinuous)
                        plantas[planta]['inventarios'][ingrediente]['safety_stock'][periodo] = ss_var

                # Agregar el consumo proyectado
                plantas[planta]['inventarios'][ingrediente]['consumo'][periodo] = consumo
        else:
            for periodo in periodos:
                # Dejar el inventario en el estado actual
                plantas[planta]['inventarios'][ingrediente]['inventario_final'][periodo] = cantidad_inicial

                # Agregar el consumo proyectado
                plantas[planta]['inventarios'][ingrediente]['consumo'][periodo] = 0.0

# %%
# Llegar el objetivo de inventario al cierre

for i in objetivo_df.index:
    planta = objetivo_df.loc[i]['planta']
    ingrediente = objetivo_df.loc[i]['ingrediente']
    objetivo_dio = objetivo_df.loc[i]['objetivo_dio']
    objetivo_kg = objetivo_df.loc[i]['objetivo_kg']
    if ingrediente in plantas[planta]['inventarios'].keys():
        plantas[planta]['inventarios'][ingrediente]['objetivo_dio'] = objetivo_dio
        plantas[planta]['inventarios'][ingrediente]['objetivo_kg'] = objetivo_kg

# %% [markdown]
# #### Llegadas programadas anteriormente a Planta

# %%
for i in transitos_planta_df.index:
    planta = transitos_planta_df.loc[i]['planta']
    ingrediente = transitos_planta_df.loc[i]['ingrediente']
    cantidad = transitos_planta_df.loc[i]['cantidad']
    fecha = transitos_planta_df.loc[i]['fecha_llegada']
    periodo = int(fecha.strftime('%Y%m%d'))
    plantas[planta]['inventarios'][ingrediente]['llegadas'][periodo].append(
        0.0)

# %% [markdown]
# ### Cargas en Puerto

# %%
transitos_planta_df[transitos_planta_df['ingrediente'] == 'tgirasol']

# %% [markdown]
# #### Crear cargas a partir de información de los transitos

# %%
# Generar Cargas
cargas = dict()

# A partir de los transitos
for i in transitos_puerto_df.index:
    importacion = str(
        transitos_puerto_df.loc[i]['importacion']).replace(' ', '')
    empresa = transitos_puerto_df.loc[i]['empresa']
    operador = transitos_puerto_df.loc[i]['operador']
    puerto = transitos_puerto_df.loc[i]['puerto']
    ingrediente = transitos_puerto_df.loc[i]['ingrediente']
    cantidad_kg = transitos_puerto_df.loc[i]['cantidad_kg']
    valor_cif = transitos_puerto_df.loc[i]['valor_kg']
    fecha = transitos_puerto_df.loc[i]['fecha_llegada']
    if not importacion in cargas.keys():
        cargas[importacion] = dict()

    cargas[importacion]['empresa'] = empresa
    cargas[importacion]['operador'] = operador
    cargas[importacion]['puerto'] = puerto
    cargas[importacion]['ingrediente'] = ingrediente
    cargas[importacion]['valor_cif'] = valor_cif
    cargas[importacion]['inventario_inicial'] = 0
    cargas[importacion]['costo_almacenamiento'] = {
        int(t.strftime('%Y%m%d')): 0 for t in fechas}
    cargas[importacion]['llegadas'] = dict()
    cargas[importacion]['fecha_inicial'] = int(fecha.strftime('%Y%m%d'))

    # Poner llegadas de materia
    while cantidad_kg > cap_descarge:
        cargas[importacion]['llegadas'][int(
            fecha.strftime('%Y%m%d'))] = cap_descarge
        cantidad_kg -= cap_descarge
        fecha = fecha + timedelta(days=1)

    if cantidad_kg > 0:
        cargas[importacion]['llegadas'][int(
            fecha.strftime('%Y%m%d'))] = cantidad_kg
    cargas[importacion]['fecha_final'] = int(fecha.strftime('%Y%m%d'))

    # Agregar las variables de inventario
    cargas[importacion]['inventario_al_final'] = dict()
    for t in periodos:
        var_name = f"O_{importacion}_{t}"
        lp_var = pu.LpVariable(name=var_name,
                               lowBound=0.0,
                               upBound=transitos_puerto_df.loc[i]['cantidad_kg'],
                               cat=pu.LpContinuous)
        cargas[importacion]['inventario_al_final'][t] = lp_var

# %% [markdown]
# #### Crear cargas a partir de inventarios en puerto

# %%

# A Partir de los inventarios en puerto
for i in inventario_puerto_df.index:
    empresa = inventario_puerto_df.loc[i]['empresa']
    operador = inventario_puerto_df.loc[i]['operador']
    puerto = inventario_puerto_df.loc[i]['puerto']
    ingrediente = inventario_puerto_df.loc[i]['ingrediente']
    importacion = str(
        inventario_puerto_df.loc[i]['importacion']).replace(' ', '')
    inventario_inicial = inventario_puerto_df.loc[i]['cantidad_kg']
    valor_cif = inventario_puerto_df.loc[i]['valor_cif_kg']
    fecha = inventario_puerto_df.loc[i]['fecha_llegada']

    if not importacion in cargas.keys():
        cargas[importacion] = dict()

    cargas[importacion]['empresa'] = empresa
    cargas[importacion]['operador'] = operador
    cargas[importacion]['puerto'] = puerto
    cargas[importacion]['ingrediente'] = ingrediente
    cargas[importacion]['valor_cif'] = valor_cif
    cargas[importacion]['inventario_inicial'] = inventario_inicial
    cargas[importacion]['costo_almacenamiento'] = {
        int(t.strftime('%Y%m%d')): 0 for t in fechas}

    # Poner llegadas de materia
    cargas[importacion]['llegadas'] = {t.strftime('%Y%m%d'): 0 for t in fechas}

    cargas[importacion]['fecha_inicial'] = int(fecha.strftime('%Y%m%d'))
    cargas[importacion]['fecha_final'] = int(fecha.strftime('%Y%m%d'))
    # Agregar las variables de inventario
    cargas[importacion]['inventario_al_final'] = dict()

    for t in periodos:

        var_name = f"O_{importacion}_{t}"
        lp_var = pu.LpVariable(name=var_name,
                               lowBound=0.0,
                               upBound=inventario_puerto_df.loc[i]['cantidad_kg'],
                               cat=pu.LpContinuous)
        cargas[importacion]['inventario_al_final'][t] = lp_var

# %% [markdown]
# #### Costos de almacenamiento

# %%
# Agregar costos de almacenamiento a cada carga
for i in costos_almacenamiento_df.index:
    importacion = str(
        costos_almacenamiento_df.loc[i]['importacion']).replace(' ', '')
    fecha = int(
        costos_almacenamiento_df.loc[i]['fecha_corte'].strftime('%Y%m%d'))
    valor_kg = costos_almacenamiento_df.loc[i]['valor_kg']

    if importacion in cargas.keys():
        if fecha in cargas[importacion]['costo_almacenamiento']:
            cargas[importacion]['costo_almacenamiento'][fecha] += valor_kg

# %% [markdown]
# #### Costos de Bodegaje

# %%
# Agregar costos de bodegaje cuando es un producto en tránsito a puerto a cada carga
for importacion, carga in cargas.items():
    index = ('bodega', carga['operador'],
             carga['puerto'], carga['ingrediente'])
    valor_kg = operaciones_portuarias_df.loc[index]['valor_kg']
    if carga['fecha_inicial'] >= int(fechas[0].strftime('%Y%m%d')) and carga['fecha_final'] <= int(fechas[-1].strftime('%Y%m%d')):
        carga['costo_almacenamiento'][carga['fecha_final']] += valor_kg

# %% [markdown]
# #### Costos intercompany

# %%
intercompany_df = intercompany_df.melt(id_vars='origen',
                                       value_vars=['contegral', 'finca'],
                                       var_name='destino',
                                       value_name='intercompany')

intercompany_df.set_index(['origen', 'destino'], inplace=True)

# %% [markdown]
# #### Costos de transporte (fletes)

# %%
# Encontrar el costo total de transporte por kilogramo
fletes_df = fletes_df.melt(id_vars=['puerto', 'operador', 'ingrediente'],
                           value_vars=list(plantas.keys()),
                           value_name='costo_per_kg',
                           var_name='planta')

# Calcular valor del flete
fletes_df['flete'] = cap_camion*fletes_df['costo_per_kg']

fletes_df = pd.merge(left=fletes_df,
                     right=plantas_df[['planta', 'empresa']],
                     left_on='planta',
                     right_on='planta')

fletes_df.set_index(
    ['puerto', 'operador', 'ingrediente', 'planta'], inplace=True)

# %% [markdown]
# #### Variables de Despacho

# %%
# Tomar en cuenta solo los periodos relevantes
periodo_final = periodos.index(periodos[-1])-lead_time+1

print('despachos entre',
      periodos[periodo_administrativo], 'y', periodos[periodo_final])
# Informacion de transporte
for importacion, carga in cargas.items():
    puerto = carga['puerto']
    operador = carga['operador']
    ingrediente = carga['ingrediente']
    costo_envio = dict()

    for nombre_planta, planta in plantas.items():
        empresa_destino = planta['empresa']
        costo_intercompany = intercompany_df.loc[(
            carga['empresa'], empresa_destino)]['intercompany']
        valor_intercompany = cap_camion*carga['valor_cif']*(costo_intercompany)
        flete = fletes_df.loc[(
            puerto, operador, ingrediente, nombre_planta)]['flete']
        valor_despacho_directo_kg = cap_camion * \
            operaciones_portuarias_df.loc[(
                'directo', operador, puerto, ingrediente)]['valor_kg']

        periodo_llegada = carga['fecha_inicial']

        # Costo de flete
        costo_envio[nombre_planta] = dict()
        costo_envio[nombre_planta]['intercompany'] = costo_intercompany
        costo_envio[nombre_planta]['flete'] = flete
        costo_envio[nombre_planta]['cantidad_despacho'] = cap_camion
        costo_envio[nombre_planta]['valor_intercompany'] = valor_intercompany
        costo_envio[nombre_planta]['costo_despacho_directo'] = valor_despacho_directo_kg

        costo_envio[nombre_planta]['costo_envio'] = dict()
        costo_envio[nombre_planta]['tipo_envio'] = dict()
        costo_envio[nombre_planta]['variable_despacho'] = dict()

        # Descuento de almacenamiento en puerto
        costo_envio[nombre_planta]['descuento_almacenamiento'] = dict()
        costo_descuento_almacenamiento = 0.0
        for periodo in periodos[::-1]:
            if carga['costo_almacenamiento'][periodo] != 0.0:
                costo_descuento_almacenamiento = carga['costo_almacenamiento'][periodo]
            costo_envio[nombre_planta]['descuento_almacenamiento'][periodo] = costo_descuento_almacenamiento

        # Calcular costo de envio
        for periodo in periodos[periodo_administrativo:periodo_final]:
            # Si el periodo esta entre la fecha de llegada, colocar operacion portuaria por despacho directo.
            if periodo >= carga['fecha_inicial'] and periodo <= carga['fecha_final']:
                costo_envio[nombre_planta]['costo_envio'][periodo] = valor_intercompany + \
                    flete + valor_despacho_directo_kg
                costo_envio[nombre_planta]['tipo_envio'][periodo] = 'directo'

            else:
                costo_envio[nombre_planta]['costo_envio'][periodo] = valor_intercompany + flete
                costo_envio[nombre_planta]['tipo_envio'][periodo] = 'indirecto'

            # Variable de transporte

            # Antes de crear las variables de transporte, es importante saber si la planta tiene consumo del ingrediente
            if ingrediente in planta['inventarios'].keys():

                consumo_total = sum(
                    [c for p, c in planta['inventarios'][ingrediente]['consumo'].items()])

                # Máxima capacidad de recepcion como límite superior para la variable
                tiempo_total = planta['tiempo_total']
                tiempo_ingrediente_por_camion = planta['tiempo_ingrediente'][ingrediente]

                # máxima capacidad de recepcion
                cantidad_camiones_admisibles = int(
                    tiempo_total/tiempo_ingrediente_por_camion)

                # Cantidad de llegadas
                Llegadas = sum([v for p, v in carga['llegadas'].items()])

                # Inventario inicial
                inventario_inicial = carga['inventario_inicial']

                # cuántos camiones se podrían despachar con el inventario existente más las llegadas:
                if inventario_inicial + Llegadas > cap_camion:
                    cantidad_camiones_despachables = int(
                        (inventario_inicial + Llegadas)/cap_camion)
                else:
                    cantidad_camiones_despachables = 0

                limite_superior_despacho = min(
                    cantidad_camiones_admisibles, cantidad_camiones_despachables)

                # if consumo_total > 0 y el periodo actual es mayor al de llegada
                # (No tiene sentido agregar variable de desapcho si no hay qué despachar):
                if consumo_total > cap_camion and periodo >= periodo_llegada and limite_superior_despacho > 0 == 0:

                    transporte_var_name = f'T_{importacion}_{nombre_planta}_{periodo}'
                    transporte_var = pu.LpVariable(name=transporte_var_name,
                                                   lowBound=0,
                                                   upBound=limite_superior_despacho,
                                                   cat=pu.LpInteger)

                    costo_envio[nombre_planta]['variable_despacho'][periodo] = transporte_var

                    # Colocar la variable en la planta dos periodos despues
                    periodo_llegada_a_planta = periodos[periodos.index(
                        periodo)+lead_time]
                    plantas[nombre_planta]['inventarios'][ingrediente]['llegadas'][periodo_llegada_a_planta].append(
                        transporte_var)

        carga['costo_despacho'] = costo_envio

# %%
var_count = 0
for carga in cargas.keys():
    for planta in cargas[carga]['costo_despacho'].keys():
        var_count += len(cargas[carga]['costo_despacho']
                         [planta]['variable_despacho'].values())
print(var_count)
# Actualmente 16902 variables con consumos completos

# %%
clusters_dict = {
    'importacion': list(),
    'puerto': list(),
    'ingrediente': list(),
    'planta': list(),
    'periodo': list(),
    'costo_almacenamiento': list(),
    'costo_despacho': list()
}

# %% [markdown]
# ## Cluster de Cargas

# %%
for importacion in cargas.keys():
    for planta in plantas.keys():
        if planta in cargas[importacion]['costo_despacho'].keys():
            for periodo in periodos:
                if periodo in cargas[importacion]['costo_despacho'][planta]['costo_envio'].keys():

                    costo_despacho = cargas[importacion]['costo_despacho'][planta]['costo_envio'][periodo]
                    costo_almacenamiento = cargas[importacion]['costo_almacenamiento'][periodo]
                    ingrediente = cargas[importacion]['ingrediente']
                    puerto = cargas[importacion]['puerto']

                    clusters_dict['importacion'].append(importacion)
                    clusters_dict['puerto'].append(puerto)
                    clusters_dict['ingrediente'].append(ingrediente)
                    clusters_dict['planta'].append(planta)
                    clusters_dict['periodo'].append(periodo)
                    clusters_dict['costo_almacenamiento'].append(
                        costo_almacenamiento)
                    clusters_dict['costo_despacho'].append(costo_despacho)
clusters_df = pd.DataFrame(clusters_dict)

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
importaciones_list = list()
for importacion in cargas.keys():

    df = clusters_df[clusters_df['importacion'] == importacion]

    cantidad_valores_unicos = len(df['costo_despacho'].unique())

    temp = asignar_etiquetas(df=df, column_name='costo_despacho')

    importaciones_list.append(temp)

# Unir los Datasets
clusters_df = pd.concat(importaciones_list)

# Crear indices
clusters_df.set_index(['importacion', 'planta', 'periodo'], inplace=True)

# %% [markdown]
# # Inicializacion de variables

# %%
for importacion, carga in cargas.items():
    for planta in plantas.keys():
        if planta in carga['costo_despacho'].keys():
            for periodo, variable in carga['costo_despacho'][planta]['variable_despacho'].items():
                variable.setInitialValue(0)

# %%
for importacion, carga in cargas.items():
    inventario_final = carga['inventario_inicial']
    llegadas = 0.0
    for periodo in periodos:
        llegadas = 0.0
        if periodo in carga['llegadas'].keys():
            llegadas = carga['llegadas'][periodo]
        inventario_final += llegadas

        carga['inventario_al_final'][periodo].setInitialValue(inventario_final)

# %% [markdown]
# # Modelo matemático

# %% [markdown]
# ## Sets:
#
# $t$: periodos con $t \in T$
#
# $p$: productos con $p \in P$
#
# $i$: cargas con $i \in T$
#
# $j$: plantas con $j \in J$

# %% [markdown]
#
# ## Parametros:
#
# $CB:$ Costo de backorder por día
#
# $CT_{ij}$: Costo de transportar la carga $i$ hacia la planta $j$
#
# $CA_{it}$: Costo de mantener la carga $i$ almacenada al final del periodo $p$
#
# $AR_{it}$: Cantidad de producto llegando a la carga $i$ durante el periodo $p$
#
# $DM_{pjt}$: Demanda del producto $p$ en la planta $j$ durante el periodo $t$
#
# $CP_{pjt}$: Capacidad de almacenar el producto $p$ en la planta $j$
#
# $IP_{i}$: Inventario inicial de la carga $i$
#
# $TJ_{pjt}$: Cantidad programada del producto $p$ llegando a la planta $j$ durante el periodo $t$
#
# $IJ_{pj}$: Inventario inicial de producto $p$ en la planta $j$
#
# $MI_{pjt}$: Inventario mínimo a mantener del producto $p$ en la planta $j$ al final del periodo $t$
#
# $MX_{pjt}$: Inventario máximo a mantener del producto $p$ en la planta $j$ al final del periodo $t$
#

# %% [markdown]
#
# ## Variables:
#
# $T_{ijt}$: Variable entera, Cantidad de camiones de 34 Toneladas a despachar de la carga $i$ hasta la planta $j$ durante el periodo $t$
#
# $O_{it}$: Continua, Cantidad de toneladas de la carga $i$ almacenadas al final del periodo $t$
#
# $I_{pjt}$: Cantidad del producto $p$ almacenado en la planta $j$ al final del periodo $t$
#
# $B_{pjt}$: Cantidad del producto $p$ de backorder en la planta $j$ al final del periodo $t$
#
# $S_{pjt}$: Cantidad del producto $p$ por debajo del SS en la planta $j$ al final del periodo $t$
#
# $M_{pjt}$: Unidades de exceso del producto $p$ en la planta $j$ al final del periodo $t$ sobre el inventario objetivo
#
# $X_{pjt}$: Unidades por debajo del producto $p$ en la planta $j$ al final del periodo $t$ bajo el inventario objetivo
#

# %% [markdown]
#
# ## Funcion Objetivo:
#
# $$min \sum_{i}\sum_{j}\sum_{t}{CT_{ijt}*T_{ijt}} + \sum_{i}\sum_{t}CA_{it}O_{it} + \sum_{pjt}{CB*B}  + PP \sum_{M}\sum_{P}\sum_{J}{M_{mpj}} + PP \sum_{M}\sum_{P}\sum_{J}{X_{mpj}}$$

# %%
funcion_objetivo = list()

# %% [markdown]
# ### Costo por transporte
#
# El costo del transporte esta dado por el producto escalar entre los costos de envio, que ya incluyen fletes, costos porturarios y costos intercompany
#
# $$\sum_{i}\sum_{j}\sum_{t}{CT_{ijt}*T_{ijt}}$$

# %%
for periodo in periodos:
    for impo, carga in cargas.items():
        for nombre_planta, planta in plantas.items():
            if periodo in carga['costo_despacho'][nombre_planta]['variable_despacho'].keys():
                # CT_ijt*T_ijt
                # + periodos.index(periodo)
                costo_envio = carga['costo_despacho'][nombre_planta]['costo_envio'][periodo]
                costo_almacenamiento = carga['costo_despacho']['envigado']['descuento_almacenamiento'][periodo]*cap_camion
                var_envio = carga['costo_despacho'][nombre_planta]['variable_despacho'][periodo]
                funcion_objetivo.append(
                    (costo_envio-costo_almacenamiento)*var_envio)

# %% [markdown]
# ### Costo por almacenamiento en puerto (Se ha incluido como descuento en el costo de transporte)
#
# El costo por almacenamiento esta dado por el producto escalar entre los costos de almacenamiento que incluyen el costo el costo de operacion portuaria de llevar el material desde el barco hasta la bodega y, la tarifa por almacenamiento que se paga periódicamente luego de los días libres.
#
# *Sin embargo, cada vez que se envia un camion hacia cualquier planta, es un camion de producto menos que se cuenta como costo de almacenamiento, por lo que ya no es necesario incluir el costo de almacenamiento en la función objetivo.*
#
# $$\sum_{i}\sum_{t}CA_{it}O_{it}$$

# %% [markdown]
# for periodo in periodos:
#     for impo, carga in cargas.items():
#         costo_almaenamiento = carga['costo_almacenamiento'][periodo]
#         inventario_al_final = carga['inventario_al_final'][periodo]
#         if costo_almaenamiento > 0:
#             funcion_objetivo.append(costo_almaenamiento*inventario_al_final)
#         # else:
#         #    funcion_objetivo.append(0.5*inventario_al_final)

# %% [markdown]
# ### Costo de Backorder
#
# El costo por backorder es una penalización a la función objetivo, donde se carga un valor determinado por cada kilogramo de material que no esté disponible para el consumo
#
# $\sum_{pjt}{CB*B}$

# %%
for nombre_planta, planta in plantas.items():
    for nombre_ingrediente, ingrediente in planta['inventarios'].items():
        for periodo, var in ingrediente['backorder'].items():
            # if periodo in periodos[periodo_administrativo:]:
            funcion_objetivo.append(costo_backorder_dia*var)

# %% [markdown]
# ### Costo por no alcanzar el inventario de seguridad

# %%
for nombre_planta, planta in plantas.items():
    for nombre_ingrediente, ingrediente in planta['inventarios'].items():
        if 'safety_stock' in planta['inventarios'][nombre_ingrediente].keys():
            for periodo, var in ingrediente['safety_stock'].items():
                # if periodo in periodos[periodo_administrativo:]:
                funcion_objetivo.append(costo_safety_stock*var)

# %% [markdown]
# ## Restricciones:

# %% [markdown]
#
# ### Balance de masa en cargas
#
# El inventario al final del periodo es igual a:
#
# - el inventario al final del periodo anterior;
# - más las llegadas planeadas;
# - menos los despachos hacia plantas
#
# $$ O_{it} =  O_{i(t-1)} + AR_{it} - 34000\sum_{J}{T_{ijt}} \hspace{1cm} \forall i \in I, t \in T$$

# %%
rest_balance_masa_puerto = list()

for importacion, carga in cargas.items():
    for periodo in periodos:

        left = list()
        right = list()

        # Oit
        Oit = carga['inventario_al_final'][periodo]
        left.append(Oit)

        # Oi(t-1)
        if periodo == periodos[0]:
            Oitant = carga['inventario_inicial']
        else:
            t_anterior = periodos[periodos.index(periodo)-1]
            Oitant = carga['inventario_al_final'][t_anterior]
        right.append(Oitant)

        # ARit
        if periodo in carga['llegadas'].keys():
            ar = carga['llegadas'][periodo]
            right.append(ar)

        # - 34000*Sum(Tijt)
        for planta, despacho in carga['costo_despacho'].items():
            if periodo in despacho['variable_despacho'].keys():
                var_despacho = despacho['variable_despacho'][periodo]
                left.append(cap_camion*var_despacho)

        name = f'balance_masa_{importacion}_al_final_de_{periodo}'
        rest = (pu.lpSum(left) == pu.lpSum(right), name)

        rest_balance_masa_puerto.append(rest)

# %% [markdown]
# ### Balance de masa en plantas
#
# El inventario en planta al final del periodo es igual a:
#
# - el inventario al final del periodo anterior;
# - más las llegadas ya programadas;
# - más las llegadas planeadas;
# - menos la demanda
# - más el backorder, que compensa cuando el inventario más las llegadas no son suficientes
#
# $$ I_{pjt} = I_{pj(t-1)} + TJ_{pjt} + \sum_{i}{T_{ij(t-2)}} -  DM_{pjt} + B_{pjt} \hspace{1cm} \forall p \in P, j \in J, t \in T$$
#

# %%
rest_balance_masa_planta = list()
for nombre_planta, planta in plantas.items():
    for nombre_ingrediente, ingrediente in planta['inventarios'].items():

        for periodo in periodos:

            if periodo in ingrediente['inventario_final'].keys():

                left = list()
                right = list()

                # Ipjt
                Spjt = ingrediente['inventario_final'][periodo]
                left.append(Spjt)

                # Ipj(t-1)
                if periodo == periodos[0]:
                    Ipj_tanterior = ingrediente['inventario_final'][periodo_anterior]
                else:
                    p_anterior = periodos[periodos.index(periodo)-1]
                    Ipj_tanterior = ingrediente['inventario_final'][p_anterior]

                right.append(Ipj_tanterior)

                # + TJ

                # + Tijt
                if periodo in ingrediente['llegadas'].keys():
                    for llegada_planeada_var in ingrediente['llegadas'][periodo]:
                        if type(llegada_planeada_var) == pu.LpVariable:
                            right.append(cap_camion*llegada_planeada_var)
                        else:
                            right.append(llegada_planeada_var)

                # - DMpjt

                if periodo in ingrediente['consumo'].keys():
                    DMpjt = ingrediente['consumo'][periodo]
                    left.append(DMpjt)

                # + Baclorder
                if periodo in ingrediente['backorder'].keys():
                    bak_var = ingrediente['backorder'][periodo]
                    right.append(bak_var)

                name = f'balance_planta_{nombre_planta}_de_{nombre_ingrediente}_al_final_de_{periodo}'
                rest = (pu.lpSum(left) == pu.lpSum(right), name)

                rest_balance_masa_planta.append(rest)

# %% [markdown]
# ### Capacidad de recepción por planta
#
# En una planta y un periodo en particular, la suma del producto entre el tiempo del ingrediente y la cantidad de camiones llegando no debe superar el tiempo total disponible en la planta
#
# $$ \sum_{I}{TiempoIngrediente_{pj}*T_{ijt}} \leq TiempoTotal_{t} \hspace{1cm} \forall p \in P, t \in T$$

# %%
rest_llegada_material = list()
for nombre_planta, planta in plantas.items():
    tiempo_total = planta['tiempo_total']
    for periodo in periodos:
        left_expresion = list()
        for ingrediente, parametros in planta['inventarios'].items():
            tiempo_ingrediente_por_camion = planta['tiempo_ingrediente'][ingrediente]
            if periodo in parametros['llegadas'].keys():
                for var_llegada in parametros['llegadas'][periodo]:
                    left_expresion.append(
                        tiempo_ingrediente_por_camion*var_llegada)

        # omitir restricciones sin expresiones al lado izquiero
        if len(left_expresion) > 0:
            rest_name = f'Llegada_material_{nombre_planta}_durante_{periodo}'
            rest = (pu.lpSum(left_expresion) <= tiempo_total, rest_name)
            rest_llegada_material.append(rest)

# %% [markdown]
# ### Capacidad de almacenamiento
#
# $$ I_{pjt} \leq CP_{pj} + M_{pjt} \hspace{1cm} \forall p \in P, t \in T$$
#
# La capacidad de almacenamiento ha sido configurada con el límite superior de las variables de inventario al final del periodo en cada planta

# %% [markdown]
# ### Superar el inventario de seguridad
#
# El inventario al final de un día cualquiera debe estar bajo el nivel máximo, por lo que penalizaremos en la función objetivo una variable de holgura para tal efecto
# $$ I_{pjt} \geq MX_{pjt} + M_{pjt} \hspace{1cm} \forall p \in P, j \in J, t \in T$$

# %%
rest_safety_stock = list()
for nombre_planta, planta in plantas.items():
    for ingrediente, inventarios in planta['inventarios'].items():
        if 'safety_stock_kg' in inventarios.keys():
            SS = inventarios['safety_stock_kg']
            # for periodo, variable in inventarios['inventario_final'].items():
            if len(inventarios['safety_stock'].keys()) > 0:
                for periodo in periodos:
                    rest_name = f'safety_stock_en_{nombre_planta}_de_{ingrediente}_durante_{periodo}'
                    Ipjt = inventarios['inventario_final'][periodo]
                    Spij = inventarios['safety_stock'][periodo]

                    rest = (Ipjt + Spij >= SS, rest_name)
                    rest_safety_stock.append(rest)

# %% [markdown]
# ### Superar el inventario objetivo al final del mes

# %%
rest_inventario_objetivo = list()
for nombre_planta, planta in plantas.items():
    for ingrediente, inventarios in planta['inventarios'].items():
        if 'objetivo_kg' in inventarios.keys():

            target = inventarios['objetivo_kg']
            if target > 0:
                rest_name = f'objetivo_en_{nombre_planta}_de_{ingrediente}_al_final_de_{periodos[periodo_final]}'
                Ipjt = inventarios['inventario_final'][periodos[periodo_final]]

                rest = (Ipjt >= target, rest_name)
                rest_inventario_objetivo.append(rest)

# %% [markdown]
# # Resolviendo el modelo

# %% [markdown]
# ## Generando modelo

# %%
problema = pu.LpProblem(name='Bios_Solver', sense=pu.LpMinimize)

# Agregando funcion objetivo
problema += pu.lpSum(funcion_objetivo)

# Agregando balance de masa puerto
for rest in rest_balance_masa_puerto:
    problema += rest

# Agregando balande ce masa en planta
for rest in rest_balance_masa_planta:
    problema += rest

# Agregando capacidad de recepcion
for rest in rest_llegada_material:
    problema += rest

# Agregando inventario de seguridad
for rest in rest_safety_stock:
    problema += rest

# Agregando inventario objetivo
for rest in rest_inventario_objetivo:
    problema += rest

# %% [markdown]
# ## Ejecutando modelo

# %%
print('cpu count', cpu_count)
print('tiempo limite', t_limit_minutes, 'minutos')
print('ejecutando ', len(periodos), 'periodos')

print('GAP tolerable', gap, 'millones de pesos')
engine = pu.PULP_CBC_CMD(
    timeLimit=60*t_limit_minutes,
    gapAbs=gap,
    warmStart=True,
    cuts=True,
    presolve=True,
    threads=cpu_count)

problema.solve(solver=engine)
# problema.solve()

# %% [markdown]
# # Construccion de reporte

# %% [markdown]
# ## Reporte de puerto

# %% [markdown]
# {
#     "cells": [
#         {
#

# %%
            "cell_type": "markdown",
            "metadata": {
                "tags": [
                    "parameters"
                ]
            },
            "source": [
                "# Modelo BIOS:"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Importacion de Librerias"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 1,
            "metadata": {},
            "outputs": [],
            "source": [
                "import pandas as pd\n",
                "from datetime import datetime, timedelta\n",
                "import pulp as pu\n",
                "from utils.asignador_capacidad import AsignadorCapacidad\n",
                "from utils.planta_loader import obtener_matriz_plantas\n",
                "import os\n",
                "import shutil\n",
                "import json\n",
                "import numpy as np\n",
                "from sklearn.cluster import KMeans\n",
                "from tqdm import tqdm"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Parametros generales"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 2,
            "metadata": {},
            "outputs": [],
            "source": [
                "bios_input_file = 'data/0_model_template_2204.xlsm'\n",
                "\n",
                "# Tiempo máximo de detencion en minutos\n",
                "t_limit_minutes = 60*6\n",
                "\n",
                "# Cantidad CPU habilitadas para trabajar\n",
                "cpu_count = max(1, os.cpu_count()-1)\n",
                "\n",
                "# Gap en millones de pesos\n",
                "gap = 5000000\n",
                "\n",
                "# Capacidad de carga de un camion\n",
                "cap_camion = 34000\n",
                "\n",
                "# Capacidad de descarga en puerto por día\n",
                "cap_descarge = 5000000\n",
                "\n",
                "# Costo de no safety stock por día\n",
                "costo_safety_stock = 50000\n",
                "\n",
                "# Costo de backorder por dia\n",
                "costo_backorder_dia = costo_safety_stock*5\n",
                "\n",
                "# Costo exceso de inventario\n",
                "costo_exceso_capacidad = costo_safety_stock*3\n",
                "\n",
                "# Los transportes solo tienen sentido desde el periodo 3, es dificil tomar deciciones para el mismo día\n",
                "periodo_administrativo = 1\n",
                "\n",
                "# Asumimos qe todo despacho tarda 2 días desde el momento que se envía la carga hasta que esta disponible para el consumo en planta\n",
                "lead_time = 2"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Lectura de dataframes"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 3,
            "metadata": {},
            "outputs": [
                {
                    "name": "stdout",
                    "output_type": "stream",
                    "text": [
                        "Leyendo archivo\n"
                    ]
                },
                {
                    "name": "stderr",
                    "output_type": "stream",
                    "text": [
                        "100%|██████████| 11/11 [00:00<00:00, 15.33it/s]\n"
                    ]
                },
                {
                    "name": "stdout",
                    "output_type": "stream",
                    "text": [
                        "generando periodos\n",
                        "generando consumo\n"
                    ]
                },
                {
                    "name": "stderr",
                    "output_type": "stream",
                    "text": [
                        "100%|██████████| 121/121 [00:00<00:00, 543.95it/s]\n"
                    ]
                },
                {
                    "name": "stdout",
                    "output_type": "stream",
                    "text": [
                        "trabajando con unidades de almacenamiento\n"
                    ]
                },
                {
                    "name": "stderr",
                    "output_type": "stream",
                    "text": [
                        "100%|██████████| 107/107 [00:00<00:00, 609.91it/s]\n"
                    ]
                },
                {
                    "name": "stdout",
                    "output_type": "stream",
                    "text": [
                        "trabajando con llegadas planeadas a planta\n"
                    ]
                },
                {
                    "name": "stderr",
                    "output_type": "stream",
                    "text": [
                        "100%|██████████| 24/24 [00:00<00:00, 3586.92it/s]\n"
                    ]
                },
                {
                    "name": "stdout",
                    "output_type": "stream",
                    "text": [
                        "trabajando con safety stock en planta\n"
                    ]
                },
                {
                    "name": "stderr",
                    "output_type": "stream",
                    "text": [
                        "100%|██████████| 121/121 [00:00<00:00, 190.14it/s]\n"
                    ]
                },
                {
                    "name": "stdout",
                    "output_type": "stream",
                    "text": [
                        "calculando inventarios\n"
                    ]
                },
                {
                    "name": "stderr",
                    "output_type": "stream",
                    "text": [
                        "100%|██████████| 13/13 [00:00<00:00, 25.35it/s]\n"
                    ]
                }
            ],
            "source": [
                "data_plantas_df = obtener_matriz_plantas(bios_input_file=bios_input_file)"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 4,
            "metadata": {},
            "outputs": [],
            "source": [
                "# Leer el archivo de excel\n",
                "productos_df = pd.read_excel(io=bios_input_file, sheet_name='ingredientes')\n",
                "plantas_df = pd.read_excel(io=bios_input_file, sheet_name='plantas')\n",
                "asignador = AsignadorCapacidad(bios_input_file)\n",
                "unidades_almacenamiento_df = asignador.obtener_unidades_almacenamiento()\n",
                "safety_stock_df = pd.read_excel(io=bios_input_file, sheet_name='safety_stock')\n",
                "consumo_proyectado_df = pd.read_excel(\n",
                "    io=bios_input_file, sheet_name='consumo_proyectado')\n",
                "transitos_puerto_df = pd.read_excel(\n",
                "    io=bios_input_file, sheet_name='tto_puerto')\n",
                "transitos_planta_df = pd.read_excel(\n",
                "    io=bios_input_file, sheet_name='tto_plantas')\n",
                "inventario_puerto_df = pd.read_excel(\n",
                "    io=bios_input_file, sheet_name='inventario_puerto')\n",
                "costos_almacenamiento_df = pd.read_excel(\n",
                "    io=bios_input_file, sheet_name='costos_almacenamiento_cargas')\n",
                "operaciones_portuarias_df = pd.read_excel(\n",
                "    io=bios_input_file, sheet_name='costos_operacion_portuaria')\n",
                "operaciones_portuarias_df = operaciones_portuarias_df.set_index(\n",
                "    ['tipo_operacion', 'operador', 'puerto', 'ingrediente'])\n",
                "fletes_df = pd.read_excel(io=bios_input_file, sheet_name='fletes_cop_per_kg')\n",
                "intercompany_df = pd.read_excel(\n",
                "    io=bios_input_file, sheet_name='venta_entre_empresas')\n",
                "objetivo_df = pd.read_excel(io='validaciones.xlsx', sheet_name='objetivo')"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Validaciones"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "def validar_nombres_columnas(input_file: str):\n",
                "\n",
                "    with open(\"file_structure.json\") as file:\n",
                "        paginas_dict = json.load(file)\n",
                "\n",
                "    errors_list = list()\n",
                "\n",
                "    for tab, columns in paginas_dict.items():\n",
                "        df = pd.read_excel(input_file, sheet_name=tab)\n",
                "        for column in columns:\n",
                "            if not column in df.columns:\n",
                "                errors_list.append(\n",
                "                    f'la columna \"{column}\" de la página \"{tab}\" parece faltar o estar mál escrita')\n",
                "\n",
                "    if len(errors_list) > 0:\n",
                "        return f\"Error, las siguientes columnas no se encontraron: {', '.join(errors_list)}\"\n",
                "    else:\n",
                "        return 'OK, el archivo parece tener las columnas y las pestañas completas'\n",
                "\n",
                "\n",
                "print(validar_nombres_columnas(input_file=bios_input_file))"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "def _validar_ingredientes(input_file: str):\n",
                "\n",
                "    df = pd.read_excel(io=input_file, sheet_name='ingredientes')\n",
                "\n",
                "    ingredientes = list(df['nombre'].unique())\n",
                "\n",
                "    if len(ingredientes) == df.shape[0]:\n",
                "        return \"OK, La lista de ingredientes tiene nombres únicos\"\n",
                "    else:\n",
                "        return \"Error, La lista de ingredientes tiene nombres duplicados\"\n",
                "\n",
                "\n",
                "print(_validar_ingredientes(input_file=bios_input_file))"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Creacion de parametros del problema"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### Tiempo"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 5,
            "metadata": {},
            "outputs": [
                {
                    "name": "stdout",
                    "output_type": "stream",
                    "text": [
                        "20240421 20240422 20240522\n"
                    ]
                }
            ],
            "source": [
                "# Obtener el conjunto de periodos\n",
                "fechas = [datetime.strptime(x, '%d/%m/%Y')\n",
                "          for x in consumo_proyectado_df.drop(columns=['planta', 'ingrediente']).columns]\n",
                "\n",
                "periodos = [int(x.strftime('%Y%m%d')) for x in fechas]\n",
                "\n",
                "periodo_anterior = fechas[0] - timedelta(days=1)\n",
                "periodo_anterior = int(periodo_anterior.strftime('%Y%m%d'))\n",
                "\n",
                "print(periodo_anterior,  periodos[0], periodos[-1])"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### Productos"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 6,
            "metadata": {},
            "outputs": [],
            "source": [
                "productos = [productos_df.loc[i]['nombre'] for i in productos_df.index]"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### Plantas"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "#### Tiempo de descarge de materiales"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 7,
            "metadata": {},
            "outputs": [],
            "source": [
                "# Generar plantas\n",
                "plantas = dict()\n",
                "\n",
                "for j in plantas_df.index:\n",
                "    planta = plantas_df.loc[j]['planta']\n",
                "    empresa = plantas_df.loc[j]['empresa']\n",
                "    operacion_minutos = plantas_df.loc[j]['operacion_minutos'] * \\\n",
                "        plantas_df.loc[j]['plataformas']\n",
                "    plantas[planta] = dict()\n",
                "    plantas[planta]['empresa'] = empresa\n",
                "    plantas[planta]['tiempo_total'] = operacion_minutos\n",
                "    plantas[planta]['tiempo_ingrediente'] = dict()\n",
                "    plantas[planta]['llegadas_puerto'] = dict()\n",
                "\n",
                "    for p in productos:\n",
                "        t_ingrediente = plantas_df.loc[j][p]\n",
                "        plantas[planta]['tiempo_ingrediente'][p] = t_ingrediente\n",
                "        plantas[planta]['llegadas_puerto'][p] = {t: list() for t in periodos}"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "#### Inventario en Planta"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 8,
            "metadata": {},
            "outputs": [
                {
                    "data": {
                        "text/html": [
                            "<div>\n",
                            "<style scoped>\n",
                            "    .dataframe tbody tr th:only-of-type {\n",
                            "        vertical-align: middle;\n",
                            "    }\n",
                            "\n",
                            "    .dataframe tbody tr th {\n",
                            "        vertical-align: top;\n",
                            "    }\n",
                            "\n",
                            "    .dataframe thead th {\n",
                            "        text-align: right;\n",
                            "    }\n",
                            "</style>\n",
                            "<table border=\"1\" class=\"dataframe\">\n",
                            "  <thead>\n",
                            "    <tr style=\"text-align: right;\">\n",
                            "      <th></th>\n",
                            "      <th>planta</th>\n",
                            "      <th>ingrediente_actual</th>\n",
                            "      <th>cantidad_actual</th>\n",
                            "      <th>capacidad</th>\n",
                            "      <th>dias_ss</th>\n",
                            "    </tr>\n",
                            "  </thead>\n",
                            "  <tbody>\n",
                            "    <tr>\n",
                            "      <th>0</th>\n",
                            "      <td>barbosa</td>\n",
                            "      <td>cascarilla</td>\n",
                            "      <td>1.0</td>\n",
                            "      <td>68000.0</td>\n",
                            "      <td>0.0</td>\n",
                            "    </tr>\n",
                            "    <tr>\n",
                            "      <th>1</th>\n",
                            "      <td>barbosa</td>\n",
                            "      <td>destilado</td>\n",
                            "      <td>1.0</td>\n",
                            "      <td>68000.0</td>\n",
                            "      <td>0.0</td>\n",
                            "    </tr>\n",
                            "    <tr>\n",
                            "      <th>2</th>\n",
                            "      <td>barbosa</td>\n",
                            "      <td>destiladohp</td>\n",
                            "      <td>1.0</td>\n",
                            "      <td>68000.0</td>\n",
                            "      <td>0.0</td>\n",
                            "    </tr>\n",
                            "    <tr>\n",
                            "      <th>3</th>\n",
                            "      <td>barbosa</td>\n",
                            "      <td>forraje</td>\n",
                            "      <td>1.0</td>\n",
                            "      <td>68000.0</td>\n",
                            "      <td>0.0</td>\n",
                            "    </tr>\n",
                            "    <tr>\n",
                            "      <th>4</th>\n",
                            "      <td>barbosa</td>\n",
                            "      <td>gluten</td>\n",
                            "      <td>1.0</td>\n",
                            "      <td>68000.0</td>\n",
                            "      <td>0.0</td>\n",
                            "    </tr>\n",
                            "  </tbody>\n",
                            "</table>\n",
                            "</div>"
                        ],
                        "text/plain": [
                            "    planta ingrediente_actual  cantidad_actual  capacidad  dias_ss\n",
                            "0  barbosa         cascarilla              1.0    68000.0      0.0\n",
                            "1  barbosa          destilado              1.0    68000.0      0.0\n",
                            "2  barbosa        destiladohp              1.0    68000.0      0.0\n",
                            "3  barbosa            forraje              1.0    68000.0      0.0\n",
                            "4  barbosa             gluten              1.0    68000.0      0.0"
                        ]
                    },
                    "execution_count": 8,
                    "metadata": {},
                    "output_type": "execute_result"
                }
            ],
            "source": [
                "unidades_almacenamiento_df['capacidad'] = unidades_almacenamiento_df.apply(\n",
                "    lambda x: x[x['ingrediente_actual']], axis=1)\n",
                "unidades_almacenamiento_df.drop(columns=productos, inplace=True)\n",
                "unidades_almacenamiento_df = unidades_almacenamiento_df.groupby(\n",
                "    ['planta', 'ingrediente_actual'])[['cantidad_actual', 'capacidad']].sum().reset_index()\n",
                "\n",
                "# Agregando la informacion de safety stock\n",
                "unidades_almacenamiento_df = pd.merge(left=unidades_almacenamiento_df,\n",
                "                                      right=safety_stock_df,\n",
                "                                      left_on=['planta', 'ingrediente_actual'],\n",
                "                                      right_on=['planta', 'ingrediente'],\n",
                "                                      how='left').drop(columns='ingrediente')\n",
                "\n",
                "unidades_almacenamiento_df.head()"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 9,
            "metadata": {},
            "outputs": [
                {
                    "name": "stdout",
                    "output_type": "stream",
                    "text": [
                        "(107, 36)\n"
                    ]
                },
                {
                    "data": {
                        "text/html": [
                            "<div>\n",
                            "<style scoped>\n",
                            "    .dataframe tbody tr th:only-of-type {\n",
                            "        vertical-align: middle;\n",
                            "    }\n",
                            "\n",
                            "    .dataframe tbody tr th {\n",
                            "        vertical-align: top;\n",
                            "    }\n",
                            "\n",
                            "    .dataframe thead th {\n",
                            "        text-align: right;\n",
                            "    }\n",
                            "</style>\n",
                            "<table border=\"1\" class=\"dataframe\">\n",
                            "  <thead>\n",
                            "    <tr style=\"text-align: right;\">\n",
                            "      <th></th>\n",
                            "      <th>planta</th>\n",
                            "      <th>ingrediente</th>\n",
                            "      <th>cantidad</th>\n",
                            "      <th>capacidad</th>\n",
                            "      <th>dias_ss</th>\n",
                            "      <th>20240422</th>\n",
                            "      <th>20240423</th>\n",
                            "      <th>20240424</th>\n",
                            "      <th>20240425</th>\n",
                            "      <th>20240426</th>\n",
                            "      <th>...</th>\n",
                            "      <th>20240513</th>\n",
                            "      <th>20240514</th>\n",
                            "      <th>20240515</th>\n",
                            "      <th>20240516</th>\n",
                            "      <th>20240517</th>\n",
                            "      <th>20240518</th>\n",
                            "      <th>20240519</th>\n",
                            "      <th>20240520</th>\n",
                            "      <th>20240521</th>\n",
                            "      <th>20240522</th>\n",
                            "    </tr>\n",
                            "  </thead>\n",
                            "  <tbody>\n",
                            "    <tr>\n",
                            "      <th>0</th>\n",
                            "      <td>barbosa</td>\n",
                            "      <td>cascarilla</td>\n",
                            "      <td>1.0</td>\n",
                            "      <td>68000.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.000000</td>\n",
                            "      <td>0.000000</td>\n",
                            "      <td>0.000000</td>\n",
                            "      <td>0.000000</td>\n",
                            "      <td>0.000000</td>\n",
                            "      <td>...</td>\n",
                            "      <td>0.000000</td>\n",
                            "      <td>0.000000</td>\n",
                            "      <td>0.000000</td>\n",
                            "      <td>0.000000</td>\n",
                            "      <td>0.000000</td>\n",
                            "      <td>0.000000</td>\n",
                            "      <td>0.000000</td>\n",
                            "      <td>0.000000</td>\n",
                            "      <td>0.000000</td>\n",
                            "      <td>0.000000</td>\n",
                            "    </tr>\n",
                            "    <tr>\n",
                            "      <th>1</th>\n",
                            "      <td>barbosa</td>\n",
                            "      <td>destilado</td>\n",
                            "      <td>1.0</td>\n",
                            "      <td>68000.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>439.613182</td>\n",
                            "      <td>439.613182</td>\n",
                            "      <td>439.613182</td>\n",
                            "      <td>439.613182</td>\n",
                            "      <td>439.613182</td>\n",
                            "      <td>...</td>\n",
                            "      <td>439.613182</td>\n",
                            "      <td>439.613182</td>\n",
                            "      <td>439.613182</td>\n",
                            "      <td>439.613182</td>\n",
                            "      <td>439.613182</td>\n",
                            "      <td>439.613182</td>\n",
                            "      <td>439.613182</td>\n",
                            "      <td>439.613182</td>\n",
                            "      <td>439.613182</td>\n",
                            "      <td>439.613182</td>\n",
                            "    </tr>\n",
                            "    <tr>\n",
                            "      <th>2</th>\n",
                            "      <td>barbosa</td>\n",
                            "      <td>destiladohp</td>\n",
                            "      <td>1.0</td>\n",
                            "      <td>68000.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.000000</td>\n",
                            "      <td>0.000000</td>\n",
                            "      <td>0.000000</td>\n",
                            "      <td>0.000000</td>\n",
                            "      <td>0.000000</td>\n",
                            "      <td>...</td>\n",
                            "      <td>0.000000</td>\n",
                            "      <td>0.000000</td>\n",
                            "      <td>0.000000</td>\n",
                            "      <td>0.000000</td>\n",
                            "      <td>0.000000</td>\n",
                            "      <td>0.000000</td>\n",
                            "      <td>0.000000</td>\n",
                            "      <td>0.000000</td>\n",
                            "      <td>0.000000</td>\n",
                            "      <td>0.000000</td>\n",
                            "    </tr>\n",
                            "    <tr>\n",
                            "      <th>3</th>\n",
                            "      <td>barbosa</td>\n",
                            "      <td>forraje</td>\n",
                            "      <td>1.0</td>\n",
                            "      <td>68000.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>150.727273</td>\n",
                            "      <td>150.727273</td>\n",
                            "      <td>150.727273</td>\n",
                            "      <td>150.727273</td>\n",
                            "      <td>150.727273</td>\n",
                            "      <td>...</td>\n",
                            "      <td>150.727273</td>\n",
                            "      <td>150.727273</td>\n",
                            "      <td>150.727273</td>\n",
                            "      <td>150.727273</td>\n",
                            "      <td>150.727273</td>\n",
                            "      <td>150.727273</td>\n",
                            "      <td>150.727273</td>\n",
                            "      <td>150.727273</td>\n",
                            "      <td>150.727273</td>\n",
                            "      <td>150.727273</td>\n",
                            "    </tr>\n",
                            "    <tr>\n",
                            "      <th>4</th>\n",
                            "      <td>barbosa</td>\n",
                            "      <td>gluten</td>\n",
                            "      <td>1.0</td>\n",
                            "      <td>68000.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>6064.242727</td>\n",
                            "      <td>6064.242727</td>\n",
                            "      <td>6064.242727</td>\n",
                            "      <td>6064.242727</td>\n",
                            "      <td>6064.242727</td>\n",
                            "      <td>...</td>\n",
                            "      <td>6064.242727</td>\n",
                            "      <td>6064.242727</td>\n",
                            "      <td>6064.242727</td>\n",
                            "      <td>6064.242727</td>\n",
                            "      <td>6064.242727</td>\n",
                            "      <td>6064.242727</td>\n",
                            "      <td>6064.242727</td>\n",
                            "      <td>6064.242727</td>\n",
                            "      <td>6064.242727</td>\n",
                            "      <td>6064.242727</td>\n",
                            "    </tr>\n",
                            "  </tbody>\n",
                            "</table>\n",
                            "<p>5 rows × 36 columns</p>\n",
                            "</div>"
                        ],
                        "text/plain": [
                            "    planta  ingrediente  cantidad  capacidad  dias_ss     20240422  \\\n",
                            "0  barbosa   cascarilla       1.0    68000.0      0.0     0.000000   \n",
                            "1  barbosa    destilado       1.0    68000.0      0.0   439.613182   \n",
                            "2  barbosa  destiladohp       1.0    68000.0      0.0     0.000000   \n",
                            "3  barbosa      forraje       1.0    68000.0      0.0   150.727273   \n",
                            "4  barbosa       gluten       1.0    68000.0      0.0  6064.242727   \n",
                            "\n",
                            "      20240423     20240424     20240425     20240426  ...     20240513  \\\n",
                            "0     0.000000     0.000000     0.000000     0.000000  ...     0.000000   \n",
                            "1   439.613182   439.613182   439.613182   439.613182  ...   439.613182   \n",
                            "2     0.000000     0.000000     0.000000     0.000000  ...     0.000000   \n",
                            "3   150.727273   150.727273   150.727273   150.727273  ...   150.727273   \n",
                            "4  6064.242727  6064.242727  6064.242727  6064.242727  ...  6064.242727   \n",
                            "\n",
                            "      20240514     20240515     20240516     20240517     20240518  \\\n",
                            "0     0.000000     0.000000     0.000000     0.000000     0.000000   \n",
                            "1   439.613182   439.613182   439.613182   439.613182   439.613182   \n",
                            "2     0.000000     0.000000     0.000000     0.000000     0.000000   \n",
                            "3   150.727273   150.727273   150.727273   150.727273   150.727273   \n",
                            "4  6064.242727  6064.242727  6064.242727  6064.242727  6064.242727   \n",
                            "\n",
                            "      20240519     20240520     20240521     20240522  \n",
                            "0     0.000000     0.000000     0.000000     0.000000  \n",
                            "1   439.613182   439.613182   439.613182   439.613182  \n",
                            "2     0.000000     0.000000     0.000000     0.000000  \n",
                            "3   150.727273   150.727273   150.727273   150.727273  \n",
                            "4  6064.242727  6064.242727  6064.242727  6064.242727  \n",
                            "\n",
                            "[5 rows x 36 columns]"
                        ]
                    },
                    "execution_count": 9,
                    "metadata": {},
                    "output_type": "execute_result"
                }
            ],
            "source": [
                "# Generar un diccionario para renombrar las columnas de tiempo en consumo proyectado\n",
                "consumo_proyectado_renamer = {x: datetime.strptime(x, '%d/%m/%Y').strftime(\n",
                "    '%Y%m%d') for x in consumo_proyectado_df.drop(columns=['planta', 'ingrediente']).columns}\n",
                "# Efectuar el cambio de nombre\n",
                "consumo_proyectado_df.rename(columns=consumo_proyectado_renamer, inplace=True)\n",
                "# Unir con el consumo proyectado\n",
                "unidades_almacenamiento_df = pd.merge(left=unidades_almacenamiento_df,\n",
                "                                      right=consumo_proyectado_df,\n",
                "                                      left_on=['planta', 'ingrediente_actual'],\n",
                "                                      right_on=['planta', 'ingrediente'],\n",
                "                                      how='left').drop(columns=['ingrediente']).rename(columns={'ingrediente_actual': 'ingrediente', 'cantidad_actual': 'cantidad'}).fillna(0.0)\n",
                "\n",
                "print(unidades_almacenamiento_df.shape)\n",
                "unidades_almacenamiento_df.head()"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 10,
            "metadata": {},
            "outputs": [],
            "source": [
                "renamer = {x: int(x.strftime('%Y%m%d')) for x in data_plantas_df.drop(\n",
                "    columns=['planta', 'ingrediente', 'variable']).columns}\n",
                "data_plantas_df.rename(columns=renamer, inplace=True)"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 11,
            "metadata": {},
            "outputs": [
                {
                    "data": {
                        "text/html": [
                            "<div>\n",
                            "<style scoped>\n",
                            "    .dataframe tbody tr th:only-of-type {\n",
                            "        vertical-align: middle;\n",
                            "    }\n",
                            "\n",
                            "    .dataframe tbody tr th {\n",
                            "        vertical-align: top;\n",
                            "    }\n",
                            "\n",
                            "    .dataframe thead th {\n",
                            "        text-align: right;\n",
                            "    }\n",
                            "</style>\n",
                            "<table border=\"1\" class=\"dataframe\">\n",
                            "  <thead>\n",
                            "    <tr style=\"text-align: right;\">\n",
                            "      <th></th>\n",
                            "      <th>planta</th>\n",
                            "      <th>ingrediente</th>\n",
                            "      <th>variable</th>\n",
                            "      <th>20240421</th>\n",
                            "      <th>20240422</th>\n",
                            "      <th>20240423</th>\n",
                            "      <th>20240424</th>\n",
                            "      <th>20240425</th>\n",
                            "      <th>20240426</th>\n",
                            "      <th>20240427</th>\n",
                            "      <th>...</th>\n",
                            "      <th>20240513</th>\n",
                            "      <th>20240514</th>\n",
                            "      <th>20240515</th>\n",
                            "      <th>20240516</th>\n",
                            "      <th>20240517</th>\n",
                            "      <th>20240518</th>\n",
                            "      <th>20240519</th>\n",
                            "      <th>20240520</th>\n",
                            "      <th>20240521</th>\n",
                            "      <th>20240522</th>\n",
                            "    </tr>\n",
                            "  </thead>\n",
                            "  <tbody>\n",
                            "    <tr>\n",
                            "      <th>0</th>\n",
                            "      <td>barbosa</td>\n",
                            "      <td>cascarilla</td>\n",
                            "      <td>backorder</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>...</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "    </tr>\n",
                            "    <tr>\n",
                            "      <th>1</th>\n",
                            "      <td>barbosa</td>\n",
                            "      <td>cascarilla</td>\n",
                            "      <td>capacidad_max</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>68000.0</td>\n",
                            "      <td>68000.0</td>\n",
                            "      <td>68000.0</td>\n",
                            "      <td>68000.0</td>\n",
                            "      <td>68000.0</td>\n",
                            "      <td>68000.0</td>\n",
                            "      <td>...</td>\n",
                            "      <td>68000.0</td>\n",
                            "      <td>68000.0</td>\n",
                            "      <td>68000.0</td>\n",
                            "      <td>68000.0</td>\n",
                            "      <td>68000.0</td>\n",
                            "      <td>68000.0</td>\n",
                            "      <td>68000.0</td>\n",
                            "      <td>68000.0</td>\n",
                            "      <td>68000.0</td>\n",
                            "      <td>68000.0</td>\n",
                            "    </tr>\n",
                            "    <tr>\n",
                            "      <th>2</th>\n",
                            "      <td>barbosa</td>\n",
                            "      <td>cascarilla</td>\n",
                            "      <td>consumo</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>...</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "    </tr>\n",
                            "    <tr>\n",
                            "      <th>3</th>\n",
                            "      <td>barbosa</td>\n",
                            "      <td>cascarilla</td>\n",
                            "      <td>inventario</td>\n",
                            "      <td>1.0</td>\n",
                            "      <td>1.0</td>\n",
                            "      <td>1.0</td>\n",
                            "      <td>1.0</td>\n",
                            "      <td>1.0</td>\n",
                            "      <td>1.0</td>\n",
                            "      <td>1.0</td>\n",
                            "      <td>...</td>\n",
                            "      <td>1.0</td>\n",
                            "      <td>1.0</td>\n",
                            "      <td>1.0</td>\n",
                            "      <td>1.0</td>\n",
                            "      <td>1.0</td>\n",
                            "      <td>1.0</td>\n",
                            "      <td>1.0</td>\n",
                            "      <td>1.0</td>\n",
                            "      <td>1.0</td>\n",
                            "      <td>1.0</td>\n",
                            "    </tr>\n",
                            "    <tr>\n",
                            "      <th>4</th>\n",
                            "      <td>barbosa</td>\n",
                            "      <td>cascarilla</td>\n",
                            "      <td>safety_stock</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>...</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "    </tr>\n",
                            "  </tbody>\n",
                            "</table>\n",
                            "<p>5 rows × 35 columns</p>\n",
                            "</div>"
                        ],
                        "text/plain": [
                            "    planta ingrediente       variable  20240421  20240422  20240423  20240424  \\\n",
                            "0  barbosa  cascarilla      backorder       0.0       0.0       0.0       0.0   \n",
                            "1  barbosa  cascarilla  capacidad_max       0.0   68000.0   68000.0   68000.0   \n",
                            "2  barbosa  cascarilla        consumo       0.0       0.0       0.0       0.0   \n",
                            "3  barbosa  cascarilla     inventario       1.0       1.0       1.0       1.0   \n",
                            "4  barbosa  cascarilla   safety_stock       0.0       0.0       0.0       0.0   \n",
                            "\n",
                            "   20240425  20240426  20240427  ...  20240513  20240514  20240515  20240516  \\\n",
                            "0       0.0       0.0       0.0  ...       0.0       0.0       0.0       0.0   \n",
                            "1   68000.0   68000.0   68000.0  ...   68000.0   68000.0   68000.0   68000.0   \n",
                            "2       0.0       0.0       0.0  ...       0.0       0.0       0.0       0.0   \n",
                            "3       1.0       1.0       1.0  ...       1.0       1.0       1.0       1.0   \n",
                            "4       0.0       0.0       0.0  ...       0.0       0.0       0.0       0.0   \n",
                            "\n",
                            "   20240517  20240518  20240519  20240520  20240521  20240522  \n",
                            "0       0.0       0.0       0.0       0.0       0.0       0.0  \n",
                            "1   68000.0   68000.0   68000.0   68000.0   68000.0   68000.0  \n",
                            "2       0.0       0.0       0.0       0.0       0.0       0.0  \n",
                            "3       1.0       1.0       1.0       1.0       1.0       1.0  \n",
                            "4       0.0       0.0       0.0       0.0       0.0       0.0  \n",
                            "\n",
                            "[5 rows x 35 columns]"
                        ]
                    },
                    "execution_count": 11,
                    "metadata": {},
                    "output_type": "execute_result"
                }
            ],
            "source": [
                "data_plantas_df.head()"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 12,
            "metadata": {},
            "outputs": [
                {
                    "name": "stderr",
                    "output_type": "stream",
                    "text": [
                        "100%|██████████| 624/624 [00:07<00:00, 84.65it/s] \n"
                    ]
                }
            ],
            "source": [
                "# Llenar la informacion de los inventarios\n",
                "for i in tqdm(data_plantas_df.index):\n",
                "    planta = data_plantas_df.loc[i]['planta']\n",
                "    ingrediente = data_plantas_df.loc[i]['ingrediente']\n",
                "\n",
                "    inventarios = data_plantas_df[(data_plantas_df['planta'] == planta) & (\n",
                "        data_plantas_df['ingrediente'] == ingrediente) & (data_plantas_df['variable'] == 'inventario')]\n",
                "    consumo_df = data_plantas_df[(data_plantas_df['planta'] == planta) & (\n",
                "        data_plantas_df['ingrediente'] == ingrediente) & (data_plantas_df['variable'] == 'consumo')]\n",
                "    safety_stock = data_plantas_df[(data_plantas_df['planta'] == planta) & (\n",
                "        data_plantas_df['ingrediente'] == ingrediente) & (data_plantas_df['variable'] == 'safety_stock')]\n",
                "    capacidad_df = data_plantas_df[(data_plantas_df['planta'] == planta) & (\n",
                "        data_plantas_df['ingrediente'] == ingrediente) & (data_plantas_df['variable'] == 'capacidad_max')]\n",
                "    backorder_df = data_plantas_df[(data_plantas_df['planta'] == planta) & (\n",
                "        data_plantas_df['ingrediente'] == ingrediente) & (data_plantas_df['variable'] == 'backorder')]\n",
                "    cantidad_inicial = data_plantas_df.iloc[0][periodo_anterior]\n",
                "\n",
                "    if capacidad_df.shape[0] > 0:\n",
                "\n",
                "        if consumo_df.shape[0] > 0:\n",
                "            consumo_total = np.sum(consumo_df.drop(\n",
                "                columns=['planta', 'ingrediente', 'variable']).iloc[0])\n",
                "        else:\n",
                "            consumo_total = 0.0\n",
                "        # capacidad_almacenamiento = unidades_almacenamiento_df.loc[i]['capacidad']\n",
                "        # safety_stock_dias = unidades_almacenamiento_df.loc[i]['dias_ss']\n",
                "\n",
                "        if not 'inventarios' in plantas[planta].keys():\n",
                "            plantas[planta]['inventarios'] = dict()\n",
                "\n",
                "        if not ingrediente in plantas[planta]['inventarios'].keys():\n",
                "            plantas[planta]['inventarios'][ingrediente] = dict()\n",
                "\n",
                "        # if not 'capacidad' in plantas[planta]['inventarios'][ingrediente].keys():\n",
                "        #    plantas[planta]['inventarios'][ingrediente]['capacidad'] = capacidad_almacenamiento\n",
                "\n",
                "        if not 'inventario_final' in plantas[planta]['inventarios'][ingrediente].keys():\n",
                "            plantas[planta]['inventarios'][ingrediente]['inventario_final'] = dict()\n",
                "\n",
                "        if not 'llegadas' in plantas[planta]['inventarios'][ingrediente].keys():\n",
                "            plantas[planta]['inventarios'][ingrediente]['llegadas'] = dict()\n",
                "\n",
                "        if not 'consumo' in plantas[planta]['inventarios'][ingrediente].keys():\n",
                "            plantas[planta]['inventarios'][ingrediente]['consumo'] = dict()\n",
                "\n",
                "        if not 'backorder' in plantas[planta]['inventarios'][ingrediente].keys():\n",
                "            plantas[planta]['inventarios'][ingrediente]['backorder'] = dict()\n",
                "\n",
                "        if not 'safety_stock' in plantas[planta]['inventarios'][ingrediente].keys():\n",
                "            plantas[planta]['inventarios'][ingrediente]['safety_stock'] = dict()\n",
                "\n",
                "        if not 'exceso_capacidad' in plantas[planta]['inventarios'][ingrediente].keys():\n",
                "            plantas[planta]['inventarios'][ingrediente]['exceso_capacidad'] = dict()\n",
                "\n",
                "        plantas[planta]['inventarios'][ingrediente]['inventario_final'][periodo_anterior] = cantidad_inicial\n",
                "\n",
                "        if consumo_total > 0:\n",
                "\n",
                "            # safety_stock_dias\n",
                "            plantas[planta]['inventarios'][ingrediente]['safety_stock_dias'] = 0.0\n",
                "\n",
                "            # safety_stock_kg = consumo_total*safety_stock_dias/len(periodos)\n",
                "\n",
                "            for periodo in periodos:\n",
                "\n",
                "                if safety_stock.shape[0] > 0:\n",
                "                    plantas[planta]['inventarios'][ingrediente]['safety_stock_kg'] = safety_stock.iloc[0][periodo]\n",
                "                else:\n",
                "                    plantas[planta]['inventarios'][ingrediente]['safety_stock_kg'] = 0.0\n",
                "\n",
                "                # Obtener consumo\n",
                "                consumo = consumo_df.iloc[0][periodo]\n",
                "\n",
                "                # Maximo entre inventario proyectado y la capacidad\n",
                "                capacidad_maxima = capacidad_df.iloc[0][periodo]\n",
                "                inventario_proyectado = inventarios.iloc[0][periodo]\n",
                "                capacidad_almacenamiento = max(\n",
                "                    capacidad_maxima, inventario_proyectado)\n",
                "                # Agregar las variables de inventario\n",
                "                inventario_var_name = f'I_{planta}_{ingrediente}_{periodo}'\n",
                "                inventario_var = pu.LpVariable(\n",
                "                    name=inventario_var_name,\n",
                "                    lowBound=0.0,\n",
                "                    upBound=capacidad_almacenamiento, cat=pu.LpContinuous)\n",
                "                inventario_var.setInitialValue(inventario_proyectado)\n",
                "                plantas[planta]['inventarios'][ingrediente]['inventario_final'][periodo] = inventario_var\n",
                "\n",
                "                # Agregar las variables de exceso de inventario\n",
                "                # exceso_capacidad_var_name = f'M_{planta}_{ingrediente}_{periodo}'\n",
                "                # exceso_capacidad_var = pu.LpVariable(\n",
                "                #     name=exceso_capacidad_var_name, lowBound=0.0, cat=pu.LpContinuous)\n",
                "                # plantas[planta]['inventarios'][ingrediente]['exceso_capacidad'][periodo] = exceso_capacidad_var\n",
                "\n",
                "                # Agregar las listas a donde llegarán los transportes\n",
                "                plantas[planta]['inventarios'][ingrediente]['llegadas'][periodo] = list()\n",
                "\n",
                "                # Agregar las variables de backorder\n",
                "                backorder = backorder_df.iloc[0][periodo]\n",
                "                bak_var_name = f'B_{planta}_{ingrediente}_{periodo}'\n",
                "                bak_var = pu.LpVariable(\n",
                "                    name=bak_var_name, lowBound=0.0, upBound=consumo,  cat=pu.LpContinuous)\n",
                "                bak_var.setInitialValue(backorder)\n",
                "\n",
                "                plantas[planta]['inventarios'][ingrediente]['backorder'][periodo] = bak_var\n",
                "\n",
                "                # Agregar las variables de Safety Stock\n",
                "                if safety_stock.shape[0] > 0:\n",
                "                    safety_stock_kg = safety_stock.iloc[0][periodo]\n",
                "                    if capacidad_almacenamiento > safety_stock_kg + 2*cap_camion:\n",
                "                        ss_var_name = f'S_{planta}_{ingrediente}_{periodo}'\n",
                "                        ss_var = pu.LpVariable(\n",
                "                            name=ss_var_name, lowBound=0.0, upBound=safety_stock_kg, cat=pu.LpContinuous)\n",
                "                        plantas[planta]['inventarios'][ingrediente]['safety_stock'][periodo] = ss_var\n",
                "\n",
                "                # Agregar el consumo proyectado\n",
                "                plantas[planta]['inventarios'][ingrediente]['consumo'][periodo] = consumo\n",
                "        else:\n",
                "            for periodo in periodos:\n",
                "                # Dejar el inventario en el estado actual\n",
                "                plantas[planta]['inventarios'][ingrediente]['inventario_final'][periodo] = cantidad_inicial\n",
                "\n",
                "                # Agregar el consumo proyectado\n",
                "                plantas[planta]['inventarios'][ingrediente]['consumo'][periodo] = 0.0\n",
                "\n",
                "                # Agregar las variables de exceso de inventario\n",
                "                # exceso_capacidad_var_name = f'M_{planta}_{ingrediente}_{periodo}'\n",
                "                # exceso_capacidad_var = pu.LpVariable(\n",
                "                #     name=exceso_capacidad_var_name, lowBound=0.0, cat=pu.LpContinuous)\n",
                "                # plantas[planta]['inventarios'][ingrediente]['exceso_capacidad'][periodo] = exceso_capacidad_var"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 13,
            "metadata": {},
            "outputs": [],
            "source": [
                "# Llegar el objetivo de inventario al cierre\n",
                "\n",
                "for i in objetivo_df.index:\n",
                "    planta = objetivo_df.loc[i]['planta']\n",
                "    ingrediente = objetivo_df.loc[i]['ingrediente']\n",
                "    objetivo_dio = objetivo_df.loc[i]['objetivo_dio']\n",
                "    objetivo_kg = objetivo_df.loc[i]['objetivo_kg']\n",
                "    if ingrediente in plantas[planta]['inventarios'].keys():\n",
                "        plantas[planta]['inventarios'][ingrediente]['objetivo_dio'] = objetivo_dio\n",
                "        plantas[planta]['inventarios'][ingrediente]['objetivo_kg'] = objetivo_kg"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "#### Llegadas programadas anteriormente a Planta"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 14,
            "metadata": {},
            "outputs": [],
            "source": [
                "for i in transitos_planta_df.index:\n",
                "    planta = transitos_planta_df.loc[i]['planta']\n",
                "    ingrediente = transitos_planta_df.loc[i]['ingrediente']\n",
                "    cantidad = transitos_planta_df.loc[i]['cantidad']\n",
                "    fecha = transitos_planta_df.loc[i]['fecha_llegada']\n",
                "    periodo = int(fecha.strftime('%Y%m%d'))\n",
                "    plantas[planta]['inventarios'][ingrediente]['llegadas'][periodo].append(\n",
                "        0.0)"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### Cargas en Puerto"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 15,
            "metadata": {},
            "outputs": [
                {
                    "data": {
                        "text/html": [
                            "<div>\n",
                            "<style scoped>\n",
                            "    .dataframe tbody tr th:only-of-type {\n",
                            "        vertical-align: middle;\n",
                            "    }\n",
                            "\n",
                            "    .dataframe tbody tr th {\n",
                            "        vertical-align: top;\n",
                            "    }\n",
                            "\n",
                            "    .dataframe thead th {\n",
                            "        text-align: right;\n",
                            "    }\n",
                            "</style>\n",
                            "<table border=\"1\" class=\"dataframe\">\n",
                            "  <thead>\n",
                            "    <tr style=\"text-align: right;\">\n",
                            "      <th></th>\n",
                            "      <th>planta</th>\n",
                            "      <th>ingrediente</th>\n",
                            "      <th>cantidad</th>\n",
                            "      <th>fecha_llegada</th>\n",
                            "    </tr>\n",
                            "  </thead>\n",
                            "  <tbody>\n",
                            "    <tr>\n",
                            "      <th>2</th>\n",
                            "      <td>envigado</td>\n",
                            "      <td>tgirasol</td>\n",
                            "      <td>66520.0</td>\n",
                            "      <td>2024-04-22</td>\n",
                            "    </tr>\n",
                            "    <tr>\n",
                            "      <th>4</th>\n",
                            "      <td>neiva</td>\n",
                            "      <td>tgirasol</td>\n",
                            "      <td>169980.0</td>\n",
                            "      <td>2024-04-25</td>\n",
                            "    </tr>\n",
                            "    <tr>\n",
                            "      <th>7</th>\n",
                            "      <td>buga</td>\n",
                            "      <td>tgirasol</td>\n",
                            "      <td>161280.0</td>\n",
                            "      <td>2024-04-22</td>\n",
                            "    </tr>\n",
                            "  </tbody>\n",
                            "</table>\n",
                            "</div>"
                        ],
                        "text/plain": [
                            "     planta ingrediente  cantidad fecha_llegada\n",
                            "2  envigado    tgirasol   66520.0    2024-04-22\n",
                            "4     neiva    tgirasol  169980.0    2024-04-25\n",
                            "7      buga    tgirasol  161280.0    2024-04-22"
                        ]
                    },
                    "execution_count": 15,
                    "metadata": {},
                    "output_type": "execute_result"
                }
            ],
            "source": [
                "transitos_planta_df[transitos_planta_df['ingrediente'] == 'tgirasol']"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {
                "jp-MarkdownHeadingCollapsed": true
            },
            "source": [
                "#### Crear cargas a partir de información de los transitos"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 16,
            "metadata": {},
            "outputs": [],
            "source": [
                "# Generar Cargas\n",
                "cargas = dict()\n",
                "\n",
                "# A partir de los transitos\n",
                "for i in transitos_puerto_df.index:\n",
                "    importacion = str(\n",
                "        transitos_puerto_df.loc[i]['importacion']).replace(' ', '')\n",
                "    empresa = transitos_puerto_df.loc[i]['empresa']\n",
                "    operador = transitos_puerto_df.loc[i]['operador']\n",
                "    puerto = transitos_puerto_df.loc[i]['puerto']\n",
                "    ingrediente = transitos_puerto_df.loc[i]['ingrediente']\n",
                "    cantidad_kg = transitos_puerto_df.loc[i]['cantidad_kg']\n",
                "    valor_cif = transitos_puerto_df.loc[i]['valor_kg']\n",
                "    fecha = transitos_puerto_df.loc[i]['fecha_llegada']\n",
                "    if not importacion in cargas.keys():\n",
                "        cargas[importacion] = dict()\n",
                "\n",
                "    cargas[importacion]['empresa'] = empresa\n",
                "    cargas[importacion]['operador'] = operador\n",
                "    cargas[importacion]['puerto'] = puerto\n",
                "    cargas[importacion]['ingrediente'] = ingrediente\n",
                "    cargas[importacion]['valor_cif'] = valor_cif\n",
                "    cargas[importacion]['inventario_inicial'] = 0\n",
                "    cargas[importacion]['costo_almacenamiento'] = {\n",
                "        int(t.strftime('%Y%m%d')): 0 for t in fechas}\n",
                "    cargas[importacion]['llegadas'] = dict()\n",
                "    cargas[importacion]['fecha_inicial'] = int(fecha.strftime('%Y%m%d'))\n",
                "\n",
                "    # Poner llegadas de materia\n",
                "    while cantidad_kg > cap_descarge:\n",
                "        cargas[importacion]['llegadas'][int(\n",
                "            fecha.strftime('%Y%m%d'))] = cap_descarge\n",
                "        cantidad_kg -= cap_descarge\n",
                "        fecha = fecha + timedelta(days=1)\n",
                "\n",
                "    if cantidad_kg > 0:\n",
                "        cargas[importacion]['llegadas'][int(\n",
                "            fecha.strftime('%Y%m%d'))] = cantidad_kg\n",
                "    cargas[importacion]['fecha_final'] = int(fecha.strftime('%Y%m%d'))\n",
                "\n",
                "    # Agregar las variables de inventario\n",
                "    cargas[importacion]['inventario_al_final'] = dict()\n",
                "    for t in periodos:\n",
                "        var_name = f\"O_{importacion}_{t}\"\n",
                "        lp_var = pu.LpVariable(name=var_name,\n",
                "                               lowBound=0.0,\n",
                "                               upBound=transitos_puerto_df.loc[i]['cantidad_kg'],\n",
                "                               cat=pu.LpContinuous)\n",
                "        cargas[importacion]['inventario_al_final'][t] = lp_var"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "#### Crear cargas a partir de inventarios en puerto"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 17,
            "metadata": {},
            "outputs": [],
            "source": [
                "\n",
                "# A Partir de los inventarios en puerto\n",
                "for i in inventario_puerto_df.index:\n",
                "    empresa = inventario_puerto_df.loc[i]['empresa']\n",
                "    operador = inventario_puerto_df.loc[i]['operador']\n",
                "    puerto = inventario_puerto_df.loc[i]['puerto']\n",
                "    ingrediente = inventario_puerto_df.loc[i]['ingrediente']\n",
                "    importacion = str(\n",
                "        inventario_puerto_df.loc[i]['importacion']).replace(' ', '')\n",
                "    inventario_inicial = inventario_puerto_df.loc[i]['cantidad_kg']\n",
                "    valor_cif = inventario_puerto_df.loc[i]['valor_cif_kg']\n",
                "    fecha = inventario_puerto_df.loc[i]['fecha_llegada']\n",
                "\n",
                "    if not importacion in cargas.keys():\n",
                "        cargas[importacion] = dict()\n",
                "\n",
                "    cargas[importacion]['empresa'] = empresa\n",
                "    cargas[importacion]['operador'] = operador\n",
                "    cargas[importacion]['puerto'] = puerto\n",
                "    cargas[importacion]['ingrediente'] = ingrediente\n",
                "    cargas[importacion]['valor_cif'] = valor_cif\n",
                "    cargas[importacion]['inventario_inicial'] = inventario_inicial\n",
                "    cargas[importacion]['costo_almacenamiento'] = {\n",
                "        int(t.strftime('%Y%m%d')): 0 for t in fechas}\n",
                "\n",
                "    # Poner llegadas de materia\n",
                "    cargas[importacion]['llegadas'] = {t.strftime('%Y%m%d'): 0 for t in fechas}\n",
                "\n",
                "    cargas[importacion]['fecha_inicial'] = int(fecha.strftime('%Y%m%d'))\n",
                "    cargas[importacion]['fecha_final'] = int(fecha.strftime('%Y%m%d'))\n",
                "    # Agregar las variables de inventario\n",
                "    cargas[importacion]['inventario_al_final'] = dict()\n",
                "\n",
                "    for t in periodos:\n",
                "\n",
                "        var_name = f\"O_{importacion}_{t}\"\n",
                "        lp_var = pu.LpVariable(name=var_name,\n",
                "                               lowBound=0.0,\n",
                "                               upBound=inventario_puerto_df.loc[i]['cantidad_kg'],\n",
                "                               cat=pu.LpContinuous)\n",
                "        cargas[importacion]['inventario_al_final'][t] = lp_var"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "#### Costos de almacenamiento"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 18,
            "metadata": {},
            "outputs": [],
            "source": [
                "# Agregar costos de almacenamiento a cada carga\n",
                "for i in costos_almacenamiento_df.index:\n",
                "    importacion = str(\n",
                "        costos_almacenamiento_df.loc[i]['importacion']).replace(' ', '')\n",
                "    fecha = int(\n",
                "        costos_almacenamiento_df.loc[i]['fecha_corte'].strftime('%Y%m%d'))\n",
                "    valor_kg = costos_almacenamiento_df.loc[i]['valor_kg']\n",
                "\n",
                "    if importacion in cargas.keys():\n",
                "        if fecha in cargas[importacion]['costo_almacenamiento']:\n",
                "            cargas[importacion]['costo_almacenamiento'][fecha] += valor_kg"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "#### Costos de Bodegaje"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 19,
            "metadata": {},
            "outputs": [],
            "source": [
                "# Agregar costos de bodegaje cuando es un producto en tránsito a puerto a cada carga\n",
                "for importacion, carga in cargas.items():\n",
                "    index = ('bodega', carga['operador'],\n",
                "             carga['puerto'], carga['ingrediente'])\n",
                "    valor_kg = operaciones_portuarias_df.loc[index]['valor_kg']\n",
                "    if carga['fecha_inicial'] >= int(fechas[0].strftime('%Y%m%d')) and carga['fecha_final'] <= int(fechas[-1].strftime('%Y%m%d')):\n",
                "        carga['costo_almacenamiento'][carga['fecha_final']] += valor_kg"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "#### Costos intercompany"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 20,
            "metadata": {},
            "outputs": [],
            "source": [
                "intercompany_df = intercompany_df.melt(id_vars='origen',\n",
                "                                       value_vars=['contegral', 'finca'],\n",
                "                                       var_name='destino',\n",
                "                                       value_name='intercompany')\n",
                "\n",
                "intercompany_df.set_index(['origen', 'destino'], inplace=True)"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "#### Costos de transporte (fletes)"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 21,
            "metadata": {},
            "outputs": [],
            "source": [
                "# Encontrar el costo total de transporte por kilogramo\n",
                "fletes_df = fletes_df.melt(id_vars=['puerto', 'operador', 'ingrediente'],\n",
                "                           value_vars=list(plantas.keys()),\n",
                "                           value_name='costo_per_kg',\n",
                "                           var_name='planta')\n",
                "\n",
                "# Calcular valor del flete\n",
                "fletes_df['flete'] = cap_camion*fletes_df['costo_per_kg']\n",
                "\n",
                "fletes_df = pd.merge(left=fletes_df,\n",
                "                     right=plantas_df[['planta', 'empresa']],\n",
                "                     left_on='planta',\n",
                "                     right_on='planta')\n",
                "\n",
                "fletes_df.set_index(\n",
                "    ['puerto', 'operador', 'ingrediente', 'planta'], inplace=True)"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "#### Variables de Despacho"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 22,
            "metadata": {},
            "outputs": [
                {
                    "name": "stdout",
                    "output_type": "stream",
                    "text": [
                        "despachos entre 20240423 y 20240521\n"
                    ]
                }
            ],
            "source": [
                "# Tomar en cuenta solo los periodos relevantes\n",
                "periodo_final = periodos.index(periodos[-1])-lead_time+1\n",
                "\n",
                "print('despachos entre',\n",
                "      periodos[periodo_administrativo], 'y', periodos[periodo_final])\n",
                "# Informacion de transporte\n",
                "for importacion, carga in cargas.items():\n",
                "    puerto = carga['puerto']\n",
                "    operador = carga['operador']\n",
                "    ingrediente = carga['ingrediente']\n",
                "    costo_envio = dict()\n",
                "\n",
                "    for nombre_planta, planta in plantas.items():\n",
                "        empresa_destino = planta['empresa']\n",
                "        costo_intercompany = intercompany_df.loc[(\n",
                "            carga['empresa'], empresa_destino)]['intercompany']\n",
                "        valor_intercompany = cap_camion*carga['valor_cif']*(costo_intercompany)\n",
                "        flete = fletes_df.loc[(\n",
                "            puerto, operador, ingrediente, nombre_planta)]['flete']\n",
                "        valor_despacho_directo_kg = cap_camion * \\\n",
                "            operaciones_portuarias_df.loc[(\n",
                "                'directo', operador, puerto, ingrediente)]['valor_kg']\n",
                "\n",
                "        periodo_llegada = carga['fecha_inicial']\n",
                "\n",
                "        # Costo de flete\n",
                "        costo_envio[nombre_planta] = dict()\n",
                "        costo_envio[nombre_planta]['intercompany'] = costo_intercompany\n",
                "        costo_envio[nombre_planta]['flete'] = flete\n",
                "        costo_envio[nombre_planta]['cantidad_despacho'] = cap_camion\n",
                "        costo_envio[nombre_planta]['valor_intercompany'] = valor_intercompany\n",
                "        costo_envio[nombre_planta]['costo_despacho_directo'] = valor_despacho_directo_kg\n",
                "\n",
                "        costo_envio[nombre_planta]['costo_envio'] = dict()\n",
                "        costo_envio[nombre_planta]['tipo_envio'] = dict()\n",
                "        costo_envio[nombre_planta]['variable_despacho'] = dict()\n",
                "\n",
                "        # Descuento de almacenamiento en puerto\n",
                "        costo_envio[nombre_planta]['descuento_almacenamiento'] = dict()\n",
                "        costo_descuento_almacenamiento = 0.0\n",
                "        for periodo in periodos[::-1]:\n",
                "            if carga['costo_almacenamiento'][periodo] != 0.0:\n",
                "                costo_descuento_almacenamiento = carga['costo_almacenamiento'][periodo]\n",
                "            costo_envio[nombre_planta]['descuento_almacenamiento'][periodo] = costo_descuento_almacenamiento\n",
                "\n",
                "        # Calcular costo de envio\n",
                "        for periodo in periodos[periodo_administrativo:periodo_final]:\n",
                "            # Si el periodo esta entre la fecha de llegada, colocar operacion portuaria por despacho directo.\n",
                "            if periodo >= carga['fecha_inicial'] and periodo <= carga['fecha_final']:\n",
                "                costo_envio[nombre_planta]['costo_envio'][periodo] = valor_intercompany + \\\n",
                "                    flete + valor_despacho_directo_kg\n",
                "                costo_envio[nombre_planta]['tipo_envio'][periodo] = 'directo'\n",
                "\n",
                "            else:\n",
                "                costo_envio[nombre_planta]['costo_envio'][periodo] = valor_intercompany + flete\n",
                "                costo_envio[nombre_planta]['tipo_envio'][periodo] = 'indirecto'\n",
                "\n",
                "            # Variable de transporte\n",
                "\n",
                "            # Antes de crear las variables de transporte, es importante saber si la planta tiene consumo del ingrediente\n",
                "            if ingrediente in planta['inventarios'].keys():\n",
                "\n",
                "                consumo_total = sum(\n",
                "                    [c for p, c in planta['inventarios'][ingrediente]['consumo'].items()])\n",
                "\n",
                "                # Máxima capacidad de recepcion como límite superior para la variable\n",
                "                tiempo_total = planta['tiempo_total']\n",
                "                tiempo_ingrediente_por_camion = planta['tiempo_ingrediente'][ingrediente]\n",
                "\n",
                "                # máxima capacidad de recepcion\n",
                "                cantidad_camiones_admisibles = int(\n",
                "                    tiempo_total/tiempo_ingrediente_por_camion)\n",
                "\n",
                "                # Cantidad de llegadas\n",
                "                Llegadas = sum([v for p, v in carga['llegadas'].items()])\n",
                "\n",
                "                # Inventario inicial\n",
                "                inventario_inicial = carga['inventario_inicial']\n",
                "\n",
                "                # cuántos camiones se podrían despachar con el inventario existente más las llegadas:\n",
                "                if inventario_inicial + Llegadas > cap_camion:\n",
                "                    cantidad_camiones_despachables = int(\n",
                "                        (inventario_inicial + Llegadas)/cap_camion)\n",
                "                else:\n",
                "                    cantidad_camiones_despachables = 0\n",
                "\n",
                "                limite_superior_despacho = min(\n",
                "                    cantidad_camiones_admisibles, cantidad_camiones_despachables)\n",
                "\n",
                "                # if consumo_total > 0 y el periodo actual es mayor al de llegada\n",
                "                # (No tiene sentido agregar variable de desapcho si no hay qué despachar):\n",
                "                if consumo_total > cap_camion and periodo >= periodo_llegada and limite_superior_despacho > 0 == 0:\n",
                "\n",
                "                    transporte_var_name = f'T_{importacion}_{nombre_planta}_{periodo}'\n",
                "                    transporte_var = pu.LpVariable(name=transporte_var_name,\n",
                "                                                   lowBound=0,\n",
                "                                                   upBound=limite_superior_despacho,\n",
                "                                                   cat=pu.LpInteger)\n",
                "\n",
                "                    costo_envio[nombre_planta]['variable_despacho'][periodo] = transporte_var\n",
                "\n",
                "                    # Colocar la variable en la planta dos periodos despues\n",
                "                    periodo_llegada_a_planta = periodos[periodos.index(\n",
                "                        periodo)+lead_time]\n",
                "                    plantas[nombre_planta]['inventarios'][ingrediente]['llegadas'][periodo_llegada_a_planta].append(\n",
                "                        transporte_var)\n",
                "\n",
                "        carga['costo_despacho'] = costo_envio"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 23,
            "metadata": {},
            "outputs": [
                {
                    "name": "stdout",
                    "output_type": "stream",
                    "text": [
                        "28897\n"
                    ]
                }
            ],
            "source": [
                "var_count = 0\n",
                "for carga in cargas.keys():\n",
                "    for planta in cargas[carga]['costo_despacho'].keys():\n",
                "        var_count += len(cargas[carga]['costo_despacho']\n",
                "                         [planta]['variable_despacho'].values())\n",
                "print(var_count)\n",
                "# Actualmente 16902 variables con consumos completos"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 24,
            "metadata": {},
            "outputs": [],
            "source": [
                "clusters_dict = {\n",
                "    'importacion': list(),\n",
                "    'puerto': list(),\n",
                "    'ingrediente': list(),\n",
                "    'planta': list(),\n",
                "    'periodo': list(),\n",
                "    'costo_almacenamiento': list(),\n",
                "    'costo_despacho': list()\n",
                "}"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Cluster de Cargas"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 25,
            "metadata": {},
            "outputs": [],
            "source": [
                "for importacion in cargas.keys():\n",
                "    for planta in plantas.keys():\n",
                "        if planta in cargas[importacion]['costo_despacho'].keys():\n",
                "            for periodo in periodos:\n",
                "                if periodo in cargas[importacion]['costo_despacho'][planta]['costo_envio'].keys():\n",
                "\n",
                "                    costo_despacho = cargas[importacion]['costo_despacho'][planta]['costo_envio'][periodo]\n",
                "                    costo_almacenamiento = cargas[importacion]['costo_almacenamiento'][periodo]\n",
                "                    ingrediente = cargas[importacion]['ingrediente']\n",
                "                    puerto = cargas[importacion]['puerto']\n",
                "\n",
                "                    clusters_dict['importacion'].append(importacion)\n",
                "                    clusters_dict['puerto'].append(puerto)\n",
                "                    clusters_dict['ingrediente'].append(ingrediente)\n",
                "                    clusters_dict['planta'].append(planta)\n",
                "                    clusters_dict['periodo'].append(periodo)\n",
                "                    clusters_dict['costo_almacenamiento'].append(\n",
                "                        costo_almacenamiento)\n",
                "                    clusters_dict['costo_despacho'].append(costo_despacho)\n",
                "clusters_df = pd.DataFrame(clusters_dict)"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 26,
            "metadata": {},
            "outputs": [],
            "source": [
                "def asignar_etiquetas(df: pd.DataFrame, column_name: str, n_clusters=3):\n",
                "    # Copiamos el DataFrame para no modificar el original\n",
                "    df_resultado = df.copy()\n",
                "\n",
                "    # Instanciar el modelo KMeans\n",
                "    kmeans = KMeans(n_clusters=3,\n",
                "                    init='random',\n",
                "                    n_init=10,\n",
                "                    max_iter=300,\n",
                "                    random_state=0)\n",
                "\n",
                "    # Ajustar el modelo a los datos\n",
                "    kmeans.fit(np.array(df[column_name]).reshape(-1, 1))\n",
                "\n",
                "    # Obtener las etiquetas de los clusters\n",
                "    labels = kmeans.labels_\n",
                "\n",
                "    # Agregar las etiquetas al DataFrame\n",
                "    df_resultado['cluster'] = labels\n",
                "\n",
                "    # Calcular los centroides\n",
                "    centroids = kmeans.cluster_centers_\n",
                "\n",
                "    # Calcular los límites de los clusters\n",
                "    limits = [df[labels == i].describe() for i in range(n_clusters)]\n",
                "\n",
                "    # Asignar etiquetas de 'alto', 'medio' y 'bajo'\n",
                "    for i in range(n_clusters):\n",
                "        df_resultado.loc[df_resultado['cluster'] == i, 'etiqueta'] = (\n",
                "            'alto' if centroids[i] == max(centroids) else\n",
                "            'bajo' if centroids[i] == min(centroids) else\n",
                "            'medio'\n",
                "        )\n",
                "\n",
                "    return df_resultado"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 27,
            "metadata": {},
            "outputs": [],
            "source": [
                "importaciones_list = list()\n",
                "for importacion in cargas.keys():\n",
                "\n",
                "    df = clusters_df[clusters_df['importacion'] == importacion]\n",
                "\n",
                "    cantidad_valores_unicos = len(df['costo_despacho'].unique())\n",
                "\n",
                "    temp = asignar_etiquetas(df=df, column_name='costo_despacho')\n",
                "\n",
                "    importaciones_list.append(temp)\n",
                "\n",
                "# Unir los Datasets\n",
                "clusters_df = pd.concat(importaciones_list)\n",
                "\n",
                "# Crear indices\n",
                "clusters_df.set_index(['importacion', 'planta', 'periodo'], inplace=True)"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "# Inicializacion de variables"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 28,
            "metadata": {},
            "outputs": [],
            "source": [
                "for importacion, carga in cargas.items():\n",
                "    for planta in plantas.keys():\n",
                "        if planta in carga['costo_despacho'].keys():\n",
                "            for periodo, variable in carga['costo_despacho'][planta]['variable_despacho'].items():\n",
                "                variable.setInitialValue(0)"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 29,
            "metadata": {},
            "outputs": [],
            "source": [
                "for importacion, carga in cargas.items():\n",
                "    inventario_final = carga['inventario_inicial']\n",
                "    llegadas = 0.0\n",
                "    for periodo in periodos:\n",
                "        llegadas = 0.0\n",
                "        if periodo in carga['llegadas'].keys():\n",
                "            llegadas = carga['llegadas'][periodo]\n",
                "        inventario_final += llegadas\n",
                "\n",
                "        carga['inventario_al_final'][periodo].setInitialValue(inventario_final)"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "# Modelo matemático"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Sets:\n",
                "\n",
                "$t$: periodos con $t \\in T$\n",
                "\n",
                "$p$: productos con $p \\in P$\n",
                "\n",
                "$i$: cargas con $i \\in T$\n",
                "\n",
                "$j$: plantas con $j \\in J$"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "\n",
                "## Parametros:\n",
                "\n",
                "$CB:$ Costo de backorder por día\n",
                "\n",
                "$CT_{ij}$: Costo de transportar la carga $i$ hacia la planta $j$\n",
                "\n",
                "$CA_{it}$: Costo de mantener la carga $i$ almacenada al final del periodo $p$\n",
                "\n",
                "$AR_{it}$: Cantidad de producto llegando a la carga $i$ durante el periodo $p$\n",
                "\n",
                "$DM_{pjt}$: Demanda del producto $p$ en la planta $j$ durante el periodo $t$\n",
                "\n",
                "$CP_{pjt}$: Capacidad de almacenar el producto $p$ en la planta $j$\n",
                "\n",
                "$IP_{i}$: Inventario inicial de la carga $i$\n",
                "\n",
                "$TJ_{pjt}$: Cantidad programada del producto $p$ llegando a la planta $j$ durante el periodo $t$ \n",
                "\n",
                "$IJ_{pj}$: Inventario inicial de producto $p$ en la planta $j$ \n",
                "\n",
                "$MI_{pjt}$: Inventario mínimo a mantener del producto $p$ en la planta $j$ al final del periodo $t$\n",
                "\n",
                "$MX_{pjt}$: Inventario máximo a mantener del producto $p$ en la planta $j$ al final del periodo $t$\n"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "\n",
                "## Variables:\n",
                "\n",
                "$T_{ijt}$: Variable entera, Cantidad de camiones de 34 Toneladas a despachar de la carga $i$ hasta la planta $j$ durante el periodo $t$\n",
                "\n",
                "$O_{it}$: Continua, Cantidad de toneladas de la carga $i$ almacenadas al final del periodo $t$\n",
                "\n",
                "$I_{pjt}$: Cantidad del producto $p$ almacenado en la planta $j$ al final del periodo $t$\n",
                "\n",
                "$B_{pjt}$: Cantidad del producto $p$ de backorder en la planta $j$ al final del periodo $t$\n",
                "\n",
                "$S_{pjt}$: Cantidad del producto $p$ por debajo del SS en la planta $j$ al final del periodo $t$\n",
                "\n",
                "$M_{pjt}$: Unidades de exceso del producto $p$ en la planta $j$ al final del periodo $t$ sobre el inventario objetivo\n",
                "\n",
                "$X_{pjt}$: Unidades por debajo del producto $p$ en la planta $j$ al final del periodo $t$ bajo el inventario objetivo\n"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "\n",
                "## Funcion Objetivo:\n",
                "\n",
                "$$min \\sum_{i}\\sum_{j}\\sum_{t}{CT_{ijt}*T_{ijt}} + \\sum_{i}\\sum_{t}CA_{it}O_{it} + \\sum_{pjt}{CB*B}  + PP \\sum_{M}\\sum_{P}\\sum_{J}{M_{mpj}} + PP \\sum_{M}\\sum_{P}\\sum_{J}{X_{mpj}}$$"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 30,
            "metadata": {},
            "outputs": [],
            "source": [
                "funcion_objetivo = list()"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### Costo por transporte\n",
                "\n",
                "El costo del transporte esta dado por el producto escalar entre los costos de envio, que ya incluyen fletes, costos porturarios y costos intercompany\n",
                "\n",
                "$$\\sum_{i}\\sum_{j}\\sum_{t}{CT_{ijt}*T_{ijt}}$$"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 31,
            "metadata": {},
            "outputs": [],
            "source": [
                "for periodo in periodos:\n",
                "    for impo, carga in cargas.items():\n",
                "        for nombre_planta, planta in plantas.items():\n",
                "            if periodo in carga['costo_despacho'][nombre_planta]['variable_despacho'].keys():\n",
                "                # CT_ijt*T_ijt\n",
                "                # + periodos.index(periodo)\n",
                "                costo_envio = carga['costo_despacho'][nombre_planta]['costo_envio'][periodo]\n",
                "                costo_almacenamiento = carga['costo_despacho']['envigado']['descuento_almacenamiento'][periodo]*cap_camion\n",
                "                var_envio = carga['costo_despacho'][nombre_planta]['variable_despacho'][periodo]\n",
                "                funcion_objetivo.append(\n",
                "                    (costo_envio-costo_almacenamiento)*var_envio)"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### Costo por almacenamiento en puerto (Se ha incluido como descuento en el costo de transporte)\n",
                "\n",
                "El costo por almacenamiento esta dado por el producto escalar entre los costos de almacenamiento que incluyen el costo el costo de operacion portuaria de llevar el material desde el barco hasta la bodega y, la tarifa por almacenamiento que se paga periódicamente luego de los días libres. \n",
                "\n",
                "*Sin embargo, cada vez que se envia un camion hacia cualquier planta, es un camion de producto menos que se cuenta como costo de almacenamiento, por lo que ya no es necesario incluir el costo de almacenamiento en la función objetivo.*\n",
                "\n",
                "$$\\sum_{i}\\sum_{t}CA_{it}O_{it}$$"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "for periodo in periodos:\n",
                "    for impo, carga in cargas.items():\n",
                "        costo_almaenamiento = carga['costo_almacenamiento'][periodo]\n",
                "        inventario_al_final = carga['inventario_al_final'][periodo]\n",
                "        if costo_almaenamiento > 0:\n",
                "            funcion_objetivo.append(costo_almaenamiento*inventario_al_final)\n",
                "        # else:\n",
                "        #    funcion_objetivo.append(0.5*inventario_al_final)"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### Costo de Backorder\n",
                "\n",
                "El costo por backorder es una penalización a la función objetivo, donde se carga un valor determinado por cada kilogramo de material que no esté disponible para el consumo\n",
                "\n",
                "$\\sum_{pjt}{CB*B}$"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 32,
            "metadata": {},
            "outputs": [],
            "source": [
                "for nombre_planta, planta in plantas.items():\n",
                "    for nombre_ingrediente, ingrediente in planta['inventarios'].items():\n",
                "        for periodo, var in ingrediente['backorder'].items():\n",
                "            # if periodo in periodos[periodo_administrativo:]:\n",
                "            funcion_objetivo.append(costo_backorder_dia*var)"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {
                "jp-MarkdownHeadingCollapsed": true
            },
            "source": [
                "### Costo por no alcanzar el inventario de seguridad"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 33,
            "metadata": {},
            "outputs": [],
            "source": [
                "for nombre_planta, planta in plantas.items():\n",
                "    for nombre_ingrediente, ingrediente in planta['inventarios'].items():\n",
                "        if 'safety_stock' in planta['inventarios'][nombre_ingrediente].keys():\n",
                "            for periodo, var in ingrediente['safety_stock'].items():\n",
                "                # if periodo in periodos[periodo_administrativo:]:\n",
                "                funcion_objetivo.append(costo_safety_stock*var)"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### Costo por exceder capacidad de almacenamiento"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "for nombre_planta, planta in plantas.items():\n",
                "    for nombre_ingrediente, ingrediente in planta['inventarios'].items():\n",
                "        for periodo, var in ingrediente['exceso_capacidad'].items():\n",
                "            if periodo in periodos[periodo_administrativo:]:\n",
                "                funcion_objetivo.append(costo_exceso_capacidad*var)"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Restricciones:"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "\n",
                "### Balance de masa en cargas\n",
                "\n",
                "El inventario al final del periodo es igual a:\n",
                "\n",
                "- el inventario al final del periodo anterior;\n",
                "- más las llegadas planeadas;\n",
                "- menos los despachos hacia plantas\n",
                "\n",
                "$$ O_{it} =  O_{i(t-1)} + AR_{it} - 34000\\sum_{J}{T_{ijt}} \\hspace{1cm} \\forall i \\in I, t \\in T$$"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 34,
            "metadata": {},
            "outputs": [],
            "source": [
                "rest_balance_masa_puerto = list()\n",
                "\n",
                "for importacion, carga in cargas.items():\n",
                "    for periodo in periodos:\n",
                "\n",
                "        left = list()\n",
                "        right = list()\n",
                "\n",
                "        # Oit\n",
                "        Oit = carga['inventario_al_final'][periodo]\n",
                "        left.append(Oit)\n",
                "\n",
                "        # Oi(t-1)\n",
                "        if periodo == periodos[0]:\n",
                "            Oitant = carga['inventario_inicial']\n",
                "        else:\n",
                "            t_anterior = periodos[periodos.index(periodo)-1]\n",
                "            Oitant = carga['inventario_al_final'][t_anterior]\n",
                "        right.append(Oitant)\n",
                "\n",
                "        # ARit\n",
                "        if periodo in carga['llegadas'].keys():\n",
                "            ar = carga['llegadas'][periodo]\n",
                "            right.append(ar)\n",
                "\n",
                "        # - 34000*Sum(Tijt)\n",
                "        for planta, despacho in carga['costo_despacho'].items():\n",
                "            if periodo in despacho['variable_despacho'].keys():\n",
                "                var_despacho = despacho['variable_despacho'][periodo]\n",
                "                left.append(cap_camion*var_despacho)\n",
                "\n",
                "        name = f'balance_masa_{importacion}_al_final_de_{periodo}'\n",
                "        rest = (pu.lpSum(left) == pu.lpSum(right), name)\n",
                "\n",
                "        rest_balance_masa_puerto.append(rest)"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### Balance de masa en plantas\n",
                "\n",
                "El inventario en planta al final del periodo es igual a:\n",
                "\n",
                "- el inventario al final del periodo anterior;\n",
                "- más las llegadas ya programadas;\n",
                "- más las llegadas planeadas;\n",
                "- menos la demanda\n",
                "- más el backorder, que compensa cuando el inventario más las llegadas no son suficientes\n",
                "\n",
                "$$ I_{pjt} = I_{pj(t-1)} + TJ_{pjt} + \\sum_{i}{T_{ij(t-2)}} -  DM_{pjt} + B_{pjt} \\hspace{1cm} \\forall p \\in P, j \\in J, t \\in T$$\n"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 35,
            "metadata": {},
            "outputs": [],
            "source": [
                "rest_balance_masa_planta = list()\n",
                "for nombre_planta, planta in plantas.items():\n",
                "    for nombre_ingrediente, ingrediente in planta['inventarios'].items():\n",
                "\n",
                "        for periodo in periodos:\n",
                "\n",
                "            if periodo in ingrediente['inventario_final'].keys():\n",
                "\n",
                "                left = list()\n",
                "                right = list()\n",
                "\n",
                "                # Ipjt\n",
                "                Spjt = ingrediente['inventario_final'][periodo]\n",
                "                left.append(Spjt)\n",
                "\n",
                "                # Ipj(t-1)\n",
                "                if periodo == periodos[0]:\n",
                "                    Ipj_tanterior = ingrediente['inventario_final'][periodo_anterior]\n",
                "                else:\n",
                "                    p_anterior = periodos[periodos.index(periodo)-1]\n",
                "                    Ipj_tanterior = ingrediente['inventario_final'][p_anterior]\n",
                "\n",
                "                right.append(Ipj_tanterior)\n",
                "\n",
                "                # + TJ\n",
                "\n",
                "                # + Tijt\n",
                "                if periodo in ingrediente['llegadas'].keys():\n",
                "                    for llegada_planeada_var in ingrediente['llegadas'][periodo]:\n",
                "                        if type(llegada_planeada_var) == pu.LpVariable:\n",
                "                            right.append(cap_camion*llegada_planeada_var)\n",
                "                        else:\n",
                "                            right.append(llegada_planeada_var)\n",
                "\n",
                "                # - DMpjt\n",
                "\n",
                "                if periodo in ingrediente['consumo'].keys():\n",
                "                    DMpjt = ingrediente['consumo'][periodo]\n",
                "                    left.append(DMpjt)\n",
                "\n",
                "                # + Baclorder\n",
                "                if periodo in ingrediente['backorder'].keys():\n",
                "                    bak_var = ingrediente['backorder'][periodo]\n",
                "                    right.append(bak_var)\n",
                "\n",
                "                name = f'balance_planta_{nombre_planta}_de_{nombre_ingrediente}_al_final_de_{periodo}'\n",
                "                rest = (pu.lpSum(left) == pu.lpSum(right), name)\n",
                "\n",
                "                rest_balance_masa_planta.append(rest)"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### Capacidad de recepción por planta\n",
                "\n",
                "En una planta y un periodo en particular, la suma del producto entre el tiempo del ingrediente y la cantidad de camiones llegando no debe superar el tiempo total disponible en la planta\n",
                "\n",
                "$$ \\sum_{I}{TiempoIngrediente_{pj}*T_{ijt}} \\leq TiempoTotal_{t} \\hspace{1cm} \\forall p \\in P, t \\in T$$"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 36,
            "metadata": {},
            "outputs": [],
            "source": [
                "rest_llegada_material = list()\n",
                "for nombre_planta, planta in plantas.items():\n",
                "    tiempo_total = planta['tiempo_total']\n",
                "    for periodo in periodos:\n",
                "        left_expresion = list()\n",
                "        for ingrediente, parametros in planta['inventarios'].items():\n",
                "            tiempo_ingrediente_por_camion = planta['tiempo_ingrediente'][ingrediente]\n",
                "            if periodo in parametros['llegadas'].keys():\n",
                "                for var_llegada in parametros['llegadas'][periodo]:\n",
                "                    left_expresion.append(\n",
                "                        tiempo_ingrediente_por_camion*var_llegada)\n",
                "\n",
                "        # omitir restricciones sin expresiones al lado izquiero\n",
                "        if len(left_expresion) > 0:\n",
                "            rest_name = f'Llegada_material_{nombre_planta}_durante_{periodo}'\n",
                "            rest = (pu.lpSum(left_expresion) <= tiempo_total, rest_name)\n",
                "            rest_llegada_material.append(rest)"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### Capacidad de almacenamiento\n",
                "\n",
                "$$ I_{pjt} \\leq CP_{pj} + M_{pjt} \\hspace{1cm} \\forall p \\in P, t \\in T$$"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "rest_capacidad_almacenamiento = list()\n",
                "for nombre_planta, planta in plantas.items():\n",
                "    for ingrediente, inventarios in planta['inventarios'].items():\n",
                "        CPpj = inventarios['capacidad']\n",
                "        for periodo, inventario_final_var in inventarios['inventario_final'].items():\n",
                "            if type(inventario_final_var) == pu.LpVariable:\n",
                "                rest_name = f'capacidad_almacenamiento_{nombre_planta}_de_{ingrediente}_en_{periodo}'\n",
                "                # if periodo in inventarios['exceso_capacidad'].keys():\n",
                "                Mpjt = inventarios['exceso_capacidad'][periodo]\n",
                "                rest = (inventario_final_var <= CPpj + Mpjt, rest_name)\n",
                "                # else:\n",
                "               #     rest = (inventario_final_var <= CPpj, rest_name)\n",
                "                rest_capacidad_almacenamiento.append(rest)"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### No superar el inventario máximo\n",
                "\n",
                "El inventario al final de un día cualquiera debe estar bajo el nivel máximo, por lo que penalizaremos en la función objetivo una variable de holgura para tal efecto\n",
                "$$ I_{pjt} \\leq MX_{pjt} + M_{pjt} \\hspace{1cm} \\forall p \\in P, j \\in J, t \\in T$$"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### Superar el inventario de seguridad\n",
                "\n",
                "El inventario al final de un día cualquiera debe estar bajo el nivel máximo, por lo que penalizaremos en la función objetivo una variable de holgura para tal efecto\n",
                "$$ I_{pjt} \\geq MX_{pjt} + M_{pjt} \\hspace{1cm} \\forall p \\in P, j \\in J, t \\in T$$"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 37,
            "metadata": {},
            "outputs": [],
            "source": [
                "rest_safety_stock = list()\n",
                "for nombre_planta, planta in plantas.items():\n",
                "    for ingrediente, inventarios in planta['inventarios'].items():\n",
                "        if 'safety_stock_kg' in inventarios.keys():\n",
                "            SS = inventarios['safety_stock_kg']\n",
                "            # for periodo, variable in inventarios['inventario_final'].items():\n",
                "            if len(inventarios['safety_stock'].keys()) > 0:\n",
                "                for periodo in periodos:\n",
                "                    rest_name = f'safety_stock_en_{nombre_planta}_de_{ingrediente}_durante_{periodo}'\n",
                "                    Ipjt = inventarios['inventario_final'][periodo]\n",
                "                    Spij = inventarios['safety_stock'][periodo]\n",
                "\n",
                "                    rest = (Ipjt + Spij >= SS, rest_name)\n",
                "                    rest_safety_stock.append(rest)"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### Superar el inventario objetivo al final del mes"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 38,
            "metadata": {},
            "outputs": [],
            "source": [
                "rest_inventario_objetivo = list()\n",
                "for nombre_planta, planta in plantas.items():\n",
                "    for ingrediente, inventarios in planta['inventarios'].items():\n",
                "        if 'objetivo_kg' in inventarios.keys():\n",
                "\n",
                "            target = inventarios['objetivo_kg']\n",
                "            if target > 0:\n",
                "                rest_name = f'objetivo_en_{nombre_planta}_de_{ingrediente}_al_final_de_{periodos[periodo_final]}'\n",
                "                Ipjt = inventarios['inventario_final'][periodos[periodo_final]]\n",
                "\n",
                "                rest = (Ipjt >= target, rest_name)\n",
                "                rest_inventario_objetivo.append(rest)"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "# Resolviendo el modelo"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Generando modelo"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 39,
            "metadata": {},
            "outputs": [],
            "source": [
                "problema = pu.LpProblem(name='Bios_Solver', sense=pu.LpMinimize)\n",
                "\n",
                "# Agregando funcion objetivo\n",
                "problema += pu.lpSum(funcion_objetivo)\n",
                "\n",
                "# Agregando balance de masa puerto\n",
                "for rest in rest_balance_masa_puerto:\n",
                "    problema += rest\n",
                "\n",
                "# Agregando balande ce masa en planta\n",
                "for rest in rest_balance_masa_planta:\n",
                "    problema += rest\n",
                "\n",
                "# Agregando capacidad de recepcion\n",
                "for rest in rest_llegada_material:\n",
                "    problema += rest\n",
                "\n",
                "# Agregando capacidad de almacenamiento\n",
                "# for rest in rest_capacidad_almacenamiento:\n",
                "#     problema += rest\n",
                "\n",
                "# Agregando inventario de seguridad\n",
                "for rest in rest_safety_stock:\n",
                "    problema += rest\n",
                "\n",
                "# Agregando inventario objetivo\n",
                "for rest in rest_inventario_objetivo:\n",
                "    problema += rest"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Ejecutando modelo"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 40,
            "metadata": {},
            "outputs": [
                {
                    "name": "stdout",
                    "output_type": "stream",
                    "text": [
                        "cpu count 15\n",
                        "tiempo limite 360 minutos\n",
                        "ejecutando  31 periodos\n",
                        "GAP tolerable 5000000 millones de pesos\n"
                    ]
                },
                {
                    "ename": "KeyboardInterrupt",
                    "evalue": "",
                    "output_type": "error",
                    "traceback": [
                        "\u001b[0;31m---------------------------------------------------------------------------\u001b[0m",
                        "\u001b[0;31mKeyboardInterrupt\u001b[0m                         Traceback (most recent call last)",
                        "Cell \u001b[0;32mIn[40], line 14\u001b[0m\n\u001b[1;32m      5\u001b[0m \u001b[38;5;28mprint\u001b[39m(\u001b[38;5;124m'\u001b[39m\u001b[38;5;124mGAP tolerable\u001b[39m\u001b[38;5;124m'\u001b[39m, gap, \u001b[38;5;124m'\u001b[39m\u001b[38;5;124mmillones de pesos\u001b[39m\u001b[38;5;124m'\u001b[39m)\n\u001b[1;32m      6\u001b[0m engine \u001b[38;5;241m=\u001b[39m pu\u001b[38;5;241m.\u001b[39mPULP_CBC_CMD(\n\u001b[1;32m      7\u001b[0m     timeLimit\u001b[38;5;241m=\u001b[39m\u001b[38;5;241m60\u001b[39m\u001b[38;5;241m*\u001b[39mt_limit_minutes,\n\u001b[1;32m      8\u001b[0m     gapAbs\u001b[38;5;241m=\u001b[39mgap,\n\u001b[0;32m   (...)\u001b[0m\n\u001b[1;32m     11\u001b[0m     presolve\u001b[38;5;241m=\u001b[39m\u001b[38;5;28;01mTrue\u001b[39;00m,\n\u001b[1;32m     12\u001b[0m     threads\u001b[38;5;241m=\u001b[39mcpu_count)\n\u001b[0;32m---> 14\u001b[0m \u001b[43mproblema\u001b[49m\u001b[38;5;241;43m.\u001b[39;49m\u001b[43msolve\u001b[49m\u001b[43m(\u001b[49m\u001b[43msolver\u001b[49m\u001b[38;5;241;43m=\u001b[39;49m\u001b[43mengine\u001b[49m\u001b[43m)\u001b[49m\n\u001b[1;32m     15\u001b[0m \u001b[38;5;66;03m# problema.solve()\u001b[39;00m\n",
                        "File \u001b[0;32m~/Documents/source_code/bios/env/lib/python3.11/site-packages/pulp/pulp.py:1883\u001b[0m, in \u001b[0;36mLpProblem.solve\u001b[0;34m(self, solver, **kwargs)\u001b[0m\n\u001b[1;32m   1881\u001b[0m \u001b[38;5;66;03m# time it\u001b[39;00m\n\u001b[1;32m   1882\u001b[0m \u001b[38;5;28mself\u001b[39m\u001b[38;5;241m.\u001b[39mstartClock()\n\u001b[0;32m-> 1883\u001b[0m status \u001b[38;5;241m=\u001b[39m \u001b[43msolver\u001b[49m\u001b[38;5;241;43m.\u001b[39;49m\u001b[43mactualSolve\u001b[49m\u001b[43m(\u001b[49m\u001b[38;5;28;43mself\u001b[39;49m\u001b[43m,\u001b[49m\u001b[43m \u001b[49m\u001b[38;5;241;43m*\u001b[39;49m\u001b[38;5;241;43m*\u001b[39;49m\u001b[43mkwargs\u001b[49m\u001b[43m)\u001b[49m\n\u001b[1;32m   1884\u001b[0m \u001b[38;5;28mself\u001b[39m\u001b[38;5;241m.\u001b[39mstopClock()\n\u001b[1;32m   1885\u001b[0m \u001b[38;5;28mself\u001b[39m\u001b[38;5;241m.\u001b[39mrestoreObjective(wasNone, dummyVar)\n",
                        "File \u001b[0;32m~/Documents/source_code/bios/env/lib/python3.11/site-packages/pulp/apis/coin_api.py:112\u001b[0m, in \u001b[0;36mCOIN_CMD.actualSolve\u001b[0;34m(self, lp, **kwargs)\u001b[0m\n\u001b[1;32m    110\u001b[0m \u001b[38;5;28;01mdef\u001b[39;00m \u001b[38;5;21mactualSolve\u001b[39m(\u001b[38;5;28mself\u001b[39m, lp, \u001b[38;5;241m*\u001b[39m\u001b[38;5;241m*\u001b[39mkwargs):\n\u001b[1;32m    111\u001b[0m \u001b[38;5;250m    \u001b[39m\u001b[38;5;124;03m\"\"\"Solve a well formulated lp problem\"\"\"\u001b[39;00m\n\u001b[0;32m--> 112\u001b[0m     \u001b[38;5;28;01mreturn\u001b[39;00m \u001b[38;5;28;43mself\u001b[39;49m\u001b[38;5;241;43m.\u001b[39;49m\u001b[43msolve_CBC\u001b[49m\u001b[43m(\u001b[49m\u001b[43mlp\u001b[49m\u001b[43m,\u001b[49m\u001b[43m \u001b[49m\u001b[38;5;241;43m*\u001b[39;49m\u001b[38;5;241;43m*\u001b[39;49m\u001b[43mkwargs\u001b[49m\u001b[43m)\u001b[49m\n",
                        "File \u001b[0;32m~/Documents/source_code/bios/env/lib/python3.11/site-packages/pulp/apis/coin_api.py:178\u001b[0m, in \u001b[0;36mCOIN_CMD.solve_CBC\u001b[0;34m(self, lp, use_mps)\u001b[0m\n\u001b[1;32m    176\u001b[0m \u001b[38;5;28;01melse\u001b[39;00m:\n\u001b[1;32m    177\u001b[0m     cbc \u001b[38;5;241m=\u001b[39m subprocess\u001b[38;5;241m.\u001b[39mPopen(args, stdout\u001b[38;5;241m=\u001b[39mpipe, stderr\u001b[38;5;241m=\u001b[39mpipe, stdin\u001b[38;5;241m=\u001b[39mdevnull)\n\u001b[0;32m--> 178\u001b[0m \u001b[38;5;28;01mif\u001b[39;00m \u001b[43mcbc\u001b[49m\u001b[38;5;241;43m.\u001b[39;49m\u001b[43mwait\u001b[49m\u001b[43m(\u001b[49m\u001b[43m)\u001b[49m \u001b[38;5;241m!=\u001b[39m \u001b[38;5;241m0\u001b[39m:\n\u001b[1;32m    179\u001b[0m     \u001b[38;5;28;01mif\u001b[39;00m pipe:\n\u001b[1;32m    180\u001b[0m         pipe\u001b[38;5;241m.\u001b[39mclose()\n",
                        "File \u001b[0;32m/Library/Frameworks/Python.framework/Versions/3.11/lib/python3.11/subprocess.py:1264\u001b[0m, in \u001b[0;36mPopen.wait\u001b[0;34m(self, timeout)\u001b[0m\n\u001b[1;32m   1262\u001b[0m     endtime \u001b[38;5;241m=\u001b[39m _time() \u001b[38;5;241m+\u001b[39m timeout\n\u001b[1;32m   1263\u001b[0m \u001b[38;5;28;01mtry\u001b[39;00m:\n\u001b[0;32m-> 1264\u001b[0m     \u001b[38;5;28;01mreturn\u001b[39;00m \u001b[38;5;28;43mself\u001b[39;49m\u001b[38;5;241;43m.\u001b[39;49m\u001b[43m_wait\u001b[49m\u001b[43m(\u001b[49m\u001b[43mtimeout\u001b[49m\u001b[38;5;241;43m=\u001b[39;49m\u001b[43mtimeout\u001b[49m\u001b[43m)\u001b[49m\n\u001b[1;32m   1265\u001b[0m \u001b[38;5;28;01mexcept\u001b[39;00m \u001b[38;5;167;01mKeyboardInterrupt\u001b[39;00m:\n\u001b[1;32m   1266\u001b[0m     \u001b[38;5;66;03m# https://bugs.python.org/issue25942\u001b[39;00m\n\u001b[1;32m   1267\u001b[0m     \u001b[38;5;66;03m# The first keyboard interrupt waits briefly for the child to\u001b[39;00m\n\u001b[1;32m   1268\u001b[0m     \u001b[38;5;66;03m# exit under the common assumption that it also received the ^C\u001b[39;00m\n\u001b[1;32m   1269\u001b[0m     \u001b[38;5;66;03m# generated SIGINT and will exit rapidly.\u001b[39;00m\n\u001b[1;32m   1270\u001b[0m     \u001b[38;5;28;01mif\u001b[39;00m timeout \u001b[38;5;129;01mis\u001b[39;00m \u001b[38;5;129;01mnot\u001b[39;00m \u001b[38;5;28;01mNone\u001b[39;00m:\n",
                        "File \u001b[0;32m/Library/Frameworks/Python.framework/Versions/3.11/lib/python3.11/subprocess.py:2046\u001b[0m, in \u001b[0;36mPopen._wait\u001b[0;34m(self, timeout)\u001b[0m\n\u001b[1;32m   2044\u001b[0m \u001b[38;5;28;01mif\u001b[39;00m \u001b[38;5;28mself\u001b[39m\u001b[38;5;241m.\u001b[39mreturncode \u001b[38;5;129;01mis\u001b[39;00m \u001b[38;5;129;01mnot\u001b[39;00m \u001b[38;5;28;01mNone\u001b[39;00m:\n\u001b[1;32m   2045\u001b[0m     \u001b[38;5;28;01mbreak\u001b[39;00m  \u001b[38;5;66;03m# Another thread waited.\u001b[39;00m\n\u001b[0;32m-> 2046\u001b[0m (pid, sts) \u001b[38;5;241m=\u001b[39m \u001b[38;5;28;43mself\u001b[39;49m\u001b[38;5;241;43m.\u001b[39;49m\u001b[43m_try_wait\u001b[49m\u001b[43m(\u001b[49m\u001b[38;5;241;43m0\u001b[39;49m\u001b[43m)\u001b[49m\n\u001b[1;32m   2047\u001b[0m \u001b[38;5;66;03m# Check the pid and loop as waitpid has been known to\u001b[39;00m\n\u001b[1;32m   2048\u001b[0m \u001b[38;5;66;03m# return 0 even without WNOHANG in odd situations.\u001b[39;00m\n\u001b[1;32m   2049\u001b[0m \u001b[38;5;66;03m# http://bugs.python.org/issue14396.\u001b[39;00m\n\u001b[1;32m   2050\u001b[0m \u001b[38;5;28;01mif\u001b[39;00m pid \u001b[38;5;241m==\u001b[39m \u001b[38;5;28mself\u001b[39m\u001b[38;5;241m.\u001b[39mpid:\n",
                        "File \u001b[0;32m/Library/Frameworks/Python.framework/Versions/3.11/lib/python3.11/subprocess.py:2004\u001b[0m, in \u001b[0;36mPopen._try_wait\u001b[0;34m(self, wait_flags)\u001b[0m\n\u001b[1;32m   2002\u001b[0m \u001b[38;5;250m\u001b[39m\u001b[38;5;124;03m\"\"\"All callers to this function MUST hold self._waitpid_lock.\"\"\"\u001b[39;00m\n\u001b[1;32m   2003\u001b[0m \u001b[38;5;28;01mtry\u001b[39;00m:\n\u001b[0;32m-> 2004\u001b[0m     (pid, sts) \u001b[38;5;241m=\u001b[39m \u001b[43mos\u001b[49m\u001b[38;5;241;43m.\u001b[39;49m\u001b[43mwaitpid\u001b[49m\u001b[43m(\u001b[49m\u001b[38;5;28;43mself\u001b[39;49m\u001b[38;5;241;43m.\u001b[39;49m\u001b[43mpid\u001b[49m\u001b[43m,\u001b[49m\u001b[43m \u001b[49m\u001b[43mwait_flags\u001b[49m\u001b[43m)\u001b[49m\n\u001b[1;32m   2005\u001b[0m \u001b[38;5;28;01mexcept\u001b[39;00m \u001b[38;5;167;01mChildProcessError\u001b[39;00m:\n\u001b[1;32m   2006\u001b[0m     \u001b[38;5;66;03m# This happens if SIGCLD is set to be ignored or waiting\u001b[39;00m\n\u001b[1;32m   2007\u001b[0m     \u001b[38;5;66;03m# for child processes has otherwise been disabled for our\u001b[39;00m\n\u001b[1;32m   2008\u001b[0m     \u001b[38;5;66;03m# process.  This child is dead, we can't get the status.\u001b[39;00m\n\u001b[1;32m   2009\u001b[0m     pid \u001b[38;5;241m=\u001b[39m \u001b[38;5;28mself\u001b[39m\u001b[38;5;241m.\u001b[39mpid\n",
                        "\u001b[0;31mKeyboardInterrupt\u001b[0m: "
                    ]
                },
                {
                    "name": "stdout",
                    "output_type": "stream",
                    "text": [
                        "Welcome to the CBC MILP Solver \n",
                        "Version: 2.10.3 \n",
                        "Build Date: Dec 15 2019 \n",
                        "\n",
                        "command line - /Users/luispinilla/Documents/source_code/bios/env/lib/python3.11/site-packages/pulp/solverdir/cbc/osx/64/cbc /var/folders/0p/md4rzs_n7bg992nr5mzyl7_00000gn/T/fff8af0b13db42c7a3614344083b98c7-pulp.mps -mips /var/folders/0p/md4rzs_n7bg992nr5mzyl7_00000gn/T/fff8af0b13db42c7a3614344083b98c7-pulp.mst -sec 21600 -allow 5000000 -threads 15 -presolve on -gomory on knapsack on probing on -timeMode elapsed -branch -printingOptions all -solution /var/folders/0p/md4rzs_n7bg992nr5mzyl7_00000gn/T/fff8af0b13db42c7a3614344083b98c7-pulp.sol (default strategy 1)\n",
                        "At line 2 NAME          MODEL\n",
                        "At line 3 ROWS\n",
                        "At line 9571 COLUMNS\n",
                        "At line 208580 RHS\n",
                        "At line 218147 BOUNDS\n",
                        "At line 255818 ENDATA\n",
                        "Problem MODEL has 9566 rows, 40646 columns and 107078 elements\n",
                        "Coin0008I MODEL read with 0 errors\n",
                        "opening mipstart file /var/folders/0p/md4rzs_n7bg992nr5mzyl7_00000gn/T/fff8af0b13db42c7a3614344083b98c7-pulp.mst.\n",
                        "MIPStart values read for 40646 variables.\n",
                        "seconds was changed from 1e+100 to 21600\n",
                        "allowableGap was changed from 1e-10 to 5e+06\n",
                        "threads was changed from 0 to 15\n",
                        "Option for gomoryCuts changed from ifmove to on\n",
                        "Option for knapsackCuts changed from ifmove to on\n",
                        "Option for timeMode changed from cpu to elapsed\n",
                        "Continuous objective value is 7.68626e+12 - 0.33 seconds\n",
                        "Cgl0003I 0 fixed, 2 tightened bounds, 1 strengthened rows, 0 substitutions\n",
                        "Cgl0004I processed model has 4972 rows, 36222 columns (28897 integer (3052 of which binary)) and 98435 elements\n",
                        "Cbc0045I Trying just fixing integer variables (and fixingish SOS).\n",
                        "Cbc0045I MIPStart provided solution with cost 6.02949e+13\n",
                        "Cbc0012I Integer solution of 6.0294941e+13 found by Reduced search after 0 iterations and 0 nodes (1.63 seconds)\n",
                        "Cbc0038I Full problem 4972 rows 36222 columns, reduced to 4812 rows 8383 columns\n",
                        "Cbc0031I 681 added rows had average density of 87.544787\n",
                        "Cbc0013I At root node, 681 cuts changed objective from 7.6862555e+12 to 7.7844007e+12 in 31 passes\n",
                        "Cbc0014I Cut generator 0 (Probing) - 101 row cuts average 4.0 elements, 0 column cuts (245 active)  in 2.453 seconds - new frequency is 1\n",
                        "Cbc0014I Cut generator 1 (Gomory) - 2250 row cuts average 45.4 elements, 0 column cuts (0 active)  in 4.588 seconds - new frequency is 1\n",
                        "Cbc0014I Cut generator 2 (Knapsack) - 0 row cuts average 0.0 elements, 0 column cuts (0 active)  in 0.475 seconds - new frequency is 1000\n",
                        "Cbc0014I Cut generator 3 (Clique) - 0 row cuts average 0.0 elements, 0 column cuts (0 active)  in 0.006 seconds - new frequency is -100\n",
                        "Cbc0014I Cut generator 4 (MixedIntegerRounding2) - 637 row cuts average 19.5 elements, 0 column cuts (0 active)  in 0.289 seconds - new frequency is 1\n",
                        "Cbc0014I Cut generator 5 (FlowCover) - 18 row cuts average 2.0 elements, 0 column cuts (0 active)  in 0.676 seconds - new frequency is -100\n",
                        "Cbc0014I Cut generator 6 (TwoMirCuts) - 3867 row cuts average 99.0 elements, 0 column cuts (0 active)  in 1.924 seconds - new frequency is -100\n",
                        "Cbc0014I Cut generator 7 (ZeroHalf) - 17 row cuts average 79.2 elements, 0 column cuts (0 active)  in 0.843 seconds - new frequency is -100\n",
                        "Cbc0010I After 0 nodes, 1 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (20.93 seconds)\n",
                        "Cbc0010I After 100 nodes, 51 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (52.82 seconds)\n",
                        "Cbc0010I After 200 nodes, 114 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (58.74 seconds)\n",
                        "Cbc0010I After 300 nodes, 179 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (64.44 seconds)\n",
                        "Cbc0010I After 400 nodes, 237 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (69.82 seconds)\n",
                        "Cbc0010I After 500 nodes, 296 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (75.03 seconds)\n",
                        "Cbc0010I After 600 nodes, 354 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (80.76 seconds)\n",
                        "Cbc0010I After 700 nodes, 406 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (85.37 seconds)\n",
                        "Cbc0010I After 800 nodes, 462 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (89.21 seconds)\n",
                        "Cbc0010I After 900 nodes, 524 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (92.57 seconds)\n",
                        "Cbc0010I After 1000 nodes, 583 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (96.78 seconds)\n",
                        "Cbc0010I After 1100 nodes, 646 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (100.73 seconds)\n",
                        "Cbc0010I After 1200 nodes, 714 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (103.95 seconds)\n",
                        "Cbc0010I After 1300 nodes, 774 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (107.24 seconds)\n",
                        "Cbc0010I After 1400 nodes, 829 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (110.74 seconds)\n",
                        "Cbc0010I After 1500 nodes, 892 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (114.36 seconds)\n",
                        "Cbc0010I After 1600 nodes, 951 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (118.04 seconds)\n",
                        "Cbc0010I After 1700 nodes, 1011 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (121.38 seconds)\n",
                        "Cbc0010I After 1800 nodes, 1067 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (124.35 seconds)\n",
                        "Cbc0010I After 1900 nodes, 1124 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (126.99 seconds)\n",
                        "Cbc0010I After 2000 nodes, 1185 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (129.79 seconds)\n",
                        "Cbc0010I After 2100 nodes, 1256 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (132.01 seconds)\n",
                        "Cbc0010I After 2200 nodes, 1324 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (134.28 seconds)\n",
                        "Cbc0010I After 2300 nodes, 1378 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (137.89 seconds)\n",
                        "Cbc0010I After 2400 nodes, 1426 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (141.86 seconds)\n",
                        "Cbc0010I After 2500 nodes, 1482 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (144.94 seconds)\n",
                        "Cbc0010I After 2600 nodes, 1494 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (147.43 seconds)\n",
                        "Cbc0010I After 2700 nodes, 1510 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (149.27 seconds)\n",
                        "Cbc0010I After 2800 nodes, 1570 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (151.42 seconds)\n",
                        "Cbc0010I After 2900 nodes, 1634 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (153.59 seconds)\n",
                        "Cbc0010I After 3000 nodes, 1689 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (155.68 seconds)\n",
                        "Cbc0010I After 3100 nodes, 1747 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (157.86 seconds)\n",
                        "Cbc0010I After 3200 nodes, 1809 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (160.12 seconds)\n",
                        "Cbc0010I After 3300 nodes, 1860 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (162.28 seconds)\n",
                        "Cbc0010I After 3400 nodes, 1914 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (164.31 seconds)\n",
                        "Cbc0010I After 3500 nodes, 1971 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (166.73 seconds)\n",
                        "Cbc0010I After 3600 nodes, 2024 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (169.15 seconds)\n",
                        "Cbc0010I After 3700 nodes, 2081 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (171.69 seconds)\n",
                        "Cbc0010I After 3800 nodes, 2139 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (173.66 seconds)\n",
                        "Cbc0010I After 3900 nodes, 2202 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (176.17 seconds)\n",
                        "Cbc0010I After 4000 nodes, 2262 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (178.98 seconds)\n",
                        "Cbc0010I After 4100 nodes, 2325 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (181.24 seconds)\n",
                        "Cbc0010I After 4200 nodes, 2386 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (183.81 seconds)\n",
                        "Cbc0010I After 4300 nodes, 2452 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (186.10 seconds)\n",
                        "Cbc0010I After 4400 nodes, 2514 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (188.45 seconds)\n",
                        "Cbc0010I After 4500 nodes, 2571 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (190.67 seconds)\n",
                        "Cbc0010I After 4600 nodes, 2629 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (192.95 seconds)\n",
                        "Cbc0010I After 4700 nodes, 2687 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (195.33 seconds)\n",
                        "Cbc0010I After 4800 nodes, 2746 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (197.50 seconds)\n",
                        "Cbc0010I After 4900 nodes, 2800 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (199.99 seconds)\n",
                        "Cbc0010I After 5000 nodes, 2866 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (202.11 seconds)\n",
                        "Cbc0010I After 5100 nodes, 2918 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (204.37 seconds)\n",
                        "Cbc0010I After 5200 nodes, 2974 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (207.04 seconds)\n",
                        "Cbc0010I After 5300 nodes, 3027 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (208.99 seconds)\n",
                        "Cbc0010I After 5400 nodes, 3093 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (211.34 seconds)\n",
                        "Cbc0010I After 5500 nodes, 3150 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (213.86 seconds)\n",
                        "Cbc0010I After 5600 nodes, 3205 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (216.05 seconds)\n",
                        "Cbc0010I After 5700 nodes, 3254 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (218.10 seconds)\n",
                        "Cbc0010I After 5800 nodes, 3296 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (220.20 seconds)\n",
                        "Cbc0010I After 5900 nodes, 3351 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (222.42 seconds)\n",
                        "Cbc0010I After 6000 nodes, 3408 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (224.88 seconds)\n",
                        "Cbc0010I After 6100 nodes, 3453 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (227.48 seconds)\n",
                        "Cbc0010I After 6200 nodes, 3508 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (230.12 seconds)\n",
                        "Cbc0010I After 6300 nodes, 3560 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (232.74 seconds)\n",
                        "Cbc0010I After 6400 nodes, 3625 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (235.57 seconds)\n",
                        "Cbc0010I After 6500 nodes, 3686 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (238.31 seconds)\n",
                        "Cbc0010I After 6600 nodes, 3741 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (241.28 seconds)\n",
                        "Cbc0010I After 6700 nodes, 3793 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (244.65 seconds)\n",
                        "Cbc0010I After 6800 nodes, 3845 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (247.84 seconds)\n",
                        "Cbc0010I After 6900 nodes, 3873 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (250.93 seconds)\n",
                        "Cbc0010I After 7000 nodes, 3904 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (253.91 seconds)\n",
                        "Cbc0010I After 7100 nodes, 3950 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (257.36 seconds)\n",
                        "Cbc0010I After 7200 nodes, 3996 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (260.36 seconds)\n",
                        "Cbc0010I After 7300 nodes, 4039 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (264.02 seconds)\n",
                        "Cbc0010I After 7400 nodes, 4096 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (267.99 seconds)\n",
                        "Cbc0010I After 7500 nodes, 4151 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (271.59 seconds)\n",
                        "Cbc0010I After 7600 nodes, 4191 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (274.69 seconds)\n",
                        "Cbc0010I After 7700 nodes, 4256 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (278.27 seconds)\n",
                        "Cbc0010I After 7800 nodes, 4315 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (282.89 seconds)\n",
                        "Cbc0010I After 7900 nodes, 4364 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (287.95 seconds)\n",
                        "Cbc0010I After 8000 nodes, 4418 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (291.82 seconds)\n",
                        "Cbc0010I After 8100 nodes, 4475 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (295.64 seconds)\n",
                        "Cbc0010I After 8200 nodes, 4531 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (299.67 seconds)\n",
                        "Cbc0010I After 8300 nodes, 4590 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (303.69 seconds)\n",
                        "Cbc0010I After 8400 nodes, 4643 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (308.27 seconds)\n",
                        "Cbc0010I After 8500 nodes, 4696 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (312.57 seconds)\n",
                        "Cbc0010I After 8600 nodes, 4749 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (316.96 seconds)\n",
                        "Cbc0010I After 8700 nodes, 4800 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (321.16 seconds)\n",
                        "Cbc0010I After 8800 nodes, 4846 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (326.06 seconds)\n",
                        "Cbc0010I After 8900 nodes, 4900 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (330.68 seconds)\n",
                        "Cbc0010I After 9000 nodes, 4961 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (334.40 seconds)\n",
                        "Cbc0010I After 9100 nodes, 5027 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (339.43 seconds)\n",
                        "Cbc0010I After 9200 nodes, 5086 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (343.05 seconds)\n",
                        "Cbc0010I After 9300 nodes, 5134 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (346.95 seconds)\n",
                        "Cbc0010I After 9400 nodes, 5186 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (350.86 seconds)\n",
                        "Cbc0010I After 9500 nodes, 5238 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (354.46 seconds)\n",
                        "Cbc0010I After 9600 nodes, 5295 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (358.77 seconds)\n",
                        "Cbc0010I After 9700 nodes, 5353 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (363.14 seconds)\n",
                        "Cbc0010I After 9800 nodes, 5396 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (366.66 seconds)\n",
                        "Cbc0010I After 9900 nodes, 5453 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (369.90 seconds)\n",
                        "Cbc0010I After 10000 nodes, 5516 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (373.57 seconds)\n",
                        "Cbc0010I After 10100 nodes, 5582 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (376.81 seconds)\n",
                        "Cbc0010I After 10200 nodes, 5637 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (380.06 seconds)\n",
                        "Cbc0010I After 10300 nodes, 5696 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (384.64 seconds)\n",
                        "Cbc0010I After 10400 nodes, 5754 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (387.92 seconds)\n",
                        "Cbc0010I After 10500 nodes, 5814 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (391.62 seconds)\n",
                        "Cbc0010I After 10600 nodes, 5871 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (394.65 seconds)\n",
                        "Cbc0010I After 10700 nodes, 5929 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (397.63 seconds)\n",
                        "Cbc0010I After 10800 nodes, 5983 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (400.12 seconds)\n",
                        "Cbc0010I After 10900 nodes, 6028 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (403.48 seconds)\n",
                        "Cbc0010I After 11000 nodes, 6070 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (406.32 seconds)\n",
                        "Cbc0010I After 11100 nodes, 6120 on tree, 6.0294941e+13 best solution, best possible 7.7844008e+12 (434.16 seconds)\n",
                        "Cbc0010I After 11200 nodes, 6169 on tree, 6.0294941e+13 best solution, best possible 7.7844027e+12 (452.94 seconds)\n",
                        "Cbc0010I After 11300 nodes, 6218 on tree, 6.0294941e+13 best solution, best possible 7.7844039e+12 (459.10 seconds)\n",
                        "Cbc0010I After 11400 nodes, 6268 on tree, 6.0294941e+13 best solution, best possible 7.7844039e+12 (463.58 seconds)\n",
                        "Cbc0010I After 11500 nodes, 6321 on tree, 6.0294941e+13"
                    ]
                }
            ],
            "source": [
                "print('cpu count', cpu_count)\n",
                "print('tiempo limite', t_limit_minutes, 'minutos')\n",
                "print('ejecutando ', len(periodos), 'periodos')\n",
                "\n",
                "print('GAP tolerable', gap, 'millones de pesos')\n",
                "engine = pu.PULP_CBC_CMD(\n",
                "    timeLimit=60*t_limit_minutes,\n",
                "    gapAbs=gap,\n",
                "    warmStart=True,\n",
                "    cuts=True,\n",
                "    presolve=True,\n",
                "    threads=cpu_count)\n",
                "\n",
                "problema.solve(solver=engine)\n",
                "# problema.solve()"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "# Construccion de reporte"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Reporte de puerto"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": null,
            "metadata": {},
            "outputs": [],
            "source": [
                "def get_reporte_puerto(cargas: dict) -> pd.DataFrame:\n",
                "\n",
                "    reporte_puerto_dict = dict()\n",
                "\n",
                "    reporte_puerto_dict['importacion'] = list()\n",
                "    reporte_puerto_dict['empresa'] = list()\n",
                "    reporte_puerto_dict['operador'] = list()\n",
                "    reporte_puerto_dict['puerto'] = list()\n",
                "    reporte_puerto_dict['ingrediente'] = list()\n",
                "    reporte_puerto_dict['valor_cif'] = list()\n",
                "    reporte_puerto_dict['periodo'] = list()\n",
                "    reporte_puerto_dict['costo_almacenamiento'] = list()\n",
                "    reporte_puerto_dict['llegadas'] = list()\n",
                "    reporte_puerto_dict['inventario'] = list()\n",
                "\n",
                "    for importacion, carga in cargas.items():\n",
                "\n",
                "        reporte_puerto_dict['importacion'].append(importacion)\n",
                "        reporte_puerto_dict['empresa'].append(carga['empresa'])\n",
                "        reporte_puerto_dict['operador'].append(carga['operador'])\n",
                "        reporte_puerto_dict['puerto'].append(carga['puerto'])\n",
                "        reporte_puerto_dict['ingrediente'].append(carga['ingrediente'])\n",
                "        reporte_puerto_dict['valor_cif'].append(carga['valor_cif'])\n",
                "        reporte_puerto_dict['periodo'].append(periodo_anterior)\n",
                "        reporte_puerto_dict['costo_almacenamiento'].append(0.0)\n",
                "        reporte_puerto_dict['llegadas'].append(0)\n",
                "        reporte_puerto_dict['inventario'].append(carga['inventario_inicial'])\n",
                "\n",
                "        for periodo in periodos:\n",
                "            reporte_puerto_dict['importacion'].append(importacion)\n",
                "            reporte_puerto_dict['empresa'].append(carga['empresa'])\n",
                "            reporte_puerto_dict['operador'].append(carga['operador'])\n",
                "            reporte_puerto_dict['puerto'].append(carga['puerto'])\n",
                "            reporte_puerto_dict['ingrediente'].append(carga['ingrediente'])\n",
                "            reporte_puerto_dict['valor_cif'].append(carga['valor_cif'])\n",
                "            reporte_puerto_dict['periodo'].append(periodo)\n",
                "            reporte_puerto_dict['costo_almacenamiento'].append(\n",
                "                carga['costo_almacenamiento'][periodo])\n",
                "            if periodo in carga['llegadas'].keys():\n",
                "                reporte_puerto_dict['llegadas'].append(\n",
                "                    carga['llegadas'][periodo])\n",
                "            else:\n",
                "                reporte_puerto_dict['llegadas'].append(0.0)\n",
                "            reporte_puerto_dict['inventario'].append(\n",
                "                cargas[importacion]['inventario_al_final'][periodo].varValue)\n",
                "\n",
                "    reporte_puerto_df = pd.DataFrame(reporte_puerto_dict)\n",
                "    reporte_puerto_df['costo_total_almacenamiento'] = reporte_puerto_df['inventario'] * \\\n",
                "        reporte_puerto_df['costo_almacenamiento']\n",
                "\n",
                "    return reporte_puerto_df"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Reporte transporte"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": null,
            "metadata": {},
            "outputs": [],
            "source": [
                "def get_reporte_transporte(cargas: dict) -> pd.DataFrame:\n",
                "\n",
                "    reporte_transporte_dict = dict()\n",
                "\n",
                "    reporte_transporte_dict['importacion'] = list()\n",
                "    reporte_transporte_dict['empresa'] = list()\n",
                "    reporte_transporte_dict['operador'] = list()\n",
                "    reporte_transporte_dict['puerto'] = list()\n",
                "    reporte_transporte_dict['ingrediente'] = list()\n",
                "    reporte_transporte_dict['periodo'] = list()\n",
                "    reporte_transporte_dict['tipo'] = list()\n",
                "    reporte_transporte_dict['planta'] = list()\n",
                "    reporte_transporte_dict['intercompany'] = list()\n",
                "    reporte_transporte_dict['costo_intercompany'] = list()\n",
                "    reporte_transporte_dict['flete'] = list()\n",
                "    reporte_transporte_dict['cantidad_despacho_por_camion'] = list()\n",
                "    reporte_transporte_dict['costo_portuario_despacho_directo'] = list()\n",
                "    reporte_transporte_dict['cantidad_despacho'] = list()\n",
                "    reporte_transporte_dict['cantidad_camiones_despachados'] = list()\n",
                "    reporte_transporte_dict['cantidad_despachada'] = list()\n",
                "    reporte_transporte_dict['costo_por_camion'] = list()\n",
                "    reporte_transporte_dict['cluster_flete'] = list()\n",
                "\n",
                "    for importacion, carga in cargas.items():\n",
                "        for nombre_planta, despacho in carga['costo_despacho'].items():\n",
                "            for periodo in periodos:\n",
                "                if periodo in despacho['variable_despacho'].keys():\n",
                "                    # if despacho['variable_despacho'][periodo].varValue > 0:\n",
                "\n",
                "                    reporte_transporte_dict['importacion'].append(importacion)\n",
                "                    reporte_transporte_dict['empresa'].append(carga['empresa'])\n",
                "                    reporte_transporte_dict['operador'].append(\n",
                "                        carga['operador'])\n",
                "                    reporte_transporte_dict['puerto'].append(carga['puerto'])\n",
                "                    reporte_transporte_dict['ingrediente'].append(\n",
                "                        carga['ingrediente'])\n",
                "                    reporte_transporte_dict['periodo'].append(periodo)\n",
                "                    reporte_transporte_dict['tipo'].append(\n",
                "                        despacho['tipo_envio'][periodo])\n",
                "                    reporte_transporte_dict['planta'].append(nombre_planta)\n",
                "                    reporte_transporte_dict['intercompany'].append(\n",
                "                        despacho['intercompany'])\n",
                "                    reporte_transporte_dict['costo_intercompany'].append(\n",
                "                        despacho['valor_intercompany'])\n",
                "                    reporte_transporte_dict['flete'].append(despacho['flete'])\n",
                "                    reporte_transporte_dict['cantidad_despacho_por_camion'].append(\n",
                "                        despacho['cantidad_despacho'])\n",
                "                    reporte_transporte_dict['costo_portuario_despacho_directo'].append(\n",
                "                        despacho['costo_despacho_directo'])\n",
                "                    reporte_transporte_dict['costo_por_camion'].append(\n",
                "                        despacho['costo_envio'][periodo])\n",
                "                    reporte_transporte_dict['cantidad_despacho'].append(\n",
                "                        cap_camion)\n",
                "                    reporte_transporte_dict['cantidad_camiones_despachados'].append(\n",
                "                        despacho['variable_despacho'][periodo].varValue)\n",
                "                    reporte_transporte_dict['cantidad_despachada'].append(\n",
                "                        cap_camion*despacho['variable_despacho'][periodo].varValue)\n",
                "\n",
                "                    reporte_transporte_dict['cluster_flete'].append(\n",
                "                        clusters_df.loc[(importacion, nombre_planta, periodo)]['etiqueta'])\n",
                "\n",
                "    reporte_transporte_df = pd.DataFrame(reporte_transporte_dict)\n",
                "    reporte_transporte_df['costo_total_despacho'] = reporte_transporte_df['costo_por_camion'] * \\\n",
                "        reporte_transporte_df['cantidad_camiones_despachados']\n",
                "\n",
                "    return reporte_transporte_df"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Reporte de Planta"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": null,
            "metadata": {},
            "outputs": [],
            "source": [
                "def get_reporte_plantas(plantas: dict) -> pd.DataFrame:\n",
                "\n",
                "    reporte_plantas_dict = dict()\n",
                "\n",
                "    reporte_plantas_dict = dict()\n",
                "    reporte_plantas_dict['planta'] = list()\n",
                "    reporte_plantas_dict['empresa'] = list()\n",
                "    reporte_plantas_dict['ingrediente'] = list()\n",
                "    reporte_plantas_dict['periodo'] = list()\n",
                "    reporte_plantas_dict['capcidad'] = list()\n",
                "    reporte_plantas_dict['consumo'] = list()\n",
                "    reporte_plantas_dict['backorder'] = list()\n",
                "    reporte_plantas_dict['safety_stock_kg'] = list()\n",
                "    reporte_plantas_dict['inventario_final'] = list()\n",
                "\n",
                "    for nombre_planta, planta in plantas.items():\n",
                "        for ingrediente, inventario in planta['inventarios'].items():\n",
                "\n",
                "            reporte_plantas_dict['planta'].append(nombre_planta)\n",
                "            reporte_plantas_dict['empresa'].append(planta['empresa'])\n",
                "            reporte_plantas_dict['ingrediente'].append(ingrediente)\n",
                "            reporte_plantas_dict['periodo'].append(periodo_anterior)\n",
                "            reporte_plantas_dict['capcidad'].append(inventario['capacidad'])\n",
                "            reporte_plantas_dict['consumo'].append(0.0)\n",
                "            reporte_plantas_dict['backorder'].append(0.0)\n",
                "            reporte_plantas_dict['safety_stock_kg'].append(0.0)\n",
                "            reporte_plantas_dict['inventario_final'].append(\n",
                "                inventario['inventario_final'][periodo_anterior])\n",
                "\n",
                "            for periodo in periodos:\n",
                "                reporte_plantas_dict['planta'].append(nombre_planta)\n",
                "                reporte_plantas_dict['empresa'].append(planta['empresa'])\n",
                "                reporte_plantas_dict['ingrediente'].append(ingrediente)\n",
                "                reporte_plantas_dict['periodo'].append(periodo)\n",
                "                reporte_plantas_dict['capcidad'].append(\n",
                "                    inventario['capacidad'])\n",
                "                reporte_plantas_dict['consumo'].append(\n",
                "                    inventario['consumo'][periodo])\n",
                "                if periodo in inventario['backorder'].keys():\n",
                "                    reporte_plantas_dict['backorder'].append(\n",
                "                        inventario['backorder'][periodo].varValue)\n",
                "                else:\n",
                "                    reporte_plantas_dict['backorder'].append(0.0)\n",
                "\n",
                "                if 'safety_stock_kg' in inventario.keys():\n",
                "                    reporte_plantas_dict['safety_stock_kg'].append(\n",
                "                        inventario['safety_stock_kg'])\n",
                "                else:\n",
                "                    reporte_plantas_dict['safety_stock_kg'].append(0.0)\n",
                "\n",
                "                if type(inventario['inventario_final'][periodo]) == pu.pulp.LpVariable:\n",
                "                    reporte_plantas_dict['inventario_final'].append(\n",
                "                        inventario['inventario_final'][periodo].varValue)\n",
                "                else:\n",
                "                    reporte_plantas_dict['inventario_final'].append(\n",
                "                        inventario['inventario_final'][periodo])\n",
                "\n",
                "    reporte_plantas_df = pd.DataFrame(reporte_plantas_dict)\n",
                "\n",
                "    return reporte_plantas_df"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Reporte de Modelo"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": null,
            "metadata": {},
            "outputs": [],
            "source": [
                "def get_reporte_modelo() -> pd.DataFrame:\n",
                "\n",
                "    reporte_dict = dict()\n",
                "    reporte_dict['Parametro'] = list()\n",
                "    reporte_dict['Valor'] = list()\n",
                "\n",
                "    reporte_dict['Parametro'].append(\"Cantidad de Núcleos CPU\")\n",
                "    reporte_dict['Valor'].append(cpu_count)\n",
                "\n",
                "    reporte_dict['Parametro'].append(\"Tiempo de trabajo\")\n",
                "    reporte_dict['Valor'].append(t_limit_minutes)\n",
                "\n",
                "    reporte_dict['Parametro'].append(\"Archivo de input\")\n",
                "    reporte_dict['Valor'].append(bios_input_file)\n",
                "\n",
                "    reporte_dict['Parametro'].append(\"GAP tolerable en Pesos\")\n",
                "    reporte_dict['Valor'].append(gap)\n",
                "\n",
                "    reporte_dict['Parametro'].append(\"Capacidad de camion en Kg\")\n",
                "    reporte_dict['Valor'].append(cap_camion)\n",
                "\n",
                "    reporte_dict['Parametro'].append(\"Capacidad de descargue en puerto en Kg\")\n",
                "    reporte_dict['Valor'].append(cap_descarge)\n",
                "\n",
                "    reporte_dict['Parametro'].append(\"Costo backorder por día\")\n",
                "    reporte_dict['Valor'].append(costo_backorder_dia)\n",
                "\n",
                "    reporte_dict['Parametro'].append(\n",
                "        \"Costo exceso inventaio en planta por día\")\n",
                "    reporte_dict['Valor'].append(costo_exceso_capacidad)\n",
                "\n",
                "    # Costo de no safety stock por día\n",
                "    reporte_dict['Parametro'].append(\"Costo de no satisfacer Safety stock\")\n",
                "    reporte_dict['Valor'].append(costo_safety_stock)\n",
                "\n",
                "    reporte_dict['Parametro'].append(\"Periodos sin despacho en días\")\n",
                "    reporte_dict['Valor'].append(periodo_administrativo)\n",
                "\n",
                "    reporte_dict['Parametro'].append(\"Lead time en dias\")\n",
                "    reporte_dict['Valor'].append(lead_time)\n",
                "\n",
                "    return pd.DataFrame(reporte_dict)"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Escribiendo el archivo"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": null,
            "metadata": {},
            "outputs": [],
            "source": [
                "reporte_modelo_df = get_reporte_modelo()\n",
                "reporte_puerto_df = get_reporte_puerto(cargas=cargas)\n",
                "reporte_plantas_df = get_reporte_plantas(plantas=plantas)\n",
                "reporte_transporte_df = get_reporte_transporte(cargas=cargas)\n",
                "\n",
                "fecha_generacion = datetime.now()\n",
                "bios_output_file = bios_input_file.replace('.xlsm', '')\n",
                "bios_output_file = f\"{bios_output_file}_{fecha_generacion.strftime('%Y%m%d%H')}.xlsx\""
            ]
        },
        {
            "cell_type": "code",
            "execution_count": null,
            "metadata": {},
            "outputs": [],
            "source": [
                "\n",
                "with pd.ExcelWriter(path=bios_output_file) as writer:\n",
                "    reporte_modelo_df.to_excel(writer, sheet_name='Modelo', index=False)\n",
                "    reporte_puerto_df.to_excel(writer, sheet_name='Puertos', index=False)\n",
                "    reporte_plantas_df.to_excel(writer, sheet_name='Plantas', index=False)\n",
                "    reporte_transporte_df.to_excel(writer, sheet_name='Despachos', index=False)"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": null,
            "metadata": {},
            "outputs": [],
            "source": [
                "# Duplicar el archivo\n",
                "shutil.copy(src=bios_output_file, dst='archivo_schema.xlsx')"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": null,
            "metadata": {},
            "outputs": [],
            "source": [
                "reporte_transporte_df['cantidad_camiones_despachados'].unique()"
            ]
        }
    ],
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3 (ipykernel)",
            "language": "python",
            "name": "python3"
        },
        "language_info": {
            "codemirror_mode": {
                "name": "ipython",
                "version": 3
            },
            "file_extension": ".py",
            "mimetype": "text/x-python",
            "name": "python",
            "nbconvert_exporter": "python",
            "pygments_lexer": "ipython3",
            "version": "3.11.4"
        }
    },
    "nbformat": 4,
    "nbformat_minor": 4
}

# %% [markdown]
# ## Reporte transporte

# %%


# %%
{
    "cells": [
        {
            "cell_type": "markdown",
            "metadata": {
                "tags": [
                    "parameters"
                ]
            },
            "source": [
                "# Modelo BIOS:"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Importacion de Librerias"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 1,
            "metadata": {},
            "outputs": [],
            "source": [
                "import pandas as pd\n",
                "from datetime import datetime, timedelta\n",
                "import pulp as pu\n",
                "from utils.asignador_capacidad import AsignadorCapacidad\n",
                "from utils.planta_loader import obtener_matriz_plantas\n",
                "import os\n",
                "import shutil\n",
                "import json\n",
                "import numpy as np\n",
                "from sklearn.cluster import KMeans\n",
                "from tqdm import tqdm"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Parametros generales"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 2,
            "metadata": {},
            "outputs": [],
            "source": [
                "bios_input_file = 'data/0_model_template_2204.xlsm'\n",
                "\n",
                "# Tiempo máximo de detencion en minutos\n",
                "t_limit_minutes = 60*6\n",
                "\n",
                "# Cantidad CPU habilitadas para trabajar\n",
                "cpu_count = max(1, os.cpu_count()-1)\n",
                "\n",
                "# Gap en millones de pesos\n",
                "gap = 5000000\n",
                "\n",
                "# Capacidad de carga de un camion\n",
                "cap_camion = 34000\n",
                "\n",
                "# Capacidad de descarga en puerto por día\n",
                "cap_descarge = 5000000\n",
                "\n",
                "# Costo de no safety stock por día\n",
                "costo_safety_stock = 50000\n",
                "\n",
                "# Costo de backorder por dia\n",
                "costo_backorder_dia = costo_safety_stock*5\n",
                "\n",
                "# Costo exceso de inventario\n",
                "costo_exceso_capacidad = costo_safety_stock*3\n",
                "\n",
                "# Los transportes solo tienen sentido desde el periodo 3, es dificil tomar deciciones para el mismo día\n",
                "periodo_administrativo = 1\n",
                "\n",
                "# Asumimos qe todo despacho tarda 2 días desde el momento que se envía la carga hasta que esta disponible para el consumo en planta\n",
                "lead_time = 2"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Lectura de dataframes"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 3,
            "metadata": {},
            "outputs": [
                {
                    "name": "stdout",
                    "output_type": "stream",
                    "text": [
                        "Leyendo archivo\n"
                    ]
                },
                {
                    "name": "stderr",
                    "output_type": "stream",
                    "text": [
                        "100%|██████████| 11/11 [00:00<00:00, 15.33it/s]\n"
                    ]
                },
                {
                    "name": "stdout",
                    "output_type": "stream",
                    "text": [
                        "generando periodos\n",
                        "generando consumo\n"
                    ]
                },
                {
                    "name": "stderr",
                    "output_type": "stream",
                    "text": [
                        "100%|██████████| 121/121 [00:00<00:00, 543.95it/s]\n"
                    ]
                },
                {
                    "name": "stdout",
                    "output_type": "stream",
                    "text": [
                        "trabajando con unidades de almacenamiento\n"
                    ]
                },
                {
                    "name": "stderr",
                    "output_type": "stream",
                    "text": [
                        "100%|██████████| 107/107 [00:00<00:00, 609.91it/s]\n"
                    ]
                },
                {
                    "name": "stdout",
                    "output_type": "stream",
                    "text": [
                        "trabajando con llegadas planeadas a planta\n"
                    ]
                },
                {
                    "name": "stderr",
                    "output_type": "stream",
                    "text": [
                        "100%|██████████| 24/24 [00:00<00:00, 3586.92it/s]\n"
                    ]
                },
                {
                    "name": "stdout",
                    "output_type": "stream",
                    "text": [
                        "trabajando con safety stock en planta\n"
                    ]
                },
                {
                    "name": "stderr",
                    "output_type": "stream",
                    "text": [
                        "100%|██████████| 121/121 [00:00<00:00, 190.14it/s]\n"
                    ]
                },
                {
                    "name": "stdout",
                    "output_type": "stream",
                    "text": [
                        "calculando inventarios\n"
                    ]
                },
                {
                    "name": "stderr",
                    "output_type": "stream",
                    "text": [
                        "100%|██████████| 13/13 [00:00<00:00, 25.35it/s]\n"
                    ]
                }
            ],
            "source": [
                "data_plantas_df = obtener_matriz_plantas(bios_input_file=bios_input_file)"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 4,
            "metadata": {},
            "outputs": [],
            "source": [
                "# Leer el archivo de excel\n",
                "productos_df = pd.read_excel(io=bios_input_file, sheet_name='ingredientes')\n",
                "plantas_df = pd.read_excel(io=bios_input_file, sheet_name='plantas')\n",
                "asignador = AsignadorCapacidad(bios_input_file)\n",
                "unidades_almacenamiento_df = asignador.obtener_unidades_almacenamiento()\n",
                "safety_stock_df = pd.read_excel(io=bios_input_file, sheet_name='safety_stock')\n",
                "consumo_proyectado_df = pd.read_excel(\n",
                "    io=bios_input_file, sheet_name='consumo_proyectado')\n",
                "transitos_puerto_df = pd.read_excel(\n",
                "    io=bios_input_file, sheet_name='tto_puerto')\n",
                "transitos_planta_df = pd.read_excel(\n",
                "    io=bios_input_file, sheet_name='tto_plantas')\n",
                "inventario_puerto_df = pd.read_excel(\n",
                "    io=bios_input_file, sheet_name='inventario_puerto')\n",
                "costos_almacenamiento_df = pd.read_excel(\n",
                "    io=bios_input_file, sheet_name='costos_almacenamiento_cargas')\n",
                "operaciones_portuarias_df = pd.read_excel(\n",
                "    io=bios_input_file, sheet_name='costos_operacion_portuaria')\n",
                "operaciones_portuarias_df = operaciones_portuarias_df.set_index(\n",
                "    ['tipo_operacion', 'operador', 'puerto', 'ingrediente'])\n",
                "fletes_df = pd.read_excel(io=bios_input_file, sheet_name='fletes_cop_per_kg')\n",
                "intercompany_df = pd.read_excel(\n",
                "    io=bios_input_file, sheet_name='venta_entre_empresas')\n",
                "objetivo_df = pd.read_excel(io='validaciones.xlsx', sheet_name='objetivo')"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Validaciones"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "def validar_nombres_columnas(input_file: str):\n",
                "\n",
                "    with open(\"file_structure.json\") as file:\n",
                "        paginas_dict = json.load(file)\n",
                "\n",
                "    errors_list = list()\n",
                "\n",
                "    for tab, columns in paginas_dict.items():\n",
                "        df = pd.read_excel(input_file, sheet_name=tab)\n",
                "        for column in columns:\n",
                "            if not column in df.columns:\n",
                "                errors_list.append(\n",
                "                    f'la columna \"{column}\" de la página \"{tab}\" parece faltar o estar mál escrita')\n",
                "\n",
                "    if len(errors_list) > 0:\n",
                "        return f\"Error, las siguientes columnas no se encontraron: {', '.join(errors_list)}\"\n",
                "    else:\n",
                "        return 'OK, el archivo parece tener las columnas y las pestañas completas'\n",
                "\n",
                "\n",
                "print(validar_nombres_columnas(input_file=bios_input_file))"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "def _validar_ingredientes(input_file: str):\n",
                "\n",
                "    df = pd.read_excel(io=input_file, sheet_name='ingredientes')\n",
                "\n",
                "    ingredientes = list(df['nombre'].unique())\n",
                "\n",
                "    if len(ingredientes) == df.shape[0]:\n",
                "        return \"OK, La lista de ingredientes tiene nombres únicos\"\n",
                "    else:\n",
                "        return \"Error, La lista de ingredientes tiene nombres duplicados\"\n",
                "\n",
                "\n",
                "print(_validar_ingredientes(input_file=bios_input_file))"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Creacion de parametros del problema"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### Tiempo"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 5,
            "metadata": {},
            "outputs": [
                {
                    "name": "stdout",
                    "output_type": "stream",
                    "text": [
                        "20240421 20240422 20240522\n"
                    ]
                }
            ],
            "source": [
                "# Obtener el conjunto de periodos\n",
                "fechas = [datetime.strptime(x, '%d/%m/%Y')\n",
                "          for x in consumo_proyectado_df.drop(columns=['planta', 'ingrediente']).columns]\n",
                "\n",
                "periodos = [int(x.strftime('%Y%m%d')) for x in fechas]\n",
                "\n",
                "periodo_anterior = fechas[0] - timedelta(days=1)\n",
                "periodo_anterior = int(periodo_anterior.strftime('%Y%m%d'))\n",
                "\n",
                "print(periodo_anterior,  periodos[0], periodos[-1])"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### Productos"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 6,
            "metadata": {},
            "outputs": [],
            "source": [
                "productos = [productos_df.loc[i]['nombre'] for i in productos_df.index]"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### Plantas"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "#### Tiempo de descarge de materiales"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 7,
            "metadata": {},
            "outputs": [],
            "source": [
                "# Generar plantas\n",
                "plantas = dict()\n",
                "\n",
                "for j in plantas_df.index:\n",
                "    planta = plantas_df.loc[j]['planta']\n",
                "    empresa = plantas_df.loc[j]['empresa']\n",
                "    operacion_minutos = plantas_df.loc[j]['operacion_minutos'] * \\\n",
                "        plantas_df.loc[j]['plataformas']\n",
                "    plantas[planta] = dict()\n",
                "    plantas[planta]['empresa'] = empresa\n",
                "    plantas[planta]['tiempo_total'] = operacion_minutos\n",
                "    plantas[planta]['tiempo_ingrediente'] = dict()\n",
                "    plantas[planta]['llegadas_puerto'] = dict()\n",
                "\n",
                "    for p in productos:\n",
                "        t_ingrediente = plantas_df.loc[j][p]\n",
                "        plantas[planta]['tiempo_ingrediente'][p] = t_ingrediente\n",
                "        plantas[planta]['llegadas_puerto'][p] = {t: list() for t in periodos}"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "#### Inventario en Planta"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 8,
            "metadata": {},
            "outputs": [
                {
                    "data": {
                        "text/html": [
                            "<div>\n",
                            "<style scoped>\n",
                            "    .dataframe tbody tr th:only-of-type {\n",
                            "        vertical-align: middle;\n",
                            "    }\n",
                            "\n",
                            "    .dataframe tbody tr th {\n",
                            "        vertical-align: top;\n",
                            "    }\n",
                            "\n",
                            "    .dataframe thead th {\n",
                            "        text-align: right;\n",
                            "    }\n",
                            "</style>\n",
                            "<table border=\"1\" class=\"dataframe\">\n",
                            "  <thead>\n",
                            "    <tr style=\"text-align: right;\">\n",
                            "      <th></th>\n",
                            "      <th>planta</th>\n",
                            "      <th>ingrediente_actual</th>\n",
                            "      <th>cantidad_actual</th>\n",
                            "      <th>capacidad</th>\n",
                            "      <th>dias_ss</th>\n",
                            "    </tr>\n",
                            "  </thead>\n",
                            "  <tbody>\n",
                            "    <tr>\n",
                            "      <th>0</th>\n",
                            "      <td>barbosa</td>\n",
                            "      <td>cascarilla</td>\n",
                            "      <td>1.0</td>\n",
                            "      <td>68000.0</td>\n",
                            "      <td>0.0</td>\n",
                            "    </tr>\n",
                            "    <tr>\n",
                            "      <th>1</th>\n",
                            "      <td>barbosa</td>\n",
                            "      <td>destilado</td>\n",
                            "      <td>1.0</td>\n",
                            "      <td>68000.0</td>\n",
                            "      <td>0.0</td>\n",
                            "    </tr>\n",
                            "    <tr>\n",
                            "      <th>2</th>\n",
                            "      <td>barbosa</td>\n",
                            "      <td>destiladohp</td>\n",
                            "      <td>1.0</td>\n",
                            "      <td>68000.0</td>\n",
                            "      <td>0.0</td>\n",
                            "    </tr>\n",
                            "    <tr>\n",
                            "      <th>3</th>\n",
                            "      <td>barbosa</td>\n",
                            "      <td>forraje</td>\n",
                            "      <td>1.0</td>\n",
                            "      <td>68000.0</td>\n",
                            "      <td>0.0</td>\n",
                            "    </tr>\n",
                            "    <tr>\n",
                            "      <th>4</th>\n",
                            "      <td>barbosa</td>\n",
                            "      <td>gluten</td>\n",
                            "      <td>1.0</td>\n",
                            "      <td>68000.0</td>\n",
                            "      <td>0.0</td>\n",
                            "    </tr>\n",
                            "  </tbody>\n",
                            "</table>\n",
                            "</div>"
                        ],
                        "text/plain": [
                            "    planta ingrediente_actual  cantidad_actual  capacidad  dias_ss\n",
                            "0  barbosa         cascarilla              1.0    68000.0      0.0\n",
                            "1  barbosa          destilado              1.0    68000.0      0.0\n",
                            "2  barbosa        destiladohp              1.0    68000.0      0.0\n",
                            "3  barbosa            forraje              1.0    68000.0      0.0\n",
                            "4  barbosa             gluten              1.0    68000.0      0.0"
                        ]
                    },
                    "execution_count": 8,
                    "metadata": {},
                    "output_type": "execute_result"
                }
            ],
            "source": [
                "unidades_almacenamiento_df['capacidad'] = unidades_almacenamiento_df.apply(\n",
                "    lambda x: x[x['ingrediente_actual']], axis=1)\n",
                "unidades_almacenamiento_df.drop(columns=productos, inplace=True)\n",
                "unidades_almacenamiento_df = unidades_almacenamiento_df.groupby(\n",
                "    ['planta', 'ingrediente_actual'])[['cantidad_actual', 'capacidad']].sum().reset_index()\n",
                "\n",
                "# Agregando la informacion de safety stock\n",
                "unidades_almacenamiento_df = pd.merge(left=unidades_almacenamiento_df,\n",
                "                                      right=safety_stock_df,\n",
                "                                      left_on=['planta', 'ingrediente_actual'],\n",
                "                                      right_on=['planta', 'ingrediente'],\n",
                "                                      how='left').drop(columns='ingrediente')\n",
                "\n",
                "unidades_almacenamiento_df.head()"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 9,
            "metadata": {},
            "outputs": [
                {
                    "name": "stdout",
                    "output_type": "stream",
                    "text": [
                        "(107, 36)\n"
                    ]
                },
                {
                    "data": {
                        "text/html": [
                            "<div>\n",
                            "<style scoped>\n",
                            "    .dataframe tbody tr th:only-of-type {\n",
                            "        vertical-align: middle;\n",
                            "    }\n",
                            "\n",
                            "    .dataframe tbody tr th {\n",
                            "        vertical-align: top;\n",
                            "    }\n",
                            "\n",
                            "    .dataframe thead th {\n",
                            "        text-align: right;\n",
                            "    }\n",
                            "</style>\n",
                            "<table border=\"1\" class=\"dataframe\">\n",
                            "  <thead>\n",
                            "    <tr style=\"text-align: right;\">\n",
                            "      <th></th>\n",
                            "      <th>planta</th>\n",
                            "      <th>ingrediente</th>\n",
                            "      <th>cantidad</th>\n",
                            "      <th>capacidad</th>\n",
                            "      <th>dias_ss</th>\n",
                            "      <th>20240422</th>\n",
                            "      <th>20240423</th>\n",
                            "      <th>20240424</th>\n",
                            "      <th>20240425</th>\n",
                            "      <th>20240426</th>\n",
                            "      <th>...</th>\n",
                            "      <th>20240513</th>\n",
                            "      <th>20240514</th>\n",
                            "      <th>20240515</th>\n",
                            "      <th>20240516</th>\n",
                            "      <th>20240517</th>\n",
                            "      <th>20240518</th>\n",
                            "      <th>20240519</th>\n",
                            "      <th>20240520</th>\n",
                            "      <th>20240521</th>\n",
                            "      <th>20240522</th>\n",
                            "    </tr>\n",
                            "  </thead>\n",
                            "  <tbody>\n",
                            "    <tr>\n",
                            "      <th>0</th>\n",
                            "      <td>barbosa</td>\n",
                            "      <td>cascarilla</td>\n",
                            "      <td>1.0</td>\n",
                            "      <td>68000.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.000000</td>\n",
                            "      <td>0.000000</td>\n",
                            "      <td>0.000000</td>\n",
                            "      <td>0.000000</td>\n",
                            "      <td>0.000000</td>\n",
                            "      <td>...</td>\n",
                            "      <td>0.000000</td>\n",
                            "      <td>0.000000</td>\n",
                            "      <td>0.000000</td>\n",
                            "      <td>0.000000</td>\n",
                            "      <td>0.000000</td>\n",
                            "      <td>0.000000</td>\n",
                            "      <td>0.000000</td>\n",
                            "      <td>0.000000</td>\n",
                            "      <td>0.000000</td>\n",
                            "      <td>0.000000</td>\n",
                            "    </tr>\n",
                            "    <tr>\n",
                            "      <th>1</th>\n",
                            "      <td>barbosa</td>\n",
                            "      <td>destilado</td>\n",
                            "      <td>1.0</td>\n",
                            "      <td>68000.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>439.613182</td>\n",
                            "      <td>439.613182</td>\n",
                            "      <td>439.613182</td>\n",
                            "      <td>439.613182</td>\n",
                            "      <td>439.613182</td>\n",
                            "      <td>...</td>\n",
                            "      <td>439.613182</td>\n",
                            "      <td>439.613182</td>\n",
                            "      <td>439.613182</td>\n",
                            "      <td>439.613182</td>\n",
                            "      <td>439.613182</td>\n",
                            "      <td>439.613182</td>\n",
                            "      <td>439.613182</td>\n",
                            "      <td>439.613182</td>\n",
                            "      <td>439.613182</td>\n",
                            "      <td>439.613182</td>\n",
                            "    </tr>\n",
                            "    <tr>\n",
                            "      <th>2</th>\n",
                            "      <td>barbosa</td>\n",
                            "      <td>destiladohp</td>\n",
                            "      <td>1.0</td>\n",
                            "      <td>68000.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.000000</td>\n",
                            "      <td>0.000000</td>\n",
                            "      <td>0.000000</td>\n",
                            "      <td>0.000000</td>\n",
                            "      <td>0.000000</td>\n",
                            "      <td>...</td>\n",
                            "      <td>0.000000</td>\n",
                            "      <td>0.000000</td>\n",
                            "      <td>0.000000</td>\n",
                            "      <td>0.000000</td>\n",
                            "      <td>0.000000</td>\n",
                            "      <td>0.000000</td>\n",
                            "      <td>0.000000</td>\n",
                            "      <td>0.000000</td>\n",
                            "      <td>0.000000</td>\n",
                            "      <td>0.000000</td>\n",
                            "    </tr>\n",
                            "    <tr>\n",
                            "      <th>3</th>\n",
                            "      <td>barbosa</td>\n",
                            "      <td>forraje</td>\n",
                            "      <td>1.0</td>\n",
                            "      <td>68000.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>150.727273</td>\n",
                            "      <td>150.727273</td>\n",
                            "      <td>150.727273</td>\n",
                            "      <td>150.727273</td>\n",
                            "      <td>150.727273</td>\n",
                            "      <td>...</td>\n",
                            "      <td>150.727273</td>\n",
                            "      <td>150.727273</td>\n",
                            "      <td>150.727273</td>\n",
                            "      <td>150.727273</td>\n",
                            "      <td>150.727273</td>\n",
                            "      <td>150.727273</td>\n",
                            "      <td>150.727273</td>\n",
                            "      <td>150.727273</td>\n",
                            "      <td>150.727273</td>\n",
                            "      <td>150.727273</td>\n",
                            "    </tr>\n",
                            "    <tr>\n",
                            "      <th>4</th>\n",
                            "      <td>barbosa</td>\n",
                            "      <td>gluten</td>\n",
                            "      <td>1.0</td>\n",
                            "      <td>68000.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>6064.242727</td>\n",
                            "      <td>6064.242727</td>\n",
                            "      <td>6064.242727</td>\n",
                            "      <td>6064.242727</td>\n",
                            "      <td>6064.242727</td>\n",
                            "      <td>...</td>\n",
                            "      <td>6064.242727</td>\n",
                            "      <td>6064.242727</td>\n",
                            "      <td>6064.242727</td>\n",
                            "      <td>6064.242727</td>\n",
                            "      <td>6064.242727</td>\n",
                            "      <td>6064.242727</td>\n",
                            "      <td>6064.242727</td>\n",
                            "      <td>6064.242727</td>\n",
                            "      <td>6064.242727</td>\n",
                            "      <td>6064.242727</td>\n",
                            "    </tr>\n",
                            "  </tbody>\n",
                            "</table>\n",
                            "<p>5 rows × 36 columns</p>\n",
                            "</div>"
                        ],
                        "text/plain": [
                            "    planta  ingrediente  cantidad  capacidad  dias_ss     20240422  \\\n",
                            "0  barbosa   cascarilla       1.0    68000.0      0.0     0.000000   \n",
                            "1  barbosa    destilado       1.0    68000.0      0.0   439.613182   \n",
                            "2  barbosa  destiladohp       1.0    68000.0      0.0     0.000000   \n",
                            "3  barbosa      forraje       1.0    68000.0      0.0   150.727273   \n",
                            "4  barbosa       gluten       1.0    68000.0      0.0  6064.242727   \n",
                            "\n",
                            "      20240423     20240424     20240425     20240426  ...     20240513  \\\n",
                            "0     0.000000     0.000000     0.000000     0.000000  ...     0.000000   \n",
                            "1   439.613182   439.613182   439.613182   439.613182  ...   439.613182   \n",
                            "2     0.000000     0.000000     0.000000     0.000000  ...     0.000000   \n",
                            "3   150.727273   150.727273   150.727273   150.727273  ...   150.727273   \n",
                            "4  6064.242727  6064.242727  6064.242727  6064.242727  ...  6064.242727   \n",
                            "\n",
                            "      20240514     20240515     20240516     20240517     20240518  \\\n",
                            "0     0.000000     0.000000     0.000000     0.000000     0.000000   \n",
                            "1   439.613182   439.613182   439.613182   439.613182   439.613182   \n",
                            "2     0.000000     0.000000     0.000000     0.000000     0.000000   \n",
                            "3   150.727273   150.727273   150.727273   150.727273   150.727273   \n",
                            "4  6064.242727  6064.242727  6064.242727  6064.242727  6064.242727   \n",
                            "\n",
                            "      20240519     20240520     20240521     20240522  \n",
                            "0     0.000000     0.000000     0.000000     0.000000  \n",
                            "1   439.613182   439.613182   439.613182   439.613182  \n",
                            "2     0.000000     0.000000     0.000000     0.000000  \n",
                            "3   150.727273   150.727273   150.727273   150.727273  \n",
                            "4  6064.242727  6064.242727  6064.242727  6064.242727  \n",
                            "\n",
                            "[5 rows x 36 columns]"
                        ]
                    },
                    "execution_count": 9,
                    "metadata": {},
                    "output_type": "execute_result"
                }
            ],
            "source": [
                "# Generar un diccionario para renombrar las columnas de tiempo en consumo proyectado\n",
                "consumo_proyectado_renamer = {x: datetime.strptime(x, '%d/%m/%Y').strftime(\n",
                "    '%Y%m%d') for x in consumo_proyectado_df.drop(columns=['planta', 'ingrediente']).columns}\n",
                "# Efectuar el cambio de nombre\n",
                "consumo_proyectado_df.rename(columns=consumo_proyectado_renamer, inplace=True)\n",
                "# Unir con el consumo proyectado\n",
                "unidades_almacenamiento_df = pd.merge(left=unidades_almacenamiento_df,\n",
                "                                      right=consumo_proyectado_df,\n",
                "                                      left_on=['planta', 'ingrediente_actual'],\n",
                "                                      right_on=['planta', 'ingrediente'],\n",
                "                                      how='left').drop(columns=['ingrediente']).rename(columns={'ingrediente_actual': 'ingrediente', 'cantidad_actual': 'cantidad'}).fillna(0.0)\n",
                "\n",
                "print(unidades_almacenamiento_df.shape)\n",
                "unidades_almacenamiento_df.head()"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 10,
            "metadata": {},
            "outputs": [],
            "source": [
                "renamer = {x: int(x.strftime('%Y%m%d')) for x in data_plantas_df.drop(\n",
                "    columns=['planta', 'ingrediente', 'variable']).columns}\n",
                "data_plantas_df.rename(columns=renamer, inplace=True)"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 11,
            "metadata": {},
            "outputs": [
                {
                    "data": {
                        "text/html": [
                            "<div>\n",
                            "<style scoped>\n",
                            "    .dataframe tbody tr th:only-of-type {\n",
                            "        vertical-align: middle;\n",
                            "    }\n",
                            "\n",
                            "    .dataframe tbody tr th {\n",
                            "        vertical-align: top;\n",
                            "    }\n",
                            "\n",
                            "    .dataframe thead th {\n",
                            "        text-align: right;\n",
                            "    }\n",
                            "</style>\n",
                            "<table border=\"1\" class=\"dataframe\">\n",
                            "  <thead>\n",
                            "    <tr style=\"text-align: right;\">\n",
                            "      <th></th>\n",
                            "      <th>planta</th>\n",
                            "      <th>ingrediente</th>\n",
                            "      <th>variable</th>\n",
                            "      <th>20240421</th>\n",
                            "      <th>20240422</th>\n",
                            "      <th>20240423</th>\n",
                            "      <th>20240424</th>\n",
                            "      <th>20240425</th>\n",
                            "      <th>20240426</th>\n",
                            "      <th>20240427</th>\n",
                            "      <th>...</th>\n",
                            "      <th>20240513</th>\n",
                            "      <th>20240514</th>\n",
                            "      <th>20240515</th>\n",
                            "      <th>20240516</th>\n",
                            "      <th>20240517</th>\n",
                            "      <th>20240518</th>\n",
                            "      <th>20240519</th>\n",
                            "      <th>20240520</th>\n",
                            "      <th>20240521</th>\n",
                            "      <th>20240522</th>\n",
                            "    </tr>\n",
                            "  </thead>\n",
                            "  <tbody>\n",
                            "    <tr>\n",
                            "      <th>0</th>\n",
                            "      <td>barbosa</td>\n",
                            "      <td>cascarilla</td>\n",
                            "      <td>backorder</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>...</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "    </tr>\n",
                            "    <tr>\n",
                            "      <th>1</th>\n",
                            "      <td>barbosa</td>\n",
                            "      <td>cascarilla</td>\n",
                            "      <td>capacidad_max</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>68000.0</td>\n",
                            "      <td>68000.0</td>\n",
                            "      <td>68000.0</td>\n",
                            "      <td>68000.0</td>\n",
                            "      <td>68000.0</td>\n",
                            "      <td>68000.0</td>\n",
                            "      <td>...</td>\n",
                            "      <td>68000.0</td>\n",
                            "      <td>68000.0</td>\n",
                            "      <td>68000.0</td>\n",
                            "      <td>68000.0</td>\n",
                            "      <td>68000.0</td>\n",
                            "      <td>68000.0</td>\n",
                            "      <td>68000.0</td>\n",
                            "      <td>68000.0</td>\n",
                            "      <td>68000.0</td>\n",
                            "      <td>68000.0</td>\n",
                            "    </tr>\n",
                            "    <tr>\n",
                            "      <th>2</th>\n",
                            "      <td>barbosa</td>\n",
                            "      <td>cascarilla</td>\n",
                            "      <td>consumo</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>...</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "    </tr>\n",
                            "    <tr>\n",
                            "      <th>3</th>\n",
                            "      <td>barbosa</td>\n",
                            "      <td>cascarilla</td>\n",
                            "      <td>inventario</td>\n",
                            "      <td>1.0</td>\n",
                            "      <td>1.0</td>\n",
                            "      <td>1.0</td>\n",
                            "      <td>1.0</td>\n",
                            "      <td>1.0</td>\n",
                            "      <td>1.0</td>\n",
                            "      <td>1.0</td>\n",
                            "      <td>...</td>\n",
                            "      <td>1.0</td>\n",
                            "      <td>1.0</td>\n",
                            "      <td>1.0</td>\n",
                            "      <td>1.0</td>\n",
                            "      <td>1.0</td>\n",
                            "      <td>1.0</td>\n",
                            "      <td>1.0</td>\n",
                            "      <td>1.0</td>\n",
                            "      <td>1.0</td>\n",
                            "      <td>1.0</td>\n",
                            "    </tr>\n",
                            "    <tr>\n",
                            "      <th>4</th>\n",
                            "      <td>barbosa</td>\n",
                            "      <td>cascarilla</td>\n",
                            "      <td>safety_stock</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>...</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "      <td>0.0</td>\n",
                            "    </tr>\n",
                            "  </tbody>\n",
                            "</table>\n",
                            "<p>5 rows × 35 columns</p>\n",
                            "</div>"
                        ],
                        "text/plain": [
                            "    planta ingrediente       variable  20240421  20240422  20240423  20240424  \\\n",
                            "0  barbosa  cascarilla      backorder       0.0       0.0       0.0       0.0   \n",
                            "1  barbosa  cascarilla  capacidad_max       0.0   68000.0   68000.0   68000.0   \n",
                            "2  barbosa  cascarilla        consumo       0.0       0.0       0.0       0.0   \n",
                            "3  barbosa  cascarilla     inventario       1.0       1.0       1.0       1.0   \n",
                            "4  barbosa  cascarilla   safety_stock       0.0       0.0       0.0       0.0   \n",
                            "\n",
                            "   20240425  20240426  20240427  ...  20240513  20240514  20240515  20240516  \\\n",
                            "0       0.0       0.0       0.0  ...       0.0       0.0       0.0       0.0   \n",
                            "1   68000.0   68000.0   68000.0  ...   68000.0   68000.0   68000.0   68000.0   \n",
                            "2       0.0       0.0       0.0  ...       0.0       0.0       0.0       0.0   \n",
                            "3       1.0       1.0       1.0  ...       1.0       1.0       1.0       1.0   \n",
                            "4       0.0       0.0       0.0  ...       0.0       0.0       0.0       0.0   \n",
                            "\n",
                            "   20240517  20240518  20240519  20240520  20240521  20240522  \n",
                            "0       0.0       0.0       0.0       0.0       0.0       0.0  \n",
                            "1   68000.0   68000.0   68000.0   68000.0   68000.0   68000.0  \n",
                            "2       0.0       0.0       0.0       0.0       0.0       0.0  \n",
                            "3       1.0       1.0       1.0       1.0       1.0       1.0  \n",
                            "4       0.0       0.0       0.0       0.0       0.0       0.0  \n",
                            "\n",
                            "[5 rows x 35 columns]"
                        ]
                    },
                    "execution_count": 11,
                    "metadata": {},
                    "output_type": "execute_result"
                }
            ],
            "source": [
                "data_plantas_df.head()"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 12,
            "metadata": {},
            "outputs": [
                {
                    "name": "stderr",
                    "output_type": "stream",
                    "text": [
                        "100%|██████████| 624/624 [00:07<00:00, 84.65it/s] \n"
                    ]
                }
            ],
            "source": [
                "# Llenar la informacion de los inventarios\n",
                "for i in tqdm(data_plantas_df.index):\n",
                "    planta = data_plantas_df.loc[i]['planta']\n",
                "    ingrediente = data_plantas_df.loc[i]['ingrediente']\n",
                "\n",
                "    inventarios = data_plantas_df[(data_plantas_df['planta'] == planta) & (\n",
                "        data_plantas_df['ingrediente'] == ingrediente) & (data_plantas_df['variable'] == 'inventario')]\n",
                "    consumo_df = data_plantas_df[(data_plantas_df['planta'] == planta) & (\n",
                "        data_plantas_df['ingrediente'] == ingrediente) & (data_plantas_df['variable'] == 'consumo')]\n",
                "    safety_stock = data_plantas_df[(data_plantas_df['planta'] == planta) & (\n",
                "        data_plantas_df['ingrediente'] == ingrediente) & (data_plantas_df['variable'] == 'safety_stock')]\n",
                "    capacidad_df = data_plantas_df[(data_plantas_df['planta'] == planta) & (\n",
                "        data_plantas_df['ingrediente'] == ingrediente) & (data_plantas_df['variable'] == 'capacidad_max')]\n",
                "    backorder_df = data_plantas_df[(data_plantas_df['planta'] == planta) & (\n",
                "        data_plantas_df['ingrediente'] == ingrediente) & (data_plantas_df['variable'] == 'backorder')]\n",
                "    cantidad_inicial = data_plantas_df.iloc[0][periodo_anterior]\n",
                "\n",
                "    if capacidad_df.shape[0] > 0:\n",
                "\n",
                "        if consumo_df.shape[0] > 0:\n",
                "            consumo_total = np.sum(consumo_df.drop(\n",
                "                columns=['planta', 'ingrediente', 'variable']).iloc[0])\n",
                "        else:\n",
                "            consumo_total = 0.0\n",
                "        # capacidad_almacenamiento = unidades_almacenamiento_df.loc[i]['capacidad']\n",
                "        # safety_stock_dias = unidades_almacenamiento_df.loc[i]['dias_ss']\n",
                "\n",
                "        if not 'inventarios' in plantas[planta].keys():\n",
                "            plantas[planta]['inventarios'] = dict()\n",
                "\n",
                "        if not ingrediente in plantas[planta]['inventarios'].keys():\n",
                "            plantas[planta]['inventarios'][ingrediente] = dict()\n",
                "\n",
                "        # if not 'capacidad' in plantas[planta]['inventarios'][ingrediente].keys():\n",
                "        #    plantas[planta]['inventarios'][ingrediente]['capacidad'] = capacidad_almacenamiento\n",
                "\n",
                "        if not 'inventario_final' in plantas[planta]['inventarios'][ingrediente].keys():\n",
                "            plantas[planta]['inventarios'][ingrediente]['inventario_final'] = dict()\n",
                "\n",
                "        if not 'llegadas' in plantas[planta]['inventarios'][ingrediente].keys():\n",
                "            plantas[planta]['inventarios'][ingrediente]['llegadas'] = dict()\n",
                "\n",
                "        if not 'consumo' in plantas[planta]['inventarios'][ingrediente].keys():\n",
                "            plantas[planta]['inventarios'][ingrediente]['consumo'] = dict()\n",
                "\n",
                "        if not 'backorder' in plantas[planta]['inventarios'][ingrediente].keys():\n",
                "            plantas[planta]['inventarios'][ingrediente]['backorder'] = dict()\n",
                "\n",
                "        if not 'safety_stock' in plantas[planta]['inventarios'][ingrediente].keys():\n",
                "            plantas[planta]['inventarios'][ingrediente]['safety_stock'] = dict()\n",
                "\n",
                "        if not 'exceso_capacidad' in plantas[planta]['inventarios'][ingrediente].keys():\n",
                "            plantas[planta]['inventarios'][ingrediente]['exceso_capacidad'] = dict()\n",
                "\n",
                "        plantas[planta]['inventarios'][ingrediente]['inventario_final'][periodo_anterior] = cantidad_inicial\n",
                "\n",
                "        if consumo_total > 0:\n",
                "\n",
                "            # safety_stock_dias\n",
                "            plantas[planta]['inventarios'][ingrediente]['safety_stock_dias'] = 0.0\n",
                "\n",
                "            # safety_stock_kg = consumo_total*safety_stock_dias/len(periodos)\n",
                "\n",
                "            for periodo in periodos:\n",
                "\n",
                "                if safety_stock.shape[0] > 0:\n",
                "                    plantas[planta]['inventarios'][ingrediente]['safety_stock_kg'] = safety_stock.iloc[0][periodo]\n",
                "                else:\n",
                "                    plantas[planta]['inventarios'][ingrediente]['safety_stock_kg'] = 0.0\n",
                "\n",
                "                # Obtener consumo\n",
                "                consumo = consumo_df.iloc[0][periodo]\n",
                "\n",
                "                # Maximo entre inventario proyectado y la capacidad\n",
                "                capacidad_maxima = capacidad_df.iloc[0][periodo]\n",
                "                inventario_proyectado = inventarios.iloc[0][periodo]\n",
                "                capacidad_almacenamiento = max(\n",
                "                    capacidad_maxima, inventario_proyectado)\n",
                "                # Agregar las variables de inventario\n",
                "                inventario_var_name = f'I_{planta}_{ingrediente}_{periodo}'\n",
                "                inventario_var = pu.LpVariable(\n",
                "                    name=inventario_var_name,\n",
                "                    lowBound=0.0,\n",
                "                    upBound=capacidad_almacenamiento, cat=pu.LpContinuous)\n",
                "                inventario_var.setInitialValue(inventario_proyectado)\n",
                "                plantas[planta]['inventarios'][ingrediente]['inventario_final'][periodo] = inventario_var\n",
                "\n",
                "                # Agregar las variables de exceso de inventario\n",
                "                # exceso_capacidad_var_name = f'M_{planta}_{ingrediente}_{periodo}'\n",
                "                # exceso_capacidad_var = pu.LpVariable(\n",
                "                #     name=exceso_capacidad_var_name, lowBound=0.0, cat=pu.LpContinuous)\n",
                "                # plantas[planta]['inventarios'][ingrediente]['exceso_capacidad'][periodo] = exceso_capacidad_var\n",
                "\n",
                "                # Agregar las listas a donde llegarán los transportes\n",
                "                plantas[planta]['inventarios'][ingrediente]['llegadas'][periodo] = list()\n",
                "\n",
                "                # Agregar las variables de backorder\n",
                "                backorder = backorder_df.iloc[0][periodo]\n",
                "                bak_var_name = f'B_{planta}_{ingrediente}_{periodo}'\n",
                "                bak_var = pu.LpVariable(\n",
                "                    name=bak_var_name, lowBound=0.0, upBound=consumo,  cat=pu.LpContinuous)\n",
                "                bak_var.setInitialValue(backorder)\n",
                "\n",
                "                plantas[planta]['inventarios'][ingrediente]['backorder'][periodo] = bak_var\n",
                "\n",
                "                # Agregar las variables de Safety Stock\n",
                "                if safety_stock.shape[0] > 0:\n",
                "                    safety_stock_kg = safety_stock.iloc[0][periodo]\n",
                "                    if capacidad_almacenamiento > safety_stock_kg + 2*cap_camion:\n",
                "                        ss_var_name = f'S_{planta}_{ingrediente}_{periodo}'\n",
                "                        ss_var = pu.LpVariable(\n",
                "                            name=ss_var_name, lowBound=0.0, upBound=safety_stock_kg, cat=pu.LpContinuous)\n",
                "                        plantas[planta]['inventarios'][ingrediente]['safety_stock'][periodo] = ss_var\n",
                "\n",
                "                # Agregar el consumo proyectado\n",
                "                plantas[planta]['inventarios'][ingrediente]['consumo'][periodo] = consumo\n",
                "        else:\n",
                "            for periodo in periodos:\n",
                "                # Dejar el inventario en el estado actual\n",
                "                plantas[planta]['inventarios'][ingrediente]['inventario_final'][periodo] = cantidad_inicial\n",
                "\n",
                "                # Agregar el consumo proyectado\n",
                "                plantas[planta]['inventarios'][ingrediente]['consumo'][periodo] = 0.0\n",
                "\n",
                "                # Agregar las variables de exceso de inventario\n",
                "                # exceso_capacidad_var_name = f'M_{planta}_{ingrediente}_{periodo}'\n",
                "                # exceso_capacidad_var = pu.LpVariable(\n",
                "                #     name=exceso_capacidad_var_name, lowBound=0.0, cat=pu.LpContinuous)\n",
                "                # plantas[planta]['inventarios'][ingrediente]['exceso_capacidad'][periodo] = exceso_capacidad_var"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 13,
            "metadata": {},
            "outputs": [],
            "source": [
                "# Llegar el objetivo de inventario al cierre\n",
                "\n",
                "for i in objetivo_df.index:\n",
                "    planta = objetivo_df.loc[i]['planta']\n",
                "    ingrediente = objetivo_df.loc[i]['ingrediente']\n",
                "    objetivo_dio = objetivo_df.loc[i]['objetivo_dio']\n",
                "    objetivo_kg = objetivo_df.loc[i]['objetivo_kg']\n",
                "    if ingrediente in plantas[planta]['inventarios'].keys():\n",
                "        plantas[planta]['inventarios'][ingrediente]['objetivo_dio'] = objetivo_dio\n",
                "        plantas[planta]['inventarios'][ingrediente]['objetivo_kg'] = objetivo_kg"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "#### Llegadas programadas anteriormente a Planta"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 14,
            "metadata": {},
            "outputs": [],
            "source": [
                "for i in transitos_planta_df.index:\n",
                "    planta = transitos_planta_df.loc[i]['planta']\n",
                "    ingrediente = transitos_planta_df.loc[i]['ingrediente']\n",
                "    cantidad = transitos_planta_df.loc[i]['cantidad']\n",
                "    fecha = transitos_planta_df.loc[i]['fecha_llegada']\n",
                "    periodo = int(fecha.strftime('%Y%m%d'))\n",
                "    plantas[planta]['inventarios'][ingrediente]['llegadas'][periodo].append(\n",
                "        0.0)"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### Cargas en Puerto"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 15,
            "metadata": {},
            "outputs": [
                {
                    "data": {
                        "text/html": [
                            "<div>\n",
                            "<style scoped>\n",
                            "    .dataframe tbody tr th:only-of-type {\n",
                            "        vertical-align: middle;\n",
                            "    }\n",
                            "\n",
                            "    .dataframe tbody tr th {\n",
                            "        vertical-align: top;\n",
                            "    }\n",
                            "\n",
                            "    .dataframe thead th {\n",
                            "        text-align: right;\n",
                            "    }\n",
                            "</style>\n",
                            "<table border=\"1\" class=\"dataframe\">\n",
                            "  <thead>\n",
                            "    <tr style=\"text-align: right;\">\n",
                            "      <th></th>\n",
                            "      <th>planta</th>\n",
                            "      <th>ingrediente</th>\n",
                            "      <th>cantidad</th>\n",
                            "      <th>fecha_llegada</th>\n",
                            "    </tr>\n",
                            "  </thead>\n",
                            "  <tbody>\n",
                            "    <tr>\n",
                            "      <th>2</th>\n",
                            "      <td>envigado</td>\n",
                            "      <td>tgirasol</td>\n",
                            "      <td>66520.0</td>\n",
                            "      <td>2024-04-22</td>\n",
                            "    </tr>\n",
                            "    <tr>\n",
                            "      <th>4</th>\n",
                            "      <td>neiva</td>\n",
                            "      <td>tgirasol</td>\n",
                            "      <td>169980.0</td>\n",
                            "      <td>2024-04-25</td>\n",
                            "    </tr>\n",
                            "    <tr>\n",
                            "      <th>7</th>\n",
                            "      <td>buga</td>\n",
                            "      <td>tgirasol</td>\n",
                            "      <td>161280.0</td>\n",
                            "      <td>2024-04-22</td>\n",
                            "    </tr>\n",
                            "  </tbody>\n",
                            "</table>\n",
                            "</div>"
                        ],
                        "text/plain": [
                            "     planta ingrediente  cantidad fecha_llegada\n",
                            "2  envigado    tgirasol   66520.0    2024-04-22\n",
                            "4     neiva    tgirasol  169980.0    2024-04-25\n",
                            "7      buga    tgirasol  161280.0    2024-04-22"
                        ]
                    },
                    "execution_count": 15,
                    "metadata": {},
                    "output_type": "execute_result"
                }
            ],
            "source": [
                "transitos_planta_df[transitos_planta_df['ingrediente'] == 'tgirasol']"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {
                "jp-MarkdownHeadingCollapsed": true
            },
            "source": [
                "#### Crear cargas a partir de información de los transitos"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 16,
            "metadata": {},
            "outputs": [],
            "source": [
                "# Generar Cargas\n",
                "cargas = dict()\n",
                "\n",
                "# A partir de los transitos\n",
                "for i in transitos_puerto_df.index:\n",
                "    importacion = str(\n",
                "        transitos_puerto_df.loc[i]['importacion']).replace(' ', '')\n",
                "    empresa = transitos_puerto_df.loc[i]['empresa']\n",
                "    operador = transitos_puerto_df.loc[i]['operador']\n",
                "    puerto = transitos_puerto_df.loc[i]['puerto']\n",
                "    ingrediente = transitos_puerto_df.loc[i]['ingrediente']\n",
                "    cantidad_kg = transitos_puerto_df.loc[i]['cantidad_kg']\n",
                "    valor_cif = transitos_puerto_df.loc[i]['valor_kg']\n",
                "    fecha = transitos_puerto_df.loc[i]['fecha_llegada']\n",
                "    if not importacion in cargas.keys():\n",
                "        cargas[importacion] = dict()\n",
                "\n",
                "    cargas[importacion]['empresa'] = empresa\n",
                "    cargas[importacion]['operador'] = operador\n",
                "    cargas[importacion]['puerto'] = puerto\n",
                "    cargas[importacion]['ingrediente'] = ingrediente\n",
                "    cargas[importacion]['valor_cif'] = valor_cif\n",
                "    cargas[importacion]['inventario_inicial'] = 0\n",
                "    cargas[importacion]['costo_almacenamiento'] = {\n",
                "        int(t.strftime('%Y%m%d')): 0 for t in fechas}\n",
                "    cargas[importacion]['llegadas'] = dict()\n",
                "    cargas[importacion]['fecha_inicial'] = int(fecha.strftime('%Y%m%d'))\n",
                "\n",
                "    # Poner llegadas de materia\n",
                "    while cantidad_kg > cap_descarge:\n",
                "        cargas[importacion]['llegadas'][int(\n",
                "            fecha.strftime('%Y%m%d'))] = cap_descarge\n",
                "        cantidad_kg -= cap_descarge\n",
                "        fecha = fecha + timedelta(days=1)\n",
                "\n",
                "    if cantidad_kg > 0:\n",
                "        cargas[importacion]['llegadas'][int(\n",
                "            fecha.strftime('%Y%m%d'))] = cantidad_kg\n",
                "    cargas[importacion]['fecha_final'] = int(fecha.strftime('%Y%m%d'))\n",
                "\n",
                "    # Agregar las variables de inventario\n",
                "    cargas[importacion]['inventario_al_final'] = dict()\n",
                "    for t in periodos:\n",
                "        var_name = f\"O_{importacion}_{t}\"\n",
                "        lp_var = pu.LpVariable(name=var_name,\n",
                "                               lowBound=0.0,\n",
                "                               upBound=transitos_puerto_df.loc[i]['cantidad_kg'],\n",
                "                               cat=pu.LpContinuous)\n",
                "        cargas[importacion]['inventario_al_final'][t] = lp_var"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "#### Crear cargas a partir de inventarios en puerto"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 17,
            "metadata": {},
            "outputs": [],
            "source": [
                "\n",
                "# A Partir de los inventarios en puerto\n",
                "for i in inventario_puerto_df.index:\n",
                "    empresa = inventario_puerto_df.loc[i]['empresa']\n",
                "    operador = inventario_puerto_df.loc[i]['operador']\n",
                "    puerto = inventario_puerto_df.loc[i]['puerto']\n",
                "    ingrediente = inventario_puerto_df.loc[i]['ingrediente']\n",
                "    importacion = str(\n",
                "        inventario_puerto_df.loc[i]['importacion']).replace(' ', '')\n",
                "    inventario_inicial = inventario_puerto_df.loc[i]['cantidad_kg']\n",
                "    valor_cif = inventario_puerto_df.loc[i]['valor_cif_kg']\n",
                "    fecha = inventario_puerto_df.loc[i]['fecha_llegada']\n",
                "\n",
                "    if not importacion in cargas.keys():\n",
                "        cargas[importacion] = dict()\n",
                "\n",
                "    cargas[importacion]['empresa'] = empresa\n",
                "    cargas[importacion]['operador'] = operador\n",
                "    cargas[importacion]['puerto'] = puerto\n",
                "    cargas[importacion]['ingrediente'] = ingrediente\n",
                "    cargas[importacion]['valor_cif'] = valor_cif\n",
                "    cargas[importacion]['inventario_inicial'] = inventario_inicial\n",
                "    cargas[importacion]['costo_almacenamiento'] = {\n",
                "        int(t.strftime('%Y%m%d')): 0 for t in fechas}\n",
                "\n",
                "    # Poner llegadas de materia\n",
                "    cargas[importacion]['llegadas'] = {t.strftime('%Y%m%d'): 0 for t in fechas}\n",
                "\n",
                "    cargas[importacion]['fecha_inicial'] = int(fecha.strftime('%Y%m%d'))\n",
                "    cargas[importacion]['fecha_final'] = int(fecha.strftime('%Y%m%d'))\n",
                "    # Agregar las variables de inventario\n",
                "    cargas[importacion]['inventario_al_final'] = dict()\n",
                "\n",
                "    for t in periodos:\n",
                "\n",
                "        var_name = f\"O_{importacion}_{t}\"\n",
                "        lp_var = pu.LpVariable(name=var_name,\n",
                "                               lowBound=0.0,\n",
                "                               upBound=inventario_puerto_df.loc[i]['cantidad_kg'],\n",
                "                               cat=pu.LpContinuous)\n",
                "        cargas[importacion]['inventario_al_final'][t] = lp_var"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "#### Costos de almacenamiento"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 18,
            "metadata": {},
            "outputs": [],
            "source": [
                "# Agregar costos de almacenamiento a cada carga\n",
                "for i in costos_almacenamiento_df.index:\n",
                "    importacion = str(\n",
                "        costos_almacenamiento_df.loc[i]['importacion']).replace(' ', '')\n",
                "    fecha = int(\n",
                "        costos_almacenamiento_df.loc[i]['fecha_corte'].strftime('%Y%m%d'))\n",
                "    valor_kg = costos_almacenamiento_df.loc[i]['valor_kg']\n",
                "\n",
                "    if importacion in cargas.keys():\n",
                "        if fecha in cargas[importacion]['costo_almacenamiento']:\n",
                "            cargas[importacion]['costo_almacenamiento'][fecha] += valor_kg"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "#### Costos de Bodegaje"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 19,
            "metadata": {},
            "outputs": [],
            "source": [
                "# Agregar costos de bodegaje cuando es un producto en tránsito a puerto a cada carga\n",
                "for importacion, carga in cargas.items():\n",
                "    index = ('bodega', carga['operador'],\n",
                "             carga['puerto'], carga['ingrediente'])\n",
                "    valor_kg = operaciones_portuarias_df.loc[index]['valor_kg']\n",
                "    if carga['fecha_inicial'] >= int(fechas[0].strftime('%Y%m%d')) and carga['fecha_final'] <= int(fechas[-1].strftime('%Y%m%d')):\n",
                "        carga['costo_almacenamiento'][carga['fecha_final']] += valor_kg"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "#### Costos intercompany"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 20,
            "metadata": {},
            "outputs": [],
            "source": [
                "intercompany_df = intercompany_df.melt(id_vars='origen',\n",
                "                                       value_vars=['contegral', 'finca'],\n",
                "                                       var_name='destino',\n",
                "                                       value_name='intercompany')\n",
                "\n",
                "intercompany_df.set_index(['origen', 'destino'], inplace=True)"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "#### Costos de transporte (fletes)"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 21,
            "metadata": {},
            "outputs": [],
            "source": [
                "# Encontrar el costo total de transporte por kilogramo\n",
                "fletes_df = fletes_df.melt(id_vars=['puerto', 'operador', 'ingrediente'],\n",
                "                           value_vars=list(plantas.keys()),\n",
                "                           value_name='costo_per_kg',\n",
                "                           var_name='planta')\n",
                "\n",
                "# Calcular valor del flete\n",
                "fletes_df['flete'] = cap_camion*fletes_df['costo_per_kg']\n",
                "\n",
                "fletes_df = pd.merge(left=fletes_df,\n",
                "                     right=plantas_df[['planta', 'empresa']],\n",
                "                     left_on='planta',\n",
                "                     right_on='planta')\n",
                "\n",
                "fletes_df.set_index(\n",
                "    ['puerto', 'operador', 'ingrediente', 'planta'], inplace=True)"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "#### Variables de Despacho"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 22,
            "metadata": {},
            "outputs": [
                {
                    "name": "stdout",
                    "output_type": "stream",
                    "text": [
                        "despachos entre 20240423 y 20240521\n"
                    ]
                }
            ],
            "source": [
                "# Tomar en cuenta solo los periodos relevantes\n",
                "periodo_final = periodos.index(periodos[-1])-lead_time+1\n",
                "\n",
                "print('despachos entre',\n",
                "      periodos[periodo_administrativo], 'y', periodos[periodo_final])\n",
                "# Informacion de transporte\n",
                "for importacion, carga in cargas.items():\n",
                "    puerto = carga['puerto']\n",
                "    operador = carga['operador']\n",
                "    ingrediente = carga['ingrediente']\n",
                "    costo_envio = dict()\n",
                "\n",
                "    for nombre_planta, planta in plantas.items():\n",
                "        empresa_destino = planta['empresa']\n",
                "        costo_intercompany = intercompany_df.loc[(\n",
                "            carga['empresa'], empresa_destino)]['intercompany']\n",
                "        valor_intercompany = cap_camion*carga['valor_cif']*(costo_intercompany)\n",
                "        flete = fletes_df.loc[(\n",
                "            puerto, operador, ingrediente, nombre_planta)]['flete']\n",
                "        valor_despacho_directo_kg = cap_camion * \\\n",
                "            operaciones_portuarias_df.loc[(\n",
                "                'directo', operador, puerto, ingrediente)]['valor_kg']\n",
                "\n",
                "        periodo_llegada = carga['fecha_inicial']\n",
                "\n",
                "        # Costo de flete\n",
                "        costo_envio[nombre_planta] = dict()\n",
                "        costo_envio[nombre_planta]['intercompany'] = costo_intercompany\n",
                "        costo_envio[nombre_planta]['flete'] = flete\n",
                "        costo_envio[nombre_planta]['cantidad_despacho'] = cap_camion\n",
                "        costo_envio[nombre_planta]['valor_intercompany'] = valor_intercompany\n",
                "        costo_envio[nombre_planta]['costo_despacho_directo'] = valor_despacho_directo_kg\n",
                "\n",
                "        costo_envio[nombre_planta]['costo_envio'] = dict()\n",
                "        costo_envio[nombre_planta]['tipo_envio'] = dict()\n",
                "        costo_envio[nombre_planta]['variable_despacho'] = dict()\n",
                "\n",
                "        # Descuento de almacenamiento en puerto\n",
                "        costo_envio[nombre_planta]['descuento_almacenamiento'] = dict()\n",
                "        costo_descuento_almacenamiento = 0.0\n",
                "        for periodo in periodos[::-1]:\n",
                "            if carga['costo_almacenamiento'][periodo] != 0.0:\n",
                "                costo_descuento_almacenamiento = carga['costo_almacenamiento'][periodo]\n",
                "            costo_envio[nombre_planta]['descuento_almacenamiento'][periodo] = costo_descuento_almacenamiento\n",
                "\n",
                "        # Calcular costo de envio\n",
                "        for periodo in periodos[periodo_administrativo:periodo_final]:\n",
                "            # Si el periodo esta entre la fecha de llegada, colocar operacion portuaria por despacho directo.\n",
                "            if periodo >= carga['fecha_inicial'] and periodo <= carga['fecha_final']:\n",
                "                costo_envio[nombre_planta]['costo_envio'][periodo] = valor_intercompany + \\\n",
                "                    flete + valor_despacho_directo_kg\n",
                "                costo_envio[nombre_planta]['tipo_envio'][periodo] = 'directo'\n",
                "\n",
                "            else:\n",
                "                costo_envio[nombre_planta]['costo_envio'][periodo] = valor_intercompany + flete\n",
                "                costo_envio[nombre_planta]['tipo_envio'][periodo] = 'indirecto'\n",
                "\n",
                "            # Variable de transporte\n",
                "\n",
                "            # Antes de crear las variables de transporte, es importante saber si la planta tiene consumo del ingrediente\n",
                "            if ingrediente in planta['inventarios'].keys():\n",
                "\n",
                "                consumo_total = sum(\n",
                "                    [c for p, c in planta['inventarios'][ingrediente]['consumo'].items()])\n",
                "\n",
                "                # Máxima capacidad de recepcion como límite superior para la variable\n",
                "                tiempo_total = planta['tiempo_total']\n",
                "                tiempo_ingrediente_por_camion = planta['tiempo_ingrediente'][ingrediente]\n",
                "\n",
                "                # máxima capacidad de recepcion\n",
                "                cantidad_camiones_admisibles = int(\n",
                "                    tiempo_total/tiempo_ingrediente_por_camion)\n",
                "\n",
                "                # Cantidad de llegadas\n",
                "                Llegadas = sum([v for p, v in carga['llegadas'].items()])\n",
                "\n",
                "                # Inventario inicial\n",
                "                inventario_inicial = carga['inventario_inicial']\n",
                "\n",
                "                # cuántos camiones se podrían despachar con el inventario existente más las llegadas:\n",
                "                if inventario_inicial + Llegadas > cap_camion:\n",
                "                    cantidad_camiones_despachables = int(\n",
                "                        (inventario_inicial + Llegadas)/cap_camion)\n",
                "                else:\n",
                "                    cantidad_camiones_despachables = 0\n",
                "\n",
                "                limite_superior_despacho = min(\n",
                "                    cantidad_camiones_admisibles, cantidad_camiones_despachables)\n",
                "\n",
                "                # if consumo_total > 0 y el periodo actual es mayor al de llegada\n",
                "                # (No tiene sentido agregar variable de desapcho si no hay qué despachar):\n",
                "                if consumo_total > cap_camion and periodo >= periodo_llegada and limite_superior_despacho > 0 == 0:\n",
                "\n",
                "                    transporte_var_name = f'T_{importacion}_{nombre_planta}_{periodo}'\n",
                "                    transporte_var = pu.LpVariable(name=transporte_var_name,\n",
                "                                                   lowBound=0,\n",
                "                                                   upBound=limite_superior_despacho,\n",
                "                                                   cat=pu.LpInteger)\n",
                "\n",
                "                    costo_envio[nombre_planta]['variable_despacho'][periodo] = transporte_var\n",
                "\n",
                "                    # Colocar la variable en la planta dos periodos despues\n",
                "                    periodo_llegada_a_planta = periodos[periodos.index(\n",
                "                        periodo)+lead_time]\n",
                "                    plantas[nombre_planta]['inventarios'][ingrediente]['llegadas'][periodo_llegada_a_planta].append(\n",
                "                        transporte_var)\n",
                "\n",
                "        carga['costo_despacho'] = costo_envio"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 23,
            "metadata": {},
            "outputs": [
                {
                    "name": "stdout",
                    "output_type": "stream",
                    "text": [
                        "28897\n"
                    ]
                }
            ],
            "source": [
                "var_count = 0\n",
                "for carga in cargas.keys():\n",
                "    for planta in cargas[carga]['costo_despacho'].keys():\n",
                "        var_count += len(cargas[carga]['costo_despacho']\n",
                "                         [planta]['variable_despacho'].values())\n",
                "print(var_count)\n",
                "# Actualmente 16902 variables con consumos completos"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 24,
            "metadata": {},
            "outputs": [],
            "source": [
                "clusters_dict = {\n",
                "    'importacion': list(),\n",
                "    'puerto': list(),\n",
                "    'ingrediente': list(),\n",
                "    'planta': list(),\n",
                "    'periodo': list(),\n",
                "    'costo_almacenamiento': list(),\n",
                "    'costo_despacho': list()\n",
                "}"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Cluster de Cargas"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 25,
            "metadata": {},
            "outputs": [],
            "source": [
                "for importacion in cargas.keys():\n",
                "    for planta in plantas.keys():\n",
                "        if planta in cargas[importacion]['costo_despacho'].keys():\n",
                "            for periodo in periodos:\n",
                "                if periodo in cargas[importacion]['costo_despacho'][planta]['costo_envio'].keys():\n",
                "\n",
                "                    costo_despacho = cargas[importacion]['costo_despacho'][planta]['costo_envio'][periodo]\n",
                "                    costo_almacenamiento = cargas[importacion]['costo_almacenamiento'][periodo]\n",
                "                    ingrediente = cargas[importacion]['ingrediente']\n",
                "                    puerto = cargas[importacion]['puerto']\n",
                "\n",
                "                    clusters_dict['importacion'].append(importacion)\n",
                "                    clusters_dict['puerto'].append(puerto)\n",
                "                    clusters_dict['ingrediente'].append(ingrediente)\n",
                "                    clusters_dict['planta'].append(planta)\n",
                "                    clusters_dict['periodo'].append(periodo)\n",
                "                    clusters_dict['costo_almacenamiento'].append(\n",
                "                        costo_almacenamiento)\n",
                "                    clusters_dict['costo_despacho'].append(costo_despacho)\n",
                "clusters_df = pd.DataFrame(clusters_dict)"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 26,
            "metadata": {},
            "outputs": [],
            "source": [
                "def asignar_etiquetas(df: pd.DataFrame, column_name: str, n_clusters=3):\n",
                "    # Copiamos el DataFrame para no modificar el original\n",
                "    df_resultado = df.copy()\n",
                "\n",
                "    # Instanciar el modelo KMeans\n",
                "    kmeans = KMeans(n_clusters=3,\n",
                "                    init='random',\n",
                "                    n_init=10,\n",
                "                    max_iter=300,\n",
                "                    random_state=0)\n",
                "\n",
                "    # Ajustar el modelo a los datos\n",
                "    kmeans.fit(np.array(df[column_name]).reshape(-1, 1))\n",
                "\n",
                "    # Obtener las etiquetas de los clusters\n",
                "    labels = kmeans.labels_\n",
                "\n",
                "    # Agregar las etiquetas al DataFrame\n",
                "    df_resultado['cluster'] = labels\n",
                "\n",
                "    # Calcular los centroides\n",
                "    centroids = kmeans.cluster_centers_\n",
                "\n",
                "    # Calcular los límites de los clusters\n",
                "    limits = [df[labels == i].describe() for i in range(n_clusters)]\n",
                "\n",
                "    # Asignar etiquetas de 'alto', 'medio' y 'bajo'\n",
                "    for i in range(n_clusters):\n",
                "        df_resultado.loc[df_resultado['cluster'] == i, 'etiqueta'] = (\n",
                "            'alto' if centroids[i] == max(centroids) else\n",
                "            'bajo' if centroids[i] == min(centroids) else\n",
                "            'medio'\n",
                "        )\n",
                "\n",
                "    return df_resultado"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 27,
            "metadata": {},
            "outputs": [],
            "source": [
                "importaciones_list = list()\n",
                "for importacion in cargas.keys():\n",
                "\n",
                "    df = clusters_df[clusters_df['importacion'] == importacion]\n",
                "\n",
                "    cantidad_valores_unicos = len(df['costo_despacho'].unique())\n",
                "\n",
                "    temp = asignar_etiquetas(df=df, column_name='costo_despacho')\n",
                "\n",
                "    importaciones_list.append(temp)\n",
                "\n",
                "# Unir los Datasets\n",
                "clusters_df = pd.concat(importaciones_list)\n",
                "\n",
                "# Crear indices\n",
                "clusters_df.set_index(['importacion', 'planta', 'periodo'], inplace=True)"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "# Inicializacion de variables"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 28,
            "metadata": {},
            "outputs": [],
            "source": [
                "for importacion, carga in cargas.items():\n",
                "    for planta in plantas.keys():\n",
                "        if planta in carga['costo_despacho'].keys():\n",
                "            for periodo, variable in carga['costo_despacho'][planta]['variable_despacho'].items():\n",
                "                variable.setInitialValue(0)"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 29,
            "metadata": {},
            "outputs": [],
            "source": [
                "for importacion, carga in cargas.items():\n",
                "    inventario_final = carga['inventario_inicial']\n",
                "    llegadas = 0.0\n",
                "    for periodo in periodos:\n",
                "        llegadas = 0.0\n",
                "        if periodo in carga['llegadas'].keys():\n",
                "            llegadas = carga['llegadas'][periodo]\n",
                "        inventario_final += llegadas\n",
                "\n",
                "        carga['inventario_al_final'][periodo].setInitialValue(inventario_final)"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "# Modelo matemático"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Sets:\n",
                "\n",
                "$t$: periodos con $t \\in T$\n",
                "\n",
                "$p$: productos con $p \\in P$\n",
                "\n",
                "$i$: cargas con $i \\in T$\n",
                "\n",
                "$j$: plantas con $j \\in J$"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "\n",
                "## Parametros:\n",
                "\n",
                "$CB:$ Costo de backorder por día\n",
                "\n",
                "$CT_{ij}$: Costo de transportar la carga $i$ hacia la planta $j$\n",
                "\n",
                "$CA_{it}$: Costo de mantener la carga $i$ almacenada al final del periodo $p$\n",
                "\n",
                "$AR_{it}$: Cantidad de producto llegando a la carga $i$ durante el periodo $p$\n",
                "\n",
                "$DM_{pjt}$: Demanda del producto $p$ en la planta $j$ durante el periodo $t$\n",
                "\n",
                "$CP_{pjt}$: Capacidad de almacenar el producto $p$ en la planta $j$\n",
                "\n",
                "$IP_{i}$: Inventario inicial de la carga $i$\n",
                "\n",
                "$TJ_{pjt}$: Cantidad programada del producto $p$ llegando a la planta $j$ durante el periodo $t$ \n",
                "\n",
                "$IJ_{pj}$: Inventario inicial de producto $p$ en la planta $j$ \n",
                "\n",
                "$MI_{pjt}$: Inventario mínimo a mantener del producto $p$ en la planta $j$ al final del periodo $t$\n",
                "\n",
                "$MX_{pjt}$: Inventario máximo a mantener del producto $p$ en la planta $j$ al final del periodo $t$\n"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "\n",
                "## Variables:\n",
                "\n",
                "$T_{ijt}$: Variable entera, Cantidad de camiones de 34 Toneladas a despachar de la carga $i$ hasta la planta $j$ durante el periodo $t$\n",
                "\n",
                "$O_{it}$: Continua, Cantidad de toneladas de la carga $i$ almacenadas al final del periodo $t$\n",
                "\n",
                "$I_{pjt}$: Cantidad del producto $p$ almacenado en la planta $j$ al final del periodo $t$\n",
                "\n",
                "$B_{pjt}$: Cantidad del producto $p$ de backorder en la planta $j$ al final del periodo $t$\n",
                "\n",
                "$S_{pjt}$: Cantidad del producto $p$ por debajo del SS en la planta $j$ al final del periodo $t$\n",
                "\n",
                "$M_{pjt}$: Unidades de exceso del producto $p$ en la planta $j$ al final del periodo $t$ sobre el inventario objetivo\n",
                "\n",
                "$X_{pjt}$: Unidades por debajo del producto $p$ en la planta $j$ al final del periodo $t$ bajo el inventario objetivo\n"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "\n",
                "## Funcion Objetivo:\n",
                "\n",
                "$$min \\sum_{i}\\sum_{j}\\sum_{t}{CT_{ijt}*T_{ijt}} + \\sum_{i}\\sum_{t}CA_{it}O_{it} + \\sum_{pjt}{CB*B}  + PP \\sum_{M}\\sum_{P}\\sum_{J}{M_{mpj}} + PP \\sum_{M}\\sum_{P}\\sum_{J}{X_{mpj}}$$"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 30,
            "metadata": {},
            "outputs": [],
            "source": [
                "funcion_objetivo = list()"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### Costo por transporte\n",
                "\n",
                "El costo del transporte esta dado por el producto escalar entre los costos de envio, que ya incluyen fletes, costos porturarios y costos intercompany\n",
                "\n",
                "$$\\sum_{i}\\sum_{j}\\sum_{t}{CT_{ijt}*T_{ijt}}$$"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 31,
            "metadata": {},
            "outputs": [],
            "source": [
                "for periodo in periodos:\n",
                "    for impo, carga in cargas.items():\n",
                "        for nombre_planta, planta in plantas.items():\n",
                "            if periodo in carga['costo_despacho'][nombre_planta]['variable_despacho'].keys():\n",
                "                # CT_ijt*T_ijt\n",
                "                # + periodos.index(periodo)\n",
                "                costo_envio = carga['costo_despacho'][nombre_planta]['costo_envio'][periodo]\n",
                "                costo_almacenamiento = carga['costo_despacho']['envigado']['descuento_almacenamiento'][periodo]*cap_camion\n",
                "                var_envio = carga['costo_despacho'][nombre_planta]['variable_despacho'][periodo]\n",
                "                funcion_objetivo.append(\n",
                "                    (costo_envio-costo_almacenamiento)*var_envio)"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### Costo por almacenamiento en puerto (Se ha incluido como descuento en el costo de transporte)\n",
                "\n",
                "El costo por almacenamiento esta dado por el producto escalar entre los costos de almacenamiento que incluyen el costo el costo de operacion portuaria de llevar el material desde el barco hasta la bodega y, la tarifa por almacenamiento que se paga periódicamente luego de los días libres. \n",
                "\n",
                "*Sin embargo, cada vez que se envia un camion hacia cualquier planta, es un camion de producto menos que se cuenta como costo de almacenamiento, por lo que ya no es necesario incluir el costo de almacenamiento en la función objetivo.*\n",
                "\n",
                "$$\\sum_{i}\\sum_{t}CA_{it}O_{it}$$"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "for periodo in periodos:\n",
                "    for impo, carga in cargas.items():\n",
                "        costo_almaenamiento = carga['costo_almacenamiento'][periodo]\n",
                "        inventario_al_final = carga['inventario_al_final'][periodo]\n",
                "        if costo_almaenamiento > 0:\n",
                "            funcion_objetivo.append(costo_almaenamiento*inventario_al_final)\n",
                "        # else:\n",
                "        #    funcion_objetivo.append(0.5*inventario_al_final)"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### Costo de Backorder\n",
                "\n",
                "El costo por backorder es una penalización a la función objetivo, donde se carga un valor determinado por cada kilogramo de material que no esté disponible para el consumo\n",
                "\n",
                "$\\sum_{pjt}{CB*B}$"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 32,
            "metadata": {},
            "outputs": [],
            "source": [
                "for nombre_planta, planta in plantas.items():\n",
                "    for nombre_ingrediente, ingrediente in planta['inventarios'].items():\n",
                "        for periodo, var in ingrediente['backorder'].items():\n",
                "            # if periodo in periodos[periodo_administrativo:]:\n",
                "            funcion_objetivo.append(costo_backorder_dia*var)"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {
                "jp-MarkdownHeadingCollapsed": true
            },
            "source": [
                "### Costo por no alcanzar el inventario de seguridad"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 33,
            "metadata": {},
            "outputs": [],
            "source": [
                "for nombre_planta, planta in plantas.items():\n",
                "    for nombre_ingrediente, ingrediente in planta['inventarios'].items():\n",
                "        if 'safety_stock' in planta['inventarios'][nombre_ingrediente].keys():\n",
                "            for periodo, var in ingrediente['safety_stock'].items():\n",
                "                # if periodo in periodos[periodo_administrativo:]:\n",
                "                funcion_objetivo.append(costo_safety_stock*var)"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### Costo por exceder capacidad de almacenamiento"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "for nombre_planta, planta in plantas.items():\n",
                "    for nombre_ingrediente, ingrediente in planta['inventarios'].items():\n",
                "        for periodo, var in ingrediente['exceso_capacidad'].items():\n",
                "            if periodo in periodos[periodo_administrativo:]:\n",
                "                funcion_objetivo.append(costo_exceso_capacidad*var)"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Restricciones:"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "\n",
                "### Balance de masa en cargas\n",
                "\n",
                "El inventario al final del periodo es igual a:\n",
                "\n",
                "- el inventario al final del periodo anterior;\n",
                "- más las llegadas planeadas;\n",
                "- menos los despachos hacia plantas\n",
                "\n",
                "$$ O_{it} =  O_{i(t-1)} + AR_{it} - 34000\\sum_{J}{T_{ijt}} \\hspace{1cm} \\forall i \\in I, t \\in T$$"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 34,
            "metadata": {},
            "outputs": [],
            "source": [
                "rest_balance_masa_puerto = list()\n",
                "\n",
                "for importacion, carga in cargas.items():\n",
                "    for periodo in periodos:\n",
                "\n",
                "        left = list()\n",
                "        right = list()\n",
                "\n",
                "        # Oit\n",
                "        Oit = carga['inventario_al_final'][periodo]\n",
                "        left.append(Oit)\n",
                "\n",
                "        # Oi(t-1)\n",
                "        if periodo == periodos[0]:\n",
                "            Oitant = carga['inventario_inicial']\n",
                "        else:\n",
                "            t_anterior = periodos[periodos.index(periodo)-1]\n",
                "            Oitant = carga['inventario_al_final'][t_anterior]\n",
                "        right.append(Oitant)\n",
                "\n",
                "        # ARit\n",
                "        if periodo in carga['llegadas'].keys():\n",
                "            ar = carga['llegadas'][periodo]\n",
                "            right.append(ar)\n",
                "\n",
                "        # - 34000*Sum(Tijt)\n",
                "        for planta, despacho in carga['costo_despacho'].items():\n",
                "            if periodo in despacho['variable_despacho'].keys():\n",
                "                var_despacho = despacho['variable_despacho'][periodo]\n",
                "                left.append(cap_camion*var_despacho)\n",
                "\n",
                "        name = f'balance_masa_{importacion}_al_final_de_{periodo}'\n",
                "        rest = (pu.lpSum(left) == pu.lpSum(right), name)\n",
                "\n",
                "        rest_balance_masa_puerto.append(rest)"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### Balance de masa en plantas\n",
                "\n",
                "El inventario en planta al final del periodo es igual a:\n",
                "\n",
                "- el inventario al final del periodo anterior;\n",
                "- más las llegadas ya programadas;\n",
                "- más las llegadas planeadas;\n",
                "- menos la demanda\n",
                "- más el backorder, que compensa cuando el inventario más las llegadas no son suficientes\n",
                "\n",
                "$$ I_{pjt} = I_{pj(t-1)} + TJ_{pjt} + \\sum_{i}{T_{ij(t-2)}} -  DM_{pjt} + B_{pjt} \\hspace{1cm} \\forall p \\in P, j \\in J, t \\in T$$\n"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 35,
            "metadata": {},
            "outputs": [],
            "source": [
                "rest_balance_masa_planta = list()\n",
                "for nombre_planta, planta in plantas.items():\n",
                "    for nombre_ingrediente, ingrediente in planta['inventarios'].items():\n",
                "\n",
                "        for periodo in periodos:\n",
                "\n",
                "            if periodo in ingrediente['inventario_final'].keys():\n",
                "\n",
                "                left = list()\n",
                "                right = list()\n",
                "\n",
                "                # Ipjt\n",
                "                Spjt = ingrediente['inventario_final'][periodo]\n",
                "                left.append(Spjt)\n",
                "\n",
                "                # Ipj(t-1)\n",
                "                if periodo == periodos[0]:\n",
                "                    Ipj_tanterior = ingrediente['inventario_final'][periodo_anterior]\n",
                "                else:\n",
                "                    p_anterior = periodos[periodos.index(periodo)-1]\n",
                "                    Ipj_tanterior = ingrediente['inventario_final'][p_anterior]\n",
                "\n",
                "                right.append(Ipj_tanterior)\n",
                "\n",
                "                # + TJ\n",
                "\n",
                "                # + Tijt\n",
                "                if periodo in ingrediente['llegadas'].keys():\n",
                "                    for llegada_planeada_var in ingrediente['llegadas'][periodo]:\n",
                "                        if type(llegada_planeada_var) == pu.LpVariable:\n",
                "                            right.append(cap_camion*llegada_planeada_var)\n",
                "                        else:\n",
                "                            right.append(llegada_planeada_var)\n",
                "\n",
                "                # - DMpjt\n",
                "\n",
                "                if periodo in ingrediente['consumo'].keys():\n",
                "                    DMpjt = ingrediente['consumo'][periodo]\n",
                "                    left.append(DMpjt)\n",
                "\n",
                "                # + Baclorder\n",
                "                if periodo in ingrediente['backorder'].keys():\n",
                "                    bak_var = ingrediente['backorder'][periodo]\n",
                "                    right.append(bak_var)\n",
                "\n",
                "                name = f'balance_planta_{nombre_planta}_de_{nombre_ingrediente}_al_final_de_{periodo}'\n",
                "                rest = (pu.lpSum(left) == pu.lpSum(right), name)\n",
                "\n",
                "                rest_balance_masa_planta.append(rest)"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### Capacidad de recepción por planta\n",
                "\n",
                "En una planta y un periodo en particular, la suma del producto entre el tiempo del ingrediente y la cantidad de camiones llegando no debe superar el tiempo total disponible en la planta\n",
                "\n",
                "$$ \\sum_{I}{TiempoIngrediente_{pj}*T_{ijt}} \\leq TiempoTotal_{t} \\hspace{1cm} \\forall p \\in P, t \\in T$$"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 36,
            "metadata": {},
            "outputs": [],
            "source": [
                "rest_llegada_material = list()\n",
                "for nombre_planta, planta in plantas.items():\n",
                "    tiempo_total = planta['tiempo_total']\n",
                "    for periodo in periodos:\n",
                "        left_expresion = list()\n",
                "        for ingrediente, parametros in planta['inventarios'].items():\n",
                "            tiempo_ingrediente_por_camion = planta['tiempo_ingrediente'][ingrediente]\n",
                "            if periodo in parametros['llegadas'].keys():\n",
                "                for var_llegada in parametros['llegadas'][periodo]:\n",
                "                    left_expresion.append(\n",
                "                        tiempo_ingrediente_por_camion*var_llegada)\n",
                "\n",
                "        # omitir restricciones sin expresiones al lado izquiero\n",
                "        if len(left_expresion) > 0:\n",
                "            rest_name = f'Llegada_material_{nombre_planta}_durante_{periodo}'\n",
                "            rest = (pu.lpSum(left_expresion) <= tiempo_total, rest_name)\n",
                "            rest_llegada_material.append(rest)"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### Capacidad de almacenamiento\n",
                "\n",
                "$$ I_{pjt} \\leq CP_{pj} + M_{pjt} \\hspace{1cm} \\forall p \\in P, t \\in T$$"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "rest_capacidad_almacenamiento = list()\n",
                "for nombre_planta, planta in plantas.items():\n",
                "    for ingrediente, inventarios in planta['inventarios'].items():\n",
                "        CPpj = inventarios['capacidad']\n",
                "        for periodo, inventario_final_var in inventarios['inventario_final'].items():\n",
                "            if type(inventario_final_var) == pu.LpVariable:\n",
                "                rest_name = f'capacidad_almacenamiento_{nombre_planta}_de_{ingrediente}_en_{periodo}'\n",
                "                # if periodo in inventarios['exceso_capacidad'].keys():\n",
                "                Mpjt = inventarios['exceso_capacidad'][periodo]\n",
                "                rest = (inventario_final_var <= CPpj + Mpjt, rest_name)\n",
                "                # else:\n",
                "               #     rest = (inventario_final_var <= CPpj, rest_name)\n",
                "                rest_capacidad_almacenamiento.append(rest)"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### No superar el inventario máximo\n",
                "\n",
                "El inventario al final de un día cualquiera debe estar bajo el nivel máximo, por lo que penalizaremos en la función objetivo una variable de holgura para tal efecto\n",
                "$$ I_{pjt} \\leq MX_{pjt} + M_{pjt} \\hspace{1cm} \\forall p \\in P, j \\in J, t \\in T$$"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### Superar el inventario de seguridad\n",
                "\n",
                "El inventario al final de un día cualquiera debe estar bajo el nivel máximo, por lo que penalizaremos en la función objetivo una variable de holgura para tal efecto\n",
                "$$ I_{pjt} \\geq MX_{pjt} + M_{pjt} \\hspace{1cm} \\forall p \\in P, j \\in J, t \\in T$$"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 37,
            "metadata": {},
            "outputs": [],
            "source": [
                "rest_safety_stock = list()\n",
                "for nombre_planta, planta in plantas.items():\n",
                "    for ingrediente, inventarios in planta['inventarios'].items():\n",
                "        if 'safety_stock_kg' in inventarios.keys():\n",
                "            SS = inventarios['safety_stock_kg']\n",
                "            # for periodo, variable in inventarios['inventario_final'].items():\n",
                "            if len(inventarios['safety_stock'].keys()) > 0:\n",
                "                for periodo in periodos:\n",
                "                    rest_name = f'safety_stock_en_{nombre_planta}_de_{ingrediente}_durante_{periodo}'\n",
                "                    Ipjt = inventarios['inventario_final'][periodo]\n",
                "                    Spij = inventarios['safety_stock'][periodo]\n",
                "\n",
                "                    rest = (Ipjt + Spij >= SS, rest_name)\n",
                "                    rest_safety_stock.append(rest)"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### Superar el inventario objetivo al final del mes"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 38,
            "metadata": {},
            "outputs": [],
            "source": [
                "rest_inventario_objetivo = list()\n",
                "for nombre_planta, planta in plantas.items():\n",
                "    for ingrediente, inventarios in planta['inventarios'].items():\n",
                "        if 'objetivo_kg' in inventarios.keys():\n",
                "\n",
                "            target = inventarios['objetivo_kg']\n",
                "            if target > 0:\n",
                "                rest_name = f'objetivo_en_{nombre_planta}_de_{ingrediente}_al_final_de_{periodos[periodo_final]}'\n",
                "                Ipjt = inventarios['inventario_final'][periodos[periodo_final]]\n",
                "\n",
                "                rest = (Ipjt >= target, rest_name)\n",
                "                rest_inventario_objetivo.append(rest)"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "# Resolviendo el modelo"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Generando modelo"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 39,
            "metadata": {},
            "outputs": [],
            "source": [
                "problema = pu.LpProblem(name='Bios_Solver', sense=pu.LpMinimize)\n",
                "\n",
                "# Agregando funcion objetivo\n",
                "problema += pu.lpSum(funcion_objetivo)\n",
                "\n",
                "# Agregando balance de masa puerto\n",
                "for rest in rest_balance_masa_puerto:\n",
                "    problema += rest\n",
                "\n",
                "# Agregando balande ce masa en planta\n",
                "for rest in rest_balance_masa_planta:\n",
                "    problema += rest\n",
                "\n",
                "# Agregando capacidad de recepcion\n",
                "for rest in rest_llegada_material:\n",
                "    problema += rest\n",
                "\n",
                "# Agregando capacidad de almacenamiento\n",
                "# for rest in rest_capacidad_almacenamiento:\n",
                "#     problema += rest\n",
                "\n",
                "# Agregando inventario de seguridad\n",
                "for rest in rest_safety_stock:\n",
                "    problema += rest\n",
                "\n",
                "# Agregando inventario objetivo\n",
                "for rest in rest_inventario_objetivo:\n",
                "    problema += rest"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Ejecutando modelo"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 40,
            "metadata": {},
            "outputs": [
                {
                    "name": "stdout",
                    "output_type": "stream",
                    "text": [
                        "cpu count 15\n",
                        "tiempo limite 360 minutos\n",
                        "ejecutando  31 periodos\n",
                        "GAP tolerable 5000000 millones de pesos\n"
                    ]
                },
                {
                    "ename": "KeyboardInterrupt",
                    "evalue": "",
                    "output_type": "error",
                    "traceback": [
                        "\u001b[0;31m---------------------------------------------------------------------------\u001b[0m",
                        "\u001b[0;31mKeyboardInterrupt\u001b[0m                         Traceback (most recent call last)",
                        "Cell \u001b[0;32mIn[40], line 14\u001b[0m\n\u001b[1;32m      5\u001b[0m \u001b[38;5;28mprint\u001b[39m(\u001b[38;5;124m'\u001b[39m\u001b[38;5;124mGAP tolerable\u001b[39m\u001b[38;5;124m'\u001b[39m, gap, \u001b[38;5;124m'\u001b[39m\u001b[38;5;124mmillones de pesos\u001b[39m\u001b[38;5;124m'\u001b[39m)\n\u001b[1;32m      6\u001b[0m engine \u001b[38;5;241m=\u001b[39m pu\u001b[38;5;241m.\u001b[39mPULP_CBC_CMD(\n\u001b[1;32m      7\u001b[0m     timeLimit\u001b[38;5;241m=\u001b[39m\u001b[38;5;241m60\u001b[39m\u001b[38;5;241m*\u001b[39mt_limit_minutes,\n\u001b[1;32m      8\u001b[0m     gapAbs\u001b[38;5;241m=\u001b[39mgap,\n\u001b[0;32m   (...)\u001b[0m\n\u001b[1;32m     11\u001b[0m     presolve\u001b[38;5;241m=\u001b[39m\u001b[38;5;28;01mTrue\u001b[39;00m,\n\u001b[1;32m     12\u001b[0m     threads\u001b[38;5;241m=\u001b[39mcpu_count)\n\u001b[0;32m---> 14\u001b[0m \u001b[43mproblema\u001b[49m\u001b[38;5;241;43m.\u001b[39;49m\u001b[43msolve\u001b[49m\u001b[43m(\u001b[49m\u001b[43msolver\u001b[49m\u001b[38;5;241;43m=\u001b[39;49m\u001b[43mengine\u001b[49m\u001b[43m)\u001b[49m\n\u001b[1;32m     15\u001b[0m \u001b[38;5;66;03m# problema.solve()\u001b[39;00m\n",
                        "File \u001b[0;32m~/Documents/source_code/bios/env/lib/python3.11/site-packages/pulp/pulp.py:1883\u001b[0m, in \u001b[0;36mLpProblem.solve\u001b[0;34m(self, solver, **kwargs)\u001b[0m\n\u001b[1;32m   1881\u001b[0m \u001b[38;5;66;03m# time it\u001b[39;00m\n\u001b[1;32m   1882\u001b[0m \u001b[38;5;28mself\u001b[39m\u001b[38;5;241m.\u001b[39mstartClock()\n\u001b[0;32m-> 1883\u001b[0m status \u001b[38;5;241m=\u001b[39m \u001b[43msolver\u001b[49m\u001b[38;5;241;43m.\u001b[39;49m\u001b[43mactualSolve\u001b[49m\u001b[43m(\u001b[49m\u001b[38;5;28;43mself\u001b[39;49m\u001b[43m,\u001b[49m\u001b[43m \u001b[49m\u001b[38;5;241;43m*\u001b[39;49m\u001b[38;5;241;43m*\u001b[39;49m\u001b[43mkwargs\u001b[49m\u001b[43m)\u001b[49m\n\u001b[1;32m   1884\u001b[0m \u001b[38;5;28mself\u001b[39m\u001b[38;5;241m.\u001b[39mstopClock()\n\u001b[1;32m   1885\u001b[0m \u001b[38;5;28mself\u001b[39m\u001b[38;5;241m.\u001b[39mrestoreObjective(wasNone, dummyVar)\n",
                        "File \u001b[0;32m~/Documents/source_code/bios/env/lib/python3.11/site-packages/pulp/apis/coin_api.py:112\u001b[0m, in \u001b[0;36mCOIN_CMD.actualSolve\u001b[0;34m(self, lp, **kwargs)\u001b[0m\n\u001b[1;32m    110\u001b[0m \u001b[38;5;28;01mdef\u001b[39;00m \u001b[38;5;21mactualSolve\u001b[39m(\u001b[38;5;28mself\u001b[39m, lp, \u001b[38;5;241m*\u001b[39m\u001b[38;5;241m*\u001b[39mkwargs):\n\u001b[1;32m    111\u001b[0m \u001b[38;5;250m    \u001b[39m\u001b[38;5;124;03m\"\"\"Solve a well formulated lp problem\"\"\"\u001b[39;00m\n\u001b[0;32m--> 112\u001b[0m     \u001b[38;5;28;01mreturn\u001b[39;00m \u001b[38;5;28;43mself\u001b[39;49m\u001b[38;5;241;43m.\u001b[39;49m\u001b[43msolve_CBC\u001b[49m\u001b[43m(\u001b[49m\u001b[43mlp\u001b[49m\u001b[43m,\u001b[49m\u001b[43m \u001b[49m\u001b[38;5;241;43m*\u001b[39;49m\u001b[38;5;241;43m*\u001b[39;49m\u001b[43mkwargs\u001b[49m\u001b[43m)\u001b[49m\n",
                        "File \u001b[0;32m~/Documents/source_code/bios/env/lib/python3.11/site-packages/pulp/apis/coin_api.py:178\u001b[0m, in \u001b[0;36mCOIN_CMD.solve_CBC\u001b[0;34m(self, lp, use_mps)\u001b[0m\n\u001b[1;32m    176\u001b[0m \u001b[38;5;28;01melse\u001b[39;00m:\n\u001b[1;32m    177\u001b[0m     cbc \u001b[38;5;241m=\u001b[39m subprocess\u001b[38;5;241m.\u001b[39mPopen(args, stdout\u001b[38;5;241m=\u001b[39mpipe, stderr\u001b[38;5;241m=\u001b[39mpipe, stdin\u001b[38;5;241m=\u001b[39mdevnull)\n\u001b[0;32m--> 178\u001b[0m \u001b[38;5;28;01mif\u001b[39;00m \u001b[43mcbc\u001b[49m\u001b[38;5;241;43m.\u001b[39;49m\u001b[43mwait\u001b[49m\u001b[43m(\u001b[49m\u001b[43m)\u001b[49m \u001b[38;5;241m!=\u001b[39m \u001b[38;5;241m0\u001b[39m:\n\u001b[1;32m    179\u001b[0m     \u001b[38;5;28;01mif\u001b[39;00m pipe:\n\u001b[1;32m    180\u001b[0m         pipe\u001b[38;5;241m.\u001b[39mclose()\n",
                        "File \u001b[0;32m/Library/Frameworks/Python.framework/Versions/3.11/lib/python3.11/subprocess.py:1264\u001b[0m, in \u001b[0;36mPopen.wait\u001b[0;34m(self, timeout)\u001b[0m\n\u001b[1;32m   1262\u001b[0m     endtime \u001b[38;5;241m=\u001b[39m _time() \u001b[38;5;241m+\u001b[39m timeout\n\u001b[1;32m   1263\u001b[0m \u001b[38;5;28;01mtry\u001b[39;00m:\n\u001b[0;32m-> 1264\u001b[0m     \u001b[38;5;28;01mreturn\u001b[39;00m \u001b[38;5;28;43mself\u001b[39;49m\u001b[38;5;241;43m.\u001b[39;49m\u001b[43m_wait\u001b[49m\u001b[43m(\u001b[49m\u001b[43mtimeout\u001b[49m\u001b[38;5;241;43m=\u001b[39;49m\u001b[43mtimeout\u001b[49m\u001b[43m)\u001b[49m\n\u001b[1;32m   1265\u001b[0m \u001b[38;5;28;01mexcept\u001b[39;00m \u001b[38;5;167;01mKeyboardInterrupt\u001b[39;00m:\n\u001b[1;32m   1266\u001b[0m     \u001b[38;5;66;03m# https://bugs.python.org/issue25942\u001b[39;00m\n\u001b[1;32m   1267\u001b[0m     \u001b[38;5;66;03m# The first keyboard interrupt waits briefly for the child to\u001b[39;00m\n\u001b[1;32m   1268\u001b[0m     \u001b[38;5;66;03m# exit under the common assumption that it also received the ^C\u001b[39;00m\n\u001b[1;32m   1269\u001b[0m     \u001b[38;5;66;03m# generated SIGINT and will exit rapidly.\u001b[39;00m\n\u001b[1;32m   1270\u001b[0m     \u001b[38;5;28;01mif\u001b[39;00m timeout \u001b[38;5;129;01mis\u001b[39;00m \u001b[38;5;129;01mnot\u001b[39;00m \u001b[38;5;28;01mNone\u001b[39;00m:\n",
                        "File \u001b[0;32m/Library/Frameworks/Python.framework/Versions/3.11/lib/python3.11/subprocess.py:2046\u001b[0m, in \u001b[0;36mPopen._wait\u001b[0;34m(self, timeout)\u001b[0m\n\u001b[1;32m   2044\u001b[0m \u001b[38;5;28;01mif\u001b[39;00m \u001b[38;5;28mself\u001b[39m\u001b[38;5;241m.\u001b[39mreturncode \u001b[38;5;129;01mis\u001b[39;00m \u001b[38;5;129;01mnot\u001b[39;00m \u001b[38;5;28;01mNone\u001b[39;00m:\n\u001b[1;32m   2045\u001b[0m     \u001b[38;5;28;01mbreak\u001b[39;00m  \u001b[38;5;66;03m# Another thread waited.\u001b[39;00m\n\u001b[0;32m-> 2046\u001b[0m (pid, sts) \u001b[38;5;241m=\u001b[39m \u001b[38;5;28;43mself\u001b[39;49m\u001b[38;5;241;43m.\u001b[39;49m\u001b[43m_try_wait\u001b[49m\u001b[43m(\u001b[49m\u001b[38;5;241;43m0\u001b[39;49m\u001b[43m)\u001b[49m\n\u001b[1;32m   2047\u001b[0m \u001b[38;5;66;03m# Check the pid and loop as waitpid has been known to\u001b[39;00m\n\u001b[1;32m   2048\u001b[0m \u001b[38;5;66;03m# return 0 even without WNOHANG in odd situations.\u001b[39;00m\n\u001b[1;32m   2049\u001b[0m \u001b[38;5;66;03m# http://bugs.python.org/issue14396.\u001b[39;00m\n\u001b[1;32m   2050\u001b[0m \u001b[38;5;28;01mif\u001b[39;00m pid \u001b[38;5;241m==\u001b[39m \u001b[38;5;28mself\u001b[39m\u001b[38;5;241m.\u001b[39mpid:\n",
                        "File \u001b[0;32m/Library/Frameworks/Python.framework/Versions/3.11/lib/python3.11/subprocess.py:2004\u001b[0m, in \u001b[0;36mPopen._try_wait\u001b[0;34m(self, wait_flags)\u001b[0m\n\u001b[1;32m   2002\u001b[0m \u001b[38;5;250m\u001b[39m\u001b[38;5;124;03m\"\"\"All callers to this function MUST hold self._waitpid_lock.\"\"\"\u001b[39;00m\n\u001b[1;32m   2003\u001b[0m \u001b[38;5;28;01mtry\u001b[39;00m:\n\u001b[0;32m-> 2004\u001b[0m     (pid, sts) \u001b[38;5;241m=\u001b[39m \u001b[43mos\u001b[49m\u001b[38;5;241;43m.\u001b[39;49m\u001b[43mwaitpid\u001b[49m\u001b[43m(\u001b[49m\u001b[38;5;28;43mself\u001b[39;49m\u001b[38;5;241;43m.\u001b[39;49m\u001b[43mpid\u001b[49m\u001b[43m,\u001b[49m\u001b[43m \u001b[49m\u001b[43mwait_flags\u001b[49m\u001b[43m)\u001b[49m\n\u001b[1;32m   2005\u001b[0m \u001b[38;5;28;01mexcept\u001b[39;00m \u001b[38;5;167;01mChildProcessError\u001b[39;00m:\n\u001b[1;32m   2006\u001b[0m     \u001b[38;5;66;03m# This happens if SIGCLD is set to be ignored or waiting\u001b[39;00m\n\u001b[1;32m   2007\u001b[0m     \u001b[38;5;66;03m# for child processes has otherwise been disabled for our\u001b[39;00m\n\u001b[1;32m   2008\u001b[0m     \u001b[38;5;66;03m# process.  This child is dead, we can't get the status.\u001b[39;00m\n\u001b[1;32m   2009\u001b[0m     pid \u001b[38;5;241m=\u001b[39m \u001b[38;5;28mself\u001b[39m\u001b[38;5;241m.\u001b[39mpid\n",
                        "\u001b[0;31mKeyboardInterrupt\u001b[0m: "
                    ]
                },
                {
                    "name": "stdout",
                    "output_type": "stream",
                    "text": [
                        "Welcome to the CBC MILP Solver \n",
                        "Version: 2.10.3 \n",
                        "Build Date: Dec 15 2019 \n",
                        "\n",
                        "command line - /Users/luispinilla/Documents/source_code/bios/env/lib/python3.11/site-packages/pulp/solverdir/cbc/osx/64/cbc /var/folders/0p/md4rzs_n7bg992nr5mzyl7_00000gn/T/fff8af0b13db42c7a3614344083b98c7-pulp.mps -mips /var/folders/0p/md4rzs_n7bg992nr5mzyl7_00000gn/T/fff8af0b13db42c7a3614344083b98c7-pulp.mst -sec 21600 -allow 5000000 -threads 15 -presolve on -gomory on knapsack on probing on -timeMode elapsed -branch -printingOptions all -solution /var/folders/0p/md4rzs_n7bg992nr5mzyl7_00000gn/T/fff8af0b13db42c7a3614344083b98c7-pulp.sol (default strategy 1)\n",
                        "At line 2 NAME          MODEL\n",
                        "At line 3 ROWS\n",
                        "At line 9571 COLUMNS\n",
                        "At line 208580 RHS\n",
                        "At line 218147 BOUNDS\n",
                        "At line 255818 ENDATA\n",
                        "Problem MODEL has 9566 rows, 40646 columns and 107078 elements\n",
                        "Coin0008I MODEL read with 0 errors\n",
                        "opening mipstart file /var/folders/0p/md4rzs_n7bg992nr5mzyl7_00000gn/T/fff8af0b13db42c7a3614344083b98c7-pulp.mst.\n",
                        "MIPStart values read for 40646 variables.\n",
                        "seconds was changed from 1e+100 to 21600\n",
                        "allowableGap was changed from 1e-10 to 5e+06\n",
                        "threads was changed from 0 to 15\n",
                        "Option for gomoryCuts changed from ifmove to on\n",
                        "Option for knapsackCuts changed from ifmove to on\n",
                        "Option for timeMode changed from cpu to elapsed\n",
                        "Continuous objective value is 7.68626e+12 - 0.33 seconds\n",
                        "Cgl0003I 0 fixed, 2 tightened bounds, 1 strengthened rows, 0 substitutions\n",
                        "Cgl0004I processed model has 4972 rows, 36222 columns (28897 integer (3052 of which binary)) and 98435 elements\n",
                        "Cbc0045I Trying just fixing integer variables (and fixingish SOS).\n",
                        "Cbc0045I MIPStart provided solution with cost 6.02949e+13\n",
                        "Cbc0012I Integer solution of 6.0294941e+13 found by Reduced search after 0 iterations and 0 nodes (1.63 seconds)\n",
                        "Cbc0038I Full problem 4972 rows 36222 columns, reduced to 4812 rows 8383 columns\n",
                        "Cbc0031I 681 added rows had average density of 87.544787\n",
                        "Cbc0013I At root node, 681 cuts changed objective from 7.6862555e+12 to 7.7844007e+12 in 31 passes\n",
                        "Cbc0014I Cut generator 0 (Probing) - 101 row cuts average 4.0 elements, 0 column cuts (245 active)  in 2.453 seconds - new frequency is 1\n",
                        "Cbc0014I Cut generator 1 (Gomory) - 2250 row cuts average 45.4 elements, 0 column cuts (0 active)  in 4.588 seconds - new frequency is 1\n",
                        "Cbc0014I Cut generator 2 (Knapsack) - 0 row cuts average 0.0 elements, 0 column cuts (0 active)  in 0.475 seconds - new frequency is 1000\n",
                        "Cbc0014I Cut generator 3 (Clique) - 0 row cuts average 0.0 elements, 0 column cuts (0 active)  in 0.006 seconds - new frequency is -100\n",
                        "Cbc0014I Cut generator 4 (MixedIntegerRounding2) - 637 row cuts average 19.5 elements, 0 column cuts (0 active)  in 0.289 seconds - new frequency is 1\n",
                        "Cbc0014I Cut generator 5 (FlowCover) - 18 row cuts average 2.0 elements, 0 column cuts (0 active)  in 0.676 seconds - new frequency is -100\n",
                        "Cbc0014I Cut generator 6 (TwoMirCuts) - 3867 row cuts average 99.0 elements, 0 column cuts (0 active)  in 1.924 seconds - new frequency is -100\n",
                        "Cbc0014I Cut generator 7 (ZeroHalf) - 17 row cuts average 79.2 elements, 0 column cuts (0 active)  in 0.843 seconds - new frequency is -100\n",
                        "Cbc0010I After 0 nodes, 1 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (20.93 seconds)\n",
                        "Cbc0010I After 100 nodes, 51 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (52.82 seconds)\n",
                        "Cbc0010I After 200 nodes, 114 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (58.74 seconds)\n",
                        "Cbc0010I After 300 nodes, 179 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (64.44 seconds)\n",
                        "Cbc0010I After 400 nodes, 237 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (69.82 seconds)\n",
                        "Cbc0010I After 500 nodes, 296 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (75.03 seconds)\n",
                        "Cbc0010I After 600 nodes, 354 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (80.76 seconds)\n",
                        "Cbc0010I After 700 nodes, 406 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (85.37 seconds)\n",
                        "Cbc0010I After 800 nodes, 462 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (89.21 seconds)\n",
                        "Cbc0010I After 900 nodes, 524 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (92.57 seconds)\n",
                        "Cbc0010I After 1000 nodes, 583 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (96.78 seconds)\n",
                        "Cbc0010I After 1100 nodes, 646 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (100.73 seconds)\n",
                        "Cbc0010I After 1200 nodes, 714 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (103.95 seconds)\n",
                        "Cbc0010I After 1300 nodes, 774 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (107.24 seconds)\n",
                        "Cbc0010I After 1400 nodes, 829 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (110.74 seconds)\n",
                        "Cbc0010I After 1500 nodes, 892 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (114.36 seconds)\n",
                        "Cbc0010I After 1600 nodes, 951 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (118.04 seconds)\n",
                        "Cbc0010I After 1700 nodes, 1011 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (121.38 seconds)\n",
                        "Cbc0010I After 1800 nodes, 1067 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (124.35 seconds)\n",
                        "Cbc0010I After 1900 nodes, 1124 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (126.99 seconds)\n",
                        "Cbc0010I After 2000 nodes, 1185 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (129.79 seconds)\n",
                        "Cbc0010I After 2100 nodes, 1256 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (132.01 seconds)\n",
                        "Cbc0010I After 2200 nodes, 1324 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (134.28 seconds)\n",
                        "Cbc0010I After 2300 nodes, 1378 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (137.89 seconds)\n",
                        "Cbc0010I After 2400 nodes, 1426 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (141.86 seconds)\n",
                        "Cbc0010I After 2500 nodes, 1482 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (144.94 seconds)\n",
                        "Cbc0010I After 2600 nodes, 1494 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (147.43 seconds)\n",
                        "Cbc0010I After 2700 nodes, 1510 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (149.27 seconds)\n",
                        "Cbc0010I After 2800 nodes, 1570 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (151.42 seconds)\n",
                        "Cbc0010I After 2900 nodes, 1634 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (153.59 seconds)\n",
                        "Cbc0010I After 3000 nodes, 1689 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (155.68 seconds)\n",
                        "Cbc0010I After 3100 nodes, 1747 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (157.86 seconds)\n",
                        "Cbc0010I After 3200 nodes, 1809 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (160.12 seconds)\n",
                        "Cbc0010I After 3300 nodes, 1860 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (162.28 seconds)\n",
                        "Cbc0010I After 3400 nodes, 1914 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (164.31 seconds)\n",
                        "Cbc0010I After 3500 nodes, 1971 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (166.73 seconds)\n",
                        "Cbc0010I After 3600 nodes, 2024 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (169.15 seconds)\n",
                        "Cbc0010I After 3700 nodes, 2081 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (171.69 seconds)\n",
                        "Cbc0010I After 3800 nodes, 2139 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (173.66 seconds)\n",
                        "Cbc0010I After 3900 nodes, 2202 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (176.17 seconds)\n",
                        "Cbc0010I After 4000 nodes, 2262 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (178.98 seconds)\n",
                        "Cbc0010I After 4100 nodes, 2325 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (181.24 seconds)\n",
                        "Cbc0010I After 4200 nodes, 2386 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (183.81 seconds)\n",
                        "Cbc0010I After 4300 nodes, 2452 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (186.10 seconds)\n",
                        "Cbc0010I After 4400 nodes, 2514 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (188.45 seconds)\n",
                        "Cbc0010I After 4500 nodes, 2571 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (190.67 seconds)\n",
                        "Cbc0010I After 4600 nodes, 2629 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (192.95 seconds)\n",
                        "Cbc0010I After 4700 nodes, 2687 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (195.33 seconds)\n",
                        "Cbc0010I After 4800 nodes, 2746 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (197.50 seconds)\n",
                        "Cbc0010I After 4900 nodes, 2800 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (199.99 seconds)\n",
                        "Cbc0010I After 5000 nodes, 2866 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (202.11 seconds)\n",
                        "Cbc0010I After 5100 nodes, 2918 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (204.37 seconds)\n",
                        "Cbc0010I After 5200 nodes, 2974 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (207.04 seconds)\n",
                        "Cbc0010I After 5300 nodes, 3027 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (208.99 seconds)\n",
                        "Cbc0010I After 5400 nodes, 3093 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (211.34 seconds)\n",
                        "Cbc0010I After 5500 nodes, 3150 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (213.86 seconds)\n",
                        "Cbc0010I After 5600 nodes, 3205 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (216.05 seconds)\n",
                        "Cbc0010I After 5700 nodes, 3254 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (218.10 seconds)\n",
                        "Cbc0010I After 5800 nodes, 3296 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (220.20 seconds)\n",
                        "Cbc0010I After 5900 nodes, 3351 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (222.42 seconds)\n",
                        "Cbc0010I After 6000 nodes, 3408 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (224.88 seconds)\n",
                        "Cbc0010I After 6100 nodes, 3453 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (227.48 seconds)\n",
                        "Cbc0010I After 6200 nodes, 3508 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (230.12 seconds)\n",
                        "Cbc0010I After 6300 nodes, 3560 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (232.74 seconds)\n",
                        "Cbc0010I After 6400 nodes, 3625 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (235.57 seconds)\n",
                        "Cbc0010I After 6500 nodes, 3686 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (238.31 seconds)\n",
                        "Cbc0010I After 6600 nodes, 3741 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (241.28 seconds)\n",
                        "Cbc0010I After 6700 nodes, 3793 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (244.65 seconds)\n",
                        "Cbc0010I After 6800 nodes, 3845 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (247.84 seconds)\n",
                        "Cbc0010I After 6900 nodes, 3873 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (250.93 seconds)\n",
                        "Cbc0010I After 7000 nodes, 3904 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (253.91 seconds)\n",
                        "Cbc0010I After 7100 nodes, 3950 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (257.36 seconds)\n",
                        "Cbc0010I After 7200 nodes, 3996 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (260.36 seconds)\n",
                        "Cbc0010I After 7300 nodes, 4039 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (264.02 seconds)\n",
                        "Cbc0010I After 7400 nodes, 4096 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (267.99 seconds)\n",
                        "Cbc0010I After 7500 nodes, 4151 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (271.59 seconds)\n",
                        "Cbc0010I After 7600 nodes, 4191 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (274.69 seconds)\n",
                        "Cbc0010I After 7700 nodes, 4256 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (278.27 seconds)\n",
                        "Cbc0010I After 7800 nodes, 4315 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (282.89 seconds)\n",
                        "Cbc0010I After 7900 nodes, 4364 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (287.95 seconds)\n",
                        "Cbc0010I After 8000 nodes, 4418 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (291.82 seconds)\n",
                        "Cbc0010I After 8100 nodes, 4475 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (295.64 seconds)\n",
                        "Cbc0010I After 8200 nodes, 4531 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (299.67 seconds)\n",
                        "Cbc0010I After 8300 nodes, 4590 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (303.69 seconds)\n",
                        "Cbc0010I After 8400 nodes, 4643 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (308.27 seconds)\n",
                        "Cbc0010I After 8500 nodes, 4696 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (312.57 seconds)\n",
                        "Cbc0010I After 8600 nodes, 4749 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (316.96 seconds)\n",
                        "Cbc0010I After 8700 nodes, 4800 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (321.16 seconds)\n",
                        "Cbc0010I After 8800 nodes, 4846 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (326.06 seconds)\n",
                        "Cbc0010I After 8900 nodes, 4900 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (330.68 seconds)\n",
                        "Cbc0010I After 9000 nodes, 4961 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (334.40 seconds)\n",
                        "Cbc0010I After 9100 nodes, 5027 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (339.43 seconds)\n",
                        "Cbc0010I After 9200 nodes, 5086 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (343.05 seconds)\n",
                        "Cbc0010I After 9300 nodes, 5134 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (346.95 seconds)\n",
                        "Cbc0010I After 9400 nodes, 5186 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (350.86 seconds)\n",
                        "Cbc0010I After 9500 nodes, 5238 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (354.46 seconds)\n",
                        "Cbc0010I After 9600 nodes, 5295 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (358.77 seconds)\n",
                        "Cbc0010I After 9700 nodes, 5353 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (363.14 seconds)\n",
                        "Cbc0010I After 9800 nodes, 5396 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (366.66 seconds)\n",
                        "Cbc0010I After 9900 nodes, 5453 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (369.90 seconds)\n",
                        "Cbc0010I After 10000 nodes, 5516 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (373.57 seconds)\n",
                        "Cbc0010I After 10100 nodes, 5582 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (376.81 seconds)\n",
                        "Cbc0010I After 10200 nodes, 5637 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (380.06 seconds)\n",
                        "Cbc0010I After 10300 nodes, 5696 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (384.64 seconds)\n",
                        "Cbc0010I After 10400 nodes, 5754 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (387.92 seconds)\n",
                        "Cbc0010I After 10500 nodes, 5814 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (391.62 seconds)\n",
                        "Cbc0010I After 10600 nodes, 5871 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (394.65 seconds)\n",
                        "Cbc0010I After 10700 nodes, 5929 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (397.63 seconds)\n",
                        "Cbc0010I After 10800 nodes, 5983 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (400.12 seconds)\n",
                        "Cbc0010I After 10900 nodes, 6028 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (403.48 seconds)\n",
                        "Cbc0010I After 11000 nodes, 6070 on tree, 6.0294941e+13 best solution, best possible 7.7844007e+12 (406.32 seconds)\n",
                        "Cbc0010I After 11100 nodes, 6120 on tree, 6.0294941e+13 best solution, best possible 7.7844008e+12 (434.16 seconds)\n",
                        "Cbc0010I After 11200 nodes, 6169 on tree, 6.0294941e+13 best solution, best possible 7.7844027e+12 (452.94 seconds)\n",
                        "Cbc0010I After 11300 nodes, 6218 on tree, 6.0294941e+13 best solution, best possible 7.7844039e+12 (459.10 seconds)\n",
                        "Cbc0010I After 11400 nodes, 6268 on tree, 6.0294941e+13 best solution, best possible 7.7844039e+12 (463.58 seconds)\n",
                        "Cbc0010I After 11500 nodes, 6321 on tree, 6.0294941e+13"
                    ]
                }
            ],
            "source": [
                "print('cpu count', cpu_count)\n",
                "print('tiempo limite', t_limit_minutes, 'minutos')\n",
                "print('ejecutando ', len(periodos), 'periodos')\n",
                "\n",
                "print('GAP tolerable', gap, 'millones de pesos')\n",
                "engine = pu.PULP_CBC_CMD(\n",
                "    timeLimit=60*t_limit_minutes,\n",
                "    gapAbs=gap,\n",
                "    warmStart=True,\n",
                "    cuts=True,\n",
                "    presolve=True,\n",
                "    threads=cpu_count)\n",
                "\n",
                "problema.solve(solver=engine)\n",
                "# problema.solve()"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "# Construccion de reporte"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Reporte de puerto"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": null,
            "metadata": {},
            "outputs": [],
            "source": [
                "def get_reporte_puerto(cargas: dict) -> pd.DataFrame:\n",
                "\n",
                "    reporte_puerto_dict = dict()\n",
                "\n",
                "    reporte_puerto_dict['importacion'] = list()\n",
                "    reporte_puerto_dict['empresa'] = list()\n",
                "    reporte_puerto_dict['operador'] = list()\n",
                "    reporte_puerto_dict['puerto'] = list()\n",
                "    reporte_puerto_dict['ingrediente'] = list()\n",
                "    reporte_puerto_dict['valor_cif'] = list()\n",
                "    reporte_puerto_dict['periodo'] = list()\n",
                "    reporte_puerto_dict['costo_almacenamiento'] = list()\n",
                "    reporte_puerto_dict['llegadas'] = list()\n",
                "    reporte_puerto_dict['inventario'] = list()\n",
                "\n",
                "    for importacion, carga in cargas.items():\n",
                "\n",
                "        reporte_puerto_dict['importacion'].append(importacion)\n",
                "        reporte_puerto_dict['empresa'].append(carga['empresa'])\n",
                "        reporte_puerto_dict['operador'].append(carga['operador'])\n",
                "        reporte_puerto_dict['puerto'].append(carga['puerto'])\n",
                "        reporte_puerto_dict['ingrediente'].append(carga['ingrediente'])\n",
                "        reporte_puerto_dict['valor_cif'].append(carga['valor_cif'])\n",
                "        reporte_puerto_dict['periodo'].append(periodo_anterior)\n",
                "        reporte_puerto_dict['costo_almacenamiento'].append(0.0)\n",
                "        reporte_puerto_dict['llegadas'].append(0)\n",
                "        reporte_puerto_dict['inventario'].append(carga['inventario_inicial'])\n",
                "\n",
                "        for periodo in periodos:\n",
                "            reporte_puerto_dict['importacion'].append(importacion)\n",
                "            reporte_puerto_dict['empresa'].append(carga['empresa'])\n",
                "            reporte_puerto_dict['operador'].append(carga['operador'])\n",
                "            reporte_puerto_dict['puerto'].append(carga['puerto'])\n",
                "            reporte_puerto_dict['ingrediente'].append(carga['ingrediente'])\n",
                "            reporte_puerto_dict['valor_cif'].append(carga['valor_cif'])\n",
                "            reporte_puerto_dict['periodo'].append(periodo)\n",
                "            reporte_puerto_dict['costo_almacenamiento'].append(\n",
                "                carga['costo_almacenamiento'][periodo])\n",
                "            if periodo in carga['llegadas'].keys():\n",
                "                reporte_puerto_dict['llegadas'].append(\n",
                "                    carga['llegadas'][periodo])\n",
                "            else:\n",
                "                reporte_puerto_dict['llegadas'].append(0.0)\n",
                "            reporte_puerto_dict['inventario'].append(\n",
                "                cargas[importacion]['inventario_al_final'][periodo].varValue)\n",
                "\n",
                "    reporte_puerto_df = pd.DataFrame(reporte_puerto_dict)\n",
                "    reporte_puerto_df['costo_total_almacenamiento'] = reporte_puerto_df['inventario'] * \\\n",
                "        reporte_puerto_df['costo_almacenamiento']\n",
                "\n",
                "    return reporte_puerto_df"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Reporte transporte"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": null,
            "metadata": {},
            "outputs": [],
            "source": [
                "def get_reporte_transporte(cargas: dict) -> pd.DataFrame:\n",
                "\n",
                "    reporte_transporte_dict = dict()\n",
                "\n",
                "    reporte_transporte_dict['importacion'] = list()\n",
                "    reporte_transporte_dict['empresa'] = list()\n",
                "    reporte_transporte_dict['operador'] = list()\n",
                "    reporte_transporte_dict['puerto'] = list()\n",
                "    reporte_transporte_dict['ingrediente'] = list()\n",
                "    reporte_transporte_dict['periodo'] = list()\n",
                "    reporte_transporte_dict['tipo'] = list()\n",
                "    reporte_transporte_dict['planta'] = list()\n",
                "    reporte_transporte_dict['intercompany'] = list()\n",
                "    reporte_transporte_dict['costo_intercompany'] = list()\n",
                "    reporte_transporte_dict['flete'] = list()\n",
                "    reporte_transporte_dict['cantidad_despacho_por_camion'] = list()\n",
                "    reporte_transporte_dict['costo_portuario_despacho_directo'] = list()\n",
                "    reporte_transporte_dict['cantidad_despacho'] = list()\n",
                "    reporte_transporte_dict['cantidad_camiones_despachados'] = list()\n",
                "    reporte_transporte_dict['cantidad_despachada'] = list()\n",
                "    reporte_transporte_dict['costo_por_camion'] = list()\n",
                "    reporte_transporte_dict['cluster_flete'] = list()\n",
                "\n",
                "    for importacion, carga in cargas.items():\n",
                "        for nombre_planta, despacho in carga['costo_despacho'].items():\n",
                "            for periodo in periodos:\n",
                "                if periodo in despacho['variable_despacho'].keys():\n",
                "                    # if despacho['variable_despacho'][periodo].varValue > 0:\n",
                "\n",
                "                    reporte_transporte_dict['importacion'].append(importacion)\n",
                "                    reporte_transporte_dict['empresa'].append(carga['empresa'])\n",
                "                    reporte_transporte_dict['operador'].append(\n",
                "                        carga['operador'])\n",
                "                    reporte_transporte_dict['puerto'].append(carga['puerto'])\n",
                "                    reporte_transporte_dict['ingrediente'].append(\n",
                "                        carga['ingrediente'])\n",
                "                    reporte_transporte_dict['periodo'].append(periodo)\n",
                "                    reporte_transporte_dict['tipo'].append(\n",
                "                        despacho['tipo_envio'][periodo])\n",
                "                    reporte_transporte_dict['planta'].append(nombre_planta)\n",
                "                    reporte_transporte_dict['intercompany'].append(\n",
                "                        despacho['intercompany'])\n",
                "                    reporte_transporte_dict['costo_intercompany'].append(\n",
                "                        despacho['valor_intercompany'])\n",
                "                    reporte_transporte_dict['flete'].append(despacho['flete'])\n",
                "                    reporte_transporte_dict['cantidad_despacho_por_camion'].append(\n",
                "                        despacho['cantidad_despacho'])\n",
                "                    reporte_transporte_dict['costo_portuario_despacho_directo'].append(\n",
                "                        despacho['costo_despacho_directo'])\n",
                "                    reporte_transporte_dict['costo_por_camion'].append(\n",
                "                        despacho['costo_envio'][periodo])\n",
                "                    reporte_transporte_dict['cantidad_despacho'].append(\n",
                "                        cap_camion)\n",
                "                    reporte_transporte_dict['cantidad_camiones_despachados'].append(\n",
                "                        despacho['variable_despacho'][periodo].varValue)\n",
                "                    reporte_transporte_dict['cantidad_despachada'].append(\n",
                "                        cap_camion*despacho['variable_despacho'][periodo].varValue)\n",
                "\n",
                "                    reporte_transporte_dict['cluster_flete'].append(\n",
                "                        clusters_df.loc[(importacion, nombre_planta, periodo)]['etiqueta'])\n",
                "\n",
                "    reporte_transporte_df = pd.DataFrame(reporte_transporte_dict)\n",
                "    reporte_transporte_df['costo_total_despacho'] = reporte_transporte_df['costo_por_camion'] * \\\n",
                "        reporte_transporte_df['cantidad_camiones_despachados']\n",
                "\n",
                "    return reporte_transporte_df"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Reporte de Planta"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": null,
            "metadata": {},
            "outputs": [],
            "source": [
                "def get_reporte_plantas(plantas: dict) -> pd.DataFrame:\n",
                "\n",
                "    reporte_plantas_dict = dict()\n",
                "\n",
                "    reporte_plantas_dict = dict()\n",
                "    reporte_plantas_dict['planta'] = list()\n",
                "    reporte_plantas_dict['empresa'] = list()\n",
                "    reporte_plantas_dict['ingrediente'] = list()\n",
                "    reporte_plantas_dict['periodo'] = list()\n",
                "    reporte_plantas_dict['capcidad'] = list()\n",
                "    reporte_plantas_dict['consumo'] = list()\n",
                "    reporte_plantas_dict['backorder'] = list()\n",
                "    reporte_plantas_dict['safety_stock_kg'] = list()\n",
                "    reporte_plantas_dict['inventario_final'] = list()\n",
                "\n",
                "    for nombre_planta, planta in plantas.items():\n",
                "        for ingrediente, inventario in planta['inventarios'].items():\n",
                "\n",
                "            reporte_plantas_dict['planta'].append(nombre_planta)\n",
                "            reporte_plantas_dict['empresa'].append(planta['empresa'])\n",
                "            reporte_plantas_dict['ingrediente'].append(ingrediente)\n",
                "            reporte_plantas_dict['periodo'].append(periodo_anterior)\n",
                "            reporte_plantas_dict['capcidad'].append(inventario['capacidad'])\n",
                "            reporte_plantas_dict['consumo'].append(0.0)\n",
                "            reporte_plantas_dict['backorder'].append(0.0)\n",
                "            reporte_plantas_dict['safety_stock_kg'].append(0.0)\n",
                "            reporte_plantas_dict['inventario_final'].append(\n",
                "                inventario['inventario_final'][periodo_anterior])\n",
                "\n",
                "            for periodo in periodos:\n",
                "                reporte_plantas_dict['planta'].append(nombre_planta)\n",
                "                reporte_plantas_dict['empresa'].append(planta['empresa'])\n",
                "                reporte_plantas_dict['ingrediente'].append(ingrediente)\n",
                "                reporte_plantas_dict['periodo'].append(periodo)\n",
                "                reporte_plantas_dict['capcidad'].append(\n",
                "                    inventario['capacidad'])\n",
                "                reporte_plantas_dict['consumo'].append(\n",
                "                    inventario['consumo'][periodo])\n",
                "                if periodo in inventario['backorder'].keys():\n",
                "                    reporte_plantas_dict['backorder'].append(\n",
                "                        inventario['backorder'][periodo].varValue)\n",
                "                else:\n",
                "                    reporte_plantas_dict['backorder'].append(0.0)\n",
                "\n",
                "                if 'safety_stock_kg' in inventario.keys():\n",
                "                    reporte_plantas_dict['safety_stock_kg'].append(\n",
                "                        inventario['safety_stock_kg'])\n",
                "                else:\n",
                "                    reporte_plantas_dict['safety_stock_kg'].append(0.0)\n",
                "\n",
                "                if type(inventario['inventario_final'][periodo]) == pu.pulp.LpVariable:\n",
                "                    reporte_plantas_dict['inventario_final'].append(\n",
                "                        inventario['inventario_final'][periodo].varValue)\n",
                "                else:\n",
                "                    reporte_plantas_dict['inventario_final'].append(\n",
                "                        inventario['inventario_final'][periodo])\n",
                "\n",
                "    reporte_plantas_df = pd.DataFrame(reporte_plantas_dict)\n",
                "\n",
                "    return reporte_plantas_df"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Reporte de Modelo"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": null,
            "metadata": {},
            "outputs": [],
            "source": [
                "def get_reporte_modelo() -> pd.DataFrame:\n",
                "\n",
                "    reporte_dict = dict()\n",
                "    reporte_dict['Parametro'] = list()\n",
                "    reporte_dict['Valor'] = list()\n",
                "\n",
                "    reporte_dict['Parametro'].append(\"Cantidad de Núcleos CPU\")\n",
                "    reporte_dict['Valor'].append(cpu_count)\n",
                "\n",
                "    reporte_dict['Parametro'].append(\"Tiempo de trabajo\")\n",
                "    reporte_dict['Valor'].append(t_limit_minutes)\n",
                "\n",
                "    reporte_dict['Parametro'].append(\"Archivo de input\")\n",
                "    reporte_dict['Valor'].append(bios_input_file)\n",
                "\n",
                "    reporte_dict['Parametro'].append(\"GAP tolerable en Pesos\")\n",
                "    reporte_dict['Valor'].append(gap)\n",
                "\n",
                "    reporte_dict['Parametro'].append(\"Capacidad de camion en Kg\")\n",
                "    reporte_dict['Valor'].append(cap_camion)\n",
                "\n",
                "    reporte_dict['Parametro'].append(\"Capacidad de descargue en puerto en Kg\")\n",
                "    reporte_dict['Valor'].append(cap_descarge)\n",
                "\n",
                "    reporte_dict['Parametro'].append(\"Costo backorder por día\")\n",
                "    reporte_dict['Valor'].append(costo_backorder_dia)\n",
                "\n",
                "    reporte_dict['Parametro'].append(\n",
                "        \"Costo exceso inventaio en planta por día\")\n",
                "    reporte_dict['Valor'].append(costo_exceso_capacidad)\n",
                "\n",
                "    # Costo de no safety stock por día\n",
                "    reporte_dict['Parametro'].append(\"Costo de no satisfacer Safety stock\")\n",
                "    reporte_dict['Valor'].append(costo_safety_stock)\n",
                "\n",
                "    reporte_dict['Parametro'].append(\"Periodos sin despacho en días\")\n",
                "    reporte_dict['Valor'].append(periodo_administrativo)\n",
                "\n",
                "    reporte_dict['Parametro'].append(\"Lead time en dias\")\n",
                "    reporte_dict['Valor'].append(lead_time)\n",
                "\n",
                "    return pd.DataFrame(reporte_dict)"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Escribiendo el archivo"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": null,
            "metadata": {},
            "outputs": [],
            "source": [
                "reporte_modelo_df = get_reporte_modelo()\n",
                "reporte_puerto_df = get_reporte_puerto(cargas=cargas)\n",
                "reporte_plantas_df = get_reporte_plantas(plantas=plantas)\n",
                "reporte_transporte_df = get_reporte_transporte(cargas=cargas)\n",
                "\n",
                "fecha_generacion = datetime.now()\n",
                "bios_output_file = bios_input_file.replace('.xlsm', '')\n",
                "bios_output_file = f\"{bios_output_file}_{fecha_generacion.strftime('%Y%m%d%H')}.xlsx\""
            ]
        },
        {
            "cell_type": "code",
            "execution_count": null,
            "metadata": {},
            "outputs": [],
            "source": [
                "\n",
                "with pd.ExcelWriter(path=bios_output_file) as writer:\n",
                "    reporte_modelo_df.to_excel(writer, sheet_name='Modelo', index=False)\n",
                "    reporte_puerto_df.to_excel(writer, sheet_name='Puertos', index=False)\n",
                "    reporte_plantas_df.to_excel(writer, sheet_name='Plantas', index=False)\n",
                "    reporte_transporte_df.to_excel(writer, sheet_name='Despachos', index=False)"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": null,
            "metadata": {},
            "outputs": [],
            "source": [
                "# Duplicar el archivo\n",
                "shutil.copy(src=bios_output_file, dst='archivo_schema.xlsx')"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": null,
            "metadata": {},
            "outputs": [],
            "source": [
                "reporte_transporte_df['cantidad_camiones_despachados'].unique()"
            ]
        }
    ],
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3 (ipykernel)",
            "language": "python",
            "name": "python3"
        },
        "language_info": {
            "codemirror_mode": {
                "name": "ipython",
                "version": 3
            },
            "file_extension": ".py",
            "mimetype": "text/x-python",
            "name": "python",
            "nbconvert_exporter": "python",
            "pygments_lexer": "ipython3",
            "version": "3.11.4"
        }
    },
    "nbformat": 4,
    "nbformat_minor": 4
}

# %% [markdown]
# ## Reporte de Planta

# %%
def get_reporte_plantas(plantas: dict) -> pd.DataFrame:

    reporte_plantas_dict = dict()

    reporte_plantas_dict = dict()
    reporte_plantas_dict['planta'] = list()
    reporte_plantas_dict['empresa'] = list()
    reporte_plantas_dict['ingrediente'] = list()
    reporte_plantas_dict['periodo'] = list()
    reporte_plantas_dict['capcidad'] = list()
    reporte_plantas_dict['consumo'] = list()
    reporte_plantas_dict['backorder'] = list()
    reporte_plantas_dict['safety_stock_kg'] = list()
    reporte_plantas_dict['inventario_final'] = list()

    for nombre_planta, planta in plantas.items():
        for ingrediente, inventario in planta['inventarios'].items():

            reporte_plantas_dict['planta'].append(nombre_planta)
            reporte_plantas_dict['empresa'].append(planta['empresa'])
            reporte_plantas_dict['ingrediente'].append(ingrediente)
            reporte_plantas_dict['periodo'].append(periodo_anterior)
            reporte_plantas_dict['capcidad'].append(inventario['capacidad'])
            reporte_plantas_dict['consumo'].append(0.0)
            reporte_plantas_dict['backorder'].append(0.0)
            reporte_plantas_dict['safety_stock_kg'].append(0.0)
            reporte_plantas_dict['inventario_final'].append(
                inventario['inventario_final'][periodo_anterior])

            for periodo in periodos:
                reporte_plantas_dict['planta'].append(nombre_planta)
                reporte_plantas_dict['empresa'].append(planta['empresa'])
                reporte_plantas_dict['ingrediente'].append(ingrediente)
                reporte_plantas_dict['periodo'].append(periodo)
                reporte_plantas_dict['capcidad'].append(
                    inventario['capacidad'])
                reporte_plantas_dict['consumo'].append(
                    inventario['consumo'][periodo])
                if periodo in inventario['backorder'].keys():
                    reporte_plantas_dict['backorder'].append(
                        inventario['backorder'][periodo].varValue)
                else:
                    reporte_plantas_dict['backorder'].append(0.0)

                if 'safety_stock_kg' in inventario.keys():
                    reporte_plantas_dict['safety_stock_kg'].append(
                        inventario['safety_stock_kg'])
                else:
                    reporte_plantas_dict['safety_stock_kg'].append(0.0)

                if type(inventario['inventario_final'][periodo]) == pu.pulp.LpVariable:
                    reporte_plantas_dict['inventario_final'].append(
                        inventario['inventario_final'][periodo].varValue)
                else:
                    reporte_plantas_dict['inventario_final'].append(
                        inventario['inventario_final'][periodo])

    reporte_plantas_df = pd.DataFrame(reporte_plantas_dict)

    return reporte_plantas_df

# %% [markdown]
# ## Reporte de Modelo

# %%
def get_reporte_modelo() -> pd.DataFrame:

    reporte_dict = dict()
    reporte_dict['Parametro'] = list()
    reporte_dict['Valor'] = list()

    reporte_dict['Parametro'].append("Cantidad de Núcleos CPU")
    reporte_dict['Valor'].append(cpu_count)

    reporte_dict['Parametro'].append("Tiempo de trabajo")
    reporte_dict['Valor'].append(t_limit_minutes)

    reporte_dict['Parametro'].append("Archivo de input")
    reporte_dict['Valor'].append(bios_input_file)

    reporte_dict['Parametro'].append("GAP tolerable en Pesos")
    reporte_dict['Valor'].append(gap)

    reporte_dict['Parametro'].append("Capacidad de camion en Kg")
    reporte_dict['Valor'].append(cap_camion)

    reporte_dict['Parametro'].append("Capacidad de descargue en puerto en Kg")
    reporte_dict['Valor'].append(cap_descarge)

    reporte_dict['Parametro'].append("Costo backorder por día")
    reporte_dict['Valor'].append(costo_backorder_dia)

    reporte_dict['Parametro'].append(
        "Costo exceso inventaio en planta por día")
    reporte_dict['Valor'].append(costo_exceso_capacidad)

    # Costo de no safety stock por día
    reporte_dict['Parametro'].append("Costo de no satisfacer Safety stock")
    reporte_dict['Valor'].append(costo_safety_stock)

    reporte_dict['Parametro'].append("Periodos sin despacho en días")
    reporte_dict['Valor'].append(periodo_administrativo)

    reporte_dict['Parametro'].append("Lead time en dias")
    reporte_dict['Valor'].append(lead_time)

    return pd.DataFrame(reporte_dict)

# %% [markdown]
# ## Escribiendo el archivo

# %%
reporte_modelo_df = get_reporte_modelo()
reporte_puerto_df = get_reporte_puerto(cargas=cargas)
reporte_plantas_df = get_reporte_plantas(plantas=plantas)
reporte_transporte_df = get_reporte_transporte(cargas=cargas)

fecha_generacion = datetime.now()
bios_output_file = bios_input_file.replace('.xlsm', '')
bios_output_file = f"{bios_output_file}_{fecha_generacion.strftime('%Y%m%d%H')}.xlsx"

# %%

with pd.ExcelWriter(path=bios_output_file) as writer:
    reporte_modelo_df.to_excel(writer, sheet_name='Modelo', index=False)
    reporte_puerto_df.to_excel(writer, sheet_name='Puertos', index=False)
    reporte_plantas_df.to_excel(writer, sheet_name='Plantas', index=False)
    reporte_transporte_df.to_excel(writer, sheet_name='Despachos', index=False)

# %%
# Duplicar el archivo
shutil.copy(src=bios_output_file, dst='archivo_schema.xlsx')

# %%
reporte_transporte_df['cantidad_camiones_despachados'].unique()


