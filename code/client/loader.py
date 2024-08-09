import pandas as pd
import numpy as np
from tqdm import tqdm
from asignador_capacidad import AsignadorCapacidad
import logging
import json
from itertools import accumulate
from datetime import datetime, date


class Loader():
    def __init__(self, input_file:str, cap_descarge=5000000, cap_camion=34000) -> None:
        
        self.file = input_file
        self.problema = dict()
        self.problema["filename"] = input_file
        self.cap_descarge = cap_descarge
        self.problema["capacidad_descarge"] = cap_descarge  
        self.cap_camion = cap_camion
        self.problema["capacidad_camion"] = cap_camion
        
        self._load_consumos()
        self._load_inventario_planta()
        self._load_transito_planta()
        self._load_tiempos_proceso()
        self._load_inventario_puerto()
        self._load_transito_puerto()
        self.limpiar_importaciones()
        self._load_operaciones_portuarias()
        self._load_fletes()
        self._load_intercompanies_cost()
        self._load_costos_almacenamiento_puerto()
        
        self.calcular_costos()
        
        self.save()
        
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
                logging.warning("%s no esta en la lista de plantas con consumo proyectado de %s", i[0], i[1])
        
    def _load_transito_planta(self):
        
        logging.debug("cargando informacion de tránsitos a planta")
        
        fixed_columns = ['planta', 'ingrediente', 'fecha_llegada']
        
        df = pd.read_excel(self.file, sheet_name="tto_plantas")
                   
        df['fecha_llegada'] = df['fecha_llegada'].apply(lambda x: x.date()) 
        temp = df[fixed_columns].duplicated()
        
        if df[temp].shape[0] > 0:
            logging.warning(f"Existen duplicados en cuando a {' '.join(fixed_columns)} en la hoja de transitos a plantas. La aplicacion va a totalizar estos traánsitos")
                      
        df = df.groupby(fixed_columns)[['cantidad']].sum()

        for planta in tqdm(self.problema['plantas'].keys()):
            for ingrediente in self.problema['plantas'][planta]['ingredientes'].keys():
                self.problema['plantas'][planta]['ingredientes'][ingrediente]['llegada_planeada'] = list()
                for t in self.fechas:
                    index = (planta, ingrediente, t)
                    if index in df.index:
                        self.problema['plantas'][planta]['ingredientes'][ingrediente]['llegada_planeada'].append(df.loc[index]['cantidad'])
                    else:
                        self.problema['plantas'][planta]['ingredientes'][ingrediente]['llegada_planeada'].append(0.0)
            
    def _load_tiempos_proceso(self):
        
        logging.debug("cargando informacion de tiempos de proceso")
        
        df = pd.read_excel(self.file, sheet_name='plantas')
        
        df.set_index('planta', inplace=True)
        
        for planta in tqdm(self.problema['plantas'].keys()):
            
            self.problema['plantas'][planta]['empresa'] = df.loc[planta]['empresa']
            self.problema['plantas'][planta]['tiempo_disponible'] = df.loc[planta]['operacion_minutos']*df.loc[planta]['plataformas']
            
            for ingrediente in self.problema['plantas'][planta]['ingredientes'].keys():
                self.problema['plantas'][planta]['ingredientes'][ingrediente]['tiempo_proceso'] = df.loc[planta][ingrediente]

    def _load_inventario_puerto(self):
        
        logging.debug("cargando informacion de inventario de puertos")
        
        df = pd.read_excel(self.file, sheet_name='inventario_puerto')

        df['importacion'] = df['importacion'].apply(lambda x: str(x).upper().strip().replace(' ', ''))

        df['fecha_llegada'] = df['fecha_llegada'].apply(lambda x: x.date()) 
        
        self.problema['importaciones'] = dict()
        
        for i in tqdm(df.index):
            empresa = df.loc[i]['empresa']
            operador = df.loc[i]['operador']
            puerto = df.loc[i]['puerto']
            ingrediente = df.loc[i]['ingrediente']
            importacion= df.loc[i]['importacion']
            fecha_llegada = df.loc[i]['fecha_llegada']
            valor_cif = df.loc[i]['valor_cif_kg']
            cantidad = df.loc[i]['cantidad_kg']
            
            if ingrediente not in self.problema['importaciones'].keys():
                self.problema['importaciones'][ingrediente] = dict()
                
            if puerto not in self.problema['importaciones'][ingrediente].keys():
                self.problema['importaciones'][ingrediente][puerto] = dict()
                
            if operador not in self.problema['importaciones'][ingrediente][puerto].keys():
                self.problema['importaciones'][ingrediente][puerto][operador] = dict()
                
            if empresa not in self.problema['importaciones'][ingrediente][puerto][operador].keys():
                self.problema['importaciones'][ingrediente][puerto][operador][empresa] = dict()
            
            if importacion not in self.problema['importaciones'][ingrediente][puerto][operador][empresa].keys():
                self.problema['importaciones'][ingrediente][puerto][operador][empresa][importacion] = dict()
            
            if 'llegadas' not in self.problema['importaciones'][ingrediente][puerto][operador][empresa][importacion].keys():
                self.problema['importaciones'][ingrediente][puerto][operador][empresa][importacion]['llegadas'] = len(self.fechas)*[0.0]
                        
            self.problema['importaciones'][ingrediente][puerto][operador][empresa][importacion]['fecha_llegada'] = fecha_llegada
            self.problema['importaciones'][ingrediente][puerto][operador][empresa][importacion]['valor_cif'] = valor_cif
            self.problema['importaciones'][ingrediente][puerto][operador][empresa][importacion]['inventario_inicial'] = cantidad
            
    def _load_transito_puerto(self):
        
        logging.debug("cargando informacion de tránsitos a puerto")
        
        df = pd.read_excel(self.file, sheet_name='tto_puerto')
        
        df['fecha_llegada'] = df['fecha_llegada'].apply(lambda x: x.date()) 
        
        # validar si las fechas de llegada están dentro de las fechas
        temp = df[df['fecha_llegada'].apply(lambda x: x in self.fechas)==False]
        
        if temp.shape[0]>0:
            issue = f" las siguientes importaciones tienen fecha de llegada en el pasado: {', '.join(temp['importacion'])} \n Por favor llevarlas al inventario en puerto para que sean tenidas en cuenta"
            logging.warning(issue)
            
        df['importacion'] = df['importacion'].apply(lambda x: str(x).upper().strip().replace(' ', ''))

        for i in tqdm(df.index):
            empresa = df.loc[i]['empresa']
            operador = df.loc[i]['operador']
            puerto = df.loc[i]['puerto']
            ingrediente = df.loc[i]['ingrediente']
            importacion= df.loc[i]['importacion']
            fecha_llegada = df.loc[i]['fecha_llegada']
            valor_cif = df.loc[i]['valor_kg']
            cantidad = df.loc[i]['cantidad_kg']
            
            if ingrediente not in self.problema['importaciones'].keys():
                self.problema['importaciones'][ingrediente] = dict()
                
            if puerto not in self.problema['importaciones'][ingrediente].keys():
                self.problema['importaciones'][ingrediente][puerto] = dict()
                
            if operador not in self.problema['importaciones'][ingrediente][puerto].keys():
                self.problema['importaciones'][ingrediente][puerto][operador] = dict()
                
            if empresa not in self.problema['importaciones'][ingrediente][puerto][operador].keys():
                self.problema['importaciones'][ingrediente][puerto][operador][empresa] = dict()
            
            if importacion not in self.problema['importaciones'][ingrediente][puerto][operador][empresa].keys():
                self.problema['importaciones'][ingrediente][puerto][operador][empresa][importacion] = dict()
            
            if 'llegadas' not in self.problema['importaciones'][ingrediente][puerto][operador][empresa][importacion].keys():
                self.problema['importaciones'][ingrediente][puerto][operador][empresa][importacion]['llegadas'] = list()
            
            if 'fecha_llegada' in self.problema['importaciones'][ingrediente][puerto][operador][empresa][importacion].keys():
                logging.warning(f"La importacion {importacion} de {ingrediente} en {operador}_{puerto} parece duplicada")
            else:
                self.problema['importaciones'][ingrediente][puerto][operador][empresa][importacion]['fecha_llegada'] = fecha_llegada   
                self.problema['importaciones'][ingrediente][puerto][operador][empresa][importacion]['valor_cif'] = valor_cif
                self.problema['importaciones'][ingrediente][puerto][operador][empresa][importacion]['inventario_inicial'] = 0.0
                
            
            for t in self.fechas:
                
                if t >= fecha_llegada and cantidad>0:
                    
                    if cantidad>self.cap_descarge:
                        self.problema['importaciones'][ingrediente][puerto][operador][empresa][importacion]['llegadas'].append(self.cap_descarge)
                        cantidad -=self.cap_descarge
                    else:
                        self.problema['importaciones'][ingrediente][puerto][operador][empresa][importacion]['llegadas'].append(cantidad)
                        cantidad = 0.0
                else:
                    self.problema['importaciones'][ingrediente][puerto][operador][empresa][importacion]['llegadas'].append(0.0)
                 
    def _load_operaciones_portuarias(self):
        
        logging.debug("cargando informacion de costos portuarios")
        
        fixed_columns = ['tipo_operacion', 'operador', 'puerto', 'ingrediente']
        
        df = pd.read_excel(self.file, sheet_name="costos_operacion_portuaria")
        
        temp = df[df[fixed_columns].duplicated()]
        
        if temp.shape[0] > 0:
            issue = "Existen duplicados en la hoja costos_operacion_portuaria"
            logging.critical(issue)
            raise Exception(issue)
            
        df.set_index(fixed_columns, inplace=True)
            
        for ingrediente, ingrediente_values in tqdm(self.problema['importaciones'].items()):
            for puerto, puerto_values in ingrediente_values.items():
                for operador, operador_values in puerto_values.items():
                    for empresa, empresa_value in operador_values.items():
                        for importacion, importacion_values in empresa_value.items():
                            importacion_values['costos_despacho_directo'] = list()
                            importacion_values['costos_bodegaje'] = list()
                            
                            # Obtener la última fecha de llegada de material
                            llegadas = importacion_values['llegadas']    
                            
                            # Verificar si la importacion tiene llegadas durante el horizonte de planeación
                            if sum(llegadas)>0:                             
                                last_arrival_index =  max([llegadas.index(x) for x in llegadas if x>0])
                            else:
                                last_arrival_index = -1
                            
                            for t in self.fechas:
                                i = ('bodega', operador, puerto, ingrediente)
                                
                                if i in df.index and last_arrival_index >= 0:
                                    if t == self.fechas[last_arrival_index]:
                                        importacion_values['costos_bodegaje'].append(df.loc[i]['valor_kg'])
                                    else:
                                        importacion_values['costos_bodegaje'].append(0.0)
                                else:
                                    importacion_values['costos_bodegaje'].append(0.0)
                                    
                                i = ('directo', operador, puerto, ingrediente)
                                
                                if i in df.index and importacion_values['llegadas'][self.fechas.index(t)]>0.0:
                                    importacion_values['costos_despacho_directo'].append(df.loc[i]['valor_kg'])
                                else:
                                    importacion_values['costos_despacho_directo'].append(0.0)
                                
    def _load_fletes(self):
        
        logging.debug("cargando informacion de costo de fletes")
        
        fixed_columns = ['puerto', 'operador', 'ingrediente']
        
        df = pd.read_excel(self.file, sheet_name='fletes_cop_per_kg')
    
        df.set_index(fixed_columns, inplace=True)
        
        for ingrediente, ingrediente_values in tqdm(self.problema['importaciones'].items()):
            for puerto, puerto_values in ingrediente_values.items():
                for operador, operador_values in puerto_values.items():
                    for empresa, empresa_value in operador_values.items():
                        for importacion, importacion_values in empresa_value.items():
                                importacion_values['flete_camion'] = dict()
                    
                                i = (puerto, operador, ingrediente)
                                
                                if i in df.index:
                                    for c in df.columns:
                                        importacion_values['flete_camion'][c] = self.cap_camion*df.loc[i][c]
                            
    def _load_intercompanies_cost(self):
        
        logging.debug("cargando informacion de costos intercompany")
        
        df = pd.read_excel(self.file, sheet_name='venta_entre_empresas')
                  
        df = pd.melt(frame=df, id_vars='origen', value_vars=df.drop(columns=['origen']).columns, var_name='destino', value_name='intercompany')          
        
        df.set_index(['origen', 'destino'], inplace=True)
                    
        for ingrediente, ingrediente_values in tqdm(self.problema['importaciones'].items()):
            for puerto, puerto_values in ingrediente_values.items():
                for operador, operador_values in puerto_values.items():
                    for empresa, empresa_value in operador_values.items():
                        for importacion, importacion_values in empresa_value.items():
                            importacion_values['intercompany_camion'] = dict()
                            for planta in importacion_values['flete_camion'].keys():
                                i = (empresa, self.problema['plantas'][planta]['empresa'])
                                importacion_values['intercompany_camion'][planta] = self.cap_camion*df.loc[i]['intercompany']*importacion_values['valor_cif']
        
    def _load_costos_almacenamiento_puerto(self):
        
        logging.debug("cargando informacion de costos de almacenamiento en puerto")
        
        fixed_columns = ['empresa', 'ingrediente', 'operador', 'puerto', 'importacion', 'fecha_corte']
        
        df = pd.read_excel(self.file, sheet_name='costos_almacenamiento_cargas')
        
        df['importacion'] = df['importacion'].apply(lambda x: str(x).upper().strip().replace(' ', ''))
        
        df['fecha_corte'] = df['fecha_corte'].apply(lambda x: x.date())
               
        temp = df[df[fixed_columns].duplicated()]
        
        if temp.shape[0] > 0:
            issue = "Existen duplicados en la hoja costos_almacenamiento_cargas"
            logging.critical(issue)
            raise Exception(issue)
            
        df.set_index(fixed_columns, inplace=True)
            
        for ingrediente, ingrediente_values in tqdm(self.problema['importaciones'].items()):
            for puerto, puerto_values in ingrediente_values.items():
                for operador, operador_values in puerto_values.items():
                    for empresa, empresa_value in operador_values.items():
                        for importacion, importacion_values in empresa_value.items():
                            importacion_values['costo_almacenamiento'] = list()
                            
                            for t in self.fechas:
                                
                                i = (empresa, ingrediente, operador, puerto, importacion, t)
                                
                                if i in df.index:
                                    importacion_values['costo_almacenamiento'].append(df.loc[i]['valor_kg'])
                                else:
                                    importacion_values['costo_almacenamiento'].append(0.0)
                            
                            if sum(importacion_values['costo_almacenamiento']) == 0.0:
                                logging.warning(f"la importacion de {ingrediente} en {puerto} con {operador} {importacion} parece no tener costos de almacenamiento asociados")
    
    
    def limpiar_importaciones(self):
        # Borra todas las importaciones cuyas llegadas más inventarios no tengan al menos un camion despachable
        for ingrediente, ingrediente_values in tqdm(self.problema['importaciones'].items()):
            for puerto, puerto_values in ingrediente_values.items():
                for operador, operador_values in puerto_values.items():
                    for empresa, empresa_value in operador_values.items():
                        lista_a_eliminar = list()
                        for importacion, importacion_values in empresa_value.items():
                            total_despacho = importacion_values['inventario_inicial'] + sum(importacion_values['llegadas'])
                            if total_despacho < self.cap_camion:
                                logging.warn(f"la importacion {importacion} de {empresa} con {ingrediente} en {operador} y puerto {puerto} será eliminada del modelo por no tener capacidad para llenar un camión")
                                lista_a_eliminar.append(importacion)
                        
                        for importacion in lista_a_eliminar:
                            empresa_value.pop(importacion)
                       
    def calcular_costos(self):
        for ingrediente, ingrediente_values in tqdm(self.problema['importaciones'].items()):
            for puerto, puerto_values in ingrediente_values.items():
                for operador, operador_values in puerto_values.items():
                    for empresa, empresa_value in operador_values.items():
                        for importacion, importacion_values in empresa_value.items():
                            # Costos de almacenamiento
                            costo_total_almacenamiento = list(self.cap_camion*(np.array(importacion_values['costo_almacenamiento']) + np.array(importacion_values['costos_bodegaje'])))
                            importacion_values['costo_almacenamiento_camion'] = costo_total_almacenamiento
                            importacion_values['ahorro_camion'] = list(accumulate(costo_total_almacenamiento[::-1]))[::-1]
                            
                            # Costos de despacho por camion
                            importacion_values['costo_despacho_camion'] = dict()
                            for planta in importacion_values['flete_camion'].keys():
                                fletes =  importacion_values['flete_camion'][planta] * np.ones(len(self.fechas))
                                despacho_directo = self.cap_camion*np.array(importacion_values['costos_despacho_directo'])
                                costo_intercompany = importacion_values['intercompany_camion'][planta] * np.ones(len(self.fechas))
                                ahorro_almacenamiento = np.array(importacion_values['ahorro_camion'])
                                costo_camion = fletes + despacho_directo + costo_intercompany - ahorro_almacenamiento
                                importacion_values['costo_despacho_camion'][planta] = list(costo_camion)
        
    
    def save(self):
        with open(self.file.replace('.xlsm', '.json'), 'w') as file:
            json.dump(self.problema, file, indent=4, sort_keys=True, default=str)
            
        
        