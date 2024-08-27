import os
os.chdir('C:\\Users\\luisf\\Documents\\source\\bios\\code')


import pandas as pd
import logging

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s: %(message)s', 
                    datefmt='%m/%d/%Y %I:%M:%S %p')


input_file = file = "C:\\Users\\luisf\\Downloads\\0_model_template_1608.xlsm"

from client.loader import Loader
loader = Loader(input_file)


problema = loader.problema

# os.chdir('C:\\Users\\luisf\\Documents\\source\\bios\\code')

from solver.math_models.minimizar_costo_total import MinCostoTotal
model_02 = MinCostoTotal(problema)

model_02.solve()

for var in model_02.inv_planta_var['cienaga']['maiz']:
    print(var.varValue)




'''
with pd.ExcelWriter(path='despachos.xlsx') as writer:
    despachos_df.to_excel(writer, sheet_name='despachos', index=False)
    puertos_df.to_excel(writer, sheet_name='puertos', index=False)
    plantas_df.to_excel(writer, sheet_name='plantas', index=False)

# fechas = loader.fechas
# cap_camion = loader.cap_camion
'''