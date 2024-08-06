import pandas as pd
from datetime import datetime, date
from tqdm import tqdm
from asignador_capacidad import AsignadorCapacidad
import logging


class Loader():
    def __init__(self, input_file:str) -> None:
        
        self.file = input_file
        self.problema = dict()
        self.problema["filename"] = input_file        
        self._load_consumos()
        self._load_inventario_planta()

    def _load_consumos(self):
        
        logging.debug("cargando informacion de consumos")
        
        fixed_columns = ['planta', 'ingrediente']
        
        df = pd.read_excel(self.file, sheet_name="consumo_proyectado")

        temp = df[fixed_columns].duplicated()
        
        if df[temp].shape[0] > 0:
            logging.critical("Existen duplicados en la hoja de consumos proyectados")
            raise Exception("Existen duplicados en la hoja de consumos proyectados")
        
        self.fechas = [datetime.strptime(x, "%d/%m/%Y").date() for x in df.drop(columns=fixed_columns).columns]
        
        self.problema["fecha"] = self.fechas[0]
        
        df.set_index(fixed_columns, inplace=True)
        
        self.problema["plantas"] = dict()

        
        for i in tqdm(df.index):
            
            if df.loc[i].sum() > 0.0:
            
                if i[0] not in self.problema["plantas"].keys():
                    self.problema["plantas"][i[0]] = dict()
                    self.problema["plantas"][i[0]]["ingredientes"] = dict()
                    
                if i[1] not in self.problema["plantas"][i[0]]["ingredientes"].keys():
                    self.problema["plantas"][i[0]]["ingredientes"][i[1]] = dict()
                 
                self.problema["plantas"][i[0]]["ingredientes"][i[1]]['consumo'] = list(df.loc[i]) 

    def _load_inventario_planta(self):
        
        logging.debug("Cargando informacion de inventarios en planta")
        
        asignador = AsignadorCapacidad(file=self.file)
        
        df = asignador.obtener_unidades_almacenamiento()
        
        df['Capacidad'] = df.apply(lambda x: x[x['ingrediente_actual']], axis=1)
        
        df.rename(columns={'planta': 'Planta', 'ingrediente_actual': 'Ingrediente', 'cantidad_actual': 'Inventario'}, inplace=True)
        
        df = df.groupby(['Planta', 'Ingrediente'])[['Capacidad', 'Inventario']].sum()
        
        for i in tqdm(df.index):
            
            inventario = df.loc[i]['Inventario']
            capacidad = df.loc[i]['Capacidad']
            
            if i[0] in self.problema['plantas'].keys():
                
                if i[1] in self.problema['plantas'][i[0]]['ingredientes'].keys():
                    
                    if capacidad == 0:
                        logging.critical("%s no tiene capacidad asignada", i)
                        raise Exception(f"{i} no tiene capacidad asignada")
                        
                    if inventario == 0:
                        logging.warning("%s no tiene inventario", i)
                    
                    self.problema['plantas'][i[0]]['ingredientes'][i[1]]['capacidad'] = capacidad
                    self.problema['plantas'][i[0]]['ingredientes'][i[1]]['inventario_inicial'] = inventario
                
            else:
                logging.warning("%s no esta en la lista de plantas con consumo proyectado", i[0])
        
        

    def _load_transito_planta():
        
        fixed_columns = ['planta', 'ingrediente', 'fecha_llegada']
        
        df = pd.read_excel(file, sheet_name="tto_plantas")
                   
        df['fecha_llegada'] = df['fecha_llegada'].apply(lambda x: x.date()) 
        temp = df[fixed_columns].duplicated()
        
        if df[temp].shape[0] > 0:
            logging.critical("Existen duplicados en la hoja de transitos a plantas")
            raise Exception("Existen duplicados en la hoja de transitos a plantas")
            
        df = df.groupby(fixed_columns)[['cantidad']].sum()

        for planta in problema['plantas'].keys():
            for ingredinte in problema['plantas'][planta].keys():
                print(planta, ingrediente)
                problema['plantas'][planta][ingrediente]['llegada_planeada'] = list()
                for t in fechas:
                    if (planta, ingrediente, t) in df.index:
                        print(planta,ingrediente,t)
            

df.index[0]



