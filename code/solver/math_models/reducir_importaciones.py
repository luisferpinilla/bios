import numpy as np



    
def reducir_importaciones(problema:dict):
        
    importaciones = problema['importaciones'].copy()

    impo_reducidas = dict()

    for ingrediente in importaciones.keys():
        inventario_inicial = 0
        llegadas = [0]*len(problema['fechas'])
        
        impo_reducidas[ingrediente] = {"puerto":{"operador":{"empresa":{"importacion":dict()}}}}
        
        for puerto in importaciones[ingrediente].keys():
            for operador in importaciones[ingrediente][puerto].keys():
                for empresa in importaciones[ingrediente][puerto][operador].keys():
                    for impo in importaciones[ingrediente][puerto][operador][empresa].keys():
                        # Inventario inicial
                        inventario_impo = int(importaciones[ingrediente][puerto][operador][empresa][impo]['inventario_inicial'] / problema['capacidad_camion'])*problema['capacidad_camion']
                        if inventario_impo > 0:
                            inventario_inicial += inventario_impo
                        
                        
        for t in range(len(problema['fechas'])):   
            llegada_impo = 0
            for puerto in importaciones[ingrediente].keys():
                for operador in importaciones[ingrediente][puerto].keys():
                    for empresa in importaciones[ingrediente][puerto][operador].keys():
                        for impo in importaciones[ingrediente][puerto][operador][empresa].keys():
                        
                            llegada_impo += int(importaciones[ingrediente][puerto][operador][empresa][impo]['llegadas'][t] / problema['capacidad_camion'])*problema['capacidad_camion']  
                            llegadas[t] += llegada_impo
                            
        impo_reducidas[ingrediente]["puerto"]["operador"]["empresa"]["importacion"]["inventario_inicial"] = inventario_inicial                  
        impo_reducidas[ingrediente]["puerto"]["operador"]["empresa"]["importacion"]["llegadas"] = llegadas
        impo_reducidas[ingrediente]["puerto"]["operador"]["empresa"]["importacion"]["costo_despacho_camion"] = [1000000]*len(problema['fechas'])
        
        inventario = inventario_inicial
        impo_reducidas[ingrediente]["puerto"]["operador"]["empresa"]["importacion"]["inventario"] = list()
        for planta in problema['plantas'].keys():
            if ingrediente in problema['plantas'][planta]['ingredientes'].keys():
                max_ingreso_tiempo = int(problema['plantas'][planta]['tiempo_disponible']/problema['plantas'][planta]['ingredientes'][ingrediente]['tiempo_proceso'])
                max_ingreso_cap_alm = int(problema['plantas'][planta]['ingredientes'][ingrediente]['capacidad']/problema['capacidad_camion'])
                   
                impo_reducidas[ingrediente]["puerto"]["operador"]["empresa"]["importacion"]["despachos"] = dict() 
                impo_reducidas[ingrediente]["puerto"]["operador"]["empresa"]["importacion"]["despachos"][planta] = dict()                   
                impo_reducidas[ingrediente]["puerto"]["operador"]["empresa"]["importacion"]["despachos"][planta]['minimo'] = [int(x) for x in list(np.zeros(len(problema['fechas'])))]
                impo_reducidas[ingrediente]["puerto"]["operador"]["empresa"]["importacion"]["despachos"][planta]['safety_stock'] = [int(x) for x in list(np.zeros(len(problema['fechas'])))]
                impo_reducidas[ingrediente]["puerto"]["operador"]["empresa"]["importacion"]["despachos"][planta]['target'] = [int(x) for x in list(np.zeros(len(problema['fechas'])))]
                impo_reducidas[ingrediente]["puerto"]["operador"]["empresa"]["importacion"]["despachos"][planta]['maximo'] = min(max_ingreso_tiempo,max_ingreso_tiempo,max_ingreso_cap_alm)
            
       
        for t in range(len(problema['fechas'])):
            llegada = impo_reducidas[ingrediente]["puerto"]["operador"]["empresa"]["importacion"]["llegadas"][t]
            inventario += llegada
            impo_reducidas[ingrediente]["puerto"]["operador"]["empresa"]["importacion"]["inventario"].append(inventario)
    

    
    
    
    problema_reducido = problema.copy()

    problema_reducido['importaciones'] = impo_reducidas
    
    return problema_reducido
