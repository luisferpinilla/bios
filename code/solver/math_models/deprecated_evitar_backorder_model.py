from tqdm import tqdm
import pulp as pu
import os

class EvitarBackorder():

    def __init__(self, problema:dict) -> None:
        
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
        self.ejecucion_consumo = dict()

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

        # Funcion objetivo: consumo_ejecutado
        self.fobj_ejecucion_consumo = list()

        self.__gen_variables_planta()
        self.__gen_variables_despachos()
        self.__gen_variables_inventario_puerto()
        self.__gen_rest_balance_planta()
        self.__gen_rest_balance_puerto()
        # self.__gen_rest_recepcion_planta()
        self.__gen_fob_ejecucion_consumo()


    def __gen_variables_planta(self):
        
        for planta in tqdm(self.problema['plantas']):
            self.inventario_planta[planta] = dict()
            self.inventario_proyectado[planta] = dict()
            self.faltante_objetivo_inventario[planta] = dict()
            self.ejecucion_consumo[planta] = dict()
            
            for ingrediente in self.problema['plantas'][planta]['ingredientes'].keys():
                
                self.inventario_planta[planta][ingrediente] = dict()
                self.inventario_proyectado[planta][ingrediente] = dict()
                self.faltante_objetivo_inventario[planta][ingrediente] = dict()
                self.ejecucion_consumo[planta][ingrediente] = dict()
                
                ii = self.problema['plantas'][planta]['ingredientes'][ingrediente]['inventario_inicial']
                ca = self.problema['plantas'][planta]['ingredientes'][ingrediente]['capacidad']

                for t in range(len(self.problema['fechas'])):
                    
                    ii += self.problema['plantas'][planta]['ingredientes'][ingrediente]['llegada_planeada'][t]
                    ii -= self.problema['plantas'][planta]['ingredientes'][ingrediente]['consumo'][t]

                    self.inventario_proyectado[planta][ingrediente][t] = ii

                    inventario_var = pu.LpVariable(
                        name=f'inv_{planta}_{ingrediente}_{t}',
                        lowBound=0.0,
                        # upBound=max(ii, ca),
                        cat=pu.LpContinuous)
                    # inventario_var.setInitialValue(max(ii, 0.0))
                    self.inventario_planta[planta][ingrediente][t] = inventario_var

                    # faltante_var = pu.LpVariable(
                    #     name=f'fal_{planta}_{ingrediente}_{periodo}',
                    #     lowBound=0.0,
                    #     upBound=obj,
                    #     cat=pu.LpContinuous)
                    # self.faltante_objetivo_inventario[planta][ingrediente][periodo] = faltante_var
                    # fal = max(obj - max(ii, 0.0), 0.0)
                    # faltante_var.setInitialValue(fal)

                    ejecucion_var = pu.LpVariable(
                        name=f'eje_{planta}_{ingrediente}_{t}',
                        cat=pu.LpContinuous,
                        lowBound=0,
                        upBound=self.problema['plantas'][planta]['ingredientes'][ingrediente]['consumo'][t])
                    self.ejecucion_consumo[planta][ingrediente][t] = ejecucion_var

    def __gen_variables_despachos(self):
        for ingrediente in self.problema['importaciones'].keys():
            
            if not ingrediente in self.despachos_planta.keys():
                self.despachos_planta[ingrediente] = dict()
                self.recibo_planta[ingrediente] = dict()
            
            plantas = [x for x in self.problema['plantas'] if ingrediente in self.problema['plantas'][x]['ingredientes'].keys()]
            
            for planta in plantas:

                self.recibo_planta[ingrediente][planta] = dict()

                self.despachos_planta[ingrediente][planta] = dict()

                t_proceso = self.problema['plantas'][planta]['ingredientes'][ingrediente]['tiempo_proceso']
                t_disponible = self.problema['plantas'][planta]['tiempo_disponible']
                max_cap_recepcion = min(int(t_disponible/t_proceso), self.problema['plantas'][planta]['ingredientes'][ingrediente]['capacidad']/34000)

                for t in range(1, len(self.problema['fechas'])-2):

                    # max_inventario = int(self.inventario_planta[planta][ingrediente][periodo].upBound/self.problema.cap_camion)

                    despacho_name = f'despacho_{ingrediente}_{planta}_{t}'
                    despacho_var = pu.LpVariable(name=despacho_name,
                                                lowBound=0,
                                                upBound=max_cap_recepcion,
                                                cat=pu.LpInteger)
                    despacho_var.setInitialValue(0)

                    self.despachos_planta[ingrediente][planta][t] = despacho_var

                    periodo_leadtime = t+2
                    self.recibo_planta[ingrediente][planta][periodo_leadtime] = despacho_var

    def __gen_variables_inventario_puerto(self):
                
        for ingrediente in self.problema['importaciones'].keys():
            
            self.inventario_puerto[ingrediente] = dict()
            
            ii = sum([int(self.problema['importaciones'][ingrediente][p][o][e][i]['inventario_inicial']/self.problema['capacidad_camion']) for p in self.problema['importaciones'][ingrediente].keys() for o in self.problema['importaciones'][ingrediente][p].keys() for e in self.problema['importaciones'][ingrediente][p][o].keys() for i in self.problema['importaciones'][ingrediente][p][o][e].keys()])
            
            for t in range(len(self.problema['fechas'])):
                
                arp = sum([int(self.problema['importaciones'][ingrediente][p][o][e][i]['llegadas'][t]/self.problema['capacidad_camion']) for p in self.problema['importaciones'][ingrediente].keys() for o in self.problema['importaciones'][ingrediente][p].keys() for e in self.problema['importaciones'][ingrediente][p][o].keys() for i in self.problema['importaciones'][ingrediente][p][o][e].keys()])
                
                ii += arp
                var_name = f'inv_{ingrediente}_{t}'
                var = pu.LpVariable(name=var_name, lowBound=0, cat=pu.LpInteger)
                var.setInitialValue(ii)
                self.inventario_puerto[ingrediente][t] = var

    def __gen_rest_balance_planta(self):
        
        for planta in tqdm(self.problema["plantas"]):
            for ingrediente in self.problema["plantas"][planta]['ingredientes'].keys():
                for periodo in range(len(self.problema['fechas'])):
                    # I = It-1 + llegadas_programadas + llegadas_puerto - ejecusion_consumo
                    rest_name = f'balance_planta_{planta}_{ingrediente}_{periodo}'
                    I = self.inventario_planta[planta][ingrediente][periodo]
                    
                    llegada_planeada = self.problema["plantas"][planta]['ingredientes'][ingrediente]['llegada_planeada'][periodo]
                    ejecucion = self.ejecucion_consumo[planta][ingrediente][periodo]
                    
                   
                    if ingrediente in self.recibo_planta.keys():
                        if periodo in self.recibo_planta[ingrediente][planta].keys():
                            llegada_planta = self.recibo_planta[ingrediente][planta][periodo]
                        else:
                            llegada_planta = 0
                    else:
                        llegada_planta = 0

                    if periodo == 0:
                        Iant = Iant = self.problema["plantas"][planta]['ingredientes'][ingrediente]['inventario_inicial']
                    else:

                        periodo_anterior = periodo-1

                        Iant = self.inventario_planta[planta][ingrediente][periodo_anterior]

                    rest = (I == Iant + llegada_planeada + self.problema['capacidad_camion']*llegada_planta - ejecucion, rest_name)
                    self.balance_masa_planta.append(rest)

    def __gen_rest_balance_puerto(self):
        
        for ingrediente in self.problema['importaciones'].keys():
            for periodo in range(len(self.problema['fechas'])):
                # I = It-1 + llegadas_programadas - despachos_planta
                I = self.inventario_puerto[ingrediente][periodo]


                
                if periodo == 0:
                    Iant = sum([int(self.problema['importaciones'][ingrediente][p][o][e][i]['inventario_inicial']/self.problema['capacidad_camion']) for p in self.problema['importaciones'][ingrediente].keys() for o in self.problema['importaciones'][ingrediente][p].keys() for e in self.problema['importaciones'][ingrediente][p][o].keys() for i in self.problema['importaciones'][ingrediente][p][o][e].keys()])
                else:
                    periodo_ant = periodo-1
                    Iant = self.inventario_puerto[ingrediente][periodo_ant]

                llegada_programada = sum([int(self.problema['importaciones'][ingrediente][p][o][e][i]['llegadas'][periodo]/self.problema['capacidad_camion']) for p in self.problema['importaciones'][ingrediente].keys() for o in self.problema['importaciones'][ingrediente][p].keys() for e in self.problema['importaciones'][ingrediente][p][o].keys() for i in self.problema['importaciones'][ingrediente][p][o][e].keys()])


                despacho_list = list()

                for planta in self.despachos_planta[ingrediente].keys():
                    if periodo in self.despachos_planta[ingrediente][planta].keys():
                        despacho_list.append(self.despachos_planta[ingrediente][planta][periodo])

                rest_name = f'balance_puerto_{ingrediente}_{periodo}'
                rest = (I == Iant + llegada_programada -
                        pu.lpSum(despacho_list), rest_name)

                self.balance_masa_puerto.append(rest)

    def __gen_rest_recepcion_planta(self):

        for periodo in range(len(self.problema['fechas'])):
            for ingrediente in self.recibo_planta.keys():
                for planta in self.recibo_planta[ingrediente].keys():
                
                    tiempo_proceso = self.problema['plantas'][planta]['ingredientes'][indrediente]['tiempo_proceso']
                    var = self.recibo_planta[ingrediente][planta][periodo]
                    recibo_a_planta = [ tiempo_proceso * var  for ingrediente in self.problema['importaciones'].keys() if periodo in self.recibo_planta[ingrediente][planta].keys()]
                
                
                if len(recibo_a_planta)>0:
                    rest_name = f'recepcion_{planta}_{periodo}'
                    rest = (pu.lpSum(recibo_a_planta) <= self.problema.tiempo_disponible[planta], rest_name)
                    self.rest_recepcion_planta.append(rest)

    def __gen_fob_ejecucion_consumo(self):
        for planta in self.ejecucion_consumo.keys():
            for ingrediente in self.ejecucion_consumo[planta].keys():
                for periodo in range(len(self.problema['fechas'])):
                    self.fobj_ejecucion_consumo.append(self.ejecucion_consumo[planta][ingrediente][periodo])

    def solve(self, t_limit_minutes=15):
        # Cantidad CPU habilitadas para trabajar
        cpu_count = max(1, os.cpu_count()-1)

        solucionador = pu.LpProblem(name='Bios_Solver_fase_1', sense=pu.LpMaximize)

        # Agregando funcion objetivo
        solucionador += pu.lpSum(self.fobj_ejecucion_consumo)

        # Agregando balance de masa puerto
        for rest in self.balance_masa_puerto:
            solucionador += rest

        # Agregando balance ce masa en planta
        for rest in self.balance_masa_planta:
            solucionador += rest

        # Agregando restriccion de recepcion en planta
        for rest in self.rest_recepcion_planta:
            solucionador += rest

        print('cpu count', cpu_count)
        print('ejecutando ', len(self.problema['fechas']), 'periodos')
        print(f'ejecutando por {t_limit_minutes} minutos')

        engine_cbc = pu.PULP_CBC_CMD(
            timeLimit=60*t_limit_minutes,            
            gapRel=0.05,
            warmStart=False,
            threads=cpu_count)

        engine_glpk = pu.GLPK_CMD(
            mip=True,
            timeLimit=60*t_limit_minutes, 
            msg=True,
            keepFiles=True,
            path=r"C:\glpk-4.65\w64\glpsol.exe",
        )

        solucionador.writeLP('model.lp')

        solucionador.solve(solver=engine_glpk)

        pu.LpStatus[solucionador.status]

    def get_reporte_despachos(self)->list:
        reporte_despachos = list()
        for ingrediente in self.despachos_planta.keys():
            for planta in self.despachos_planta[ingrediente].keys():
                for periodo in self.despachos_planta[ingrediente][planta].keys():
                    valor = self.despachos_planta[ingrediente][planta][periodo].varValue
                    tiempo_proceso = self.problema['plantas'][planta]['ingredientes'][ingrediente]['tiempo_proceso']
                    dato = {
                        'variable': 'despacho a planta',
                        'ingrediente': ingrediente,
                        'planta': planta,
                        'periodo': periodo,
                        'valor': valor,
                        'tiempo_recepcion': valor*tiempo_proceso
                    }
                    reporte_despachos.append(dato)

        return reporte_despachos
      
    def get_reporte_inventario_puerto(self)-> list:

        reporte_inventario_puerto = list()
        for ingrediente in self.inventario_puerto.keys():
            for periodo in self.inventario_puerto[ingrediente].keys():
                dato = {
                    'variable': 'inventario en puerto',
                    'ingrediente': ingrediente,
                    'periodo': periodo,
                    'valor': self.inventario_puerto[ingrediente][periodo].varValue
                }
                reporte_inventario_puerto.append(dato)

        return reporte_inventario_puerto
       
    def get_reporte_inventario_planta(self)->list:
        reporte_inventario_planta = list()
        for planta in self.inventario_planta.keys():
            for ingrediente in self.inventario_planta[planta].keys():
                for periodo in self.inventario_planta[planta][ingrediente]:
                    dato = {
                        'variable': 'inventario en planta',
                        'planta': planta,
                        'ingrediente': ingrediente,
                        'periodo': periodo,
                        'valor': self.inventario_planta[planta][ingrediente][periodo].varValue,
                        'capacidad': self.problema['plantas'][planta]['ingredientes'][ingrediente]['capacidad'],
                        'consumo': self.problema['plantas'][planta]['ingredientes'][ingrediente]['consumo'][periodo],
                        #'objetivo':self.problema.objetivo_inventario[planta][ingrediente]
                    }
                    reporte_inventario_planta.append(dato)