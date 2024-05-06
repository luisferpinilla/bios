
import pandas as pd
import os
import pulp as pu
from utils.modelo import generar_modelo
from utils.modelo import generar_funcion_objetivo
from utils.modelo import generar_res_balance_masa_cargas
from utils.modelo import generar_res_balance_masa_plantas
from utils.modelo import generar_res_objetivo_fin_mes
from utils.modelo import generar_res_capacidad_recepcion_plantas
from utils.reporte import generar_reporte
from utils.reporte import guardar_reporte


def resolver_modelo(variables: dict, periodos: list, cargas_df: pd.DataFrame, plantas_df: pd.DataFrame):

    # Cantidad CPU habilitadas para trabajar
    cpu_count = max(1, os.cpu_count()-1)

    # Gap en millones de pesos
    gap = 5000000
    # Tiempo máximo de detencion en minutos
    t_limit_minutes = 20

    # Armar el modelo
    func_obj = generar_funcion_objetivo(
        variables, periodos, cargas_df, plantas_df)

    rest_balance_puerto = generar_res_balance_masa_cargas(
        variables, periodos, cargas_df)

    rest_balance_planta = generar_res_balance_masa_plantas(
        variables, periodos, plantas_df)

    rest_capacidad_recepcion = generar_res_capacidad_recepcion_plantas(
        variables, plantas_df, periodos)

    rest_objetivo_inventario_025 = generar_res_objetivo_fin_mes(plantas_df,variables, periodos, 0.25)
    rest_objetivo_inventario_050 = generar_res_objetivo_fin_mes(plantas_df,variables, periodos, 0.50)
    rest_objetivo_inventario_075 = generar_res_objetivo_fin_mes(plantas_df,variables, periodos, 0.75)
    rest_objetivo_inventario_100 = generar_res_objetivo_fin_mes(plantas_df,variables, periodos, 1.00)

    problema = pu.LpProblem(name='Bios_Solver', sense=pu.LpMinimize)

    # Agregando funcion objetivo
    problema += pu.lpSum(func_obj)

    # Agregando balance de masa puerto
    for rest in rest_balance_puerto:
        problema += rest

    # Agregando balande ce masa en planta
    for rest in rest_balance_planta:
        problema += rest

    print('Ejecutando modelo fase 1')
    print('cpu count', cpu_count)
    print('tiempo limite', t_limit_minutes, 'minutos')
    print('ejecutando ', len(periodos), 'periodos')
    print('GAP tolerable', gap, 'millones de pesos')

    engine = pu.PULP_CBC_CMD(
        timeLimit=60*t_limit_minutes,
        gapAbs=gap,
        gapRel=0.05,
        warmStart=True,
        cuts=True,
        presolve=True,
        threads=cpu_count)

    problema.solve(solver=engine)

    print('Ejecutando modelo fase 2')
    # Agregando restriccion de objetivo de inventario
    for rest in rest_objetivo_inventario_100:
        problema += rest

    print('cpu count', cpu_count)
    print('tiempo limite', t_limit_minutes, 'minutos')
    print('ejecutando ', len(periodos), 'periodos')
    print('GAP tolerable', gap, 'millones de pesos')

    engine = pu.PULP_CBC_CMD(
        timeLimit=60*20,
        gapAbs=gap,
        gapRel=0.05,
        warmStart=True,
        cuts=True,
        presolve=True,
        threads=cpu_count)

    problema.solve(solver=engine)

    # Agregando restriccion de recepcion
    # for rest in rest_capacidad_recepcion:
    #    problema += rest


if __name__ == '__main__':

    bios_input_file = 'data/0_model_template_2204.xlsm'

    bios_ouput_file = bios_input_file.replace('.xlsm', '_model.xlsx')

    plantas_df, cargas_df, estadisticas, periodos, variables = generar_modelo(
        bios_input_file)

    resolver_modelo(variables, periodos, cargas_df, plantas_df)

    plantas_df, cargas_df = generar_reporte(plantas_df, cargas_df, variables)

    guardar_reporte(bios_ouput_file, plantas_df, cargas_df, estadisticas)

    print('finalizado')
