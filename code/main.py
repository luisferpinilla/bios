from dotenv import load_dotenv
import os
import json
import logging

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s: %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')

load_dotenv()

input_file = file = os.getenv("bios_input_file")
working_dir = os.getenv("working_dir")
os.chdir(working_dir)

print(f"cargando el archivo \"{input_file}\"")

from client.loader import Loader
loader = Loader(input_file)
loader.load_data()
# problema = loader.problema

# loader.problema = problema
loader.gen_solucion_fase_01()
loader.gen_solucion_fase_02()
loader.save()
loader.save_reports()


'''
from solver.math_models.reducir_importaciones import reducir_importaciones
problema = reducir_importaciones(problema)

# os.chdir('C:\\Users\\luisf\\Documents\\source\\bios\\code')

from solver.math_models.minimizar_costo_total import MinCostoTotal
model_02 = MinCostoTotal(problema)
model_02.model.writeLP('model.lp')
model_02.model.writeMPS('model.mps')
model_02.solve()

model_02.gen_reports()

problema = model_02.problema




# Leer resultado
with open(input_file.replace('.xlsm', '.json'), 'r') as file:
    problema = json.load(file)
    

for planta in problema['plantas'].keys():
    for ingrediente in problema['plantas'][planta]['ingredientes'].keys():
        for t in range(len(problema['fechas'])):
            # if problema['plantas'][planta]['ingredientes'][ingrediente]['backorder'][t]>0:
            print(planta, ingrediente, t, 
                      "inventario:", problema['plantas'][planta]['ingredientes'][ingrediente]['inventario'][t],  
                      "backorder:", problema['plantas'][planta]['ingredientes'][ingrediente]['backorder'][t],
                      "consumo:", problema['plantas'][planta]['ingredientes'][ingrediente]['consumo'][t])


with pd.ExcelWriter(path='despachos.xlsx') as writer:
    despachos_df.to_excel(writer, sheet_name='despachos', index=False)
    puertos_df.to_excel(writer, sheet_name='puertos', index=False)
    plantas_df.to_excel(writer, sheet_name='plantas', index=False)

# fechas = loader.fechas
# cap_camion = loader.cap_camion
'''
                    
            