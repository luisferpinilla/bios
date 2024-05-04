#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat May  4 09:48:51 2024

@author: luispinilla
"""


from utils.planta_loader import __leer_archivo
from utils.planta_loader import __generar_periodos
from utils.planta_loader import obtener_objetivo_inventario
from utils.planta_loader import obtener_matriz_plantas
from utils.planta_loader import obtener_matriz_importaciones
from utils.planta_loader import validacion_eliminar_cargas_sin_inventario
from utils.planta_loader import validacion_eliminar_ingredientes_sin_consumo

import pandas as pd

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