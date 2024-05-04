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
import math
import pulp as pu

def generar_variables_despacho(periodos:list, cargas_df:pd.DataFrame, plantas_df:pd.DataFrame, variables:dict)->dict:
    
    variables_despacho = dict()
    variables_recepcion = dict()
    periodo_admin = 2
    lead_time = 2
    
    for i in tqdm(cargas_df[cargas_df['variable']=='inventario'].index):
        
        ingrediente = cargas_df.loc[i]['ingrediente']
        importacion = cargas_df.loc[i]['importacion']
        empresa = cargas_df.loc[i]['empresa']
        puerto = cargas_df.loc[i]['puerto']
        operador = cargas_df.loc[i]['operador']
        
        importacion_var_group = f'despacho_{ingrediente}_{importacion}_{empresa}_{puerto}_{operador}'
        variables_despacho[importacion_var_group] = dict()
        
        plantas = list(plantas_df[plantas_df['ingrediente']==ingrediente]['planta'].unique())
        
        
        for planta in plantas:
            
            if not planta in variables_recepcion.keys():
                variables_recepcion[planta] = dict()
                
            if not ingrediente in variables_recepcion[planta].keys():
                variables_recepcion[planta][ingrediente] = dict()    
        
            inventario_planta_row = plantas_df[(plantas_df['planta']==planta)&(plantas_df['ingrediente']==ingrediente)&(plantas_df['variable']=='inventario')]
            capacidad_planta_row = plantas_df[(plantas_df['planta']==planta)&(plantas_df['ingrediente']==ingrediente)&(plantas_df['variable']=='capacidad_max')]
        
            for periodo in periodos[periodo_admin:-lead_time:]:
                
                inventario_puerto = cargas_df.loc[i][periodo]
                        
                if inventario_puerto >= 34000:
                               
                    var_name = f'despacho_{ingrediente}_{importacion}_{empresa}_{puerto}_{operador}_{planta}_{periodo.strftime("%Y%m%d")}'
                    
                    max_despacho_puerto = math.trunc(inventario_puerto / 34000)
                    
                    if inventario_planta_row.shape[0]==1:
                        inventario_planta = float(inventario_planta_row.iloc[0][periodo])
                    else:
                        inventario_planta = 0.0
                        
                    if capacidad_planta_row.shape[0]==1:
                        capacidad_planta = float(capacidad_planta_row.iloc[0][periodo])
                    else:
                        capacidad_planta = 0.0
                        
                    max_recepcion = math.trunc(capacidad_planta - inventario_planta)/34000
                    
                    upbound = max(max_recepcion, max_despacho_puerto)
                    
                    var = pu.LpVariable(name=var_name,
                                        lowBound=0,
                                        upBound=upbound,
                                        cat=pu.LpInteger)
                    
                    
                    if not periodo in variables_despacho[importacion_var_group].keys():
                        variables_despacho[importacion_var_group][periodo] = list()
                        
                    periodo_entrega = periodos[periodos.index(periodo)+lead_time]     
                    if not periodo_entrega in variables_recepcion[planta][ingrediente].keys():                 
                        variables_recepcion[planta][ingrediente][periodo_entrega] = list()
                    
                    variables_despacho[importacion_var_group][periodo].append(var)
                    variables_recepcion[planta][ingrediente][periodo_entrega].append(var)

    variables['despacho'] = variables_despacho
    variables['recepcion'] = variables_recepcion
    
def generar_variables_inventario_puerto(variables:dict, periodos:list, cargas_df:pd.DataFrame):
    
    variables_inventario_puerto = dict()
    
    for i in tqdm(cargas_df[cargas_df['variable']=='inventario'].index):
        
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
                                upBound=inventario_puerto,
                                cat=pu.LpContinuous)
            
            variables_inventario_puerto[importacion_var_group][periodo]=var
            
    variables['inventario_puerto'] = variables_inventario_puerto
        
    
def generar_variables_inventario_planta(variables:dict, periodos:list, plantas_df:pd.DataFrame):    
    pass


def generar_variables_backorder_planta(variables:dict, periodos:list, plantas_df:pd.DataFrame):
    pass


def generar_Variables_safety_stock_planta(variables:dict, periodos:list, plantas_df:pd.DataFrame):
    pass

def generar_funcion_objetivo(variables:dict, periodos:list, cargas_df:pd.DataFrame, plantas_df:pd.DataFrame)->list:
    # Costo de transporte
    # Costo almacenamiento en puerto
    # costo backorder
    # Costo no alcanzar SS
    pass
    

def generar_res_balance_masa_cargas()->list:
    pass

def generar_res_balance_masa_plantas()->list:
    pass

def generar_res_capacidad_recepcion_plantas()->list:
    pass

def generar_res_superar_ss()->list:
    pass

def generar_res_objetivo_fin_mes()->list:
    pass

def resolver_modelo():
    pass


def generar_reporte():

    
    
def generar_modelo(file:str):
    
    variables = dict()
    
    dataframes = __leer_archivo(bios_input_file=bios_input_file)

    periodos = __generar_periodos(dataframes)
    
    estadisticas = obtener_objetivo_inventario(bios_input_file)

    plantas_df = obtener_matriz_plantas(dataframes, periodos, estadisticas)

    cargas_df = obtener_matriz_importaciones(dataframes, periodos)

    validation_list = list()
    
    cargas_df = validacion_eliminar_cargas_sin_inventario(cargas_df,validation_list)

    plantas_df = validacion_eliminar_ingredientes_sin_consumo(plantas_df, validation_list)

    bios_model_file = bios_input_file.replace('.xlsm', '_model.xlsx')
    
    generar_variables_despacho(periodos, cargas_df, plantas_df, variables)
    
    generar_variables_inventario_puerto(variables, periodos, cargas_df)
    
    with pd.ExcelWriter(path=bios_model_file) as writer:
        plantas_df.to_excel(writer, sheet_name='plantas', index=False)
        cargas_df.to_excel(writer, sheet_name='cargas', index=False)
        estadisticas['objetivo_inventario'].to_excel(writer, sheet_name='objetivo_inventario', index=False)

   
    



if __name__ == '__main__':

    bios_input_file = 'data/0_model_template_2204.xlsm'

    dataframes = __leer_archivo(bios_input_file=bios_input_file)

    periodos = __generar_periodos(dataframes)
    
    estadisticas = obtener_objetivo_inventario(bios_input_file)

    plantas_df = obtener_matriz_plantas(dataframes, periodos, estadisticas)

    cargas_df = obtener_matriz_importaciones(dataframes, periodos)

    validation_list = list()
    
    cargas_df = validacion_eliminar_cargas_sin_inventario(cargas_df,validation_list)

    plantas_df = validacion_eliminar_ingredientes_sin_consumo(plantas_df, validation_list)

    bios_model_file = bios_input_file.replace('.xlsm', '_model.xlsx')
    
    

    with pd.ExcelWriter(path=bios_model_file) as writer:
        plantas_df.to_excel(writer, sheet_name='plantas', index=False)
        cargas_df.to_excel(writer, sheet_name='cargas', index=False)
        estadisticas['objetivo_inventario'].to_excel(writer, sheet_name='objetivo_inventario', index=False)

    print('finalizado')