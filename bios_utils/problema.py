import pandas as pd
from bios_utils.loader import get_inventario_capacidad_planta
from bios_utils.loader import get_llegadas_programadas_planta
from bios_utils.loader import get_consumo_proyectado
from bios_utils.loader import get_tiempos_proceso
from bios_utils.loader import get_objetivo_inventario
from bios_utils.loader import get_costo_operacion_portuaria
from bios_utils.loader import get_transitos_a_puerto
from bios_utils.loader import get_inventario_puerto
from bios_utils.loader import get_inventario_puerto
from bios_utils.loader import get_costo_almaceniento_puerto
from bios_utils.loader import get_cargas_despachables
from bios_utils.loader import get_fletes
from bios_utils.loader import get_intercompany

class Problema():
    
    def __init__(self, bios_input_file, cap_carga_camion=34000) -> None:
        
        self.bios_input_file = bios_input_file
        self.cap_camion = cap_carga_camion

        self.__load_file()

        self.importaciones = self.__load_lista_importaciones()
        self.empresas = self.__load_empresas()
        self.plantas = self.__load_plantas()
        self.ingredientes = self.__load_ingredientes()
        self.periodos = self.__load_periodos()
        self.consumo_proyectado = self.__load_consumo_proyectado()
        self.llegadas_planeadas_planta = self.__load_llegadas_planeadas_planta()
        self.inventario_planta, self.capacidad_planta = self.__load_inventario_capacidad_planta()
        self.tiempo_disponible, self.tiempo_limpieza, self.tiempo_proceso = self.__load_tiempos_proceso()
        self.objetivo_inventario = self.__load_objetivo_inventario()
        self.inventario_inicial_puerto = self.__load_inventario_inicial_puerto()
        self.inventario_totalizado_inicial_puerto = self.__load_inventario_totalizado_inicial_puerto()
        self.llegadas_puerto = self.__load_llegadas_puerto()
        self.llegadas_totalizadas_puerto = self.__load_llegadas_totalizadas_a_puerto()
        self.costos_transporte = self.__load_costos_transporte()
        self.costo_almacenamiento = self.__load_costos_almacenamiento()
        

    def __load_file(self):

        # Plantas
        self.plantas_df = pd.read_excel(io=self.bios_input_file, sheet_name='plantas')

        # Inventarios y capacidad de almacenamiento en planta
        self.inventario_planta_df = get_inventario_capacidad_planta(
            bios_input_file=self.bios_input_file)

        # Transito a plantas
        self.llegadas_programadas_df = get_llegadas_programadas_planta(
            bios_input_file=self.bios_input_file)

        # Consumo Proyectado
        self.consumo_proyectado_df = get_consumo_proyectado(bios_input_file=self.bios_input_file)

        # Tiempos de Proceso
        self.tiempos_proceso_df = get_tiempos_proceso(bios_input_file=self.bios_input_file)

        # Objetivo de inventario
        self.objetivo_df = get_objetivo_inventario(bios_input_file=self.bios_input_file)

        # Costo de Operaciones portuarias
        self.costo_portuario_bodegaje_df, self.costo_portuario_directo_df = get_costo_operacion_portuaria(
            bios_input_file=self.bios_input_file)

        # Transitos a Puerto
        self.tto_puerto_df = get_transitos_a_puerto(bios_input_file=self.bios_input_file)

        # Inventarios en Puerto
        self.inventario_puerto_df = get_inventario_puerto(bios_input_file=self.bios_input_file)

        # Cargas despachables
        self.cargas_despachables_df = get_cargas_despachables(
            bios_input_file=self.bios_input_file)

        # Costos Almacenamiento Cargas
        self.costos_almacenamiento_df = get_costo_almaceniento_puerto(
            bios_input_file=self.bios_input_file)

        # Fletes
        self.fletes_df = get_fletes(bios_input_file=self.bios_input_file)

        # Intercompany
        self.intercompany_df = get_intercompany(bios_input_file=self.bios_input_file)

    def __load_costos_almacenamiento(self):
        df = self.costos_almacenamiento_df.set_index(['empresa', 'puerto', 'operador', 'ingrediente', 'importacion', 'fecha_corte'])

        costo_almacenamiento = dict()
        for i in self.importaciones:
            costo_almacenamiento[i] = dict()
            for periodo in self.periodos:
                impo_index = tuple(list(i) + [periodo])
                if impo_index in df.index:
                    costo = df.loc[impo_index]['valor_kg']
                else:
                    costo = 0.0

                if not periodo in costo_almacenamiento[i].keys():
                    costo_almacenamiento[i][periodo] = dict()
                costo_almacenamiento[i][periodo] = costo

        return costo_almacenamiento

    def __load_costos_transporte(self):
        columns = ['Empresa', 'Puerto', 'Operador', 'Ingrediente', 'Importacion', 'valor_kg']
        importaciones_df = self.cargas_despachables_df.groupby(columns)[[]].count().reset_index().copy()

        df = importaciones_df.rename(columns={'Empresa': 'Empresa_Origen'}).copy()

        # Cruzar con fechas de consumo
        df = pd.merge(left=df,right=pd.DataFrame(self.periodos).rename(columns={0: 'Fecha'}), how='cross')

        temp = self.fletes_df.copy()
        columns = ['puerto', 'operador', 'ingrediente']
        temp = temp.melt(id_vars=columns, value_vars=temp.drop(
            columns=columns).columns, var_name='Planta', value_name='flete_kg')
        temp['Empresa_Destino'] = temp['Planta'].map(self.empresas)
        temp['Flete_Camion'] = self.cap_camion*temp['flete_kg']
        temp.drop(columns=['flete_kg'], inplace=True)
        temp.rename(columns={'puerto': 'Puerto', 'operador': 'Operador','ingrediente': 'Ingrediente'}, inplace=True)
                
        df = pd.merge(left=df, right=temp,
              left_on=['Puerto', 'Operador', 'Ingrediente'],
              right_on=['Puerto', 'Operador', 'Ingrediente'],
              how='left')
        
        self.costo_portuario_directo_df = self.costo_portuario_directo_df.rename(columns={'operador': 'Operador',
                                                                        'puerto': 'Puerto',
                                                                        'ingrediente': 'Ingrediente',
                                                                        'valor_kg': 'Directo'})
        
        # cruzar transitos con operacion portuaria de despacho directo
        temp = pd.merge(left=self.transitos_a_puerto_df.reset_index().drop(columns=['Llegada', 'Camiones', 'valor_kg', 'Inventario']).rename(columns={'Empresa': 'Empresa_Origen'}),
                right=self.costo_portuario_directo_df,
                left_on=['Operador', 'Puerto', 'Ingrediente'],
                right_on=['Operador', 'Puerto', 'Ingrediente'],
                how='left')
        
        # temp['Fecha'] = temp['Fecha'].apply(lambda x: x.strftime("%Y-%m-%d"))
        temp['Directo'] = self.cap_camion*temp['Directo']

        # Anexar costos portuarios por despacho directo
        df = pd.merge(left=df,
                    right=temp,
                    left_on=['Empresa_Origen', 'Puerto', 'Operador',
                            'Ingrediente', 'Importacion', 'Fecha'],
                    right_on=['Empresa_Origen', 'Puerto', 'Operador',
                                'Ingrediente', 'Importacion', 'Fecha'],
                    how='left')
        
        df['Directo'] = df['Directo'].fillna(0)

        intercompany_df = self.intercompany_df.melt(id_vars='origen', 
                                                    value_vars=list(set(self.empresas.values())), var_name='Empresa_Destino', 
                                                    value_name='intercompany').rename(columns={'origen': 'Empresa_Origen'})
        
        # Intercompany
        df = pd.merge(left=df,
              right=intercompany_df,
              left_on=['Empresa_Origen', 'Empresa_Destino'],
              right_on=['Empresa_Origen', 'Empresa_Destino'],
              how='left') 

        # Calcular costo total despacho
        df['CostoTotalCamion'] = df['Flete_Camion'] + df['Directo'] + \
            (self.cap_camion*df['intercompany']*df['valor_kg'])  
        
        costo_transporte_df = df.copy()

        costo_transporte_df.set_index(keys=['Empresa_Origen', 'Puerto', 'Operador',
                              'Ingrediente', 'Importacion', 'Planta', 'Fecha'], inplace=True)
        
        costo_transporte = dict()
        for i in self.importaciones:
            costo_transporte[i] = dict()
            for planta in self.plantas:
                costo_transporte[i][planta] = dict()
                for periodo in self.periodos:
                    impo_index = tuple(list(i) + [planta, periodo])
                    if impo_index in costo_transporte_df.index:
                        costo = costo_transporte_df.loc[impo_index]['CostoTotalCamion']
                        costo_transporte[i][planta][periodo] = costo
        
        return costo_transporte

    def __load_inventario_inicial_puerto(self):

        inventario_inicial_puerto = dict()
        inventario_inicial_puerto_df = self.cargas_despachables_df[self.cargas_despachables_df['Inventario'] > 0].copy()
        inventario_inicial_puerto_df.set_index(keys=['Empresa', 'Puerto', 'Operador', 'Ingrediente', 'Importacion'], inplace=True)

        
        for i in self.importaciones:
            if i in inventario_inicial_puerto_df.index:
                cantidad = int(
                    inventario_inicial_puerto_df.loc[i]['Inventario'])
            else:
                cantidad = 0
            inventario_inicial_puerto[i] = cantidad

        return inventario_inicial_puerto

    def __load_lista_importaciones(self):
        importaciones = list()
        for i in range(self.cargas_despachables_df.shape[0]):
            inventario = int(self.cargas_despachables_df.iloc[i]['Inventario'])
            llegadas = int(self.cargas_despachables_df.iloc[i]['Llegada'])

            if inventario > self.cap_camion or llegadas > self.cap_camion:

                index = (self.cargas_despachables_df.iloc[i]['Empresa'],
                        self.cargas_despachables_df.iloc[i]['Puerto'],
                        self.cargas_despachables_df.iloc[i]['Operador'],
                        self.cargas_despachables_df.iloc[i]['Ingrediente'],
                        self.cargas_despachables_df.iloc[i]['Importacion'])

                importaciones.append(index)

        return list(set(importaciones))

    def __load_llegadas_puerto(self):
        
        self.transitos_a_puerto_df = self.cargas_despachables_df[self.cargas_despachables_df['Llegada'] > 0].copy()
        self.transitos_a_puerto_df.set_index(['Empresa', 'Puerto', 'Operador', 'Ingrediente', 'Importacion', 'Fecha'], inplace=True)

        llegadas_puerto = dict()

        for i in self.importaciones:
            llegadas_puerto[i] = dict()
            for periodo in self.periodos:
                i2 = tuple(list(i) + [periodo])

                if i2 in self.transitos_a_puerto_df.index:
                    cantidad_puerto = int(self.transitos_a_puerto_df.loc[i2]['Llegada'])
                else:
                    cantidad_puerto = 0
                llegadas_puerto[i][periodo] = cantidad_puerto

        return llegadas_puerto

    def __load_inventario_totalizado_inicial_puerto(self):
        # Transformar a camiones
        self.cargas_despachables_df['Camiones'] = self.cargas_despachables_df['Inventario'].apply(
            lambda x: int(x/self.cap_camion))
        df = self.cargas_despachables_df.groupby(['Ingrediente'])[
            ['Camiones']].sum()
        
        # Inicializar inventario inicial en puerto
        inventario_inicial_puerto = dict()
        for ingrediente in self.ingredientes:
            if ingrediente in df.index:
                cantidad = df.loc[ingrediente]['Camiones']
                inventario_inicial_puerto[ingrediente] = cantidad
            else:
                inventario_inicial_puerto[ingrediente] = 0

        return inventario_inicial_puerto

    def __load_llegadas_totalizadas_a_puerto(self):
        # Transitos programados
        self.tto_puerto_df['Camiones'] = self.tto_puerto_df['Llegada'].apply(
            lambda x: int(x/self.cap_camion))
        # Agrupar y totalizar por la cantidad de camiones
        df = self.tto_puerto_df.groupby(['Ingrediente', 'Fecha'])[
            ['Camiones']].sum()
        
        llegadas_puerto = dict()
        for ingrediente in self.ingredientes:
            llegadas_puerto[ingrediente] = dict()
            for periodo in self.periodos:
                i = (ingrediente, periodo)
                if i in df.index:
                    camiones = df.loc[i]['Camiones']
                else:
                    camiones = 0
                llegadas_puerto[ingrediente][periodo] = camiones
                
        return llegadas_puerto
    
    def __load_objetivo_inventario(self):
        self.objetivo_df.set_index(['Planta', 'Ingrediente'], inplace=True)

        objetivo_inventario = dict()

        for planta in self.plantas:
            objetivo_inventario[planta] = dict()
            for ingrediente in self.ingredientes:
                i = (planta, ingrediente)
                if i in self.objetivo_df.index:
                    objetivo = self.objetivo_df.loc[i]['kilogramos']
                else:
                    objetivo = 0.0

                objetivo_inventario[planta][ingrediente] = objetivo
        
        return objetivo_inventario

    def __load_tiempos_proceso(self):
        self.plantas_df.set_index(['planta'], inplace=True)
        tiempo_disponible = dict()
        tiempo_limpieza = dict()
        tiempo_proceso = dict()
        for planta in self.plantas:

            if planta in self.plantas_df.index:
                disponible = self.plantas_df.loc[planta]['operacion_minutos'] * \
                    self.plantas_df.loc[planta]['plataformas']
                limpieza = self.plantas_df.loc[planta]['minutos_limpieza']
            else:
                disponible = 0
                limpieza = 0

            tiempo_disponible[planta] = disponible
            tiempo_limpieza[planta] = limpieza

        df = self.plantas_df.reset_index().melt(id_vars=['planta'],
                                   value_vars=self.ingredientes,
                                   value_name='Tiempo_Operacion',
                                   var_name='Ingrediente')
        
        df.set_index(['planta', 'Ingrediente'], inplace=True)

        for planta in self.plantas:
            tiempo_proceso[planta] = dict()
            for ingrediente in self.ingredientes:
                i = (planta, ingrediente)
                if i in df.index:
                    tiempo = df.loc[i]['Tiempo_Operacion']
                else:
                    tiempo = 0
                tiempo_proceso[planta][ingrediente] = tiempo

        return tiempo_disponible, tiempo_limpieza, tiempo_proceso

    def __load_inventario_capacidad_planta(self):
        # Iventario y capacidad
        self.inventario_planta_df.set_index(['Planta', 'Ingrediente'], inplace=True)

        inventario_inicial = dict()
        capacidad_planta = dict()
        for planta in self.plantas:
            inventario_inicial[planta] = dict()
            capacidad_planta[planta] = dict()
            for ingrediente in self.ingredientes:
                i = (planta, ingrediente)
                if i in self.inventario_planta_df.index:
                    capacidad = self.inventario_planta_df.loc[i]['Capacidad']
                    inventario = self.inventario_planta_df.loc[i]['Inventario']
                else:
                    capacidad = 0
                    inventario = 0
                inventario_inicial[planta][ingrediente] = inventario
                capacidad_planta[planta][ingrediente] = capacidad
        
        return inventario_inicial, capacidad_planta
    
    def __load_llegadas_planeadas_planta(self)->dict:
        self.llegadas_programadas_df.set_index(['Planta', 'Ingrediente', 'Fecha'], inplace=True)

        # Llegadas planeadas
        llegadas_planteadas = dict()
        for planta in self.plantas:
            llegadas_planteadas[planta] = dict()
            for ingrediente in self.ingredientes:
                llegadas_planteadas[planta][ingrediente] = dict()
                for periodo in self.periodos:
                    i = (planta, ingrediente, periodo)
                    if i in self.llegadas_programadas_df.index:
                        llegadas = self.llegadas_programadas_df.loc[i]['Llegadas_planeadas']
                    else:
                        llegadas = 0
                    llegadas_planteadas[planta][ingrediente][periodo] = llegadas

        return llegadas_planteadas

    def __load_empresas(self)->dict:
            empresas_dict = {self.plantas_df.iloc[i]['planta']: self.plantas_df.iloc[i]
                    ['empresa'] for i in range(self.plantas_df.shape[0])}
            return empresas_dict

    def __load_plantas(self)->list:
        plantas = list(self.plantas_df['planta'].unique())
        return plantas
    
    def __load_periodos(self)->list:
        periodos = sorted(list(self.consumo_proyectado_df['Fecha'].unique()))
        return periodos

    def __load_ingredientes(self)->list:
        ingredientes = list(self.consumo_proyectado_df['Ingrediente'].unique())
        return ingredientes

    def __load_consumo_proyectado(self)->dict:

        # Consumo Proyectado
        self.consumo_proyectado_df.set_index(
            ['Planta', 'Ingrediente', 'Fecha'], inplace=True)

        consumo_proyectado = dict()
        for planta in self.plantas:
            consumo_proyectado[planta] = dict()
            for ingrediente in self.ingredientes:
                consumo_proyectado[planta][ingrediente] = dict()
                for periodo in self.periodos:
                    i = (planta, ingrediente, periodo)
                    if i in self.consumo_proyectado_df.index:
                        consumo = int(self.consumo_proyectado_df.loc[i]['Consumo'])
                    else:
                        consumo = 0.0
                    consumo_proyectado[planta][ingrediente][periodo] = consumo
        
        return consumo_proyectado