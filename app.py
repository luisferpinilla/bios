import streamlit as st
import pandas as pd
from bios_utils.asignador_capacidad import AsignadorCapacidad
from bios_utils.objetivo_inventario import obtener_objetivo_inventario
from datetime import datetime, timedelta
from tqdm import tqdm
import numpy as np
import pulp as pu
import os

# # Modelo de base de datos


@st.cache_data
def resolver_modelo(bios_input_file: str):
    # %%
    # engine = create_engine(
    #    "mysql+mysqlconnector://root:secret@localhost:3306/bios")
    # session = Session(engine)

    # %%
    # Capacidad de carga de un camion
    cap_camion = 34000

    # Capacidad de descarga en puerto por día
    cap_descarge = 5000000

    # %% [markdown]
    # # Parametros Generales

    # %% [markdown]
    # ## Inventarios y capacidad de almacenamiento en planta

    # %%
    # Cargar inventario y capacidad de plantas
    asignador = AsignadorCapacidad(bios_input_file)
    df = asignador.obtener_unidades_almacenamiento()
    df['Capacidad'] = df.apply(lambda x: x[x['ingrediente_actual']], axis=1)
    df.rename(columns={'planta': 'Planta', 'ingrediente_actual': 'Ingrediente',
                       'cantidad_actual': 'Inventario'}, inplace=True)
    inventario_planta_df = df.groupby(['Planta', 'Ingrediente'])[
        ['Capacidad', 'Inventario']].sum().reset_index()

    # %% [markdown]
    # ### Transito a plantas

    # %%
    # llegadas programadas a planta
    df = pd.read_excel(
        io=bios_input_file, sheet_name='tto_plantas')
    df = df.groupby(['planta', 'ingrediente', 'fecha_llegada'])[['cantidad']].sum().reset_index().rename(columns={
        'planta': 'Planta', 'ingrediente': 'Ingrediente', 'fecha_llegada': 'Fecha', 'cantidad': 'Llegadas_planeadas'})
    llegadas_programadas_df = df

    # %% [markdown]
    # ### Consumo Proyectado

    # %%
    # Consumo proyectado
    df = pd.read_excel(io=bios_input_file, sheet_name='consumo_proyectado').rename(
        columns={'planta': 'Planta', 'ingrediente': 'Ingrediente'})

    columns = df.drop(columns=['Planta', 'Ingrediente']).columns

    df = df.melt(id_vars=['Planta', 'Ingrediente'],
                 value_vars=columns, var_name='Fecha', value_name='Consumo')

    df['Fecha'] = df['Fecha'].apply(
        lambda x: datetime.strptime(x, '%d/%m/%Y').strftime('%Y-%m-%d'))

    consumo_proyectado_df = df

    # %% [markdown]
    # ### Tiempos de Proceso

    # %%
    # Tiempos de proceso
    df = pd.read_excel(io=bios_input_file, sheet_name='plantas')
    # Tiempos de proceso
    columns = ['planta',	'empresa',	'operacion_minutos',
               'minutos_limpieza', 'plataformas']
    df = df.melt(id_vars=['planta', 'empresa'], value_vars=df.drop(columns=columns).columns, var_name='Ingrediente',
                 value_name='Tiempo_Operacion').rename(columns={'planta': 'Planta', 'empresa': 'Empresa'})
    tiempos_proceso_df = df

    # %% [markdown]
    # ### Objetivo de inventario

    # %%
    # Objetivo de inventarios
    df = obtener_objetivo_inventario(bios_input_file=bios_input_file)
    df = df['objetivo_inventario'].copy()

    objetivo_df = df[['planta', 'ingrediente', 'objetivo_dio', 'objetivo_kg']].rename(columns={'planta': 'Planta',
                                                                                               'ingrediente': 'Ingrediente',
                                                                                               'objetivo_dio': 'objetivo',
                                                                                               'objetivo_kg': 'kilogramos'})

    # %% [markdown]
    # ### Costo de Operaciones portuarias

    # %%
    # Costo de Operaciones portuarias
    operaciones_portuarias_df = pd.read_excel(
        io=bios_input_file, sheet_name='costos_operacion_portuaria')
    costo_portuario_directo_df = operaciones_portuarias_df[operaciones_portuarias_df['tipo_operacion'] == 'directo'].copy(
    ).drop(columns='tipo_operacion')
    costo_portuario_bodegaje_df = operaciones_portuarias_df[operaciones_portuarias_df['tipo_operacion'] == 'bodega'].copy(
    ).drop(columns='tipo_operacion')

    # %% [markdown]
    # ### Transitos a Puerto

    # %%
    # Transitos a puerto
    df = pd.read_excel(io=bios_input_file, sheet_name='tto_puerto')
    transitos_list = list()
    for i in tqdm(df.index):
        # print('-----------------')
        # print(transitos_puerto_df.loc[i])
        empresa = df.loc[i]['empresa']
        operador = df.loc[i]['operador']
        puerto = df.loc[i]['puerto']
        ingrediente = df.loc[i]['ingrediente']
        importacion = df.loc[i]['importacion']
        fecha = df.loc[i]['fecha_llegada']
        cantidad = int(df.loc[i]['cantidad_kg'])
        valor_kg = float(df.loc[i]['valor_kg'])

        # Agregar las llegadas segun la capacidad del puerto
        while cantidad > cap_descarge:
            dato = {
                'Empresa': empresa,
                'Puerto': puerto,
                'Operador': operador,
                'Ingrediente': ingrediente,
                'Importacion': importacion,
                'Fecha': fecha.strftime('%Y-%m-%d'),
                'Inventario': 0,
                'valor_kg': valor_kg,
                'Llegada': cap_descarge
            }
            transitos_list.append(dato)

            cantidad -= cap_descarge
            fecha = fecha + timedelta(days=1)

        if cantidad > 0:

            dato = {
                'Empresa': empresa,
                'Puerto': puerto,
                'Operador': operador,
                'Ingrediente': ingrediente,
                'Importacion': importacion,
                'Fecha': fecha.strftime('%Y-%m-%d'),
                'Inventario': 0,
                'valor_kg': valor_kg,
                'Llegada': cantidad
            }
            transitos_list.append(dato)

    tto_puerto_df = pd.DataFrame(transitos_list)
    # tto_puerto_df['Fecha'] = tto_puerto_df['Fecha'].apply(lambda x: x.strftime('%Y-%m-%d'))

    # %% [markdown]
    # ### Inventarios en Puerto

    # %%
    df = pd.read_excel(io=bios_input_file, sheet_name='inventario_puerto')
    inventario_puerto_list = list()
    for i in tqdm(df.index):
        empresa = df.loc[i]['empresa']
        operador = df.loc[i]['operador']
        puerto = df.loc[i]['puerto']
        ingrediente = df.loc[i]['ingrediente']
        importacion = df.loc[i]['importacion']
        fecha = df.loc[i]['fecha_llegada']
        cantidad = int(df.loc[i]['cantidad_kg'])
        valor_kg = float(df.loc[i]['valor_cif_kg'])

        dato = {
            'Empresa': empresa,
            'Puerto': puerto,
            'Operador': operador,
            'Ingrediente': ingrediente,
            'Importacion': importacion,
            'Fecha': fecha.strftime('%Y-%m-%d'),
            'Inventario': cantidad,
            'valor_kg': valor_kg,
            'Llegada': 0
        }
        inventario_puerto_list.append(dato)
    inventario_puerto_df = pd.DataFrame(inventario_puerto_list)

    # %% [markdown]
    # ### Cargas despachables

    # %%
    cargas_despachables_df = pd.concat([inventario_puerto_df, tto_puerto_df])

    # %%
    cargas_despachables_df[(cargas_despachables_df['Inventario'] >= 34000) & (
        cargas_despachables_df['Llegada'] >= 0)].shape

    # %% [markdown]
    # ### Costos Almacenamiento Cargas

    # %%
    # Leer el archivo de excel
    costos_almacenamiento_df = pd.read_excel(
        io=bios_input_file, sheet_name='costos_almacenamiento_cargas')

    # %%
    costos_almacenamiento_df['fecha_corte'] = costos_almacenamiento_df['fecha_corte'].apply(
        lambda x: x.strftime('%Y-%m-%d'))

    # %% [markdown]
    # ### Fletes

    # %%
    fletes_df = pd.read_excel(
        io=bios_input_file, sheet_name='fletes_cop_per_kg')

    # %% [markdown]
    # ### Intercompany

    # %%
    intercompany_df = pd.read_excel(
        io=bios_input_file, sheet_name='venta_entre_empresas')

    # %%
    type(consumo_proyectado_df.iloc[0]['Fecha'])

    # %%
    # Listas de conjuntos

    plantas_df = pd.read_excel(io=bios_input_file, sheet_name='plantas')

    plantas = list(plantas_df['planta'].unique())
    empresas = list(plantas_df['empresa'].unique())
    empresas_dict = {plantas_df.iloc[i]['planta']: plantas_df.iloc[i]
                     ['empresa'] for i in range(plantas_df.shape[0])}

    periodos = sorted(list(consumo_proyectado_df['Fecha'].unique()))
    ingredientes = list(consumo_proyectado_df['Ingrediente'].unique())

    # %% [markdown]
    # ### Consumo proyectado

    # %%
    # Consumo Proyectado
    consumo_proyectado_df.set_index(
        ['Planta', 'Ingrediente', 'Fecha'], inplace=True)

    consumo_proyectado = dict()
    for planta in plantas:
        consumo_proyectado[planta] = dict()
        for ingrediente in ingredientes:
            consumo_proyectado[planta][ingrediente] = dict()
            for periodo in periodos:
                i = (planta, ingrediente, periodo)
                if i in consumo_proyectado_df.index:
                    consumo = consumo_proyectado_df.loc[i]['Consumo']
                else:
                    consumo = 0.0
                consumo_proyectado[planta][ingrediente][periodo] = consumo

    # %% [markdown]
    # ### Llegadas programadas a planta

    # %%
    llegadas_programadas_df.set_index(
        ['Planta', 'Ingrediente', 'Fecha'], inplace=True)

    # Llegadas planeadas
    llegadas_planteadas = dict()
    for planta in plantas:
        llegadas_planteadas[planta] = dict()
        for ingrediente in ingredientes:
            llegadas_planteadas[planta][ingrediente] = dict()
            for periodo in periodos:
                i = (planta, ingrediente, periodo)
                if i in llegadas_programadas_df.index:
                    llegadas = llegadas_programadas_df.loc[i]['Llegadas_planeadas']
                else:
                    llegadas = 0
                llegadas_planteadas[planta][ingrediente][periodo] = llegadas

    # %% [markdown]
    # ### Inventario inicial y Capacidad de almacenamiento

    # %%
    # Iventario y capacidad
    inventario_planta_df.set_index(['Planta', 'Ingrediente'], inplace=True)

    inventario_inicial = dict()
    capacidad_planta = dict()
    for planta in plantas:
        inventario_inicial[planta] = dict()
        capacidad_planta[planta] = dict()
        for ingrediente in ingredientes:
            i = (planta, ingrediente)
            if i in inventario_planta_df.index:
                capacidad = inventario_planta_df.loc[i]['Capacidad']
                inventario = inventario_planta_df.loc[i]['Inventario']
            else:
                capacidad = 0
                inventario = 0
            inventario_inicial[planta][ingrediente] = inventario
            capacidad_planta[planta][ingrediente] = capacidad

    # %% [markdown]
    # ### Capacidad de recepcion

    # %%
    plantas_df.set_index(['planta'], inplace=True)
    tiempo_disponible = dict()
    tiempo_limpieza = dict()
    tiempo_proceso = dict()
    for planta in plantas:

        if planta in plantas_df.index:
            disponible = plantas_df.loc[planta]['operacion_minutos'] * \
                plantas_df.loc[planta]['plataformas']
            limpieza = plantas_df.loc[planta]['minutos_limpieza']
        else:
            disponible = 0
            limpieza = 0

        tiempo_disponible[planta] = disponible
        tiempo_limpieza[planta] = limpieza

    # %% [markdown]
    # ### Tiempo de proceso de recepción

    # %%
    df = plantas_df.reset_index().melt(id_vars=['planta'],
                                       value_vars=ingredientes,
                                       value_name='Tiempo_Operacion',
                                       var_name='Ingrediente')

    # %%
    df.set_index(['planta', 'Ingrediente'], inplace=True)

    tiempos_proceso = dict()
    for planta in plantas:
        tiempos_proceso[planta] = dict()
        for ingrediente in ingredientes:
            i = (planta, ingrediente)
            if i in df.index:
                tiempo = df.loc[i]['Tiempo_Operacion']
            else:
                tiempo = 0
            tiempos_proceso[planta][ingrediente] = tiempo

    # %% [markdown]
    # ### Objetivo de inventario

    # %%
    objetivo_df.set_index(['Planta', 'Ingrediente'], inplace=True)

    objetivo_inventario = dict()

    for planta in plantas:
        objetivo_inventario[planta] = dict()
        for ingrediente in ingredientes:
            i = (planta, ingrediente)
            if i in objetivo_df.index:
                objetivo = objetivo_df.loc[i]['kilogramos']
            else:
                objetivo = 0.0

            objetivo_inventario[planta][ingrediente] = objetivo

    # %% [markdown]
    # ### Importaciones en puerto

    # %%
    # Transformar a camiones
    cargas_despachables_df['Camiones'] = cargas_despachables_df['Inventario'].apply(
        lambda x: int(x/34000))
    df = cargas_despachables_df.groupby(['Ingrediente'])[
        ['Camiones']].sum()

    # %%
    # Inicializar inventario inicial en puerto
    inventario_inicial_puerto = dict()
    for ingrediente in ingredientes:
        if ingrediente in df.index:
            cantidad = df.loc[ingrediente]['Camiones']
            inventario_inicial_puerto[ingrediente] = cantidad
        else:
            inventario_inicial_puerto[ingrediente] = 0

    # %% [markdown]
    # ### Transitos a puerto

    # %%
    # Transitos programados
    tto_puerto_df['Camiones'] = tto_puerto_df['Llegada'].apply(
        lambda x: int(x/34000))
    # Agrupar y totalizar por la cantidad de camiones
    df = tto_puerto_df.groupby(['Ingrediente', 'Fecha'])[
        ['Camiones']].sum()

    # %%
    llegadas_puerto = dict()
    for ingrediente in ingredientes:
        llegadas_puerto[ingrediente] = dict()
        for periodo in periodos:
            i = (ingrediente, periodo)
            if i in df.index:
                camiones = df.loc[i]['Camiones']
            else:
                camiones = 0
            llegadas_puerto[ingrediente][periodo] = camiones

    # %% [markdown]
    # # Creacion del Modelo de alcance de Objetivo

    # %% [markdown]
    # ## Variables

    # %% [markdown]
    # #### Inventario en planta, Faltante hasta el objetivo y Backorder

    # %%
    # Variables de inventario
    inventario_planta = dict()
    inventario_proyectado = dict()

    # FAltante para opbjetivo de inventario
    faltante_objetivo_inventario = dict()

    # invenatrio proyectado
    inventario_proyectado = dict()

    # Backorder
    backorder = dict()

    # Safety stock
    safety_stock = dict()
    for planta in tqdm(plantas):
        inventario_planta[planta] = dict()
        inventario_proyectado[planta] = dict()
        faltante_objetivo_inventario[planta] = dict()
        safety_stock[planta] = dict()
        backorder[planta] = dict()
        for ingrediente in ingredientes:
            inventario_planta[planta][ingrediente] = dict()
            inventario_proyectado[planta][ingrediente] = dict()
            faltante_objetivo_inventario[planta][ingrediente] = dict()
            backorder[planta][ingrediente] = dict()
            safety_stock[planta][ingrediente] = dict()
            ii = inventario_inicial[planta][ingrediente]
            ca = capacidad_planta[planta][ingrediente]
            obj = objetivo_inventario[planta][ingrediente]
            for periodo in periodos:
                ii += llegadas_planteadas[planta][ingrediente][periodo]
                ii -= consumo_proyectado[planta][ingrediente][periodo]

                inventario_proyectado[planta][ingrediente][periodo] = ii

                inventario_var = pu.LpVariable(
                    name=f'inv_{planta}_{ingrediente}_{periodo}',
                    lowBound=0.0,
                    upBound=max(ii, ca),
                    cat=pu.LpContinuous)
                inventario_var.setInitialValue(max(ii, 0.0))
                inventario_planta[planta][ingrediente][periodo] = inventario_var

                faltante_var = pu.LpVariable(
                    name=f'fal_{planta}_{ingrediente}_{periodo}',
                    lowBound=0.0,
                    upBound=obj,
                    cat=pu.LpContinuous)
                faltante_objetivo_inventario[planta][ingrediente][periodo] = faltante_var
                fal = max(obj - max(ii, 0.0), 0.0)
                faltante_var.setInitialValue(fal)

                backorder_var = pu.LpVariable(
                    name=f'bkr_{planta}_{ingrediente}_{periodo}',
                    cat=pu.LpBinary)

                if ii < 0:
                    backorder_var.setInitialValue(1)
                else:
                    backorder_var.setInitialValue(0)
                backorder[planta][ingrediente][periodo] = backorder_var

                # safety_stock_var = pu.LpVariable(
                #    name=f'bkr_{planta}_{ingrediente}_{periodo}',
                #    cat=pu.LpBinary)
                # safety_stock[planta][ingrediente][periodo] = safety_stock_var

    # %% [markdown]
    # #### inventario en puerto

    # %%
    # Variables de inventario
    inventario_puerto = dict()
    for ingrediente in ingredientes:
        inventario_puerto[ingrediente] = dict()
        ii = inventario_inicial_puerto[ingrediente]
        for periodo in periodos:
            arp = llegadas_puerto[ingrediente][periodo]
            ii += arp
            var_name = f'inv_{ingrediente}_{periodo}'
            var = pu.LpVariable(name=var_name, lowBound=0, cat=pu.LpInteger)
            var.setInitialValue(ii)
            inventario_puerto[ingrediente][periodo] = var

    # %% [markdown]
    # #### Despachos hacia Planta

    # %%
    # Variables de despacho
    despachos_planta = dict()
    # Variables de recibo en planta
    recibo_planta = dict()

    for ingrediente in ingredientes:
        if not ingrediente in despachos_planta.keys():
            despachos_planta[ingrediente] = dict()
            recibo_planta[ingrediente] = dict()
        for planta in plantas:

            recibo_planta[ingrediente][planta] = dict()

            despachos_planta[ingrediente][planta] = dict()

            t_proceso = tiempos_proceso[planta][ingrediente]
            t_disponible = tiempo_disponible[planta]
            max_cap_recepcion = int(t_disponible/t_proceso)

            for periodo in periodos[1:-2:]:

                max_inventario = int(
                    inventario_planta[planta][ingrediente][periodo].upBound/34000)

                despacho_name = f'despacho_{ingrediente}_{planta}_{periodo}'
                despacho_var = pu.LpVariable(name=despacho_name,
                                             lowBound=0,
                                             upBound=min(
                                                 max_inventario, max_cap_recepcion),
                                             cat=pu.LpInteger)
                despacho_var.setInitialValue(0)

                despachos_planta[ingrediente][planta][periodo] = despacho_var

                periodo_leadtime = periodos[periodos.index(periodo)+2]
                recibo_planta[ingrediente][planta][periodo_leadtime] = despacho_var

    # %% [markdown]
    # ## Restricciones

    # %% [markdown]
    # ### Balance de masa en planta

    # %%
    # Balance de masa planta
    balance_masa_planta = list()
    for planta in tqdm(inventario_planta.keys()):
        for ingrediente in inventario_planta[planta].keys():
            for periodo in periodos:
                # I = It-1 + llegadas_programadas + llegadas_puerto - backorder*consumo
                rest_name = f'balance_planta_{planta}_{ingrediente}_{periodo}'
                I = inventario_planta[planta][ingrediente][periodo]
                llegada_planeada = llegadas_planteadas[planta][ingrediente][periodo]
                con = consumo_proyectado[planta][ingrediente][periodo]
                bk = backorder[planta][ingrediente][periodo]
                if periodo in recibo_planta[ingrediente][planta].keys():
                    llegada_planta = recibo_planta[ingrediente][planta][periodo]
                else:
                    llegada_planta = 0

                if periodos.index(periodo) == 0:
                    Iant = Iant = inventario_inicial[planta][ingrediente]
                else:

                    periodo_anterior = periodos[periodos.index(periodo)-1]

                    Iant = inventario_planta[planta][ingrediente][periodo_anterior]

                rest = (I == Iant + llegada_planeada + 34000 *
                        llegada_planta - con + con*bk, rest_name)
                balance_masa_planta.append(rest)

    # %% [markdown]
    # ### Balance de masa puerto

    # %%
    # Balance de masa puerto
    balance_masa_puerto = list()
    for ingrediente in ingredientes:
        for periodo in periodos:
            # I = It-1 + llegadas_programadas - despachos_planta
            I = inventario_puerto[ingrediente][periodo]

            if periodos.index(periodo) == 0:
                Iant = inventario_inicial_puerto[ingrediente]
            else:
                periodo_ant = periodos[periodos.index(periodo)-1]
                Iant = inventario_puerto[ingrediente][periodo_ant]

            llegada_programada = llegadas_puerto[ingrediente][periodo]

            if periodo in despachos_planta[ingrediente][planta].keys():
                despacho_list = [despachos_planta[ingrediente][planta][periodo]
                                 for planta in plantas if planta in despachos_planta[ingrediente].keys()]
            else:
                despacho_list = list()

            rest_name = f'balance_puerto_{ingrediente}_{periodo}'
            rest = (I == Iant + llegada_programada -
                    pu.lpSum(despacho_list), rest_name)

            balance_masa_puerto.append(rest)

    # %% [markdown]
    # ### Capacidad de recepcion en planta

    # %%
    # Capacidad de recepcion en planta
    rest_recepcion_planta = list()

    for planta in plantas:
        for periodo in periodos:
            if periodo in recibo_planta[ingrediente][planta].keys():
                recibo_a_plantas = [tiempos_proceso[planta][ingrediente] *
                                    recibo_planta[ingrediente][planta][periodo] for ingrediente in ingredientes]
                rest_name = f'recepcion_{planta}_{periodo}'
                rest = (pu.lpSum(recibo_a_plantas) <=
                        tiempo_disponible[planta], rest_name)
                rest_recepcion_planta.append(rest)

    # %%
    # Faltante para llegar al inventario objetivo
    faltante_inventaio_objetivo = list()
    for planta in inventario_planta.keys():
        for ingrediente in inventario_planta[planta].keys():
            # Calcular la media de consumo para cumplir el objetivo
            consumo_planta = np.mean(
                [c for t, c in consumo_proyectado[planta][ingrediente].items()])
            objetivo = objetivo_inventario[planta][ingrediente]

            if consumo_planta > 0 and objetivo > 0:
                for periodo in periodos:
                    # IF + OB >= O
                    IF = inventario_planta[planta][ingrediente][periodo]
                    OB = faltante_objetivo_inventario[planta][ingrediente][periodo]

                    rest_name = f'objetivo_inventario_{planta}_{ingrediente}_{periodo}'
                    rest = (IF + OB >= objetivo, rest_name)
                    faltante_inventaio_objetivo.append(rest)

    # %% [markdown]
    # ## Funcion objetivo
    # Maximizar la porción faltante de días de inventario al final del día
    # ### Faltante hasta objetivo

    # %%
    funcion_objetivo = list()
    for planta in inventario_planta.keys():
        for ingrediente in inventario_planta[planta].keys():
            for periodo in periodos:
                funcion_objetivo.append(
                    faltante_objetivo_inventario[planta][ingrediente][periodo])

    # %% [markdown]
    # ### Backorder

    # %%
    for planta in backorder.keys():
        for ingrediente in backorder[planta].keys():
            for periodo in periodos:
                funcion_objetivo.append(
                    100*objetivo_inventario[planta][ingrediente]*backorder[planta][ingrediente][periodo])

    # %% [markdown]
    # ## Solucion Modelo Fase 1
    # Se pretende maximizar los dias de inventario de todos los igredientes en todas las plantas durante todos los periodos.
    # Sujeto a que no se pueda exceder la capaciadd maxina de almacenamiento
    # La idea es que se vaa despachar todo el inventario que las plantas puedan recibir dada su capacidad limitada de recepcion.
    #

    # %%
    # Cantidad CPU habilitadas para trabajar
    cpu_count = max(1, os.cpu_count()-1)

    problema = pu.LpProblem(name='Bios_Solver_fase_1', sense=pu.LpMinimize)

    # Agregando funcion objetivo
    problema += pu.lpSum(funcion_objetivo)

    # Agregando balance de masa puerto
    for rest in balance_masa_puerto:
        problema += rest

    # Agregando balance ce masa en planta
    for rest in balance_masa_planta:
        problema += rest

    # Agregando restriccion de recepcion en planta
    for rest in rest_recepcion_planta:
        problema += rest

    # Faltante de objetivo
    for rest in faltante_inventaio_objetivo:
        problema += rest

    t_limit_minutes = 25

    print('cpu count', cpu_count)
    print('ejecutando ', len(periodos), 'periodos')
    engine_cbc = pu.PULP_CBC_CMD(
        timeLimit=60*t_limit_minutes,
        gapRel=0.05,
        warmStart=False,
        threads=cpu_count)

    engine_glpk = pu.GLPK_CMD(
        mip=True,
        timeLimit=60*t_limit_minutes
    )

    problema.writeLP('model.lp')

    problema.solve(solver=engine_cbc)

    pu.LpStatus[problema.status]

    # %% [markdown]
    # ##  Reporte Fase 1

    # %%
    reporte_despachos = list()
    for ingrediente in despachos_planta.keys():
        for planta in despachos_planta[ingrediente].keys():
            for periodo in despachos_planta[ingrediente][planta].keys():
                valor = despachos_planta[ingrediente][planta][periodo].varValue
                tiempo_proceso = tiempos_proceso[planta][ingrediente]
                dato = {
                    'variable': 'despacho a planta',
                    'ingrediente': ingrediente,
                    'planta': planta,
                    'periodo': periodo,
                    'valor': valor,
                    'tiempo_recepcion': valor*tiempo_proceso
                }
                reporte_despachos.append(dato)

    # %%
    reporte_inventario_puerto = list()
    for ingrediente in inventario_puerto.keys():
        for periodo in inventario_puerto[ingrediente].keys():
            dato = {
                'variable': 'inventario en puerto',
                'ingrediente': ingrediente,
                'periodo': periodo,
                'valor': inventario_puerto[ingrediente][periodo].varValue
            }
            reporte_inventario_puerto.append(dato)

    # %%
    reporte_inventario_planta = list()
    for planta in inventario_planta.keys():
        for ingrediente in inventario_planta[planta].keys():
            for periodo in inventario_planta[planta][ingrediente]:
                dato = {
                    'variable': 'inventario en planta',
                    'planta': planta,
                    'ingrediente': ingrediente,
                    'periodo': periodo,
                    'valor': inventario_planta[planta][ingrediente][periodo].varValue,
                    'capacidad': capacidad_planta[planta][ingrediente],
                    'consumo': consumo_proyectado[planta][ingrediente][periodo],
                    'backorder': backorder[planta][ingrediente][periodo].varValue,
                    'objetivo': objetivo_inventario[planta][ingrediente]
                }
                reporte_inventario_planta.append(dato)

    # %% [markdown]
    # ## Fase 2
    # Dado que ya se tendrá un plan de recepcion de camiones en las plantas, la fase 2 asigna el invenatario en puerto a los camiones
    # a despachar, minimizando el costo de almacenamiento y transporte

    # %% [markdown]
    # ## Parámetros

    # %% [markdown]
    # ### Lista de importaciones

    # %%
    importaciones = list()
    for i in tqdm(range(cargas_despachables_df.shape[0])):
        inventario = int(cargas_despachables_df.iloc[i]['Inventario'])
        llegadas = int(cargas_despachables_df.iloc[i]['Llegada'])

        if inventario > 34000 or llegadas > 34000:

            index = (cargas_despachables_df.iloc[i]['Empresa'],
                     cargas_despachables_df.iloc[i]['Puerto'],
                     cargas_despachables_df.iloc[i]['Operador'],
                     cargas_despachables_df.iloc[i]['Ingrediente'],
                     cargas_despachables_df.iloc[i]['Importacion'])

            importaciones.append(index)

    importaciones = list(set(importaciones))

    # %% [markdown]
    # ### Llegadas a puerto

    # %%
    transitos_a_puerto_df = cargas_despachables_df[cargas_despachables_df['Llegada'] > 0].copy(
    )
    transitos_a_puerto_df.set_index(
        ['Empresa', 'Puerto', 'Operador', 'Ingrediente', 'Importacion', 'Fecha'], inplace=True)

    # %%
    llegadas_puerto = dict()
    for i in tqdm(importaciones):
        llegadas_puerto[i] = dict()
        for periodo in periodos:
            i2 = tuple(list(i) + [periodo])

            if i2 in transitos_a_puerto_df.index:
                cantidad_puerto = int(transitos_a_puerto_df.loc[i2]['Llegada'])
            else:
                cantidad_puerto = 0
            llegadas_puerto[i][periodo] = cantidad_puerto

    # %% [markdown]
    # ### Inventario inicial Puerto

    # %%
    inventario_inicial_puerto_df = cargas_despachables_df[cargas_despachables_df['Inventario'] > 0].copy(
    )
    inventario_inicial_puerto_df.set_index(
        keys=['Empresa', 'Puerto', 'Operador', 'Ingrediente', 'Importacion'], inplace=True)

    # %%
    inventario_inicial_puerto = dict()
    for i in tqdm(importaciones):
        if i in inventario_inicial_puerto_df.index:
            cantidad = int(
                inventario_inicial_puerto_df.loc[i]['Inventario'])
        else:
            cantidad = 0
        inventario_inicial_puerto[i] = cantidad

    # %% [markdown]
    # ### Costos de transporte

    # %%
    columns = ['Empresa', 'Puerto', 'Operador',
               'Ingrediente', 'Importacion', 'valor_kg']
    importaciones_df = cargas_despachables_df.groupby(
        columns)[[]].count().reset_index().copy()

    # %%
    df = importaciones_df.rename(columns={'Empresa': 'Empresa_Origen'}).copy()

    print(df.shape)

    # %%
    # Cruzar con fechas de consumo
    df = pd.merge(left=df,
                  right=pd.DataFrame(periodos).rename(columns={0: 'Fecha'}),
                  how='cross')
    print(df.shape)

    # %%
    temp = fletes_df.copy()
    columns = ['puerto', 'operador', 'ingrediente']
    temp = temp.melt(id_vars=columns, value_vars=temp.drop(
        columns=columns).columns, var_name='Planta', value_name='flete_kg')
    temp['Empresa_Destino'] = temp['Planta'].map(empresas_dict)
    temp['Flete_Camion'] = 34000*temp['flete_kg']
    temp.drop(columns=['flete_kg'], inplace=True)
    temp.rename(columns={'puerto': 'Puerto', 'operador': 'Operador',
                'ingrediente': 'Ingrediente'}, inplace=True)
    print(temp.shape)

    # %%
    # Cruzar con fletes
    df = pd.merge(left=df,
                  right=temp,
                  left_on=['Puerto', 'Operador', 'Ingrediente'],
                  right_on=['Puerto', 'Operador', 'Ingrediente'],
                  how='left')
    print(df.shape)

    # %%
    costo_portuario_directo_df = costo_portuario_directo_df.rename(columns={'operador': 'Operador',
                                                                            'puerto': 'Puerto',
                                                                            'ingrediente': 'Ingrediente',
                                                                            'valor_kg': 'Directo'})

    # %%
    # cruzar transitos con operacion portuaria de despacho directo
    temp = pd.merge(left=transitos_a_puerto_df.reset_index().drop(columns=['Llegada', 'Camiones', 'valor_kg', 'Inventario']).rename(columns={'Empresa': 'Empresa_Origen'}),
                    right=costo_portuario_directo_df,
                    left_on=['Operador', 'Puerto', 'Ingrediente'],
                    right_on=['Operador', 'Puerto', 'Ingrediente'],
                    how='left')
    # temp['Fecha'] = temp['Fecha'].apply(lambda x: x.strftime("%Y-%m-%d"))
    temp['Directo'] = 34000*temp['Directo']
    print(temp.shape)

    # %%
    # Anexar costos portuarios por despacho directo
    df = pd.merge(left=df,
                  right=temp,
                  left_on=['Empresa_Origen', 'Puerto', 'Operador',
                           'Ingrediente', 'Importacion', 'Fecha'],
                  right_on=['Empresa_Origen', 'Puerto', 'Operador',
                            'Ingrediente', 'Importacion', 'Fecha'],
                  how='left')
    df['Directo'] = df['Directo'].fillna(0)

    # %%
    intercompany_df = intercompany_df.melt(id_vars='origen', value_vars=empresas, var_name='Empresa_Destino',
                                           value_name='intercompany').rename(columns={'origen': 'Empresa_Origen'})

    # %%
    # Intercompany
    df = pd.merge(left=df,
                  right=intercompany_df,
                  left_on=['Empresa_Origen', 'Empresa_Destino'],
                  right_on=['Empresa_Origen', 'Empresa_Destino'],
                  how='left')

    # %%
    df['Directo'].unique()

    # %%
    # Calcular costo total despacho
    df['CostoTotalCamion'] = df['Flete_Camion'] + df['Directo'] + \
        (34000*df['intercompany']*df['valor_kg'])

    # %%
    costo_transporte_df = df.copy()

    # %%
    costo_transporte_df.set_index(keys=['Empresa_Origen', 'Puerto', 'Operador',
                                        'Ingrediente', 'Importacion', 'Planta', 'Fecha'], inplace=True)

    # %%
    costo_transporte = dict()
    for i in tqdm(importaciones):
        costo_transporte[i] = dict()
        for planta in plantas:
            costo_transporte[i][planta] = dict()
            for periodo in periodos:
                impo_index = tuple(list(i) + [planta, periodo])
                if impo_index in costo_transporte_df.index:
                    costo = costo_transporte_df.loc[impo_index]['CostoTotalCamion']
                    costo_transporte[i][planta][periodo] = costo

    # %% [markdown]
    # ### Costo de almacenamiento

    # %%
    df = costos_almacenamiento_df.set_index(
        ['empresa', 'puerto', 'operador', 'ingrediente', 'importacion', 'fecha_corte'])

    # %%
    costo_almacenamiento = dict()
    for i in tqdm(importaciones):
        costo_almacenamiento[i] = dict()
        for periodo in periodos:
            impo_index = tuple(list(i) + [periodo])
            if impo_index in df.index:
                costo = df.loc[impo_index]['valor_kg']
            else:
                costo = 0.0

            if not periodo in costo_almacenamiento[i].keys():
                costo_almacenamiento[i][periodo] = dict()
            costo_almacenamiento[i][periodo] = costo

    # %%
    # Demanda de la planta
    demanda_planta = dict()
    for planta in tqdm(plantas):
        demanda_planta[planta] = dict()
        for ingrediente in ingredientes:
            demanda_planta[planta][ingrediente] = dict()
            for periodo in periodos[1:-2:]:
                demanda_planta[planta][ingrediente][periodo] = despachos_planta[ingrediente][planta][periodo].varValue

    # %% [markdown]
    # ## Variables:

    # %%
    # Inventario en puerto
    var_inventario_puerto = dict()
    for importacion in tqdm(importaciones):
        var_inventario_puerto[importacion] = dict()
        for periodo in periodos:
            var_name = f"inv_{'_'.join(list(importacion)).replace(' ','')}_{periodo}"
            var = pu.LpVariable(name=var_name, lowBound=0, cat=pu.LpContinuous)
            var_inventario_puerto[importacion][periodo] = var

    # %%
    # Despachos hacia plantas
    var_despachos = dict()
    for importacion in tqdm(importaciones):
        var_despachos[importacion] = dict()
        for planta in plantas:
            var_despachos[importacion][planta] = dict()
            for periodo in periodos[1:-2:]:
                var_name = f'desp_{"_".join(importacion)}_{planta}_{periodo}'
                var = pu.LpVariable(name=var_name,
                                    lowBound=0,
                                    upBound=1000,
                                    cat=pu.LpInteger)
                var_despachos[importacion][planta][periodo] = var

    # %% [markdown]
    # ## Funcion Objetivo

    # %% [markdown]
    # Minimizar el costo de despacho y almacenamiento
    #
    # $ \sum_{i}{\sum_{j}{CR_{i,j}X_{i,j}}} $
    #

    # %%
    # Costo de transporte
    costo_transporte_fobj = [costo_transporte[i][j][t]*var_despachos[i][j][t]
                             for i in importaciones for j in plantas for t in periodos[1:-2:]]

    # %%
    # Costo Almacenamiento
    costo_almacenamiento_fobj = [34000*costo_almacenamiento[i][t] *
                                 var_inventario_puerto[i][t] for i in importaciones for t in periodos]

    # %%
    fobj = costo_transporte_fobj + costo_almacenamiento_fobj

    # %% [markdown]
    # ## Restricciones

    # %% [markdown]
    # Cumplimiento de la demanda
    #
    # $ \sum_{i}\sum_{j}\sum_{t}{X_{ijt}} >=  D_{jt}  $

    # %%
    cumplimiento_demanda_rest = list()
    for j in tqdm(plantas):
        for ingrediente in ingredientes:
            imp_list = [importaciones[i] for i in range(
                len(importaciones)) if importaciones[i][3] == ingrediente]
            for t in periodos[1:-2:]:
                left = pu.lpSum([var_despachos[i][j][t]
                                for i in importaciones if i[3] == ingrediente])
                right = demanda_planta[j][ingrediente][t]
                rest_name = f'cumplir_demanda_{ingrediente}_{j}_{t}'
                rest = (left == right, rest_name)
                cumplimiento_demanda_rest.append(rest)

    # %%
    len(set([x for x in importaciones]))

    # %% [markdown]
    # Balance de inventario
    #
    # $ I_{it} = I_{it-1} + A_{it} - \sum_{j}{X_{ijt}} \forall{i}, \forall {1>t>T-2}$

    # %%
    balance_inventario_puerto_rest = list()
    for i in tqdm(importaciones):

        # Generar inventario inicial como restriccion
        Iit = var_inventario_puerto[i][periodos[0]]
        if i in inventario_inicial_puerto.keys():
            Iit_1 = inventario_inicial_puerto[i]
        else:
            Iit_1 = 0
        Ait = llegadas_puerto[i][periodos[0]]
        rest_name = f"balance_inv_{'_'.join(i).replace(' ','_')}_{periodos[0]}"
        rest = (Iit == Iit_1 + Ait, rest_name)
        balance_inventario_puerto_rest.append(rest)

        # Balance de inventario con respecto al periodo anterior
        for t in periodos[1:-2:]:
            Iit = var_inventario_puerto[i][t]
            t_1 = periodos[periodos.index(t)-1]
            Iit_1 = var_inventario_puerto[i][t_1]
            Ait = llegadas_puerto[i][t]
            sum_des = [34000*var_despachos[i][j][t] for j in plantas]
            rest_name = f"balance_inv_{'_'.join(i).replace(' ','_')}_{t}"
            rest = (Iit == Iit_1 + Ait - pu.lpSum(sum_des), rest_name)
            balance_inventario_puerto_rest.append(rest)

    # %%
    balance_inventario_puerto_rest[0][1]

    # %% [markdown]
    # ## Resolver el model

    # %%
    # Cantidad CPU habilitadas para trabajar
    cpu_count = max(1, os.cpu_count()-1)

    problema = pu.LpProblem(name='Bios_Solver_fase_2', sense=pu.LpMinimize)

    # Agregando funcion objetivo
    problema += pu.lpSum(fobj)

    # Agregando balance de masa puerto
    for rest in balance_inventario_puerto_rest:
        problema += rest

    # cumplimiento de la demanda en la planta
    for rest in cumplimiento_demanda_rest:
        problema += rest

    t_limit_minutes = 5

    print('------------------------------------')
    print('cpu count', cpu_count)
    print('ejecutando ', len(periodos), 'periodos')
    engine_cbc = pu.PULP_CBC_CMD(
        timeLimit=60*t_limit_minutes,
        gapRel=0.05,
        warmStart=False,
        threads=cpu_count)

    engine_glpk = pu.GLPK_CMD(
        mip=True,
        timeLimit=60*t_limit_minutes
    )

    problema.writeLP('model_2.lp')

    problema.solve(solver=engine_cbc)

    # %%
    pu.LpStatus[problema.status]

    # %% [markdown]
    # ## Generar Reporte

    # %%
    reporte_puerto = list()
    for i in tqdm(importaciones):
        for t in periodos[:-2:]:
            dato = dict()
            dato['Empresa'] = i[0]
            dato['Puerto'] = i[1]
            dato['Operador'] = i[2]
            dato['ingrediente'] = i[3]
            dato['Importacion'] = i[4]
            dato['Fecha'] = t
            dato['Inventario'] = var_inventario_puerto[i][t].varValue
            dato['llegadas'] = llegadas_puerto[i][t]
            dato['Costo_Almacenamiento'] = int(costo_almacenamiento[i][t])
            dato['Costo_Total_Almacenamiento'] = dato['Inventario'] * \
                dato['Costo_Almacenamiento']
            reporte_puerto.append(dato)

    reporte_puerto_df = pd.DataFrame(reporte_puerto)

    # %%
    reporte_despachos = list()
    for i in tqdm(importaciones):
        for j in plantas:
            for t in periodos[1:-2:]:
                valor = var_despachos[i][j][t].varValue
                tiempo_proceso = tiempos_proceso[planta][ingrediente]
                dato = dict()
                dato['Empresa'] = i[0]
                dato['Puerto'] = i[1]
                dato['Operador'] = i[2]
                dato['ingrediente'] = i[3]
                dato['Importacion'] = i[4]
                dato['Fecha'] = t
                dato['Planta'] = j
                dato['Camiones_despachados'] = var_despachos[i][j][t].varValue
                dato['Costo_Transporte_camion'] = costo_transporte[i][j][t]
                dato['Costo_Transprote'] = dato['Camiones_despachados'] * \
                    dato['Costo_Transporte_camion']
                reporte_despachos.append(dato)

    reporte_despachos_df = pd.DataFrame(reporte_despachos)

    # %%
    reporte_inventario_planta = list()
    for planta in inventario_planta.keys():
        for ingrediente in inventario_planta[planta].keys():
            for periodo in inventario_planta[planta][ingrediente]:
                dato = {
                    'variable': 'inventario en planta',
                    'planta': planta,
                    'ingrediente': ingrediente,
                    'periodo': periodo,
                    'inventario': inventario_planta[planta][ingrediente][periodo].varValue,
                    'capacidad': capacidad_planta[planta][ingrediente],
                    'consumo': consumo_proyectado[planta][ingrediente][periodo],
                    'backorder': backorder[planta][ingrediente][periodo].varValue,
                    'objetivo': objetivo_inventario[planta][ingrediente]
                }
                reporte_inventario_planta.append(dato)

    reporte_planta_df = pd.DataFrame(reporte_inventario_planta)

    # %%
    # with pd.ExcelWriter('reporte_final.xlsx') as writer:
    #    reporte_puerto_df.to_excel(
    #        writer, sheet_name='inventario_puerto', index=False)
    #    reporte_despachos_df.to_excel(writer, sheet_name='despachos', index=False)
    #    reporte_planta_df.to_excel(
    #        writer, sheet_name='inventario_planta', index=False)

    reportes_dict = {'puerto': reporte_puerto_df,
                     'despacho': reporte_despachos_df, 'planta': reporte_planta_df}

    return reportes_dict


@st.cache_data
def convert_df(df):
    # IMPORTANT: Cache the conversion to prevent computation on every rerun
    return df.to_csv().encode("utf-8")


st.set_page_config(layout="wide")

st.button(label='call_back')

st.title('Optimizador BIOS')

if 'resultado' not in st.session_state:

    st.write('Seleccione un archivo para trabajar')

    uploaded_file = st.file_uploader("Seleccione un archivo para trabajar")

    if uploaded_file is not None:

        with st.spinner(text='Espere un momento por favor, se esta cargando el archivo'):

            # st.session_state['resultado'] = pd.read_excel(io=uploaded_file, sheet_name='consumo_proyectado')

            reportes_dict = resolver_modelo(uploaded_file)
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
