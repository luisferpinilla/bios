#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat May  4 09:48:51 2024

@author: luispinilla
"""

import pandas as pd
from utils.planta_loader import __leer_archivo
from utils.planta_loader import __generar_periodos
from utils.planta_loader import obtener_objetivo_inventario
from utils.planta_loader import obtener_matriz_plantas
from utils.planta_loader import obtener_matriz_importaciones
from utils.planta_loader import validacion_eliminar_cargas_sin_inventario
from utils.planta_loader import validacion_eliminar_ingredientes_sin_consumo
from tqdm import tqdm
from datetime import timedelta
import math
import pulp as pu
import os


def generar_variables_despacho(periodos: list, cargas_df: pd.DataFrame, plantas_df: pd.DataFrame, variables: dict) -> dict:

    variables_despacho = dict()
    variables_recepcion = dict()
    periodo_admin = 2
    lead_time = 2

    for i in tqdm(cargas_df[cargas_df['variable'] == 'inventario'].index):

        ingrediente = cargas_df.loc[i]['ingrediente']
        importacion = cargas_df.loc[i]['importacion']
        empresa = cargas_df.loc[i]['empresa']
        puerto = cargas_df.loc[i]['puerto']
        operador = cargas_df.loc[i]['operador']

        importacion_var_group = f'{ingrediente}_{importacion}_{empresa}_{puerto}_{operador}'
        variables_despacho[importacion_var_group] = dict()

        plantas = list(
            plantas_df[plantas_df['ingrediente'] == ingrediente]['planta'].unique())

        for planta in plantas:

            variables_despacho[importacion_var_group][planta] = dict()

            if not planta in variables_recepcion.keys():
                variables_recepcion[planta] = dict()

            if not ingrediente in variables_recepcion[planta].keys():
                variables_recepcion[planta][ingrediente] = dict()

            inventario_planta_row = plantas_df[(plantas_df['planta'] == planta) & (
                plantas_df['ingrediente'] == ingrediente) & (plantas_df['variable'] == 'inventario')]
            capacidad_planta_row = plantas_df[(plantas_df['planta'] == planta) & (
                plantas_df['ingrediente'] == ingrediente) & (plantas_df['variable'] == 'capacidad_max')]

            for periodo in periodos[periodo_admin:-lead_time:]:

                inventario_puerto = cargas_df.loc[i][periodo]

                if inventario_puerto >= 34000:

                    var_name = f'despacho_{ingrediente}_{importacion}_{empresa}_{puerto}_{operador}_{planta}_{periodo.strftime("%Y%m%d")}'

                    max_despacho_puerto = math.trunc(inventario_puerto / 34000)

                    if inventario_planta_row.shape[0] == 1:
                        inventario_planta = float(
                            inventario_planta_row.iloc[0][periodo])
                    else:
                        inventario_planta = 0.0

                    if capacidad_planta_row.shape[0] == 1:
                        capacidad_planta = float(
                            capacidad_planta_row.iloc[0][periodo])
                    else:
                        capacidad_planta = 0.0

                    max_recepcion = math.trunc(
                        capacidad_planta - inventario_planta)/34000

                    upbound = max(max_recepcion, max_despacho_puerto)

                    var = pu.LpVariable(name=var_name,
                                        lowBound=0,
                                        upBound=upbound,
                                        cat=pu.LpInteger)

                    var.setInitialValue(val=0, check=True)

                    variables_despacho[importacion_var_group][planta][periodo] = var

                    periodo_entrega = periodos[periodos.index(
                        periodo)+lead_time]
                    if not periodo_entrega in variables_recepcion[planta][ingrediente].keys():
                        variables_recepcion[planta][ingrediente][periodo_entrega] = list(
                        )

                    variables_recepcion[planta][ingrediente][periodo_entrega].append(
                        var)

    variables['despacho'] = variables_despacho
    variables['recepcion'] = variables_recepcion


def generar_variables_inventario_puerto(variables: dict, periodos: list, cargas_df: pd.DataFrame):

    variables_inventario_puerto = dict()

    for i in tqdm(cargas_df[cargas_df['variable'] == 'inventario'].index):

        ingrediente = cargas_df.loc[i]['ingrediente']
        importacion = cargas_df.loc[i]['importacion']
        empresa = cargas_df.loc[i]['empresa']
        puerto = cargas_df.loc[i]['puerto']
        operador = cargas_df.loc[i]['operador']

        importacion_var_group = f'{ingrediente}_{importacion}_{empresa}_{puerto}_{operador}'
        variables_inventario_puerto[importacion_var_group] = dict()

        for periodo in periodos:

            inventario_puerto = cargas_df.loc[i][periodo]

            var_name = f'inventario_{importacion_var_group}_{periodo.strftime("%Y%m%d")}'

            var = pu.LpVariable(name=var_name,
                                lowBound=0.0,
                                upBound=math.ceil(inventario_puerto),
                                cat=pu.LpContinuous)

            var.setInitialValue(val=inventario_puerto, check=True)

            variables_inventario_puerto[importacion_var_group][periodo] = var

    variables['inventario_puerto'] = variables_inventario_puerto


def generar_variables_inventario_planta(variables: dict, periodos: list, plantas_df: pd.DataFrame):

    variables_inventario = dict()

    for i in tqdm(plantas_df[plantas_df['variable'] == 'inventario'].index):

        planta = plantas_df.loc[i]['planta']
        ingrediente = plantas_df.loc[i]['ingrediente']

        var_group = f'{planta}_{ingrediente}'

        variables_inventario[var_group] = dict()

        capacidad_row = plantas_df[(plantas_df['planta'] == planta) & (
            plantas_df['ingrediente'] == ingrediente) & (plantas_df['variable'] == 'capacidad_max')].copy()
        inventario_row = plantas_df[(plantas_df['planta'] == planta) & (
            plantas_df['ingrediente'] == ingrediente) & (plantas_df['variable'] == 'inventario')].copy()

        for periodo in periodos:

            if capacidad_row.shape[0] == 1:

                capacidad = capacidad_row.iloc[0][periodo]
                inventario = inventario_row.iloc[0][periodo]

                var_name = f'inventario_{var_group}_{periodo.strftime("%Y%m%d")}'

                var = pu.LpVariable(name=var_name,
                                    lowBound=0.0,
                                    upBound=math.ceil(
                                        max(capacidad, inventario)),
                                    cat=pu.LpContinuous)

                var.setInitialValue(val=inventario, check=True)

                variables_inventario[var_group][periodo] = var

    variables['inventario_planta'] = variables_inventario


def generar_variables_backorder_planta(variables: dict, periodos: list, plantas_df: pd.DataFrame):

    variables_backorder = dict()

    for i in tqdm(plantas_df[plantas_df['variable'] == 'backorder'].index):

        planta = plantas_df.loc[i]['planta']
        ingrediente = plantas_df.loc[i]['ingrediente']

        var_group = f'{planta}_{ingrediente}'

        variables_backorder[var_group] = dict()

        consumo_row = plantas_df[(plantas_df['planta'] == planta) & (
            plantas_df['ingrediente'] == ingrediente) & (plantas_df['variable'] == 'consumo')].copy()
        inventario_row = plantas_df[(plantas_df['planta'] == planta) & (
            plantas_df['ingrediente'] == ingrediente) & (plantas_df['variable'] == 'inventario')].copy()

        for periodo in periodos:

            if consumo_row.shape[0] == 1:

                consumo = consumo_row.iloc[0][periodo]
                inventario = inventario_row.iloc[0][periodo]

                var_name = f'backorder_{var_group}_{periodo.strftime("%Y%m%d")}'

                var = pu.LpVariable(name=var_name,
                                    lowBound=0.0,
                                    upBound=consumo,
                                    cat=pu.LpContinuous)
                if consumo < inventario:
                    var.setInitialValue(val=0.0, check=True)
                else:
                    var.setInitialValue(val=consumo-inventario, check=True)

                variables_backorder[var_group][periodo] = var

    variables['backorder'] = variables_backorder


def generar_Variables_safety_stock_planta(variables: dict, periodos: list, plantas_df: pd.DataFrame):

    variables_ss = dict()

    for i in tqdm(plantas_df[plantas_df['variable'] == 'safety_stock'].index):

        planta = plantas_df.loc[i]['planta']
        ingrediente = plantas_df.loc[i]['ingrediente']

        var_group = f'safety_stock_{planta}_{ingrediente}'

        variables_ss[var_group] = dict()

        safety_stock_row = plantas_df[(plantas_df['planta'] == planta) & (
            plantas_df['ingrediente'] == ingrediente) & (plantas_df['variable'] == 'safety_stock')].copy()
        inventario_row = plantas_df[(plantas_df['planta'] == planta) & (
            plantas_df['ingrediente'] == ingrediente) & (plantas_df['variable'] == 'inventario')].copy()

        for periodo in periodos:

            if safety_stock_row.shape[0] == 1:

                safety_stock = safety_stock_row.iloc[0][periodo]
                inventario = inventario_row.iloc[0][periodo]

                if safety_stock > 0:

                    if inventario < safety_stock:

                        var_name = f'{var_group}_{periodo.strftime("%Y%m%d")}'

                        var = pu.LpVariable(name=var_name,
                                            lowBound=0.0,
                                            upBound=math.ceil(safety_stock),
                                            cat=pu.LpContinuous)

                        var.setInitialValue(
                            val=safety_stock-inventario, check=True)

                        variables_ss[var_group][periodo] = var

    variables['safety_sotck'] = variables_ss


def generar_funcion_objetivo(variables: dict, periodos: list, cargas_df: pd.DataFrame, plantas_df: pd.DataFrame) -> list:

    # Costo de no safety stock por día
    costo_safety_stock_dia = 50000

    # Costo de backorder por dia
    costo_backorder_dia = costo_safety_stock_dia*5

    # Costo de transporte

    costo_transporte_fobj = list()

    cargas = cargas_df.set_index(
        ['ingrediente', 'importacion', 'empresa', 'puerto', 'operador', 'variable']).copy()

    importaciones_index = list(
        set([(i[0], i[1], i[2], i[3], i[4]) for i in cargas.index]))

    plantas = list(plantas_df['planta'].unique())

    for i in tqdm(importaciones_index):

        key = '_'.join(i)

        for planta in plantas:

            if planta in variables['despacho'][key].keys():

                costo_despacho_camion_row = cargas.loc[(
                    i[0], i[1], i[2], i[3], i[4], f'costo_total_despacho_camion_{planta}')]

                for periodo in periodos:

                    if periodo in variables['despacho'][key][planta].keys():

                        costo = costo_despacho_camion_row[periodo]

                        var = variables['despacho'][key][planta][periodo]

                        costo_transporte_fobj.append(costo*var)

    # Costo almacenamiento en puerto
    costo_almacenamiento_fobj = list()

    for i in tqdm(importaciones_index):

        key = '_'.join(i)

        costo_almacenamiento_row = cargas.loc[(
            i[0], i[1], i[2], i[3], i[4], f'costo_almacenamiento_por_kg')]

        for periodo in periodos:

            costo_almacenamiento = costo_almacenamiento_row[periodo]

            if costo_almacenamiento > 0.0:

                var = variables['inventario_puerto'][key][periodo]

                costo_almacenamiento_fobj.append(costo_almacenamiento*var)

    # costo backorder
    costo_backorder_obj = list()

    for planta_ingrediente, values in tqdm(variables['backorder'].items()):

        for periodo, variable in values.items():

            costo_backorder_obj.append(costo_backorder_dia*variable)

    # Costo no alcanzar SS
    costo_safety_stock_obj = list()

    for planta_ingrediente, values in tqdm(variables['safety_sotck'].items()):

        for periodo, variable in values.items():

            costo_safety_stock_obj.append(costo_safety_stock_dia*variable)
            
    f_obj = costo_transporte_fobj + costo_almacenamiento_fobj + costo_backorder_obj + costo_safety_stock_obj

    return f_obj


def generar_res_balance_masa_cargas(variables: dict, periodos: list, cargas_df: pd.DataFrame) -> list:

    rest_list = list()

    # Periodo anterior
    periodo_anterior = periodos[0] - timedelta(days=1)

    cargas = cargas_df.set_index(
        ['ingrediente', 'importacion', 'empresa', 'puerto', 'operador', 'variable']).copy()

    for importacion in variables['inventario_puerto'].keys():

        i = importacion.split('_')

        inventario_inicial = cargas.loc[(
            i[0], i[1], i[2], i[3], i[4], 'inventario')][periodo_anterior]

        if (i[0], i[1], i[2], i[3], i[4], 'llegadas') in cargas.index:
            llegadas = cargas.loc[(
                i[0], i[1], i[2], i[3], i[4], 'llegadas')][periodo_anterior]
        else:
            llegadas = 0.0

        rest_name = f'balance_puerto_{importacion}_{periodo_anterior.strftime("%Y%m%d")}'

        inv_al_final = variables['inventario_puerto'][importacion][periodos[0]]

        rest = (inv_al_final == inventario_inicial + llegadas, rest_name)

        rest_list.append(rest)

        for hoy in periodos[1:]:

            # Periodo anterior
            ayer = periodos[periodos.index(hoy)-1]

            # inventario al final del periodo anterior
            inventario_ayer = variables['inventario_puerto'][importacion][ayer]

            # inventario al final de hoy
            inventario_hoy = variables['inventario_puerto'][importacion][hoy]

            if (i[0], i[1], i[2], i[3], i[4], 'llegadas') in cargas.index:
                llegadas = cargas.loc[(
                    i[0], i[1], i[2], i[3], i[4], 'llegadas')][hoy]
            else:
                llegadas = 0.0

            rest_name = f'balance_puerto_{importacion}_{hoy.strftime("%Y%m%d")}'

            # Despachos hacia plantas
            despachos = list()
            for planta, item in variables['despacho'][importacion].items():
                if hoy in item.keys():
                    despachos.append(item[hoy])

            if len(despachos) > 0:
                rest = (inventario_hoy == inventario_ayer +
                        llegadas - 34000*pu.lpSum(despachos), rest_name)
            else:
                rest = (inventario_hoy == inventario_ayer + llegadas, rest_name)

            rest_list.append(rest)
            
    return rest_list


def generar_res_balance_masa_plantas(variables: dict, periodos: list, plantas_df: pd.DataFrame) -> list:

    rest_list = list()

    # Periodo anterior
    periodo_anterior = periodos[0] - timedelta(days=1)

    plantas = plantas_df.set_index(
        ['planta', 'ingrediente', 'variable']).copy()

    for planta_ingrediente in variables['inventario_planta'].keys():

        i = planta_ingrediente.split('_')
        planta = i[0]
        ingrediente = i[1]

        inventario_inicial = plantas.loc[(i[0], i[1], 'inventario')][periodo_anterior]

        if (i[0], i[1], 'llegadas_planeadas') in plantas.index:
            llegadas = plantas.loc[(i[0], i[1], 'llegadas_planeadas')][periodo_anterior]
        else:
            llegadas = 0.0

        rest_name = f'balance_planta_{planta_ingrediente}_{periodo_anterior.strftime("%Y%m%d")}'

        
        if periodos[0] in  variables['inventario_planta'][planta_ingrediente]:
            
            inv_al_final = variables['inventario_planta'][planta_ingrediente][periodos[0]]
    
            consumo_row = plantas.loc[(i[0], i[1], 'consumo')] 
    
            rest = (inv_al_final == inventario_inicial + llegadas, rest_name)
    
            rest_list.append(rest)
    
            for hoy in periodos[1:]:
                
                consumo = consumo_row[hoy]
    
                # Periodo anterior
                ayer = periodos[periodos.index(hoy)-1]
    
                # inventario al final del periodo anterior
                inventario_ayer = variables['inventario_planta'][planta_ingrediente][ayer]
    
                # inventario al final de hoy
                inventario_hoy = variables['inventario_planta'][planta_ingrediente][hoy]
                
                # Backorder de hoy
                backorder = variables['backorder'][planta_ingrediente][hoy]
    
                if (i[0], i[1], 'llegadas') in plantas.index:
                    llegadas = plantas.loc[(i[0], i[1], 'llegadas')][hoy]
                else:
                    llegadas = 0.0
    
                rest_name = f'balance_planta_{planta_ingrediente}_{hoy.strftime("%Y%m%d")}'
    
                # Despachos hacia plantas
                llegadas_planta = list()
                if planta in variables['recepcion'].keys():
                    if ingrediente in variables['recepcion'][planta].keys():
                        if hoy in variables['recepcion'][planta][ingrediente].keys():
                            for variable in variables['recepcion'][planta][ingrediente][hoy]:
                                llegadas_planta.append(variable)
    
                if len(llegadas_planta) > 0:
                    rest = (inventario_hoy == inventario_ayer + llegadas + 34000*pu.lpSum(llegadas_planta) - consumo + backorder, rest_name)
                else:
                    rest = (inventario_hoy == inventario_ayer + llegadas - consumo + backorder, rest_name)
    
                rest_list.append(rest)
                
    return rest_list


def generar_res_capacidad_recepcion_plantas(variables:list, plantas_df:pd.DataFrame) -> list:
    
    rest_list = list()
    
    # Despachos hacia plantas
    llegadas_planta = list()
    
    for periodo in tqdm(periodos):
        
        for planta in variables['recepcion'].keys():
            
            rest_name = f'tiempo_recepcion_{planta}_{periodo.strftime("%Y%m%d")}'
            left_expresion = list()
            
            minutos_totales_row = plantas_df[(plantas_df['planta']==planta)&(plantas_df['ingrediente']=='total')&(plantas_df['variable']=='capacidad_total_minutos_dia')]              
            minutos_totales = minutos_totales_row.iloc[0][periodo]
            
            
            for ingrediente in variables['recepcion'][planta].keys():
                
                minutos_ingrediente_row = plantas_df[(plantas_df['planta']==planta)&(plantas_df['ingrediente']==ingrediente)&(plantas_df['variable']=='minutos_por_ingrediente')]              
                minutos_ingrediente = minutos_ingrediente_row.iloc[0][periodo]
                
                if periodo in variables['recepcion'][planta][ingrediente].keys():
                    
                    llegadas = variables['recepcion'][planta][ingrediente][periodo]
                    
                    for llegada in llegadas:
                    
                        left_expresion.append(float(minutos_ingrediente)*llegada)
                    
                    for variable in variables['recepcion'][planta][ingrediente][periodo]:
                        llegadas_planta.append(variable)
        
        rest= (pu.lpSum(left_expresion) <= minutos_totales, rest_name)
        
        rest_list.append(rest)
        
    return rest_list


def generar_res_superar_ss() -> list:
    pass


def generar_res_objetivo_fin_mes(variables:dict, periodos:list) -> list:
    
    rest_list = list()
    
    ultimo_periodo = periodos[-1]
    
    for planta_ingrediente in variables['inventario_planta'].keys():
        campos = planta_ingrediente.split('_')
        planta = campos[0]
        ingrediente = campos[1]
        
        objetivo_row = plantas_df[(plantas_df['planta']==planta)&(plantas_df['ingrediente']==ingrediente)&(plantas_df['variable']=='objetivo_inventario')]              
        if objetivo_row.shape[0]>0:
            objetivo = objetivo_row.iloc[0][ultimo_periodo]
            
            
            if ultimo_periodo in variables['inventario_planta'][planta_ingrediente].keys():
                var = variables['inventario_planta'][planta_ingrediente][ultimo_periodo]
                
                rest_name = f'objetivo_{planta_ingrediente}_{ultimo_periodo.strftime("%Y%m%d")}'
            
                rest = (var >= objetivo, rest_name)
                
                rest_list.append(rest)
    
    return rest_list




def resolver_modelo(variables:dict, periodos:list, cargas_df:pd.DataFrame, plantas_df:pd.DataFrame):
    
    
    # Armar el modelo
    func_obj = generar_funcion_objetivo(variables, periodos, cargas_df, plantas_df)

    rest_balance_puerto = generar_res_balance_masa_cargas(variables, periodos, cargas_df)
    
    rest_balance_planta = generar_res_balance_masa_plantas(variables, periodos, plantas_df)
    
    rest_capacidad_recepcion =  generar_res_capacidad_recepcion_plantas(variables, plantas_df)
    
    rest_objetivo_inventario = generar_res_objetivo_fin_mes(variables, periodos)
    
    problema = pu.LpProblem(name='Bios_Solver', sense=pu.LpMinimize)

    # Agregando funcion objetivo
    problema += pu.lpSum(func_obj)
    
    # Agregando balance de masa puerto
    for rest in rest_balance_puerto:
        problema += rest
    
    # Agregando balande ce masa en planta
    for rest in rest_balance_planta:
        problema += rest
        
    # Agregando restriccion de receocion
    for rest in rest_capacidad_recepcion:
        problema += rest
        
    # Agregando restriccion de objetivo de inventario
    for rest in rest_objetivo_inventario:
        problema += rest
       
    # Cantidad CPU habilitadas para trabajar
    cpu_count = max(1, os.cpu_count()-1)
    
    # Gap en millones de pesos
    gap = 5000000    
    # Tiempo máximo de detencion en minutos
    t_limit_minutes = 10  
        
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






def generar_reporte(plantas_df:pd.DataFrame,cargas_df:pd.DataFrame, variables:dict):
    
    # Remplazar valores en plantas_df y en cargas_df
    print('Generando reporte:')
    
    
    
    print('actualizando informacion de plantas')
    columns = list(plantas_df.columns)
    
    for i in tqdm(range(plantas_df.shape[0])):
        planta = plantas_df.iloc[i]['planta']
        ingrediente = plantas_df.iloc[i]['ingrediente']
        variable = plantas_df.iloc[i]['variable']
        
        # Variables de inventario de plantas
        if variable == 'inventario':
            inventarios = variables['inventario_planta']
            key = f'{planta}_{ingrediente}'
            if key in inventarios.keys():
                for periodo, lp_var in inventarios[key].items():
                    nuevo_valor = lp_var.varValue
                    plantas_df.iloc[i,columns.index(periodo)] = nuevo_valor
    
        # Variables de backorder de plantas
        if variable == 'backorder':
            inventarios = variables['backorder']
            key = f'{planta}_{ingrediente}'
            if key in inventarios.keys():
                for periodo, lp_var in inventarios[key].items():
                    nuevo_valor = lp_var.varValue
                    plantas_df.iloc[i,columns.index(periodo)] = nuevo_valor
    
    # Llegadas a planta
    print('Agregando datos de recepción al reporte de plantas')        
    recibos = list()
    for planta in tqdm(variables['recepcion'].keys()):
        for ingrediente in variables['recepcion'][planta].keys():
            for periodo in variables['recepcion'][planta][ingrediente].keys():
                for llegada in variables['recepcion'][planta][ingrediente][periodo]:
                    cantidad_llegada = llegada.varValue
                    periodo_llegada = periodo - timedelta(days=2)
                    importacion = llegada.name.replace(f'despacho_{ingrediente}_', '')
                    importacion = importacion.replace(f'_{planta}', '')
                    importacion = importacion.replace(f'_{periodo_llegada.strftime("%Y%m%d")}', '')
                    if cantidad_llegada > 0:
                        recibos.append({'planta':planta, 
                                        'ingrediente':ingrediente,
                                        'variable': f'llegadas {importacion}',
                                        periodo:cantidad_llegada*34000})
                        
    recibos_df = pd.DataFrame(recibos)
    group_by = ['planta', 'ingrediente', 'variable']
    recibos_df =  recibos_df.groupby(group_by).sum().reset_index()
    plantas_df = pd.concat([plantas_df, recibos_df]).copy()
    
    
    # Despachos de cargas
    print('Actualizando reporte de cargas')
    columns = list(cargas_df.columns)
    for i in tqdm(range(cargas_df.shape[0])):
        
        ingrediente = cargas_df.iloc[i]['ingrediente']
        importacion = cargas_df.iloc[i]['importacion']
        empresa = cargas_df.iloc[i]['empresa']
        puerto = cargas_df.iloc[i]['puerto']
        operador = cargas_df.iloc[i]['operador']
        variable = cargas_df.iloc[i]['variable']
                    
        # Variables de inventario de cargas
        if variable == 'inventario':
            inventarios = variables['inventario_puerto']
            key = f'{ingrediente}_{importacion}_{empresa}_{puerto}_{operador}'
            if key in inventarios.keys():
                for periodo, lp_var in inventarios[key].items():
                    nuevo_valor = lp_var.varValue
                    valor_anterior = cargas_df.iloc[i,columns.index(periodo)]
                    cargas_df.iloc[i,columns.index(periodo)] = nuevo_valor
                    print(planta,ingrediente, periodo, valor_anterior, nuevo_valor)
                    
              
    return (plantas_df, cargas_df)
      

def guardar_reporte(bios_ouput_file:str, plantas_df:pd.DataFrame, cargas_df:pd.DataFrame, estadisticas:pd.DataFrame):

    print('guardando', bios_ouput_file)
    with pd.ExcelWriter(path=bios_ouput_file) as writer:
        plantas_df.to_excel(writer, sheet_name='plantas', index=False)
        cargas_df.to_excel(writer, sheet_name='cargas', index=False)
        estadisticas['objetivo_inventario'].to_excel(writer, sheet_name='objetivo_inventario', index=False)
    print(bios_ouput_file, 'guardado exitósamente')


def generar_modelo(bios_input_file: str):

    variables = dict()

    dataframes = __leer_archivo(bios_input_file=bios_input_file)

    periodos = __generar_periodos(dataframes)

    estadisticas = obtener_objetivo_inventario(bios_input_file)

    plantas_df = obtener_matriz_plantas(dataframes, periodos, estadisticas)

    cargas_df = obtener_matriz_importaciones(dataframes, periodos)

    validation_list = list()

    cargas_df = validacion_eliminar_cargas_sin_inventario(
        cargas_df, validation_list)

    plantas_df = validacion_eliminar_ingredientes_sin_consumo(
        plantas_df, validation_list)



    generar_variables_despacho(periodos, cargas_df, plantas_df, variables)

    generar_variables_inventario_puerto(variables, periodos, cargas_df)

    generar_variables_inventario_planta(variables, periodos, plantas_df)

    generar_variables_backorder_planta(variables, periodos, plantas_df)

    generar_Variables_safety_stock_planta(variables, periodos, plantas_df)       
    
    return plantas_df, cargas_df, estadisticas, periodos, variables
    


if __name__ == '__main__':

    bios_input_file = 'data/0_model_template_2204.xlsm'
    
    bios_ouput_file = bios_input_file.replace('.xlsm', '_model.xlsx')

    plantas_df, cargas_df, estadisticas, periodos, variables = generar_modelo(bios_input_file)
    
    resolver_modelo(variables, periodos, cargas_df, plantas_df)

    plantas_df, cargas_df = generar_reporte(plantas_df, cargas_df, variables)

    guardar_reporte(bios_ouput_file, plantas_df, cargas_df, estadisticas)

    print('finalizado')
