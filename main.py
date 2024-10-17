import os
import logging
import time
import argparse
from datetime import datetime
import pandas as pd

def solve_model(input_file:str):
    
    inicio = time.time()
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s: %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')

    print(f"cargando el archivo \"{input_file}\"")

    from src.client.loader import Loader 
    loader = Loader(input_file)
    loader.load_data()


    loader.gen_solucion_fase_01()
    loader.gen_solucion_fase_02()
    loader.gen_solucion_fase_03()
    loader.gen_solucion_fase_04()
    plantas_df, puertos_df, despachos_df = loader.save_reports()

    output_file = input_file.replace(".xlsm", f"_{datetime.now().strftime("%Y-%m-%d_%HH%MM%SS")}.xlsx")

    with pd.ExcelWriter(output_file) as writer:
        plantas_df.to_excel(writer, sheet_name="Reporte_Plantas", index=False)
        puertos_df.to_excel(writer, sheet_name="Reporte_Puertos", index=False)
        despachos_df.to_excel(writer, sheet_name="Reporte_Despachos", index=False)

    fin = time.time()
    print('tiempo total',fin-inicio, 'segundos')




def main():
    logging.basicConfig(level=logging.DEBUG)
    parser = argparse.ArgumentParser(description="Procesar archivo de consumo proyectado.")
    parser.add_argument('file', 
                        type=str, 
                        help='Ruta del archivo de Excel a procesar.')

    # Parsear los argumentos de la línea de comandos
    args = parser.parse_args()

    # Crear una instancia de ConsumosProcessor y cargar los consumos
    solve_model(args.file)

if __name__ == "__main__":

    main()