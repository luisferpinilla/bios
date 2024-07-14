from bios_utils.problema import Problema
from tqdm import tqdm
import pulp as pu

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

        self.__gen_variables_planta()
        self.__gen_variables_despachos()
        self.__gen_variables_inventario_puerto()
        self.__gen_variables_despacho()
        self.__gen_rest_balance_planta()
        self.__gen_rest_balance_puerto()


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
            ii = self.problema.inventario_inicial_puerto[ingrediente]
            for periodo in self.problema.periodos:
                arp = self.problema.llegadas_puerto[ingrediente][periodo]
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
                    Iant = self.problema.inventario_inicial_puerto[ingrediente]
                else:
                    periodo_ant = self.problema.periodos[self.problema.periodos.index(periodo)-1]
                    Iant = self.inventario_puerto[ingrediente][periodo_ant]

                llegada_programada = self.problema.llegadas_puerto[ingrediente][periodo]

                despacho_list = list()
                for planta in self.problema.plantas:
                    if planta in self.despachos_planta[ingrediente].keys():
                        if periodo in self.despachos_planta[ingrediente][planta].keys():
                            despacho_list.append(self.despachos_planta[ingrediente][planta][periodo])

                rest_name = f'balance_puerto_{ingrediente}_{periodo}'
                rest = (I == Iant + llegada_programada -
                        pu.lpSum(despacho_list), rest_name)

                self.balance_masa_puerto.append(rest)




