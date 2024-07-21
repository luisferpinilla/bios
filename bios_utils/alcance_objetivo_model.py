from bios_utils.problema import Problema
from tqdm import tqdm
import pulp as pu
import numpy as np
import os

class AlcanceObjetivoModel():

    def __init__(self, problema:Problema) -> None:
        self.problema = problema
        # Variables de inventario en planta
        self.inventario_planta = dict()

        # Inventario proyectado
        self.inventario_proyectado = dict()

        # FAltante para opbjetivo de inventario
        self.faltante_objetivo_inventario = dict()

        # invenatrio proyectado
        self.inventario_proyectado = dict()

        # Backorder
        self.backorder = dict()

        # Variables de despacho
        self.despachos_planta = dict()
        # Variables de recibo en planta
        self.recibo_planta = dict()

        # Variables de inventario
        self.inventario_puerto = dict()

        # Variables de despacho
        self.despachos_planta = dict()

        # Variables de recibo en planta
        self.recibo_planta = dict()

        # Balance de masa planta
        self.balance_masa_planta = list()

        # Balance de masa puerto
        self.balance_masa_puerto = list()

        # Capacidad de recepcion en planta
        self.rest_recepcion_planta = list()

        # Restriccion para Faltante para llegar al inventario objetivo
        self.faltante_inventario_objetivo = list()

        # Funcion objetivo: faltante inventario
        self.fobj_faltante_inventario_objetivo = list()

        # Funcion objetivo: Backorder
        self.fobj_backorder = list()

        self.__gen_variables_planta()
        self.__gen_variables_despachos()
        self.__gen_variables_inventario_puerto()
        self.__gen_variables_despacho()
        self.__gen_rest_balance_planta()
        self.__gen_rest_balance_puerto()
        self.__gen_rest_recepcion_planta()
        self.__gen_rest_faltante_objetivo()
        self.__gen_fob_faltante_objetivo()
        self.__gen_fob_backorder()


    def __gen_variables_planta(self):
        for planta in tqdm(self.problema.plantas):
            self.inventario_planta[planta] = dict()
            self.inventario_proyectado[planta] = dict()
            self.faltante_objetivo_inventario[planta] = dict()
            self.backorder[planta] = dict()
            for ingrediente in self.problema.ingredientes:
                self.inventario_planta[planta][ingrediente] = dict()
                self.inventario_proyectado[planta][ingrediente] = dict()
                self.faltante_objetivo_inventario[planta][ingrediente] = dict()
                self.backorder[planta][ingrediente] = dict()
                ii = self.problema.inventario_planta[planta][ingrediente]
                ca = self.problema.capacidad_planta[planta][ingrediente]
                obj = self.problema.objetivo_inventario[planta][ingrediente]
                for periodo in self.problema.periodos:
                    ii += self.problema.llegadas_planeadas_planta[planta][ingrediente][periodo]
                    ii -= self.problema.consumo_proyectado[planta][ingrediente][periodo]

                    self.inventario_proyectado[planta][ingrediente][periodo] = ii

                    inventario_var = pu.LpVariable(
                        name=f'inv_{planta}_{ingrediente}_{periodo}',
                        lowBound=0.0,
                        upBound=max(ii, ca),
                        cat=pu.LpContinuous)
                    inventario_var.setInitialValue(max(ii, 0.0))
                    self.inventario_planta[planta][ingrediente][periodo] = inventario_var

                    faltante_var = pu.LpVariable(
                        name=f'fal_{planta}_{ingrediente}_{periodo}',
                        lowBound=0.0,
                        upBound=obj,
                        cat=pu.LpContinuous)
                    self.faltante_objetivo_inventario[planta][ingrediente][periodo] = faltante_var
                    fal = max(obj - max(ii, 0.0), 0.0)
                    faltante_var.setInitialValue(fal)

                    backorder_var = pu.LpVariable(
                        name=f'bkr_{planta}_{ingrediente}_{periodo}',
                        cat=pu.LpBinary)

                    if ii < 0:
                        backorder_var.setInitialValue(1)
                    else:
                        backorder_var.setInitialValue(0)
                    self.backorder[planta][ingrediente][periodo] = backorder_var

    def __gen_variables_despachos(self):
        for ingrediente in self.problema.ingredientes:
            if not ingrediente in self.despachos_planta.keys():
                self.despachos_planta[ingrediente] = dict()
                self.recibo_planta[ingrediente] = dict()
            for planta in self.problema.plantas:

                self.recibo_planta[ingrediente][planta] = dict()

                self.despachos_planta[ingrediente][planta] = dict()

                t_proceso = self.problema.tiempo_proceso[planta][ingrediente]
                t_disponible = self.problema.tiempo_disponible[planta]
                max_cap_recepcion = int(t_disponible/t_proceso)

                for periodo in self.problema.periodos[1:-2:]:

                    max_inventario = int(
                        self.inventario_planta[planta][ingrediente][periodo].upBound/self.problema.cap_camion)

                    despacho_name = f'despacho_{ingrediente}_{planta}_{periodo}'
                    despacho_var = pu.LpVariable(name=despacho_name,
                                                lowBound=0,
                                                upBound=min(
                                                    max_inventario, max_cap_recepcion),
                                                cat=pu.LpInteger)
                    despacho_var.setInitialValue(0)

                    self.despachos_planta[ingrediente][planta][periodo] = despacho_var

                    periodo_leadtime = self.problema.periodos[self.problema.periodos.index(periodo)+2]
                    self.recibo_planta[ingrediente][planta][periodo_leadtime] = despacho_var

    def __gen_variables_inventario_puerto(self):
                
        for ingrediente in self.problema.ingredientes:
            self.inventario_puerto[ingrediente] = dict()
            ii = self.problema.inventario_totalizado_inicial_puerto[ingrediente]
            for periodo in self.problema.periodos:
                arp = self.problema.llegadas_totalizadas_puerto[ingrediente][periodo]
                ii += arp
                var_name = f'inv_{ingrediente}_{periodo}'
                var = pu.LpVariable(name=var_name, lowBound=0, cat=pu.LpInteger)
                var.setInitialValue(ii)
                self.inventario_puerto[ingrediente][periodo] = var

    def __gen_variables_despacho(self):
 
        for ingrediente in self.problema.ingredientes:
            if not ingrediente in self.despachos_planta.keys():
                self.despachos_planta[ingrediente] = dict()
                self.recibo_planta[ingrediente] = dict()
            for planta in self.problema.plantas:

                self.recibo_planta[ingrediente][planta] = dict()

                self.despachos_planta[ingrediente][planta] = dict()

                t_proceso = self.problema.tiempo_proceso[planta][ingrediente]
                t_disponible = self.problema.tiempo_disponible[planta]
                max_cap_recepcion = int(t_disponible/t_proceso)

                for periodo in self.problema.periodos[1:-2:]:

                    max_inventario = int(
                        self.inventario_planta[planta][ingrediente][periodo].upBound/self.problema.cap_camion)

                    despacho_name = f'despacho_{ingrediente}_{planta}_{periodo}'
                    despacho_var = pu.LpVariable(name=despacho_name,
                                                lowBound=0,
                                                upBound=min(
                                                    max_inventario, max_cap_recepcion),
                                                cat=pu.LpInteger)
                    despacho_var.setInitialValue(0)

                    self.despachos_planta[ingrediente][planta][periodo] = despacho_var

                    periodo_leadtime = self.problema.periodos[self.problema.periodos.index(periodo)+2]
                    self.recibo_planta[ingrediente][planta][periodo_leadtime] = despacho_var

    def __gen_rest_balance_planta(self):
        
        for planta in tqdm(self.problema.plantas):
            for ingrediente in self.problema.ingredientes:
                for periodo in self.problema.periodos:
                    # I = It-1 + llegadas_programadas + llegadas_puerto - backorder*consumo
                    rest_name = f'balance_planta_{planta}_{ingrediente}_{periodo}'
                    I = self.inventario_planta[planta][ingrediente][periodo]
                    llegada_planeada = self.problema.llegadas_planeadas_planta[planta][ingrediente][periodo]
                    con = self.problema.consumo_proyectado[planta][ingrediente][periodo]
                    bk = self.backorder[planta][ingrediente][periodo]
                    if periodo in self.recibo_planta[ingrediente][planta].keys():
                        llegada_planta = self.recibo_planta[ingrediente][planta][periodo]
                    else:
                        llegada_planta = 0

                    if self.problema.periodos.index(periodo) == 0:
                        Iant = Iant = self.problema.inventario_planta[planta][ingrediente]
                    else:

                        periodo_anterior = self.problema.periodos[self.problema.periodos.index(periodo)-1]

                        Iant = self.inventario_planta[planta][ingrediente][periodo_anterior]

                    rest = (I == Iant + llegada_planeada + self.problema.cap_camion *
                            llegada_planta - con + con*bk, rest_name)
                    self.balance_masa_planta.append(rest)

    def __gen_rest_balance_puerto(self):
        
        for ingrediente in self.problema.ingredientes:
            for periodo in self.problema.periodos:
                # I = It-1 + llegadas_programadas - despachos_planta
                I = self.inventario_puerto[ingrediente][periodo]

                if self.problema.periodos.index(periodo) == 0:
                    Iant = self.problema.inventario_totalizado_inicial_puerto[ingrediente]
                else:
                    periodo_ant = self.problema.periodos[self.problema.periodos.index(periodo)-1]
                    Iant = self.inventario_puerto[ingrediente][periodo_ant]

                llegada_programada = self.problema.llegadas_totalizadas_puerto[ingrediente][periodo]

                despacho_list = list()
                for planta in self.problema.plantas:
                    if planta in self.despachos_planta[ingrediente].keys():
                        if periodo in self.despachos_planta[ingrediente][planta].keys():
                            despacho_list.append(self.despachos_planta[ingrediente][planta][periodo])

                rest_name = f'balance_puerto_{ingrediente}_{periodo}'
                rest = (I == Iant + llegada_programada -
                        pu.lpSum(despacho_list), rest_name)

                self.balance_masa_puerto.append(rest)

    def __gen_rest_recepcion_planta(self):

        for planta in self.problema.tiempo_proceso.keys():
            for periodo in self.problema.periodos:
                recibo_a_planta = [self.problema.tiempo_proceso[planta][ingrediente] * self.recibo_planta[ingrediente][planta][periodo] for ingrediente in self.problema.ingredientes if periodo in self.recibo_planta[ingrediente][planta].keys()]
                if len(recibo_a_planta)>0:
                    rest_name = f'recepcion_{planta}_{periodo}'
                    rest = (pu.lpSum(recibo_a_planta) <= self.problema.tiempo_disponible[planta], rest_name)
                    self.rest_recepcion_planta.append(rest)

    def __gen_rest_faltante_objetivo(self):
        
        for planta in self.inventario_planta.keys():
            for ingrediente in self.inventario_planta[planta].keys():
                # Calcular la media de consumo para cumplir el objetivo
                consumo_planta = np.mean([c for t, c in self.problema.consumo_proyectado[planta][ingrediente].items()])        
                objetivo = self.problema.objetivo_inventario[planta][ingrediente]        
                if consumo_planta > 0 and objetivo > 0:      
                    for periodo in self.problema.periodos:
                        # IF + OB >= Objetivo
                        IF = self.inventario_planta[planta][ingrediente][periodo]
                        OB = self.faltante_objetivo_inventario[planta][ingrediente][periodo]                     
                        rest_name = f'objetivo_inventario_{planta}_{ingrediente}_{periodo}'
                        rest = (IF + OB >= objetivo, rest_name)
                        self.faltante_inventario_objetivo.append(rest)

    def __gen_fob_faltante_objetivo(self):

        for planta in self.inventario_planta.keys():
            for ingrediente in self.inventario_planta[planta].keys():
                for periodo in self.problema.periodos:
                    self.fobj_faltante_inventario_objetivo.append(self.faltante_objetivo_inventario[planta][ingrediente][periodo])

    def __gen_fob_backorder(self):
        for planta in self.backorder.keys():
            for ingrediente in self.backorder[planta].keys():
                for periodo in self.problema.periodos:
                    self.fobj_backorder.append(100*self.problema.objetivo_inventario[planta][ingrediente]*self.backorder[planta][ingrediente][periodo])

    def solve(self):
        # Cantidad CPU habilitadas para trabajar
        cpu_count = max(1, os.cpu_count()-1)

        solucionador_01 = pu.LpProblem(name='Bios_Solver_fase_1', sense=pu.LpMinimize)

        # Agregando funcion objetivo
        solucionador_01 += pu.lpSum(self.fobj_faltante_inventario_objetivo)

        # Agregando balance de masa puerto
        for rest in self.balance_masa_puerto:
            solucionador_01 += rest

        # Agregando balance ce masa en planta
        for rest in self.balance_masa_planta:
            solucionador_01 += rest

        # Agregando restriccion de recepcion en planta
        for rest in self.rest_recepcion_planta:
            solucionador_01 += rest

        # Faltante de objetivo
        for rest in self.faltante_inventario_objetivo:
            solucionador_01 += rest

        t_limit_minutes = 15

        print('cpu count', cpu_count)
        print('ejecutando ', len(self.problema.periodos), 'periodos')
        engine_cbc = pu.PULP_CBC_CMD(
            timeLimit=60*t_limit_minutes,
            gapRel=0.05,
            warmStart=False,
            threads=cpu_count)

        engine_glpk = pu.GLPK_CMD(
            mip=True,
            timeLimit=60*t_limit_minutes,
            path=r"C:\glpk-4.65\w64\glpsol.exe",
            
        )

        solucionador_01.writeLP('model.lp')

        solucionador_01.solve(solver=engine_cbc)

        pu.LpStatus[solucionador_01.status]