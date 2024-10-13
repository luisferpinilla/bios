# -*- coding: utf-8 -*-
"""
Created on Mon Sep  9 20:00:07 2024

@author: luisf
"""
from model.problema import Problema

class Planta():
    def __init__(self, problema:Problema, empresa:str, nombre_planta:str, tiempo_total:int, tiempo_limpieza:int):
        
        self.problema = problema
        self.nombre = nombre_planta
        self.empresa = empresa
        self.tiempo_total = tiempo_total
        self.tiempo_limpieza = tiempo_limpieza
        self.tiempo_proceso = dict()
        self.ingredientes = dict()    
    
    @classmethod
    def add_consumos(self, ingrediente:str, t:int, value:int):
        
        if ingrediente not in self.ingredientes.keys():
            self.ingredientes[ingrediente] = dict()

        if "consumo" not in self.ingredientes[ingrediente].keys():
            self.ingredientes[ingrediente]["consumo"] = {x:0 for x in range(len(self.problema.fechas))}

        self.ingredientes[ingrediente]["consumo"][t] = value 

    @classmethod
    def add_llegada_planeada(self, ingrediente:str, t:int, value:int):

        if "llegada_planteada" not in self.ingredientes[ingrediente].keys():
            self.ingredientes[ingrediente]["llegada_planteada"] = {x:0 for x in range(len(self.problema.fechas))}

        self.ingredientes[ingrediente]["llegada_planteada"][t] += value

    @classmethod
    def set_tiempo_proceso(self, ingrediente:str, valor:int):
        self.tiempo_proceso[ingrediente] = valor
    
    @property
    def nombre(self):
        return self.nombre
    
    @property
    def empresa(self):
        return self.empresa

    def __str__(self) -> str:
        return self.planta
    
    def __eq__(self, value: object) -> bool:
        try:
            return isinstance(value, Planta) and value.nombre == self.nombre
        except:
            return False
        