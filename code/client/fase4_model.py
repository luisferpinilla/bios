
class Fase4Model():

    def __init__(self, problema:dict) -> None:
        self.problema = problema
        
        self.periodos = self.problema['fechas']
        self.plnatas = list(self.problema['plantas'].keys())
        self.ingredientes = list(self.problema['importaciones'].keys())
        
        self.Xipt = dict()
        self.Cipt = dict()
        self.Tipt = dict()

         
    def _generar_modelo(self):
        
        for i in self.ingredientes:
            
            
            
        

    def _generar_variables_inventario(self):
        pass

    def _generar_restriccion_despaacho(self):
        pass
    def _generar_funcion_objetivo(self):
        pass

    def solve(self):
        pass

# Xipt : Cantidad de camiones que se despachan desde la importacion i hacia la planta p durante el periodo t
# Cipt : Costo de enviar un camion desde la importacion i hacia la planta p durante el periodo t
# TIpt : Cantidad de ingrediente que se despachará a la planta p durante el periodo t
# Iit  : Inventario de producto en la importacion i al final de t
# Ait  : Cantidad de producto en kilogramos que esta llegando a la importacion i durante el periodo t
# Ai   : Inventario inicial de la importacion i

# Funcion objetivo
# Min Sum(i,p,t){Cipt*Xipt}
# Sujeto a:
# Sum(i,p,t){Xipt} == TIpt



