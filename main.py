from dotenv import load_dotenv
import os
import logging
import time

inicio = time.time()
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s: %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')

load_dotenv()

input_file = file = "/Users/luispinilla/Documents/source_code/bios/data/0_model_template_1608.xlsm" # os.getenv("bios_input_file")
working_dir = os.getenv("working_dir")

# print(os.getcwd())
os.chdir(working_dir)

print(f"cargando el archivo \"{input_file}\"")

from src.client.loader import Loader 
loader = Loader(input_file)
loader.load_data()


loader.gen_solucion_fase_01()
loader.gen_solucion_fase_02()
loader.gen_solucion_fase_03()
loader.gen_solucion_fase_04()
plantas_df, puertos_df, despachos_df = loader.save_reports()





fin = time.time()
print('tiempo total',fin-inicio, 'segundos')

