import pandas as pd
import numpy as np


class AsignadorCapacidad():

    def __init__(self, file: str) -> None:

        self.file = file

        self.ingredientes_list = self._cargar_ingredientes()
        self.plantas_list = self._cargar_plantas()
        self.consumo_df = self._cargar_consumo()
        self.safety_stock_df = self._cargar_safety_stock()
        self.unidades_df = self._cargar_unidades_almacenamiento()
        self.inventario_df = self._cargar_inventario_actual()
        self.capacidad_actual_df = None
        self.estadisticas_df = None

        self.calcular()

    def _cargar_ingredientes(self):

        ingredientes_df = pd.read_excel(
            io=self.file, sheet_name='ingredientes')
        ingredientes_list = list(ingredientes_df['nombre'].unique())
        return ingredientes_list

    def _cargar_plantas(self):
        plantas_df = pd.read_excel(io=self.file, sheet_name='plantas')
        plantas_list = list(plantas_df['planta'].unique())
        return plantas_list

    def _cargar_consumo(self):
        # Obtener consumo
        consumo_df = pd.read_excel(
            io=self.file, sheet_name='consumo_proyectado')
        indexvar = ['planta', 'ingrediente']
        consumo_columns = list(consumo_df.drop(columns=indexvar).columns)
        consumo_df['promedio'] = consumo_df[consumo_columns].apply(
            np.mean, axis=1)
        consumo_df = consumo_df[indexvar + ['promedio']]
        return consumo_df

    def _cargar_safety_stock(self):
        # Obtener minumo
        safety_stock_df = pd.read_excel(
            io=self.file, sheet_name='safety_stock')
        return safety_stock_df

    def _cargar_unidades_almacenamiento(self):
        # Leer unidades
        unidades_df = pd.read_excel(
            io=self.file,
            sheet_name='unidades_almacenamiento')

        unidades_df['ingrediente_actual'] = unidades_df.apply(
            lambda x: x['ingrediente_actual'] if x['cantidad_actual'] > 0 else '', axis=1)

        return unidades_df

    def _cargar_inventario_actual(self):
        # Obtener inventario actual
        inventario_df = pd.read_excel(io=self.file,
                                      sheet_name='unidades_almacenamiento')
        inventario_df = inventario_df[inventario_df['ingrediente_actual'].isin(
            self.ingredientes_list)].copy()

        inventario_df = inventario_df.groupby(['planta', 'ingrediente_actual'])[
            ['cantidad_actual']].sum().reset_index()

        inventario_df.rename(columns={'ingrediente_actual': 'ingrediente',
                                      'cantidad_actual': 'inventario'},
                             inplace=True)
        return inventario_df

    def _calcular_capacidad_actual(self):
        # Calcular capacidad actual

        self.capacidad_actual_df = self.unidades_df[self.unidades_df['ingrediente_actual'].isin(
            self.ingredientes_list)].copy()

        self.capacidad_actual_df['capacidad'] = self.capacidad_actual_df.apply(
            lambda x: x[x['ingrediente_actual']], axis=1)

        self.capacidad_actual_df = self.capacidad_actual_df.groupby(['planta', 'ingrediente_actual'])[
            ['capacidad']].sum().reset_index()

        self.capacidad_actual_df.rename(
            columns={'ingrediente_actual': 'ingrediente'}, inplace=True)

    def _calcular_estadisticas(self):
        # Generar la tabla de resultados
        solucion_dict = dict()
        solucion_dict['planta'] = list()
        solucion_dict['ingrediente'] = list()

        for planta in self.plantas_list:
            for ingrediente in self.ingredientes_list:
                solucion_dict['planta'].append(planta)
                solucion_dict['ingrediente'].append(ingrediente)

        solucion_df = pd.DataFrame(solucion_dict)

        # Agregar consumo a solucion_df
        solucion_df = pd.merge(left=solucion_df,
                               right=self.consumo_df,
                               left_on=['planta', 'ingrediente'],
                               right_on=['planta', 'ingrediente'],
                               how='left')
        # Agregar las columnas de dias ss y capaacidad de recepcion
        solucion_df = pd.merge(left=solucion_df,
                               right=self.safety_stock_df,
                               left_on=['planta', 'ingrediente'],
                               right_on=['planta', 'ingrediente'],
                               how='left')

        # Agregar las columnas de inventario actual
        solucion_df = pd.merge(left=solucion_df,
                               right=self.inventario_df,
                               left_on=['planta', 'ingrediente'],
                               right_on=['planta', 'ingrediente'],
                               how='left')

        # Agregar las columnas de capacidad actual
        solucion_df = pd.merge(left=solucion_df,
                               right=self.capacidad_actual_df,
                               left_on=['planta', 'ingrediente'],
                               right_on=['planta', 'ingrediente'],
                               how='left').fillna(0.0)
        solucion_df.head()
        solucion_df['minimo'] = solucion_df['dias_ss']*solucion_df['promedio']
        solucion_df['capacidad_dias'] = solucion_df.apply(
            lambda x: x['capacidad']/x['promedio'] if x['promedio'] > 0 else 1000, axis=1)

        solucion_df.sort_values(by=['capacidad_dias', 'promedio'], ascending=[
                                True, False], inplace=True)

        solucion_df.reset_index(inplace=True)

        self.estadisticas_df = solucion_df

    def calcular(self):
        values = list(self.unidades_df['ingrediente_actual'])
        cantidades = list(self.unidades_df['cantidad_actual'])

        for i in self.unidades_df.index:
            if i in self.unidades_df[self.unidades_df['cantidad_actual'] <= 0].index:

                # Obtener información sobre lo que puede guardar la primera unidad vacia
                planta = self.unidades_df.loc[i]['planta']
                unidad = self.unidades_df.loc[i]['unidad_almacenamiento']
                posibles = [
                    x for x in self.ingredientes_list if self.unidades_df.loc[i][x] > 0]

                # Totalizar la capacidad actual
                self._calcular_capacidad_actual()

                # Calcular capacidad en dias
                self._calcular_estadisticas()

                # Obtener el ingrediente con menor cantidad de capacidad en días
                ingrediente_a_asignar = self.estadisticas_df[(self.estadisticas_df['planta'] == planta) & (
                    self.estadisticas_df['ingrediente'].isin(posibles))].iloc[0]['ingrediente']
                # print('trabajando con', planta, unidad, posibles, ingrediente_a_asignar)

                # Asignar la unidad vacia al ingrediente
                values[i] = ingrediente_a_asignar
                cantidades[i] = 1.0

                self.unidades_df['ingrediente_actual'] = values
                self.unidades_df['cantidad_actual'] = cantidades

    def obtener_unidades_almacenamiento(self):
        return self.unidades_df


if __name__ == '__main__':

    asignador = AsignadorCapacidad(file='model_template.xlsm')

    print(asignador.obtener_unidades_almacenamiento())
