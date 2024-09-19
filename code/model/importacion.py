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
        self.llegadas = dict()
        self.costo_almacenamiento = dict()
        self.costo_bodegaje = dict()
        self.costo_despacho_directo = dict()
        self.despachos = {"min":dict(),
                          "safety_stock":dict(), 
                          "target":dict()}
        self.inventario_inicial = inventario_inicial
        self.inventario = list()
        self.backorder = list()
      
     
    def _calcular(self):
        pass
     
    
    def get_code(self)->str:
        return f"{self.ingrediente}_{self.puerto}_{self.operador}_{self.empresa}_{self.importacion}"
      
    def __str__(self):
        return self.get_code()
        
    def __eq__(self, o):
        try:
            return o.ingrediente == self.ingrediente and o.puerto == self.puerto and o.operador == self.operador and o.empresa==self.empresa and o.importacion==self.importacion
        except:
            return False;
    
    
        
        
        
        
    