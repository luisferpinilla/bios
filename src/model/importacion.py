# -*- coding: utf-8 -*-
"""
Created on Mon Sep  9 20:09:48 2024

@author: luisf
"""

from problema import Problema

class Importacion():
    
    def __init__(self,problema:Problema, ingrediente:str, puerto:str, operador:str, empresa:str, importacion:str, inventario_inicial=0, valor_cif=10):
        
        self.problema = problema
        self.valor_cif = valor_cif
        self.ingrediente=ingrediente
        self.puerto=puerto
        self.operador=operador
        self.empresa=empresa
        self.importacion=importacion
        self.llegadas = {x:0 for x in range(len(problema.fechas))}
        self.costo_almacenamiento = {x:0 for x in range(len(problema.fechas))}
        self.costo_bodegaje = {x:0 for x in range(len(problema.fechas))}
        self.costo_despacho_directo = {x:0 for x in range(len(problema.fechas))}
        self.costo_flete = {planta:0 for planta in problema.plantas.keys() if planta.ingredientes.consumo}
        
        
        self.despachos = {planta:{
                            "min":{x:0 for x in range(len(problema.fechas))},
                            "safety_stock":{x:0 for x in range(len(problema.fechas))}, 
                            "target":{x:0 for x in range(len(problema.fechas))},
                            "despacho_directo": {x:0 for x in range(len(problema.fechas))},
                            "ahorro_almacenamiento": {x:0 for x in range(len(problema.fechas))},
                            "flete": {x:0 for x in range(len(problema.fechas))},
                            "intercompany":{x:0 for x in range(len(problema.fechas))},
                            "total": {x:0 for x in range(len(problema.fechas))}} 
                                for planta in self.problema.plantas.keys() if ingrediente in self.problema.plantas[planta].ingredientes.keys()}
        self.inventario_inicial = inventario_inicial
        self.inventario = {x:0 for x in range(len(problema.fechas))}
        self.backorder = {x:0 for x in range(len(problema.fechas))}

        self._calcular_inventario()
      
     
    def _calcular_inventario(self):
        
        inventario = self.inventario_inicial

        for t in range(len(self.problema.fechas)):
            inventario = inventario + self.llegadas[t] - self.problema.cap_camion*(self.despachos["min"][t] - self.despachos["safety_stock"][t] - self.despachos["target"][t])
            self.inventario[t] = inventario
    
    def get_code(self)->str:
        return f"{self.ingrediente}_{self.puerto}_{self.operador}_{self.empresa}_{self.importacion}"

    def get_camiones_despachables(self)->int:
        return int(self.inventario[len(self.problema.fechas)]/self.problema.cap_camion)
      
    def __str__(self):
        return self.get_code()
        
    def __eq__(self, o):
        try:
            return o.ingrediente == self.ingrediente and o.puerto == self.puerto and o.operador == self.operador and o.empresa==self.empresa and o.importacion==self.importacion
        except:
            return False
    
    
        
        
        
        
    