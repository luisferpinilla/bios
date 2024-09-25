# -*- coding: utf-8 -*-
"""
Created on Mon Sep  9 20:03:43 2024

@author: luisf
"""

from planta import Planta
from importacion import Importacion

class Problema():
    def __init__(self, file:str, cap_camion=34000, cap_descarge=5000000):
        
        self.file = file
        self.cap_camion = cap_camion
        self.cap_descarge=cap_descarge
        self.fechas = dict()
        self.ingredientes = list()
        self.plantas = dict()
        self.importaciones = dict()
        self.despachos = dict()
        
    
    def add_ingrediente(self, ingrediente:str):
        
        if ingrediente not in self.ingredientes:
            self.ingredientes.append(ingrediente)
            
            self.importaciones[ingrediente] =  dict()
        
        
    def add_plant(self, planta:Planta):
        
        if planta.nombre in self.plantas.keys():
            raise Exception(f"la planta {planta.nombre} ya existe")

        self.plantas[planta.nombre] = planta
        
        
    def add_importacion(self, importacion:Importacion):
        
        code = importacion.get_code()
        
        if importacion.ingrediente not in self.ingredientes:
            raise Exception(f"el ingrediente {importacion.ingrediente} no existe")
        
        if code in self.importaciones.keys():
            raise Exception("La importacion ya existe")
            
        self.importaciones[importacion.ingrediente][code] = importacion
        
        
    
    def _solve_fase_01(self):
        pass
    
    
    def _solve_fase_02(self):
        pass

    def _solve_fase_03(self):
        pass
    
    def solve(self):
        pass