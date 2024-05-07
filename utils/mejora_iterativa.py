# -*- coding: utf-8 -*-

import pandas as pd
import numpy as np
from datetime import datetime, timedelta


def obtener_valor_plantas(planta:str, ingrediente:str, variable:str, periodo:datetime)->float:
    
    index_value = (planta, ingrediente, variable)
    
    if index_value in plantas_df.index:
        if periodo in plantas_df.columns:
            return plantas_df.loc[index_value][periodo]

    return None

def set_valor_plantaobtener_valor_plantas(planta:str, ingrediente:str, variable:str, periodo:datetime, value:float):
    
    index_value = (planta, ingrediente, variable)
    
    if index_value in plantas_df.index:
        if periodo in plantas_df.columns:
            plantas_df.loc[index_value][periodo] = value

    return none



def inicializar_transportes(plantas_df:pd.DataFrame, cargas_df:pd.DataFrame, periodos:list) -> pd.DataFrame:
    
    registros = list()
    
    plantas_index = plantas_df.index
    
    cargas_index = cargas_df.index
    
    for i in plantas_index:
        
        i_planta = i[0]
        i_ingrediente = i[1]
        i_variable = i[2]
        
        if i_variable =='inventario': 
        
            for j in cargas_index:
                
                j_ingrediente = j[0]
                j_importacion = j[1]
                j_empresa = j[2]
                j_puerto = j[3]
                j_operador = j[4]
                j_variable = j[5]
                
                if j_variable == 'inventario':
                
                    if i_ingrediente == j_ingrediente:
                        dato ={
                            'ingrediente':i_ingrediente,
                            'importacion':j_importacion,
                            'empresa':j_empresa,
                            'puerto':j_puerto,
                            'operador':j_operador,
                            'planta':i_planta}
                
                        registros.append(dato)
                        
    df = pd.DataFrame(registros)
    
    for periodo in periodos:        
        df[periodo] = -1
                        
    return df


def recalcular_plantas(plantas_df:pd.DataFrame, transporte_df:pd.DataFrame, periodos:list):
    
    inventario_planta = [x for x in plantas_df.index if x[2]=='inventario']
    
    for i_planta in inventario_planta:
        
        llegadas_row = transporte_df.groupby()

        for periodo in periodos[:-2]:
            
            llegadas = np.sum([transporte_df[(transporte_df['planta']==i_planta[0])&(transporte_df['ingrediente']==i_planta[1])][periodo + timedelta(days=2)]](lambda x: x if x >= 0 else 0))

        
           
def inicializar_heuristica(plantas_df:pd.DataFrame, cargas_df:pd.DataFrame, periodos:list): 
 
    plantas_df.set_index(['planta', 'ingrediente', 'variable'], inplace=True)
    
    cargas_df.set_index(['ingrediente', 'importacion', 'empresa', 'puerto', 'operador', 'variable'], inplace=True)
    
    transporte_df = inicializar_transportes(plantas_df, cargas_df, periodos)
    
    

