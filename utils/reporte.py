#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun May  5 23:52:31 2024

@author: luispinilla
"""

import pandas as pd
from tqdm import tqdm
from datetime import timedelta

def generar_reporte(plantas_df: pd.DataFrame, cargas_df: pd.DataFrame, variables: dict):

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
                    plantas_df.iloc[i, columns.index(periodo)] = nuevo_valor

        # Variables de backorder de plantas
        if variable == 'backorder':
            inventarios = variables['backorder']
            key = f'{planta}_{ingrediente}'
            if key in inventarios.keys():
                for periodo, lp_var in inventarios[key].items():
                    nuevo_valor = lp_var.varValue
                    plantas_df.iloc[i, columns.index(periodo)] = nuevo_valor

    # Llegadas a planta
    print('Agregando datos de recepción al reporte de plantas')
    recibos = list()
    for planta in tqdm(variables['recepcion'].keys()):
        for ingrediente in variables['recepcion'][planta].keys():
            for periodo in variables['recepcion'][planta][ingrediente].keys():
                for llegada in variables['recepcion'][planta][ingrediente][periodo]:
                    cantidad_llegada = llegada.varValue
                    periodo_llegada = periodo - timedelta(days=2)
                    importacion = llegada.name.replace(
                        f'despacho_{ingrediente}_', '')
                    importacion = importacion.replace(f'_{planta}', '')
                    importacion = importacion.replace(
                        f'_{periodo_llegada.strftime("%Y%m%d")}', '')
                    if cantidad_llegada > 0:
                        recibos.append({'planta': planta,
                                        'ingrediente': ingrediente,
                                        'variable': f'llegadas {importacion}',
                                        periodo: cantidad_llegada*34000})

    recibos_df = pd.DataFrame(recibos)
    group_by = ['planta', 'ingrediente', 'variable']
    recibos_df = recibos_df.groupby(group_by).sum().reset_index()
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
                    # valor_anterior = cargas_df.iloc[i,columns.index(periodo)]
                    cargas_df.iloc[i, columns.index(periodo)] = nuevo_valor

    return (plantas_df, cargas_df)


def guardar_reporte(bios_ouput_file: str, plantas_df: pd.DataFrame, cargas_df: pd.DataFrame, estadisticas: pd.DataFrame):

    print('guardando', bios_ouput_file)
    with pd.ExcelWriter(path=bios_ouput_file) as writer:
        plantas_df.to_excel(writer, sheet_name='plantas', index=False)
        cargas_df.to_excel(writer, sheet_name='cargas', index=False)
        estadisticas['objetivo_inventario'].to_excel(
            writer, sheet_name='objetivo_inventario', index=False)
    print(bios_ouput_file, 'guardado exitósamente')