
import pandas as pd
import os
import pulp as pu
from utils.modelo import generar_modelo
from utils.modelo import resolver_modelo
from utils.reporte import generar_reporte
from utils.reporte import guardar_reporte


if __name__ == '__main__':

    bios_input_file = 'data/0_model_template_2204_reducido.xlsm'

    bios_ouput_file = bios_input_file.replace('.xlsm', '_model.xlsx')

    plantas_df, cargas_df, estadisticas, periodos, variables, validaciones = generar_modelo(
        bios_input_file)

    resolver_modelo(variables, periodos, cargas_df, plantas_df)

    plantas_df, cargas_df = generar_reporte(plantas_df, cargas_df, variables)

    guardar_reporte(bios_ouput_file, plantas_df, cargas_df, estadisticas)

    print('finalizado')
