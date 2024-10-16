import pulp as pu
import pandas as pd

class Fase4Model():

    def __init__(self, problema:dict) -> None:
        self.problema = problema
        
        self.periodos = self.problema['fechas']
        self.plantas = list(self.problema['plantas'].keys())
        self.ingredientes = list(self.problema['importaciones'].keys())
        
        self.M_set = None
        self.I_set = None
        self.P_set = None
        self.T_set = None
        self.Xipt = None
        self.Cipt = None
        self.Tipt = None
        self.Iit  = None
        self.Ait  = None
        self.Ai   = None
        
        self._generar_parametros_modelo()
        self._resolver_problema()
        self._generar_reporte_optimizacion()
        self._generar_reporte_fase4()
 
         
    def _generar_parametros_modelo(self):
        
        importaciones = self.problema['importaciones']
        fechas = self.problema['fechas']
        
        M_set = list()
        I_set = list()
        P_set = list()
        T_set = list(range(len(fechas)))     
        Xipt = dict() # Cantidad de camiones que se despachan desde la importacion i hacia la planta p durante el periodo t
        Cipt = dict() # Costo de enviar un camion desde la importacion i hacia la planta p durante el periodo t
        TIpt = dict() # Cantidad de camiones que se despacharán a la planta p durante el periodo t
        Iit  = dict() # Inventario de producto en la importacion i al final de t
        Ait  = dict() # Cantidad de producto en kilogramos que esta llegando a la importacion i durante el periodo t
        Ai   = dict() # Inventario inicial de la importacion i
        
        for ingrediente in importaciones.keys():
            TIpt[ingrediente] = dict()
            M_set.append(ingrediente)
            for puerto in importaciones[ingrediente].keys():
                for operador in importaciones[ingrediente][puerto].keys():
                    for empresa in importaciones[ingrediente][puerto][operador].keys():
                        for importacion in importaciones[ingrediente][puerto][operador][empresa].keys():
                            
                            impo_obj = importaciones[ingrediente][puerto][operador][empresa][importacion]
                            impo_name = f"{ingrediente}_{puerto}_{operador}_{empresa}_{importacion}" 
                            I_set.append(impo_name)
                            
                            # Variable de inventario puerto
                            Iit[impo_name] = dict()
                            Ait[impo_name] = dict()
                            
                            # inventario inicial puerto
                            Ai[impo_name] = impo_obj['inventario_inicial'] 
                            
                            
                            for t in range(len(fechas)):
                                # Generar variable Iit
                                inventario_puerto_var_name = f"{impo_name}_{t}"
                                inventario_puerto_var = pu.LpVariable(name=inventario_puerto_var_name, lowBound=0, cat=pu.LpContinuous)
                                Iit[impo_name][t] = inventario_puerto_var  
                                
                                # Llegadas de inventario a puerto
                                Ait[impo_name][t] = impo_obj['llegadas'][t]
                                
                            
                            Xipt[impo_name] = dict()
                            Cipt[impo_name] = dict()
                            
                            for planta in impo_obj['despachos']:
                                
                                if not planta in P_set:
                                    P_set.append(planta)
                                
                                TIpt[ingrediente][planta] = dict()
                                
                                if len(impo_obj['despachos'][planta]):
                                
                                    Xipt[impo_name][planta] = dict() 
                                    Cipt[impo_name][planta] = dict()
                                    
                                    for t in range(len(fechas)):
                                        
                                        if not t in TIpt[ingrediente][planta].keys():
                                            # Completar parametro Tipt    
                                            TIpt[ingrediente][planta][t] = {'minimo':0, 'safety_stock':0, 'target':0}
                                            # Llenar el valor del costo de despacho
                                            Cipt[impo_name][planta][t] = impo_obj['costo_despacho_camion'][planta][t]
                                            
                                            # Llenar la cantidad de camiones despachados haacia la planta
                                            TIpt[ingrediente][planta][t]['minimo'] += impo_obj['despachos'][planta]['minimo'][t]
                                            TIpt[ingrediente][planta][t]['safety_stock'] += impo_obj['despachos'][planta]['safety_stock'][t]
                                            TIpt[ingrediente][planta][t]['target'] += impo_obj['despachos'][planta]['target'][t] 
                                            
                                            
                                            # Generar variable Xipt
                                            despacho_var_name = f"_{impo_name}_{planta}_{t}"
                                            despacho_var = pu.LpVariable(name=despacho_var_name, lowBound=0, cat=pu.LpInteger)
                                            Xipt[impo_name][planta][t] = despacho_var
                                            
                                            
        self.M_set = M_set
        self.I_set = I_set
        self.P_set = P_set
        self.T_set = T_set
        self.Xipt = Xipt
        self.Cipt = Cipt
        self.TIpt = TIpt
        self.Iit = Iit
        self.Ait = Ait
        self.Ai = Ai
 

    def _resolver_problema(self):
        
        # Xipt : Cantidad de camiones que se despachan desde la importacion i hacia la planta p durante el periodo t
        # Cipt : Costo de enviar un camion desde la importacion i hacia la planta p durante el periodo t
        # TIpt : Cantidad de camiones que se despacharán a la planta p durante el periodo t
        # Iit  : Inventario de producto en la importacion i al final de t
        # Ait  : Cantidad de producto en kilogramos que esta llegando a la importacion i durante el periodo t
        # Ai   : Inventario inicial de la importacion i

        # Funcion objetivo
        # Min Sum(i,p,t){Cipt*Xipt}
        # Sujeto a:
        # Sum(i,p,t){Xipt} == TIpt


        model = pu.LpProblem("Bios", sense=pu.LpMinimize)
        
        cap_camion = self.problema['capacidad_camion']
        
        # Funcion objetivo        
        fobj = [self.Cipt[i][p][t]*self.Xipt[i][p][t] for i in self.I_set for p in self.P_set for t in self.T_set if p in self.Xipt[i].keys()]

        # Restriccion Balance inventario
        balance_inv = list()
        
        for i in self.I_set:
            for t in self.T_set:
                rest_name = f"balinv_{i}_{t}"
                
                if t >0:                
                    rest = (self.Iit[i][t] ==  self.Iit[i][t-1] + self.Ait[i][t] - cap_camion*pu.lpSum([self.Xipt[i][p][t] for p in self.Xipt[i].keys()]), rest_name)
                else:
                    rest = (self.Iit[i][t] ==  self.Ai[i] + self.Ait[i][t] - cap_camion*pu.lpSum([self.Xipt[i][p][t] for p in self.Xipt[i].keys()]), rest_name)
        
                balance_inv.append(rest)        
        
        # Cumplir con el despacho total
        despacho_total = list()
        for p in self.P_set:
            for t in self.T_set[1:-2:]:
                for m in self.M_set:
                    rest_name = f"despacho_{p}_{m}_{t}"

                    sum_despachos = [self.Xipt[i][p][t] for i in self.I_set if m in i and p in self.Xipt[i].keys() and t in self.TIpt[m][p].keys()]
                    
                    if len(sum_despachos) > 0 and m in self.TIpt.keys() and p in self.TIpt[m].keys() and sum(self.TIpt[m][p][t].values())>0:
                        rest = (pu.lpSum(sum_despachos) == sum(self.TIpt[m][p][t].values()), rest_name)
                        
                        despacho_total.append(rest)
                        
                        
        model += pu.lpSum(fobj)

        for rest in balance_inv:
            model += rest  

        for rest in despacho_total:
            model += rest  

        model.solve()                     


    def _generar_reporte_optimizacion(self)->pd.DataFrame:

        df = list()
        for i in self.Xipt.keys():
            for p in self.Xipt[i].keys():
                for t in self.Xipt[i][p].keys():
                    if self.Xipt[i][p][t].varValue>0:
                        campos = i.split('_')
                        dato = {
                            "ingrediente" : campos[0],
                            "puerto" : campos[1],
                            "operador" : campos[2],
                            "empresa" : campos[3],
                            "importacion" : campos[4],
                            "planta" : p,
                            "periodo": t,
                            "camiones": int(self.Xipt[i][p][t].varValue),
                            "costo_camion": self.Cipt[i][p][t]
                        }
                        df.append(dato)

        self.reporte_df = pd.DataFrame(df).sort_values(['planta', 'ingrediente', 'periodo', 'costo_camion'], ascending=[True, True, True, False])
        
       
    def _generar_reporte_fase4(self):
        
        df = self.reporte_df.copy()
        TIpt = self.TIpt.copy()
        
        minimo_list = list()
        safety_list = list()
        target_list = list()
            
        for i in df.index:
            
            ingrediente = df.loc[i]['ingrediente']
            planta = df.loc[i]['planta']
            t = df.loc[i]['periodo']
            camiones = df.loc[i]['camiones']
            
            minimo = 0
            safety = 0
            target = 0
            
            while camiones >0:
                
                if TIpt[ingrediente][planta][t]['minimo'] > 0:
                    
                    TIpt[ingrediente][planta][t]['minimo'] -=1
                    minimo +=1
                    
                elif TIpt[ingrediente][planta][t]['safety_stock'] > 0:
                    
                    TIpt[ingrediente][planta][t]['safety_stock'] -=1
                    safety += 1
                
                elif TIpt[ingrediente][planta][t]['target'] > 0:
                    
                    TIpt[ingrediente][planta][t]['target'] -=1
                    target+=1
                    
                camiones -=1
                    
            minimo_list.append(minimo)
            safety_list.append(safety)
            target_list.append(target)
        
        df['minimo'] = minimo_list
        df['safety_stock'] = safety_list
        df['target'] = target_list
        
        self.reporte_df = df.copy()
        
        
        
        
                
                
        
        







































