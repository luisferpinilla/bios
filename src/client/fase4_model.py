import pulp as pu

class Fase4Model():

    def __init__(self, problema:dict) -> None:
        self.problema = problema
        
        self.periodos = self.problema['fechas']
        self.plantas = list(self.problema['plantas'].keys())
        self.ingredientes = list(self.problema['importaciones'].keys())
        
        self.Xipt = dict()
        self.Cipt = dict()
        self.Tipt = dict()
        self.Iit  = dict()
        self.Ait  = dict()
        self.Ai   = dict()
        
        self.rest_bal_inventario = dict()

         
    def _generar_parametros_modelo(self):
        
        importaciones = self.problema['importaciones']
        fechas = self.problema['fechas']
        
        self.Xipt = dict()
        self.Cipt = dict()
        self.Tipt = dict()
        self.Iit  = dict()
        self.Ait  = dict()
        self.Ai   = dict()
        
        for ingrediente in importaciones.keys():
            self.Tipt[ingrediente] = dict()
            for puerto in importaciones[ingrediente].keys():
                for operador in importaciones[ingrediente][puerto].keys():
                    for empresa in importaciones[ingrediente][puerto][operador].keys():
                        for importacion in importaciones[ingrediente][puerto][operador][empresa].keys():
                            
                            impo_obj = importaciones[ingrediente][puerto][operador][empresa][importacion]
                            impo_name = f"{ingrediente}_{puerto}_{operador}_{empresa}_{importacion}" 
                            print(impo_name)
                            
                            # Variable de inventario puerto
                            self.Iit[impo_name] = dict()
                            self.Ait[impo_name] = dict()
                            
                            # inventario inicial puerto
                            self.Ai[impo_name] = impo_obj['inventario_inicial'] 
                            
                            
                            for t in range(len(fechas)):
                                # Generar variable Iit
                                inventario_puerto_var_name = f"{impo_name}_{t}"
                                inventario_puerto_var = pu.LpVariable(name=inventario_puerto_var_name, lowBound=0, cat=pu.LpContinuous)
                                self.Iit[impo_name][t] = inventario_puerto_var  
                                
                                # Llegadas de inventario a puerto
                                self.Ait[impo_name][t] = impo_obj['llegadas'][t]
                                
                            
                            
                            
                            self.Xipt[impo_name] = dict()
                            self.Cipt[impo_name] = dict()
                            
                            for planta in impo_obj['despachos']:
                                
                                self.Tipt[ingrediente][planta] = dict()
                                
                                if len(impo_obj['despachos'][planta]):
                                
                                    self.Xipt[impo_name][planta] = dict() 
                                    self.Cipt[impo_name][planta] = dict()
                                    
                                    for t in range(len(fechas)):
                                        
                                        if not t in self.Tipt[ingrediente][planta].keys():
                                            # Completar parametro Tipt    
                                            self.Tipt[ingrediente][planta][t] = 0
                                            # Llenar el valor del costo de despacho
                                            self.Cipt[impo_name][planta][t] = impo_obj['costo_despacho_camion'][planta][t]
                                            
                                            # Llenar la cantidad de camiones despachados haacia la planta
                                            self.Tipt[ingrediente][planta][t] += impo_obj['despachos'][planta]['minimo'][t]
                                            self.Tipt[ingrediente][planta][t] += impo_obj['despachos'][planta]['safety_stock'][t]
                                            self.Tipt[ingrediente][planta][t] += impo_obj['despachos'][planta]['target'][t] 
                                            
                                            
                                            # Generar variable Xipt
                                            despacho_var_name = f"_{impo_name}_{planta}_{t}"
                                            despacho_var = pu.LpVariable(name=despacho_var_name, lowBound=0, cat=pu.LpInteger)
                                            self.Xipt[impo_name][planta][t] = despacho_var
                        

            


    def solve(self):
        self.model = pu.LpProblem("Bios", sense=pu.LpMinimize)

        

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

model = Fase4Model(problema)



