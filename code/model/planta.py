# -*- coding: utf-8 -*-
"""
Created on Mon Sep  9 20:00:07 2024

@author: luisf
"""

class Planta():
    def __init__(self, empresa:str, nombre:str, tiempo_total:int):
        
        self.nombre = nombre
        self.tiempo_total = tiempo_total
        self.ingredientes = dict()    
    