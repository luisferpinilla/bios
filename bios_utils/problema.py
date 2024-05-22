#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat May 18 17:20:03 2024

@author: luispinilla
"""

import pandas as pd
import numpy as np
from bios_utils.asignador_capacidad import AsignadorCapacidad
from datetime import datetime, timedelta
from bios_utils.objetivo_inventario import obtener_objetivo_inventario
from tqdm import tqdm


def get_inventario_capacidad_planta(bios_input_file:str)->pd.DataFrame:
    # Cargar inventario y capacidad de plantas
    asignador = AsignadorCapacidad(bios_input_file)
    df = asignador.obtener_unidades_almacenamiento()
    df['Capacidad'] = df.apply(lambda x: x[x['ingrediente_actual']], axis=1)
    df.rename(columns={'planta': 'Planta', 'ingrediente_actual': 'Ingrediente',
            'cantidad_actual': 'Inventario'}, inplace=True)
    inventario_planta_df = df.groupby(['Planta', 'Ingrediente'])[
        ['Capacidad', 'Inventario']].sum().reset_index()
    
    return inventario_planta_df


def get_llegadas_programadas_planta(bios_input_file:str)->pd.DataFrame:
    # llegadas programadas a planta
    df = pd.read_excel(
        io=bios_input_file, sheet_name='tto_plantas')
    df = df.groupby(['planta', 'ingrediente', 'fecha_llegada'])[['cantidad']].sum().reset_index().rename(columns={
        'planta': 'Planta', 'ingrediente': 'Ingrediente', 'fecha_llegada': 'Fecha', 'cantidad': 'Llegadas_planeadas'})
    return df


def get_consumo_proyectado(bios_input_file:str)->pd.DataFrame:
    # Consumo proyectado
    df = pd.read_excel(io=bios_input_file, sheet_name='consumo_proyectado').rename(
        columns={'planta': 'Planta', 'ingrediente': 'Ingrediente'})

    columns = df.drop(columns=['Planta', 'Ingrediente']).columns

    df = df.melt(id_vars=['Planta', 'Ingrediente'],
                value_vars=columns, var_name='Fecha', value_name='Consumo')

    df['Fecha'] = df['Fecha'].apply(
        lambda x: datetime.strptime(x, '%d/%m/%Y').strftime('%Y-%m-%d'))
    
    return df

def get_tiempos_proceso(bios_input_file:str)->pd.DataFrame:
    # Tiempos de proceso
    df = pd.read_excel(io=bios_input_file, sheet_name='plantas')
    # Tiempos de proceso
    columns = ['planta',	'empresa',	'operacion_minutos',
            'minutos_limpieza', 'plataformas']
    df = df.melt(id_vars=['planta', 'empresa'], value_vars=df.drop(columns=columns).columns, var_name='Ingrediente',
                value_name='Tiempo_Operacion').rename(columns={'planta': 'Planta', 'empresa': 'Empresa'})
    return df


def get_objetivo_inventario(bios_input_file:str)->pd.DataFrame:
    # Objetivo de inventarios
    df = obtener_objetivo_inventario(bios_input_file=bios_input_file)
    df = df['objetivo_inventario'].copy()

    objetivo_df = df[['planta', 'ingrediente', 'objetivo_dio', 'objetivo_kg']].rename(columns={'planta': 'Planta',
                                                                                    'ingrediente': 'Ingrediente',
                                                                                            'objetivo_dio': 'objetivo',
                                                                                            'objetivo_kg': 'kilogramos'})
    return objetivo_df

def get_costo_operacion_portuaria(bios_input_file:str)->pd.DataFrame:
    # Costo de Operaciones portuarias
    operaciones_portuarias_df = pd.read_excel(
        io=bios_input_file, sheet_name='costos_operacion_portuaria')
    costo_portuario_directo_df = operaciones_portuarias_df[operaciones_portuarias_df['tipo_operacion'] == 'directo'].copy(
    ).drop(columns='tipo_operacion')
    costo_portuario_bodegaje_df = operaciones_portuarias_df[operaciones_portuarias_df['tipo_operacion'] == 'bodega'].copy(
    ).drop(columns='tipo_operacion')
    return costo_portuario_bodegaje_df, costo_portuario_directo_df


def get_transitos_a_puerto(bios_input_file:str, cap_descarge=5000000)->pd.DataFrame:
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

    return tto_puerto_df


def get_inventario_puerto(bios_input_file:str)->pd.DataFrame:

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


def get_cargas_despachables(bios_input_file:str)->pd.DataFrame:

    inventario_puerto_df = get_inventario_puerto(bios_input_file=bios_input_file)
    
    tto_puerto_df = get_transitos_a_puerto(bios_input_file=bios_input_file)
    
    cargas_despachables_df = pd.concat([inventario_puerto_df, tto_puerto_df])

    cargas_despachables_df[(cargas_despachables_df['Inventario'] >= 34000) & (cargas_despachables_df['Llegada'] >= 0)]
    
    return cargas_despachables_df


def get_costo_almaceniento_puerto(bios_input_file:str)->pd.DataFrame:
    # Leer el archivo de excel
    costos_almacenamiento_df = pd.read_excel(
        io=bios_input_file, sheet_name='costos_almacenamiento_cargas')

    costos_almacenamiento_df['fecha_corte'] = costos_almacenamiento_df['fecha_corte'].apply(
        lambda x: x.strftime('%Y-%m-%d'))
    
    return costos_almacenamiento_df

def get_fletes(bios_input_file:str)->pd.DataFrame:
    df = pd.read_excel(io=bios_input_file, sheet_name='fletes_cop_per_kg')
    return df

def get_intercompany(bios_input_file:str)->pd.DataFrame:
    df = pd.read_excel(io=bios_input_file, sheet_name='venta_entre_empresas')
    return df