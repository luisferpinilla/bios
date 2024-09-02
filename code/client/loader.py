import pandas as pd
import numpy as np
from tqdm import tqdm
from client.asignador_capacidad import AsignadorCapacidad
import logging
import json
from itertools import accumulate
from datetime import datetime
from tqdm import tqdm


class Loader():
    def __init__(self, input_file:str, cap_descarge=5000000, cap_camion=34000) -> None:
    

        logging.basicConfig(level=logging.DEBUG,
                            format='%(asctime)s %(levelname)s: %(message)s', 
                            datefmt='%m/%d/%Y %I:%M:%S %p')
            
        
        self.file = input_file
        self.problema = dict()
        
        self.problema["filename"] = input_file
        self.cap_descarge = cap_descarge
        self.problema["capacidad_descarge"] = cap_descarge  
        self.cap_camion = cap_camion
        self.problema["capacidad_camion"] = cap_camion
        
        
    def load_data(self):
        
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
       self._load_safety_stock()
       
       self.calcular_costos()
       
       self.generar_variables_despacho()
       
       self.calcular_parametros() 
        
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
        
        self.problema["fechas"] = self.fechas
        
        df.set_index(fixed_columns, inplace=True)
        
        self.problema["plantas"] = dict()

        
        for i in tqdm(df.index):
            
            if df.loc[i].sum() > 0.0:
            
                if i[0] not in self.problema["plantas"].keys():
                    self.problema["plantas"][i[0]] = dict()
                    self.problema["plantas"][i[0]]["ingredientes"] = dict()
                    
                if i[1] not in self.problema["plantas"][i[0]]["ingredientes"].keys():
                    self.problema["plantas"][i[0]]["ingredientes"][i[1]] = dict()
                
                consumo = [int(x) for x in df.loc[i]]
                self.problema["plantas"][i[0]]["ingredientes"][i[1]]['consumo'] = consumo

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
                    
                    self.problema['plantas'][i[0]]['ingredientes'][i[1]]['capacidad'] = int(capacidad)
                    self.problema['plantas'][i[0]]['ingredientes'][i[1]]['inventario_inicial'] = int(inventario)
                
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
                        self.problema['plantas'][planta]['ingredientes'][ingrediente]['llegada_planeada'].append(int(df.loc[index]['cantidad']))
                    else:
                        self.problema['plantas'][planta]['ingredientes'][ingrediente]['llegada_planeada'].append(0)
            
    def _load_tiempos_proceso(self):
        
        logging.debug("cargando informacion de tiempos de proceso")
        
        df = pd.read_excel(self.file, sheet_name='plantas')
        
        df.set_index('planta', inplace=True)
        
        for planta in tqdm(self.problema['plantas'].keys()):
            
            self.problema['plantas'][planta]['empresa'] = df.loc[planta]['empresa']
            self.problema['plantas'][planta]['tiempo_disponible'] = int(df.loc[planta]['operacion_minutos']*df.loc[planta]['plataformas'])
            
            for ingrediente in self.problema['plantas'][planta]['ingredientes'].keys():
                self.problema['plantas'][planta]['ingredientes'][ingrediente]['tiempo_proceso'] = int(df.loc[planta][ingrediente])

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
            self.problema['importaciones'][ingrediente][puerto][operador][empresa][importacion]['valor_cif'] = float(valor_cif)
            self.problema['importaciones'][ingrediente][puerto][operador][empresa][importacion]['inventario_inicial'] = int(cantidad)
            
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
                                        importacion_values['costos_bodegaje'].append(float(df.loc[i]['valor_kg']))
                                    else:
                                        importacion_values['costos_bodegaje'].append(0.0)
                                else:
                                    importacion_values['costos_bodegaje'].append(0.0)
                                    
                                i = ('directo', operador, puerto, ingrediente)
                                
                                if i in df.index and importacion_values['llegadas'][self.fechas.index(t)]>0.0:
                                    importacion_values['costos_despacho_directo'].append(float(df.loc[i]['valor_kg']))
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
                                        importacion_values['flete_camion'][c] = int(self.cap_camion*df.loc[i][c])
                            
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
                                importacion_values['intercompany_camion'][planta] = float(self.cap_camion*df.loc[i]['intercompany']*importacion_values['valor_cif'])
        
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
    
    def _load_safety_stock(self):

        
        df = pd.read_excel(self.file, sheet_name='safety_stock')
        
        df.set_index(['planta', 'ingrediente'], inplace=True)
        
        cap_camion = self.problema['capacidad_camion']
        
        for planta in self.problema['plantas'].keys():
            for ingrediente in self.problema['plantas'][planta]['ingredientes'].keys():
                if 'consumo' in self.problema['plantas'][planta]['ingredientes'][ingrediente].keys():
                    i = (planta, ingrediente)
                    consumo_medio =np.mean(np.array(self.problema['plantas'][planta]['ingredientes'][ingrediente]['consumo']))
                    capacidad = self.problema['plantas'][planta]['ingredientes'][ingrediente]['capacidad']
         
                    if i in df.index:
                        ss_dias = df.loc[i]['dias_ss']
                        ss_kg = int(consumo_medio * ss_dias)
                        if ss_kg > 0:
                            if capacidad - ss_kg > 2*cap_camion:
                                self.problema['plantas'][planta]['ingredientes'][ingrediente]['safety_stock'] = [int(x) for x in ss_kg*np.ones(len(self.problema['fechas']))]
                                self.problema['plantas'][planta]['ingredientes'][ingrediente]['safety_stock_dio'] = [int(x) for x in ss_dias*np.ones(len(self.problema['fechas']))]
                            else:
                                logging.warning("La capacidad de almacenamiento de la planta %s para el ingrediente %s no es suficiente para mantener un SS de %s días equivalente a %s kilos y recibir al menos 2 camiones", planta, ingrediente, ss_dias, ss_kg)
   
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
                            costo_total_almacenamiento = [int(x) for x in costo_total_almacenamiento]
                            importacion_values['costo_almacenamiento_camion'] = costo_total_almacenamiento
                            importacion_values['ahorro_camion'] = list(accumulate(costo_total_almacenamiento[::-1]))[::-1]
                            
                            # Costos de despacho por camion
                            importacion_values['costo_despacho_camion'] = dict()
                            for planta in importacion_values['flete_camion'].keys():
                                fletes =  importacion_values['flete_camion'][planta] * np.ones(len(self.fechas))
                                despacho_directo = self.cap_camion*np.array(importacion_values['costos_despacho_directo'])
                                despacho_directo = [int(x) for x in despacho_directo]
                                costo_intercompany = importacion_values['intercompany_camion'][planta] * np.ones(len(self.fechas))
                                costo_intercompany = [int(x) for x in costo_intercompany]
                                ahorro_almacenamiento = np.array(importacion_values['ahorro_camion'])
                                ahorro_almacenamiento = [int(x) for x in ahorro_almacenamiento]
                                costo_camion = fletes + despacho_directo + costo_intercompany - ahorro_almacenamiento
                                costo_camion = [int(x) for x in costo_camion]
                                importacion_values['costo_despacho_camion'][planta] = list(costo_camion)

    def generar_variables_despacho(self):
        
        for ingrediente in self.problema['importaciones'].keys():
            
            for puerto in self.problema['importaciones'][ingrediente].keys():
                
                for operador in self.problema['importaciones'][ingrediente][puerto].keys():
                
                    for empresa in self.problema['importaciones'][ingrediente][puerto][operador].keys():
                
                        for importacion in self.problema['importaciones'][ingrediente][puerto][operador][empresa].keys():
                            
                            despachos = dict()
                            self.problema['importaciones'][ingrediente][puerto][operador][empresa][importacion]['despachos'] = despachos
                            for planta in self.problema['plantas'].keys():
                                despachos[planta] = dict()
                                
                                if ingrediente in self.problema['plantas'][planta]['ingredientes'].keys():
                                    
                                    max_ingreso_tiempo = int(self.problema['plantas'][planta]['tiempo_disponible']/self.problema['plantas'][planta]['ingredientes'][ingrediente]['tiempo_proceso'])
                                    max_ingreso_cap_alm = int(self.problema['plantas'][planta]['ingredientes'][ingrediente]['capacidad']/self.cap_camion)
                                   
                                    despachos[planta]['minimo'] = [int(x) for x in list(np.zeros(len(self.fechas)))]
                                    despachos[planta]['safety_stock'] = [int(x) for x in list(np.zeros(len(self.fechas)))]
                                    despachos[planta]['target'] = [int(x) for x in list(np.zeros(len(self.fechas)))]
                                    despachos[planta]['maximo'] = min(max_ingreso_tiempo,max_ingreso_tiempo,max_ingreso_cap_alm)
                                    
                                    if 'llegadas' not in self.problema['plantas'][planta]['ingredientes'][ingrediente].keys():
                                        self.problema['plantas'][planta]['ingredientes'][ingrediente]['llegadas'] = dict()
                                    
                                    llegadas = self.problema['plantas'][planta]['ingredientes'][ingrediente]['llegadas']
                                    
                                    llegadas[f"{ingrediente}_{puerto}_{operador}_{empresa}_{importacion}"] = [int(x) for x in list(np.zeros(len(self.fechas)))]
                                    
    def calcular_inventarios_importaciones(self):
        
        importaciones = self.problema['importaciones']
        
        periodos = len(self.fechas)
        
        for ingrediente in importaciones.keys():
            
            for puerto in importaciones[ingrediente].keys():
                
                for operador in importaciones[ingrediente][puerto].keys():
                
                    for empresa in importaciones[ingrediente][puerto][operador].keys():
                
                        for importacion in importaciones[ingrediente][puerto][operador][empresa].keys():
                            
                            inventario = importaciones[ingrediente][puerto][operador][empresa][importacion]['inventario_inicial']
                            
                            if 'inventario' not in importaciones[ingrediente][puerto][operador][empresa][importacion].keys():
                                importaciones[ingrediente][puerto][operador][empresa][importacion]['inventario'] = [0] * len(self.problema['fechas'])
                            
                            for t in range(periodos):
                                
                                llegadas = importaciones[ingrediente][puerto][operador][empresa][importacion]['llegadas'][t]
                        
                                despachos = 0
                                
                                for planta, lista in importaciones[ingrediente][puerto][operador][empresa][importacion]['despachos'].items():
                                    if 'minimo' in lista.keys():
                                        despachos += lista['minimo'][t]
                                    
                                    if 'safety_stock' in lista.keys():
                                        despachos += lista['safety_stock'][t]
                                        
                                    if 'target' in lista.keys():
                                        despachos += lista['target'][t]  
                                        
                                despachos = despachos*self.cap_camion
                                
                                inventario = inventario + llegadas - despachos
                                
                                importaciones[ingrediente][puerto][operador][empresa][importacion]['inventario'][t] = int(inventario)
                      
    def get_total_arrivals(self, planta:str, ingrediente:str, periodo:int)->int:
        
        total_llegadas = 0
        
        for importacion in self.problema['plantas'][planta]['ingredientes'][ingrediente]['llegadas'].keys():
            
            total_llegadas += self.problema['plantas'][planta]['ingredientes'][ingrediente]['llegadas'][importacion][periodo]
            total_llegadas += self.problema['plantas'][planta]['ingredientes'][ingrediente]['llegada_planeada'][importacion][periodo]
        
        return total_llegadas

    def calcular_inventarios_planta(self):
        
        def get_dio(inventario_actual:int, consumo:list, mode='count')->int:
    

            dio = 0
            if mode == 'count':
            
                horizonte = len(consumo)
                
                if horizonte>0:
                    while inventario_actual > consumo[dio] and dio < horizonte-1:
                        
                        inventario_actual -= consumo[dio]
                        dio += 1
                        
                    while inventario_actual > 0:
                        inventario_actual -= consumo[-1]
                        dio += 1
                        
            else:
                    
                promedio = np.mean(consumo)
                    
                if promedio > 0:
                    dio = inventario_actual / promedio
            
            return int(dio)
        
        plantas = self.problema['plantas']
        periodos = len(self.fechas)
        
        for planta in plantas.keys():
            
            plantas[planta]['tiempo_consumido'] = [0]*len(self.problema['fechas'])
                
            for ingrediente in plantas[planta]['ingredientes'].keys():
                    
                if 'capacidad' not in plantas[planta]['ingredientes'][ingrediente].keys() :
                    logging.critical(f"No hay capacidad para {ingrediente} en la planta {planta}")
                    
                    if 'inventario_inicial' not in plantas[planta]['ingredientes'][ingrediente].keys():
                        logging.critical(f"No hay inventario inicial de {ingrediente} en la planta {planta}")
                
                else:
                    
                    inventario = plantas[planta]['ingredientes'][ingrediente]['inventario_inicial']
                    
                    if 'inventario' not in plantas[planta]['ingredientes'][ingrediente].keys():                    
                        plantas[planta]['ingredientes'][ingrediente]['inventario'] = [0]*len(self.problema['fechas'])
                        plantas[planta]['ingredientes'][ingrediente]['dio'] = [0]*len(self.problema['fechas'])
                        plantas[planta]['ingredientes'][ingrediente]['inventario'] =[0]*len(self.problema['fechas'])
                        plantas[planta]['ingredientes'][ingrediente]['backorder'] = [0]*len(self.problema['fechas'])

                    for t in range(periodos):
                        
                        consumo = plantas[planta]['ingredientes'][ingrediente]['consumo'][t]
                        llegada_planeada = plantas[planta]['ingredientes'][ingrediente]['llegada_planeada'][t]
                        
                        llegadas = 0
                        
                        if 'llegadas' in plantas[planta]['ingredientes'][ingrediente].keys():
                            for impo in plantas[planta]['ingredientes'][ingrediente]['llegadas'].keys():
                                
                                llegadas += plantas[planta]['ingredientes'][ingrediente]['llegadas'][impo][t]
                                
                                plantas[planta]['tiempo_consumido'][t] += plantas[planta]['ingredientes'][ingrediente]['llegadas'][impo][t]*plantas[planta]['ingredientes'][ingrediente]['tiempo_proceso']
                                
                        llegadas = llegadas*self.cap_camion
                        
                        inventario = inventario + llegadas + llegada_planeada - consumo
                            
                        if inventario < 0:
                            
                            backorder = -1*inventario                            
                            inventario = 0
                                
                        else:
                            backorder = 0 
                            
                        plantas[planta]['ingredientes'][ingrediente]['dio'][t] = get_dio(inventario_actual=inventario, consumo=plantas[planta]['ingredientes'][ingrediente]['consumo'][t:], mode='avg')
                        plantas[planta]['ingredientes'][ingrediente]['inventario'][t]= inventario
                        plantas[planta]['ingredientes'][ingrediente]['backorder'][t] = backorder                        
            
    def calcular_costo_backorder(self):
        
        costo_backorder = dict()
        for ingrediente in self.problema['importaciones'].keys() :
            costo_backorder[ingrediente] = list()
            for puerto in self.problema['importaciones'][ingrediente].keys():
                for operador in self.problema['importaciones'][ingrediente][puerto].keys():
                    for empresa in self.problema['importaciones'][ingrediente][puerto][operador].keys():
                        for importacion in self.problema['importaciones'][ingrediente][puerto][operador][empresa].keys():
                            for importacion in self.problema['importaciones'][ingrediente][puerto][operador][empresa].keys():
                                for planta in self.problema['importaciones'][ingrediente][puerto][operador][empresa][importacion]['costo_despacho_camion'].keys():
                                    costo_backorder[ingrediente].append(max(self.problema['importaciones'][ingrediente][puerto][operador][empresa][importacion]['costo_despacho_camion'][planta]))
                                
        self.problema['costo_backorder'] = {ingrediente:100*max(costos)/self.problema['capacidad_camion'] for ingrediente,costos in costo_backorder.items()}   

    def calcular_parametros(self):
        
        self.calcular_inventarios_importaciones()
        
        self.calcular_inventarios_planta()
        
        self.calcular_costo_backorder()

    def get_ingredientes_disponibles(self, t:int)->dict:
        
        # Retorna un diccionario de ingredientes disponibles en un periodo de tiempo dado
        
        ingredientes_disponibles = dict()
        
        importaciones = self.problema['importaciones']
        
        for ingrediente in importaciones.keys():
            camiones_disponibles = 0
            for puerto in importaciones[ingrediente].keys():
                for operador in importaciones[ingrediente][puerto].keys():
                    for empresa in importaciones[ingrediente][puerto][operador].keys():
                        for importacion in importaciones[ingrediente][puerto][operador][empresa].keys():
                            camiones_disponibles += int(importaciones[ingrediente][puerto][operador][empresa][importacion]['inventario'][t]/self.problema['capacidad_camion'])
                            
                            if camiones_disponibles > 0:
                                if ingrediente not in ingredientes_disponibles.keys():
                                    ingredientes_disponibles[ingrediente] = dict()
                                    
                                impo = f"{ingrediente}_{puerto}_{operador}_{empresa}_{importacion}"
                                ingredientes_disponibles[ingrediente][impo] = dict()
                                ingredientes_disponibles[ingrediente][impo]["camiones_disponibles"] = camiones_disponibles
                                ingredientes_disponibles[ingrediente][impo]["costo_despacho"] = dict()
                                
                                for planta in importaciones[ingrediente][puerto][operador][empresa][importacion]['costo_despacho_camion'].keys():
                                    
                                    ingredientes_disponibles[ingrediente][impo]["costo_despacho"][planta] = importaciones[ingrediente][puerto][operador][empresa][importacion]['costo_despacho_camion'][planta][t]
                                   
        return ingredientes_disponibles
    
    def get_dio_plantas(self, periodo:int)->dict:
        
        plantas_dio = dict()
        
        plantas = self.problema['plantas']
        
        for planta in plantas.keys():
            for ingrediente in plantas[planta]['ingredientes'].keys():
                
                t_disponible = plantas[planta]['tiempo_disponible']
                t_consumido = plantas[planta]['tiempo_consumido'][periodo]
                
                max_camiones_recepcion = int((t_disponible-t_consumido)/plantas[planta]['ingredientes'][ingrediente]['tiempo_proceso'])
                max_camiones_inventario = int((plantas[planta]['ingredientes'][ingrediente]['capacidad'] - plantas[planta]['ingredientes'][ingrediente]['inventario'][periodo])/self.problema['capacidad_camion'])

                if min(max_camiones_recepcion, max_camiones_inventario) > 0:                
                
                    if planta not in plantas_dio.keys():
                        plantas_dio[planta] = dict()
                        
                    if ingrediente not in plantas_dio[planta].keys():
                        plantas_dio[planta][ingrediente] = dict()
                    
                    plantas_dio[planta][ingrediente]['dio'] = plantas[planta]['ingredientes'][ingrediente]['dio'][periodo]
                    plantas_dio[planta][ingrediente]['consumo_pendiente'] = sum(plantas[planta]['ingredientes'][ingrediente]['consumo'][periodo:])
                
        return plantas_dio
        
    def get_safety_stock_plantas(self, periodo:int)->dict:
        
        plantas_ss_dio = dict()
        
        plantas = self.problema['plantas']
        
        for planta in plantas.keys():
            for ingrediente in plantas[planta]['ingredientes'].keys():
                if 'safety_stock_dio' in plantas[planta]['ingredientes'][ingrediente].keys():
                
                    t_disponible = plantas[planta]['tiempo_disponible']
                    t_consumido = plantas[planta]['tiempo_consumido'][periodo]
                    
                    inventario = plantas[planta]['ingredientes'][ingrediente]['inventario'][periodo]
                    dio = plantas[planta]['ingredientes'][ingrediente]['dio'][periodo]
                    safety_stock_dio = plantas[planta]['ingredientes'][ingrediente]['safety_stock_dio'][periodo]
                    faltante_ss_dio = safety_stock_dio - dio
                    
                    max_camiones_recepcion = int((t_disponible-t_consumido)/plantas[planta]['ingredientes'][ingrediente]['tiempo_proceso'])
                    max_camiones_inventario = int((plantas[planta]['ingredientes'][ingrediente]['capacidad'] - inventario)/self.problema['capacidad_camion'])
                    
                    if min(max_camiones_recepcion, max_camiones_inventario) > 0 and faltante_ss_dio > 0:                
                    
                        if planta not in plantas_ss_dio.keys():
                            plantas_ss_dio[planta] = dict()
                            
                        if ingrediente not in plantas_ss_dio[planta].keys():
                            plantas_ss_dio[planta][ingrediente] = dict()
                        
                        plantas_ss_dio[planta][ingrediente]['dio'] = dio
                        plantas_ss_dio[planta][ingrediente]['faltante_ss_dio'] = faltante_ss_dio
                
        return plantas_ss_dio
    
    
    def despacho_urgente(self, plantas_dio: dict(), ingredientes:list):
        # retorna la planta con la urgencia más alta
        
        # Inicializar valores

        peor_planta_dio = None
        peor_ingrediente_dio = None
        peor_dio = 1000
        peor_consumo = 0

        # Recorrer todas las plantas
        for planta in plantas_dio.keys():
            # recorrer totos los ingredientes
            for ingrediente in ingredientes: 
                # verificar que el ingrediente este dentro de los despachable
                if ingrediente in plantas_dio[planta].keys():
                    
                    # Inicializar variables si no se ha hecho
                    if not peor_planta_dio:
                        peor_planta_dio = planta
                        peor_ingrediente_dio = ingrediente
                        peor_dio = plantas_dio[planta][ingrediente]['dio']
                        peor_consumo = plantas_dio[planta][ingrediente]['consumo_pendiente']
                                
                    # Si estamos ante un peor DIO
                    if peor_dio > plantas_dio[planta][ingrediente]['dio']:
                        # Reasignar peor dio
                        peor_planta_dio = planta
                        peor_ingrediente_dio = ingrediente
                        peor_dio = plantas_dio[planta][ingrediente]['dio']
                        peor_consumo = plantas_dio[planta][ingrediente]['consumo_pendiente']
                        
                    # Si los dios son iguales, comparar los consumos
                    elif peor_dio == plantas_dio[planta][ingrediente]['dio']:
                        if peor_consumo < plantas_dio[planta][ingrediente]['consumo_pendiente']:
                            peor_planta_dio = planta
                            peor_ingrediente_dio = ingrediente
                            peor_dio = plantas_dio[planta][ingrediente]['dio']
                            peor_consumo = plantas_dio[planta][ingrediente]['consumo_pendiente']

                        
        return peor_planta_dio, peor_ingrediente_dio, peor_dio
    
    
    def despacho_para_ss(self, plantas_dio: dict(), ingredientes:list):
        # retorna la planta con la urgencia más alta
        
        # Inicializar valores

        peor_planta_dio = None
        peor_ingrediente_dio = None
        peor_dio = 1000
        peor_faltante = 0

        # Recorrer todas las plantas
        for planta in plantas_dio.keys():
            # recorrer totos los ingredientes
            for ingrediente in ingredientes: 
                # verificar que el ingrediente este dentro de los despachable
                if ingrediente in plantas_dio[planta].keys():
                    
                    # Inicializar variables si no se ha hecho
                    if not peor_planta_dio:
                        peor_planta_dio = planta
                        peor_ingrediente_dio = ingrediente
                        peor_dio = plantas_dio[planta][ingrediente]['dio']
                        peor_faltante = plantas_dio[planta][ingrediente]['faltante_ss_dio']
                                
                    # Si estamos ante un peor DIO
                    if peor_dio > plantas_dio[planta][ingrediente]['dio']:
                        # Reasignar peor dio
                        peor_planta_dio = planta
                        peor_ingrediente_dio = ingrediente
                        peor_dio = plantas_dio[planta][ingrediente]['dio']
                        peor_faltante = plantas_dio[planta][ingrediente]['faltante_ss_dio']
                        
                    # Si los dios son iguales, comparar los consumos
                    elif peor_dio == plantas_dio[planta][ingrediente]['dio']:
                        if peor_faltante < plantas_dio[planta][ingrediente]['faltante_ss_dio']:
                            peor_planta_dio = planta
                            peor_ingrediente_dio = ingrediente
                            peor_dio = plantas_dio[planta][ingrediente]['dio']
                            peor_faltante = plantas_dio[planta][ingrediente]['faltante_ss_dio']

                        
        return peor_planta_dio, peor_ingrediente_dio, peor_dio, peor_faltante
    
    
    
                
    def get_despacho_planta_minimo_costo(self,ingrediente:str, planta:str, t:int)->dict:
        
        min_costo= None
        min_puerto = ''
        min_operador=''
        min_empresa=''
        min_impo = ''
        
        importaciones = self.problema['importaciones']
        
        for puerto in importaciones[ingrediente].keys():
            for operador in importaciones[ingrediente][puerto].keys():
                for empresa in importaciones[ingrediente][puerto][operador].keys():
                    for importacion in importaciones[ingrediente][puerto][operador][empresa].keys():
                        if importaciones[ingrediente][puerto][operador][empresa][importacion]['inventario'][t] > self.problema['capacidad_camion']:
                            if not min_costo:
                                min_costo = importaciones[ingrediente][puerto][operador][empresa][importacion]['costo_despacho_camion'][planta][t]
                                min_puerto = puerto
                                min_operador = operador
                                min_empresa = empresa
                                min_impo = importacion
                            
                            if min_costo > importaciones[ingrediente][puerto][operador][empresa][importacion]['costo_despacho_camion'][planta][t]:
                                min_costo = importaciones[ingrediente][puerto][operador][empresa][importacion]['costo_despacho_camion'][planta][t]
                                min_puerto = puerto
                                min_operador = operador
                                min_empresa = empresa
                                min_impo = importacion
                            
        return min_puerto, min_operador, min_empresa, min_impo 
                        
        
        
    

    def gen_solucion_fase_01(self):
        
        # FASE 1
        # Seleccionamos el primer periodo.
        # Vamos a nivelar el inventario de cada materia prima en planta en DIO, camion por camion
        # Empezaremos asegurando que no exista backorder en el corto plazo, para lo cual se asigna
        # la Carga disponible más económica un lead time antes, comenzando por la planta-ingrediente con
        # el menor DIO, mayor consumo y con capacidad de recibir un camion.
        # recalcular los indicadores (inventario final, DIO, etc) y continuar con el siguente DIO más bajo
        # El proceso se detiene cuando se acaba cuando no hay backorder y se sigue al siguiente periodo
        # si se agota el inventario en puerto se detiene el proceso para este ingrediente.
        
        
        
        # Fase 3 
        # Construya clusters con los valores únicos de despacho de camiones desde las importaciones
        # hasta las plantas. Elimine Los despachos que sean considerados más costosos
        # incremente periodo a periodo y camion a camiónel inventatrio en días sin sobrepasar la
        # Capacidad de almacenamiento o recepción
        
        
        # Fase 1
        print("Ejecutando Fase 1: Evitar Backorder")
        # Para cada periodo
        for t in tqdm(range(1, len(self.problema['fechas'])-2)):
       
            # Obtenga una lista de ingredientes disponibles en T
            ingredientes_disponibles = self.get_ingredientes_disponibles(t)
            
            # identifique dentro de la lista de ingredientes, cuál planta tiene el valor más bajo en DIO. Romper empate por el consumo pendiente más alto
            plantas_dio = self.get_dio_plantas(periodo=t+2)
            
 
            # Obtenga el siguiente despacho urgente
            peor_planta_dio, peor_ingrediente_dio, dio = self.despacho_urgente(plantas_dio=plantas_dio, ingredientes=list(ingredientes_disponibles.keys()))
                
           
                
            while dio <= 3 and len(ingredientes_disponibles.keys())>0:
                
                # Obtenga la importacion cuyo despacho sea el más bajo posible
                puerto, operador, empresa, importacion = self.get_despacho_planta_minimo_costo(ingrediente=peor_ingrediente_dio, planta=peor_planta_dio, t=t)
                
                # print(f"despachando {peor_ingrediente_dio} a {peor_planta_dio} con {dio}")
                self.problema['importaciones'][peor_ingrediente_dio][puerto][operador][empresa][importacion]['despachos'][peor_planta_dio]['minimo'][t] += 1
                self.problema['plantas'][peor_planta_dio]['ingredientes'][peor_ingrediente_dio]['llegadas'][f"{peor_ingrediente_dio}_{puerto}_{operador}_{empresa}_{importacion}"][t+2] +=1
                   
                self.calcular_parametros()
                    
                # Obtenga una lista de ingredientes disponibles en T
                ingredientes_disponibles = self.get_ingredientes_disponibles(t)
                
                # identifique dentro de la lista de ingredientes, cuál planta tiene el valor más bajo en DIO. Romper empate por el consumo pendiente más alto
                plantas_dio = self.get_dio_plantas(periodo=t+2)
                
                # Obtenga el siguiente despacho urgente
                peor_planta_dio, peor_ingrediente_dio, dio = self.despacho_urgente(plantas_dio=plantas_dio, ingredientes=list(ingredientes_disponibles.keys()))
              
    def gen_solucion_fase_02(self):
        
        # FASE 2
        # COntinue enviando camión a camion hasta llegar al SS
        
        # Fase 2
        print("Ejecutando Fase 2: Alcanzar Safety Stock")
        # Para cada periodo
        for t in tqdm(range(1, len(self.problema['fechas'])-2)):
       
            # Obtenga una lista de ingredientes disponibles en T
            ingredientes_disponibles = self.get_ingredientes_disponibles(t)
            
            # identifique dentro de la lista de ingredientes, cuál planta tiene el valor más bajo en DIO. Romper empate por el consumo pendiente más alto
            plantas_dio = self.get_safety_stock_plantas(periodo=t+2)
            
            # Obtenga el siguiente despacho urgente
            peor_planta_dio, peor_ingrediente_dio, dio, peor_faltante  = self.despacho_para_ss(plantas_dio=plantas_dio, ingredientes=list(ingredientes_disponibles.keys()))
            
            while dio <= self.problema['plantas'][peor_planta_dio]['ingredientes'][peor_ingrediente_dio]['safety_stock_dio']  and len(ingredientes_disponibles.keys())>0:
                
                # Obtenga la importacion cuyo despacho sea el más bajo posible
                puerto, operador, empresa, importacion = self.get_despacho_planta_minimo_costo(ingrediente=peor_ingrediente_dio, planta=peor_planta_dio, t=t)
                
                # print(f"despachando {peor_ingrediente_dio} a {peor_planta_dio} con {dio}")
                self.problema['importaciones'][peor_ingrediente_dio][puerto][operador][empresa][importacion]['despachos'][peor_planta_dio]['safety_stock'][t] += 1
                self.problema['plantas'][peor_planta_dio]['ingredientes'][peor_ingrediente_dio]['llegadas'][f"{peor_ingrediente_dio}_{puerto}_{operador}_{empresa}_{importacion}"][t+2] +=1
                   
                self.calcular_parametros()
                    
                # Obtenga una lista de ingredientes disponibles en T
                ingredientes_disponibles = self.get_ingredientes_disponibles(t)
                
                # identifique dentro de la lista de ingredientes, cuál planta tiene el valor más bajo en DIO. Romper empate por el consumo pendiente más alto
                plantas_dio = self.get_dio_plantas(periodo=t+2)
                
                # Obtenga el siguiente despacho urgente
                peor_planta_dio, peor_ingrediente_dio, dio, peor_faltante  = self.despacho_para_ss(plantas_dio=plantas_dio, ingredientes=list(ingredientes_disponibles.keys()))
        
        
        
        

    
    def save(self):
        with open(self.file.replace('.xlsm', '.json'), 'w') as file:
            json.dump(self.problema, file, indent=4, sort_keys=True, default=str)
            
    
    def save_reports(self):
        
        # Guardar reporte puertos
        
        puertos_df = list()
        
        importaciones = self.problema['importaciones']
        
        periodos = len(self.problema['fechas'])
        
        print("Guardando reporte de puertos")
        
        for ingrediente in tqdm(importaciones.keys()):
            
            for puerto in importaciones[ingrediente].keys():
                
                for operador in importaciones[ingrediente][puerto].keys():
                
                    for empresa in importaciones[ingrediente][puerto][operador].keys():
                
                        for importacion in importaciones[ingrediente][puerto][operador][empresa].keys(): 
                            
                            for t in range(periodos):
                            
                                data = {
                                    "Empresa":empresa,
                                    "Puerto":puerto,
                                    "Operador":operador,
                                    "ingrediente":ingrediente,
                                    "Importacion":importacion,
                                    "Fecha":self.problema['fechas'][t],
                                    "Inventario":importaciones[ingrediente][puerto][operador][empresa][importacion]['inventario'][t],
                                    "llegadas":importaciones[ingrediente][puerto][operador][empresa][importacion]['llegadas'][t],
                                    "Costo_Almacenamiento": importaciones[ingrediente][puerto][operador][empresa][importacion]['costo_almacenamiento'][t],
                                    "Costo_Total_Almacenamiento": importaciones[ingrediente][puerto][operador][empresa][importacion]['costo_almacenamiento'][t]*importaciones[ingrediente][puerto][operador][empresa][importacion]['inventario'][t]   
                                }
                                
                                puertos_df.append(data)
                                
        puertos_df = pd.DataFrame(puertos_df)
        
        puertos_df.to_csv(r"C:\Users\luisf\Documents\reporte_puerto.csv")
        
        # Guardando reporte de despachos
        despachos_df = list()
        
        importaciones = self.problema['importaciones']
        
        periodos = len(self.problema['fechas'])
        
        print("Guardando reporte de despachos")
        
        for ingrediente in tqdm(importaciones.keys()):
            
            for puerto in importaciones[ingrediente].keys():
                
                for operador in importaciones[ingrediente][puerto].keys():
                
                    for empresa in importaciones[ingrediente][puerto][operador].keys():
                
                        for importacion in importaciones[ingrediente][puerto][operador][empresa].keys(): 
                            
                            for planta in importaciones[ingrediente][puerto][operador][empresa][importacion]['despachos'].keys():
                            
                                for t in range(periodos):
                                    
                                    if 'minimo' in importaciones[ingrediente][puerto][operador][empresa][importacion]['despachos'][planta].keys():
                                        minimo = importaciones[ingrediente][puerto][operador][empresa][importacion]['despachos'][planta]['minimo'][t]
                                        safety_stock = importaciones[ingrediente][puerto][operador][empresa][importacion]['despachos'][planta]['safety_stock'][t]
                                        target = importaciones[ingrediente][puerto][operador][empresa][importacion]['despachos'][planta]['target'][t]
                                        camiones_despachados = minimo + safety_stock + target
                                    else:
                                        camiones_despachados = 0
                                    flete_camion = importaciones[ingrediente][puerto][operador][empresa][importacion]['flete_camion'][planta]
                                    data = {
                                        "Empresa":empresa,
                                        "Puerto":puerto,
                                        "Operador":operador,
                                        "ingrediente":ingrediente,
                                        "Importacion":importacion,
                                        "Fecha":self.problema['fechas'][t],
                                        "Planta":planta,
                                        "Camiones_despachados": camiones_despachados,
                                        "Costo_Transporte_camion": flete_camion,
                                        "Costo_Transprote": camiones_despachados * flete_camion,
                                        }
                                    
                                    despachos_df.append(data)
                                
        despachos_df = pd.DataFrame(despachos_df)
        
        despachos_df.to_csv(r"C:\Users\luisf\Documents\reporte_despachos.csv")
        
        
        # Guardando reporte de despachos
        plantas_df = list()
        
        plantas = self.problema['plantas']
        
        periodos = len(self.problema['fechas'])
        
        print("Guardando reporte de plantas") 
        
        for planta in plantas.keys():
            for ingrediente in plantas[planta]['ingredientes']:
                
                for t in range(periodos):
                            
                            inventario = plantas[planta]['ingredientes'][ingrediente]['inventario'][t]
                            capacidad = plantas[planta]['ingredientes'][ingrediente]['capacidad']
                            consumo = plantas[planta]['ingredientes'][ingrediente]['consumo'][t]
                            backorder = plantas[planta]['ingredientes'][ingrediente]['backorder'][t]
                            objetivo = capacidad
                            data = {
                                "variable":"inventario en planta",
                                "planta": planta,
                                "ingrediente": ingrediente,
                                "periodo": self.problema['fechas'][t],
                                "inventario": inventario,
                                "capacidad": capacidad,
                                "consumo": consumo,
                                "backorder": backorder,
                                "objetivo": objetivo
                                }
                            
                            plantas_df.append(data)
                        
        plantas_df = pd.DataFrame(plantas_df)
        
        plantas_df.to_csv(r"C:\Users\luisf\Documents\reporte_plantas.csv")
        
        
            
        
        