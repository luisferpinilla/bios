# -*- coding: utf-8 -*-
"""
Created on Mon Sep  9 20:03:43 2024

@author: luisf
"""
from datetime import datetime, date
from planta import Planta
from importacion import Importacion
import pandas as pd


class Problema():
    def __init__(self, file: str, cap_camion=34000, cap_descarge=5000000):

        self.file = file
        self.cap_camion = cap_camion
        self.cap_descarge = cap_descarge
        self.fechas = dict()
        self.ingredientes = list()
        self.plantas = dict()
        self.importaciones = dict()
        self.despachos = dict()

    def add_ingrediente(self, ingrediente: str):

        if ingrediente not in self.ingredientes:
            self.ingredientes.append(ingrediente)

            self.importaciones[ingrediente] = dict()

    def add_plant(self, planta: Planta):

        if planta.nombre in self.plantas.keys():
            raise Exception(f"la planta {planta.nombre} ya existe")

        self.plantas[planta.nombre] = planta

    def add_importacion(self, importacion: Importacion):

        code = importacion.get_code()

        if importacion.ingrediente not in self.ingredientes:
            raise Exception(
                f"el ingrediente {importacion.ingrediente} no existe")

        if code in self.importaciones.keys():
            raise Exception("La importacion ya existe")

        self.importaciones[importacion.ingrediente][code] = importacion

    def load_plantas(self):

        df = pd.read_excel(io=self.file, sheet_name='plantas')

        for i in df.index:
            nombre_planta = df.loc[i]['planta']
            empresa = df.loc[i]['empresa']
            operacion = df.loc[i]['operacion_minutos']
            limpieza = df.loc[i]['minutos_limpieza']
            plataformas = df.loc[i]['plataformas']

            planta = Planta(problema=self,
                            empresa=empresa,
                            nombre_planta=nombre_planta,
                            tiempo_total=operacion*plataformas,
                            tiempo_limpieza=limpieza)

            self.plantas[nombre_planta] = planta

            self.ingredientes = list(df.drop(columns=['planta',
                                                      'empresa',
                                                      'operacion_minutos',
                                                      'minutos_limpieza',
                                                      'plataformas']).columns)

            for ingrediente in self.ingredientes:

                planta.set_tiempo_proceso(
                    ingrediente=ingrediente, 
                    valor=df.loc[i][ingrediente])
                
    def load_consumos(self):

        df = pd.read_excel(io=self.file, sheet_name='consumo_proyectado')

        df.set_index(['planta', 'ingrediente'], inplace=True)

        fechas = [datetime.strptime(
            date_string=x, format='%d/%m/%Y').date() for x in df.columns]

        fechas = {fechas.index(x): x for x in fechas}

        self.fechas = fechas

        for i in df.index:

            if df.loc[i].sum() > 0.0:
                nombre_planta = i[0]
                nombre_ingrediente = i[1]

                planta = self.plantas[nombre_planta]

                fechas = list(df.columns)
                for t in fechas:
                    planta.add_consumos(
                        ingrediente=nombre_ingrediente, t=fechas.index(t), value=df.loc[i][t])
                



    def load_files(self):
        self.load_consumos()

    def _solve_fase_01(self):
        pass

    def _solve_fase_02(self):
        pass

    def _solve_fase_03(self):
        pass

    def solve(self):
        pass
