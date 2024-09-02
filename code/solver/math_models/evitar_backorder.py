# -*- coding: utf-8 -*-
"""
Created on Fri Aug 30 17:27:46 2024

@author: luisf
"""

import pulp as pu
import os
from reducir_importaciones import reducir_importaciones

class EvitarBackorder():
    
    def __init__(self, problema:dict):
        
        self.problema = reducir_importaciones(problema)
        self.despacho_var = dict() # [impo][planta][t]
        self.recibos_var = dict() # [planta][ingrediente][t]
        self.llegadas_puerto_par = dict() # [impo][t]
        self.inv_puerto_var = dict() # [impo][t]
        self.inv_planta_var = dict() # [ingrediente][planta][t]
        self.consumo_planta_var = dict() # [ingrediente][planta][t]
        self.llegadas_planta_par = dict() # [ingrediente][planta][t]
        
        self.funcion_objetivo = list() # min costos*despachos + max(costo_despacho_camion)*consumo
        
        self.balance_puerto = list() # inv_actual = inv_anterior + llegadas - despachos
        self.balance_planta = list() # inv_actual = inv_anterior + llegadas - consumo + despachos_t+2
        self.cap_recepcion_planta = list() # sum(despachos_t+2)*tiempo_proceso + llegadas_planeadas*tiempo_proceso <= tiempo_planta
        self.cap_almacenamiento_planta =  list() # inv_planta < capacidad
        
        self.model = pu.LpProblem(name='minimizar_costo_total_backorder', sense=pu.LpMaximize)
        
        self.gen_modelo()
        
        
    def gen_variables_despacho(self):
    
        # Generar variables de despacho (y recepción)
        for ingrediente in self.problema['importaciones']['importacion'].keys():
            for planta in self.problema['importaciones'][ingrediente]['puerto']['operador']['empresa']['importacion']['despachos'].keys():
                for t in range(len(self.problema['fechas'])-2):
                    var_name = f"desp_{ingrediente}_{planta}_{t}"   
                    var = pu.LpVariable(name=var_name, lowBound=0, cat=pu.LpInteger)
                    if ingrediente not in self.despacho_var.keys():
                        self.despacho_var[ingrediente] =  dict()
                    if planta not in self.despacho_var[ingrediente].keys():
                        self.despacho_var[ingrediente][planta] = dict()
                    self.despacho_var[ingrediente][planta][t]=var
                    if planta not in self.recibos_var.keys():
                        self.recibos_var[planta] = dict()
                    if t ==0:
                        self.recibos_var[planta][ingrediente] = list()
                        self.recibos_var[planta][ingrediente].append(0)
                        self.recibos_var[planta][ingrediente].append(0)
                    self.recibos_var[planta][ingrediente].append(var)
                                        
    def gen_variables_inventario_importacion(self):
        # Generar variables de inventario en puerto
        for ingrediente in self.problema['importaciones'].keys():         
                self.inv_puerto_var[f"{ingrediente}"] = list()
                for t in range(len(self.problema['fechas'])):
                    var_name = f"inv_{ingrediente}_{puerto}_{operador}_{empresa}_{importacion}_{t}"
                    maximo = self.problema['importaciones'][ingrediente][puerto][operador][empresa][importacion]['inventario'][t]
                    var = pu.LpVariable(name=var_name, lowBound=0, upBound=maximo, cat=pu.LpContinuous)
                    var.setInitialValue(maximo)
                    self.inv_puerto_var[f"{ingrediente}_{puerto}_{operador}_{empresa}_{importacion}"].append(var)

    def gen_variables_inventario_planta(self):
        
        for planta in self.problema['plantas'].keys():
            self.inv_planta_var[planta] = dict()
            self.consumo_planta_var[planta] = dict()
            for ingrediente in self.problema['plantas'][planta]['ingredientes'].keys():
                self.inv_planta_var[planta][ingrediente] = list()
                self.consumo_planta_var[planta][ingrediente] = list()
                max_cap = self.problema['plantas'][planta]['ingredientes'][ingrediente]['capacidad']
                for t in range(len(self.problema['fechas'])):
                    # Variables de inventario
                    var_name = f"inv_{planta}_{ingrediente}_{t}"
                    inv_act = self.problema['plantas'][planta]['ingredientes'][ingrediente]['inventario'][t]        
                    var = pu.LpVariable(name=var_name, lowBound=0, upBound=max(max_cap, inv_act), cat=pu.LpContinuous)
                    var.setInitialValue(inv_act)
                    self.inv_planta_var[planta][ingrediente].append(var)
                    
                    # Variables de consumo
                    var_name = f"con_{planta}_{ingrediente}_{t}"
                    consumo = self.problema['plantas'][planta]['ingredientes'][ingrediente]['consumo'][t]
                    var = pu.LpVariable(name=var_name, lowBound=0, upBound=consumo, cat=pu.LpContinuous)
                    var.setInitialValue(min(consumo, inv_act))
                    self.consumo_planta_var[planta][ingrediente].append(var)

    def gen_rest_balance_puerto(self):
        
        # inv_act = inv_ant + llegadas - despachos
        for ingrediente in self.problema['importaciones'].keys():
            for puerto in self.problema['importaciones'][ingrediente].keys():
                for operador in self.problema['importaciones'][ingrediente][puerto].keys():
                    for empresa in self.problema['importaciones'][ingrediente][puerto][operador].keys():
                        for importacion in self.problema['importaciones'][ingrediente][puerto][operador][empresa].keys():

                            inv_inicial = self.problema['importaciones'][ingrediente][puerto][operador][empresa][importacion]['inventario_inicial']
                            for t in range(len(self.problema['fechas'])):
                                if t==0:
                                    inv_ant = inv_inicial
                                else:
                                    inv_ant = self.inv_puerto_var[f"{ingrediente}_{puerto}_{operador}_{empresa}_{importacion}"][t-1]
                                    
                                llegadas = self.problema['importaciones'][ingrediente][puerto][operador][empresa][importacion]['llegadas'][t]
                                name = f"{ingrediente}_{puerto}_{operador}_{empresa}_{importacion}"
                                
                                despachos = [self.problema['capacidad_camion']*self.despacho_var[name][planta][t] for planta in self.despacho_var[name].keys() if t<len(self.problema['fechas'])-2 and t in self.despacho_var[name][planta].keys()]
            
                                inv_actual = self.inv_puerto_var[f"{ingrediente}_{puerto}_{operador}_{empresa}_{importacion}"][t]
            
                                rest_name = f"balinv_{name}_{t}"
                                
                                rest = (inv_actual == inv_ant + llegadas - pu.lpSum(despachos) ,rest_name)
                                
                                self.balance_puerto.append(rest)

    def gen_rest_balance_planta(self):
        # inv_act = inv_ant + llegadas_planeadas + llegadas - consumo
        
        for planta in self.inv_planta_var.keys():
            for ingrediente in self.inv_planta_var[planta].keys():
                inv_inicial = self.problema['plantas'][planta]['ingredientes'][ingrediente]['inventario_inicial']
                for t in range(len(self.problema['fechas'])):
                    
                    if t==0:
                        inv_ant = inv_inicial
                    else:
                        inv_ant = self.inv_planta_var[planta][ingrediente][t-1]
                        
                    llegada_planeada = self.problema['plantas'][planta]['ingredientes'][ingrediente]['llegada_planeada'][t]
                    
                    if ingrediente in self.recibos_var[planta].keys():
                        llegadas = [self.problema['capacidad_camion']*x for x in self.recibos_var[planta][ingrediente][t]]
                    else:
                        llegadas = 0
                
                    consumo = self.consumo_planta_var[planta][ingrediente][t]
                    
                    inv_actual = self.inv_planta_var[planta][ingrediente][t]
        
                    rest_name = f"balinv_{planta}_{ingrediente}_{t}"
                    
                    rest = (inv_actual == inv_ant + llegada_planeada + pu.lpSum(llegadas) - consumo, rest_name)
                    
                    self.balance_planta.append(rest)

    def gen_rest_capacidad_recepcion(self):

        for planta in self.recibos_var.keys():
            for t in range(len(self.problema['fechas'])):
                rest_name = f"recepcion_{planta}_{t}"
                recibos = list()
                for ingrediente in self.recibos_var[planta].keys():
                    tiempo_ingrediente = self.problema['plantas'][planta]['ingredientes'][ingrediente]['tiempo_proceso']
                    var = self.recibos_var[planta][ingrediente][t]
                    recibos.append(tiempo_ingrediente*var)
                    
                rest = (pu.lpSum(recibos) <= self.problema['plantas'][planta]['tiempo_disponible'], rest_name)

                self.cap_recepcion_planta.append(rest)

        
    def gen_funcion_objetivo(self):
        # MAx sum consumo - costo_despacho_Camion
        
        # restar costos de despacho del camión
        for impo in self.despacho_var.keys():
            campos = impo.split('_')
            ingrediente = campos[0]
            puerto = campos[1]
            operador = campos[2]
            empresa = campos[3]
            importacion = campos[4]
            # print(campos)
            for planta in self.despacho_var[impo].keys():
                for t in range(len(self.problema['fechas'])-2):
                    if t in self.despacho_var[impo][planta].keys():
                        var = self.despacho_var[impo][planta][t]
                        costo_camion = self.problema['importaciones'][ingrediente][puerto][operador][empresa][importacion]['costo_despacho_camion'][planta][t]*-1              
                        self.funcion_objetivo.append(costo_camion*var)
            
        # Sumar el consumo
        for planta in self.consumo_planta_var.keys():
            for ingrediente in self.consumo_planta_var[planta].keys():
                if ingrediente in self.problema['costo_backorder'].keys():
                    utilidad_consumo = self.problema['costo_backorder'][ingrediente]
                else:
                    utilidad_consumo = max(self.problema['costo_backorder'].values())
                    
                total_periodos = len(self.problema['fechas'])
                
                for t in range(total_periodos):       
                    var = self.consumo_planta_var[planta][ingrediente][t]
                    self.funcion_objetivo.append(utilidad_consumo*var)
        
        
    def gen_modelo(self):
            
        self.gen_variables_despacho()
        self.gen_variables_inventario_importacion()
        self.gen_variables_inventario_planta()
        
        # Generar restricciones
        self.gen_rest_balance_puerto()
        self.gen_rest_balance_planta()
        self.gen_rest_capacidad_recepcion()
        
        # Generar Funcion Objetivo
        self.gen_funcion_objetivo()
        
        # add funcion objetivo
        self.model += pu.lpSum(self.funcion_objetivo)
            
        for rest in self.balance_planta:
            self.model += rest
            
        for rest in self.balance_puerto:
            self.model += rest
            
        for rest in self.cap_recepcion_planta:
            self.model += rest
        
    
    
    def solve(self):
        
        # Cantidad CPU habilitadas para trabajar
        cpu_count = max(1, os.cpu_count()-1)
        

        
        t_limit_minutes = 25

        print('cpu count', cpu_count)
        print('t_limit_minutes ', t_limit_minutes, "/", t_limit_minutes*60,"seconds")
        
        engine_glpk = pu.GLPK_CMD(
            mip=True,
            # timeLimit=60*t_limit_minutes,
            options=["--mipgap", "0.05"]
        )
        
        engine_cbc = pu.PULP_CBC_CMD(
            # timeLimit=60*t_limit_minutes,
            gapRel=0.05,
            warmStart=True,
            threads=cpu_count)
        
        self.model.solve(solver=engine_cbc)


    def report_inventario_planta(self):

        for planta in self.problema['plantas'].keys():
            for ingrediente in self.problema['plantas'][planta]['ingredientes'].keys():
                for t in range(len(self.problema['fechas'])):
                    # Variables de inventario     
                    var = self.inv_planta_var[planta][ingrediente][t]
                    self.problema['plantas'][planta]['ingredientes'][ingrediente]['inventario'][t] = var.varValue
                    
                    # Variables de consumo
                    var = self.consumo_planta_var[planta][ingrediente][t]
                    consumo_inicial = self.problema['plantas'][planta]['ingredientes'][ingrediente]['consumo'][t]
                    consumo_actual = var.varValue
                    backorder_actual = consumo_inicial - consumo_actual
                    
                    self.problema['plantas'][planta]['ingredientes'][ingrediente]['consumo'][t] = consumo_actual
                    self.problema['plantas'][planta]['ingredientes'][ingrediente]['backorder'][t] = backorder_actual
                    

    def report_despachos(self):
        # Generar agregar variables de despacho a problema
        for var_name in self.despacho_var.keys():
            campos = var_name.split('_')
            ingrediente = campos[0]
            puerto = campos[1]
            operador = campos[2]
            empresa = campos[3]
            importacion = campos[4]
            for planta in self.despacho_var[var_name].keys():
                for t, var in self.despacho_var[var_name][planta].items():
                    if var.varValue > 0:
                        # print(var_name, planta, t, var.varValue)
                        self.problema['importaciones'][ingrediente][puerto][operador][empresa][importacion]['despachos'][planta]['minimo'][t] = int(max(0,var.varValue))
       
    def report_inventario_puerto(self):
        
        for var_name in self.inv_puerto_var.keys():
            campos = var_name.split('_')
            ingrediente = campos[0]
            puerto = campos[1]
            operador = campos[2]
            empresa = campos[3]
            importacion = campos[4]
        
            for t in range(len(self.inv_puerto_var[var_name])):
                var = self.inv_puerto_var[var_name][t]
                if var.varValue > 0:
                    # print(var_name, var.varValue)
                    self.problema['importaciones'][ingrediente][puerto][operador][empresa][importacion]['inventario'][t] = int(max(0,var.varValue))
                    # print(var_name, t, var.varValue, problema['importaciones'][ingrediente][puerto][operador][empresa][importacion]['inventario'][t])
        

    def gen_reports(self):

        self.report_inventario_planta()
        self.report_despachos()
        self.report_inventario_puerto()