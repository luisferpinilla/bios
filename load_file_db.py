# %% [markdown]
# # Copy file to MySQL

# %%
#!pip3 install --upgrade pip
#!pip3 install -r requirements.txt
#!sqlacodegen mysql+oursql://user:password@localhost/dbname
import pandas as pd
from utils.asignador_capacidad import AsignadorCapacidad
from utils.objetivo_inventario import obtener_objetivo_inventario
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from tqdm import tqdm

# %% [markdown]
# # Modelo de base de datos

# %%
import os

def cargar_modelo(bios_input_file:str):
    
    fname = 'bios.sqlite'
    if os.path.isfile(fname):
        os.remove(fname)

    # %%
    from sqlalchemy.ext.declarative import declarative_base
    from sqlalchemy.orm import sessionmaker

    engine = create_engine('sqlite:///bios.sqlite')
    Session = sessionmaker(bind=engine)
    session = Session()

    Base = declarative_base()

    # %% [markdown]
    # ## Moddelos de datos

    # %%
    from sqlalchemy import Column, DECIMAL, Date, Enum, Float, ForeignKey, Index, Integer, String, TIMESTAMP, text
    from sqlalchemy.orm import relationship


    class Archivo(Base):
        __tablename__ = 'archivos'

        id = Column(Integer, primary_key=True)
        file_name = Column(String(255), nullable=False, unique=True)
        upload_date = Column(TIMESTAMP, nullable=False,
                            server_default=text("CURRENT_TIMESTAMP"))
        status = Column(Enum('loaded', 'validated',
                        'unfeasible', 'sub_obtimal', 'optimal'))


    class Empresa(Base):
        __tablename__ = 'empresas'

        id = Column(Integer, primary_key=True)
        nombre = Column(String(15), nullable=False, unique=True)


    class Ingrediente(Base):
        __tablename__ = 'ingredientes'

        id = Column(Integer, primary_key=True)
        nombre = Column(String(15), nullable=False, unique=True)


    class Operadore(Base):
        __tablename__ = 'operadores'

        id = Column(Integer, primary_key=True)
        nombre = Column(String(15), nullable=False, unique=True)


    class Puerto(Base):
        __tablename__ = 'puertos'

        id = Column(Integer, primary_key=True)
        nombre = Column(String(15), nullable=False, unique=True)
        latitude = Column(DECIMAL(10, 8))
        longitude = Column(DECIMAL(11, 8))
        capacidad_descarga_kg_dia = Column(
            Integer, nullable=False, server_default=text("'5000000'"))


    class CostosPortuario(Base):
        __tablename__ = 'costos_portuarios'

        id = Column(Integer, primary_key=True)
        id_operador = Column(ForeignKey('operadores.id'), nullable=False)
        id_puerto = Column(ForeignKey('puertos.id'), nullable=False, index=True)
        id_ingrediente = Column(ForeignKey('ingredientes.id'),
                                nullable=False, index=True)
        tipo_operacion = Column(Enum('directo', 'bodega'), nullable=False)
        valor_kg = Column(DECIMAL(10, 8), nullable=False)

        ingrediente = relationship('Ingrediente')
        operadore = relationship('Operadore')
        puerto = relationship('Puerto')


    class Importacione(Base):
        __tablename__ = 'importaciones'

        id = Column(Integer, primary_key=True)
        id_archivo = Column(ForeignKey('archivos.id'), nullable=False)
        id_empresa = Column(ForeignKey('empresas.id'), nullable=False, index=True)
        id_puerto = Column(ForeignKey('puertos.id'), nullable=False, index=True)
        id_operador = Column(ForeignKey('operadores.id'),
                            nullable=False, index=True)
        id_ingrediente = Column(ForeignKey('ingredientes.id'),
                                nullable=False, index=True)
        importacion = Column(String(50), nullable=False)
        fecha_llegada = Column(Date, nullable=False)
        cantidad_puerto_kg = Column(
            Integer, nullable=False, server_default=text("'0'"))
        valor_kg = Column(DECIMAL(10, 2), nullable=False)

        archivo = relationship('Archivo')
        empresa = relationship('Empresa')
        ingrediente = relationship('Ingrediente')
        operadore = relationship('Operadore')
        puerto = relationship('Puerto')


    class Intercompany(Base):
        __tablename__ = 'intercompanies'

        id = Column(Integer, primary_key=True)
        id_empresa_origen = Column(ForeignKey('empresas.id'), nullable=False)
        id_empresa_destino = Column(ForeignKey(
            'empresas.id'), nullable=False, index=True)
        valor_intercompany = Column(DECIMAL(10, 8), nullable=False)

        destino = relationship(
            'Empresa', primaryjoin='Intercompany.id_empresa_destino == Empresa.id')
        origen = relationship(
            'Empresa', primaryjoin='Intercompany.id_empresa_origen == Empresa.id')


    class Planta(Base):
        __tablename__ = 'plantas'

        id = Column(Integer, primary_key=True)
        id_empresa = Column(ForeignKey('empresas.id'), nullable=False, index=True)
        nombre = Column(String(15), nullable=False, unique=True)
        latitude = Column(DECIMAL(10, 8))
        longitude = Column(DECIMAL(11, 8))
        capacidad_recepcion_min_dia = Column(
            Integer, nullable=False, server_default=text("'0'"))
        tiempo_limpieza_min_dia = Column(
            Integer, nullable=False, server_default=text("'0'"))

        empresa = relationship('Empresa')


    class ConsumoProyectado(Base):
        __tablename__ = 'consumo_proyectado'

        id = Column(Integer, primary_key=True)
        id_archivo = Column(ForeignKey('archivos.id'), nullable=False)
        id_planta = Column(ForeignKey('plantas.id'), nullable=False, index=True)
        id_ingrediente = Column(ForeignKey('ingredientes.id'),
                                nullable=False, index=True)
        fecha_consumo = Column(Date, nullable=False)
        consumo_kg = Column(Float(asdecimal=True), nullable=False)

        archivo = relationship('Archivo')
        ingrediente = relationship('Ingrediente')
        planta = relationship('Planta')


    class CostosAlmacenamientoPuerto(Base):
        __tablename__ = 'costos_almacenamiento_puerto'

        id = Column(Integer, primary_key=True)
        id_importacion = Column(ForeignKey('importaciones.id'), nullable=False)
        fecha_cobro = Column(Date, nullable=False)
        valor_a_cobrar_kg = Column(DECIMAL(10, 2), nullable=False)

        importacione = relationship('Importacione')


    class Flete(Base):
        __tablename__ = 'fletes'

        id = Column(Integer, primary_key=True)
        id_puerto = Column(ForeignKey('puertos.id'), nullable=False)
        id_operador = Column(ForeignKey('operadores.id'),
                            nullable=False, index=True)
        id_ingrediente = Column(ForeignKey('ingredientes.id'),
                                nullable=False, index=True)
        id_planta = Column(ForeignKey('plantas.id'), nullable=False, index=True)
        valor_flete_kg = Column(Integer, nullable=False)

        ingrediente = relationship('Ingrediente')
        operadore = relationship('Operadore')
        planta = relationship('Planta')
        puerto = relationship('Puerto')


    class SafetyStock(Base):
        __tablename__ = 'safety_stocks'

        id = Column(Integer, primary_key=True)
        id_planta = Column(ForeignKey('plantas.id'), nullable=False)
        id_ingrediente = Column(ForeignKey('ingredientes.id'),
                                nullable=False, index=True)
        dias_safety_stock = Column(
            Integer, nullable=False, server_default=text("'0'"))

        ingrediente = relationship('Ingrediente')
        planta = relationship('Planta')


    class TiempoDescarguePlanta(Base):
        __tablename__ = 'tiempo_descargue_planta'

        id = Column(Integer, primary_key=True)
        id_planta = Column(ForeignKey('plantas.id'), nullable=False)
        id_ingrediente = Column(ForeignKey('ingredientes.id'),
                                nullable=False, index=True)
        tiempo_minutos = Column(Integer, nullable=False)

        ingrediente = relationship('Ingrediente')
        planta = relationship('Planta')


    class TransitosPlanta(Base):
        __tablename__ = 'transitos_planta'

        id = Column(Integer, primary_key=True)
        id_archivo = Column(ForeignKey('archivos.id'), nullable=False)
        id_planta = Column(ForeignKey('plantas.id'), nullable=False, index=True)
        id_ingrediente = Column(ForeignKey('ingredientes.id'),
                                nullable=False, index=True)
        fecha_llegada = Column(Date, nullable=False)
        cantidad = Column(Integer, nullable=False)

        archivo = relationship('Archivo')
        ingrediente = relationship('Ingrediente')
        planta = relationship('Planta')


    class TransitosPuerto(Base):
        __tablename__ = 'transitos_puerto'

        id = Column(Integer, primary_key=True)
        id_importacion = Column(ForeignKey('importaciones.id'), nullable=False)
        fecha_descarge = Column(Date, nullable=False)
        cantidad = Column(Integer, nullable=False,
                        server_default=text("'5000000'"))

        importacione = relationship('Importacione')


    class Unidade(Base):
        __tablename__ = 'unidades'

        id = Column(Integer, primary_key=True)
        id_archivo = Column(ForeignKey('archivos.id'), nullable=False)
        id_planta = Column(ForeignKey('plantas.id'), nullable=False, index=True)
        id_ingrediente = Column(ForeignKey('ingredientes.id'), nullable=False)
        nombre = Column(String(10), nullable=False)
        capacidad = Column(Integer, nullable=False)
        inventario = Column(Integer, nullable=False)

        archivo = relationship('Archivo')
        ingrediente = relationship('Ingrediente')
        planta = relationship('Planta')


    class ObjetivosInventario(Base):
        __tablename__ = 'objetivos_inventario'

        id = Column(Integer, primary_key=True)
        id_archivo = Column(ForeignKey('archivos.id'), nullable=False)
        id_planta = Column(ForeignKey('plantas.id'), nullable=False, index=False)
        id_ingrediente = Column(ForeignKey('ingredientes.id'),
                                nullable=False, index=True)
        objetivo = Column(Integer, nullable=False)
        kilogramos = Column(Integer, nullable=False)

        archivo = relationship('Archivo')
        ingrediente = relationship('Ingrediente')
        planta = relationship('Planta')

    # %%
    Base.metadata.create_all(engine)

    # %%
    # sqlacodegen mysql+mysqlconnector://root:secret@localhost:3306/bios

    # %%
    # Conexion de base de datos
    # engine = create_engine("mysql+mysqlconnector://root:secret@localhost:3306/bios")

    # %%
    # Archivo proporcionado por BIOS

    # session = Session(engine)

    # %% [markdown]
    # ## Parametros a cargar

    # %%
    # Capacidad de carga de un camion
    cap_camion = 34000

    # Capacidad de descarga en puerto por día
    cap_descarge = 5000000

    # %%
    # Leer el archivo de excel
    productos_df = pd.read_excel(io=bios_input_file, sheet_name='ingredientes')
    plantas_df = pd.read_excel(io=bios_input_file, sheet_name='plantas')
    asignador = AsignadorCapacidad(bios_input_file)
    unidades_almacenamiento_df = asignador.obtener_unidades_almacenamiento()
    safety_stock_df = pd.read_excel(io=bios_input_file, sheet_name='safety_stock')
    consumo_proyectado_df = pd.read_excel(
        io=bios_input_file, sheet_name='consumo_proyectado')
    transitos_puerto_df = pd.read_excel(
        io=bios_input_file, sheet_name='tto_puerto')
    transitos_planta_df = pd.read_excel(
        io=bios_input_file, sheet_name='tto_plantas')
    inventario_puerto_df = pd.read_excel(
        io=bios_input_file, sheet_name='inventario_puerto')
    costos_almacenamiento_df = pd.read_excel(
        io=bios_input_file, sheet_name='costos_almacenamiento_cargas')
    operaciones_portuarias_df = pd.read_excel(
        io=bios_input_file, sheet_name='costos_operacion_portuaria')
    fletes_df = pd.read_excel(io=bios_input_file, sheet_name='fletes_cop_per_kg')
    intercompany_df = pd.read_excel(
        io=bios_input_file, sheet_name='venta_entre_empresas')
    objetivo_df = obtener_objetivo_inventario(bios_input_file=bios_input_file)

    # %% [markdown]
    # # Parametros generales
    # ## Ingresando las empresas

    # %%
    for empresa in tqdm(plantas_df['empresa'].unique()):
        empresa_model = session.execute(
            select(Empresa).filter_by(nombre=empresa)).scalar_one_or_none()
        if empresa_model is None:
            empresa_model = Empresa(nombre=empresa)
            session.add(empresa_model)
        else:
            empresa_model.nombre = empresa
        session.commit()

    # %% [markdown]
    # ## Ingresando ingredientes

    # %%
    for ingrediente in tqdm(productos_df['nombre'].unique()):
        ingrediente_model = session.execute(
            select(Ingrediente).filter_by(nombre=ingrediente)).scalar_one_or_none()
        if ingrediente_model is None:
            ingrediente_model = Ingrediente(nombre=ingrediente)
            session.add(ingrediente_model)
        else:
            ingrediente_model.nombre = ingrediente
        session.commit()

    # %% [markdown]
    # ## Plantas

    # %%
    for i in tqdm(plantas_df.index):
        planta = plantas_df.loc[i]['planta']
        empresa = plantas_df.loc[i]['empresa']
        operacion_minutos = int(plantas_df.loc[i]['operacion_minutos'])
        limpieza = int(plantas_df.loc[i]['minutos_limpieza'])
        plataformas = int(plantas_df.loc[i]['plataformas'])

        empresa_model = session.execute(
            select(Empresa).filter_by(nombre=empresa)).scalar_one_or_none()

        planta_model = session.execute(
            select(Planta).filter_by(nombre=planta)).scalar_one_or_none()

        if planta_model is None:
            planta_model = Planta(empresa=empresa_model,
                                nombre=planta,
                                latitude=0.0,
                                longitude=0.0,
                                capacidad_recepcion_min_dia=operacion_minutos*plataformas,
                                tiempo_limpieza_min_dia=limpieza)
            session.add(planta_model)
        else:
            planta_model.empresa = empresa_model
            planta_model.nombre = planta
            planta_model.latitude = 0.0
            planta_model.longitude = 0.0
            planta_model.capacidad_recepcion_min_dia = operacion_minutos*plataformas
            planta_model.tiempo_limpieza_min_dia = limpieza

        for ingrediente in productos_df['nombre'].unique():

            tiempo_descarge = int(plantas_df.loc[i][ingrediente])

            ingrediente_model = session.execute(
                select(Ingrediente).filter_by(nombre=ingrediente)).scalar_one_or_none()

            tiempoDescarguePlanta = session.execute(
                select(TiempoDescarguePlanta).filter_by(planta=planta_model,
                                                        ingrediente=ingrediente_model)).scalar_one_or_none()

            if tiempoDescarguePlanta is None:
                tiempoDescarguePlanta = TiempoDescarguePlanta(planta=planta_model,
                                                            ingrediente=ingrediente_model,
                                                            tiempo_minutos=tiempo_descarge)
                session.add(tiempoDescarguePlanta)
            else:
                tiempoDescarguePlanta.planta = planta_model
                tiempoDescarguePlanta.ingrediente = ingrediente_model
                tiempoDescarguePlanta.tiempo_minutos = tiempo_descarge

    session.commit()

    # %% [markdown]
    # ## Intercompany

    # %%
    intercompany_df = intercompany_df.melt(
        id_vars='origen', value_vars=['contegral', 'finca'], var_name='destino', value_name='valor')
    intercompany_df

    # %%
    for i in tqdm(intercompany_df.index):
        origen = intercompany_df.loc[i]['origen']
        destino = intercompany_df.loc[i]['destino']
        valor = float(intercompany_df.loc[i]['valor'])

        empresa_origen_model = session.execute(
            select(Empresa).filter_by(nombre=origen)).scalar_one_or_none()
        empresa_destino_model = session.execute(
            select(Empresa).filter_by(nombre=destino)).scalar_one_or_none()

        if not empresa_destino_model is None and not empresa_origen_model is None:
            intercompany_model = session.execute(select(Intercompany).filter_by(origen=empresa_origen_model,
                                                                                destino=empresa_destino_model)).scalar_one_or_none()
            if intercompany_model is None:
                intercompany_model = Intercompany(
                    origen=empresa_origen_model,
                    destino=empresa_destino_model,
                    valor_intercompany=valor)
                session.add(intercompany_model)
            else:
                intercompany_model.origen = empresa_origen_model
                intercompany_model.destino = empresa_destino_model
                intercompany_model.valor_intercompany = valor
        else:
            print('la empresa origen o destino no existe en la base de datos')

        session.commit()

    # %% [markdown]
    # ## Fletes

    # %%
    for puerto in tqdm(fletes_df['puerto'].unique()):
        puerto_model = session.execute(
            select(Puerto).filter_by(nombre=puerto)).scalar_one_or_none()
        if puerto_model is None:
            puerto_model = Puerto(nombre=puerto)
            session.add(puerto_model)
        else:
            puerto_model.nombre = puerto
    session.commit()

    # %%
    for operador in tqdm(fletes_df['operador'].unique()):
        operador_model = session.execute(
            select(Operadore).filter_by(nombre=operador)).scalar_one_or_none()
        if operador_model is None:
            operador_model = Operadore(nombre=operador)
            session.add(operador_model)
        else:
            operador_model.nombre = operador

    session.commit()

    # %%
    for i in tqdm(fletes_df.index):
        puerto = fletes_df.loc[i]['puerto']
        operador = fletes_df.loc[i]['operador']
        ingrediente = fletes_df.loc[i]['ingrediente']

        for planta in plantas_df['planta'].unique():

            valor = fletes_df.loc[i][planta]

            planta_model = session.execute(
                select(Planta).filter_by(nombre=planta)).scalar_one_or_none()
            puerto_model = session.execute(
                select(Puerto).filter_by(nombre=puerto)).scalar_one_or_none()
            operador_model = session.execute(
                select(Operadore).filter_by(nombre=operador)).scalar_one_or_none()
            ingrediente_model = session.execute(
                select(Ingrediente).filter_by(nombre=ingrediente)).scalar_one_or_none()

            flete_model = session.execute(select(Flete).filter_by(puerto=puerto_model,
                                                                operadore=operador_model,
                                                                ingrediente=ingrediente_model,
                                                                planta=planta_model)).scalar_one_or_none()

            if flete_model is None:
                flete_model = Flete(puerto=puerto_model,
                                    operadore=operador_model,
                                    ingrediente=ingrediente_model,
                                    planta=planta_model,
                                    valor_flete_kg=valor)

                session.add(flete_model)
            else:
                flete_model.puerto = puerto_model
                flete_model.operadore = operador_model
                flete_model.ingrediente = ingrediente_model
                flete_model.planta = planta_model
                flete_model.valor_flete_kg = valor

    session.commit()

    # %% [markdown]
    # ## Safety Stock

    # %%
    for i in tqdm(safety_stock_df.index):

        planta = safety_stock_df.loc[i]['planta']
        ingrediente = safety_stock_df.loc[i]['ingrediente']
        dias = int(safety_stock_df.loc[i]['dias_ss'])

        planta_model = session.execute(
            select(Planta).filter_by(nombre=planta)).scalar_one_or_none()

        ingrediente_model = session.execute(
            select(Ingrediente).filter_by(nombre=ingrediente)).scalar_one_or_none()

        safety_stock_model = session.execute(select(SafetyStock).filter_by(planta=planta_model,
                                                                        ingrediente=ingrediente_model)).scalar_one_or_none()

        if safety_stock_model is None:

            safety_stock_model = SafetyStock(
                planta=planta_model,
                ingrediente=ingrediente_model,
                dias_safety_stock=dias)

            session.add(safety_stock_model)
        else:

            safety_stock_model.planta = planta_model
            safety_stock_model.ingrediente = ingrediente_model
            safety_stock_model.dias_safety_stock = dias

    session.commit()

    # %% [markdown]
    # ## Costos de operacion portuaria

    # %%
    for i in tqdm(operaciones_portuarias_df.index):
        operacion = operaciones_portuarias_df.loc[i]['tipo_operacion']
        operador = operaciones_portuarias_df.loc[i]['operador']
        puerto = operaciones_portuarias_df.loc[i]['puerto']
        ingrediente = operaciones_portuarias_df.loc[i]['ingrediente']
        valor_kg = float(operaciones_portuarias_df.loc[i]['valor_kg'])

        operador_model = session.execute(
            select(Operadore).filter_by(nombre=operador)).scalar_one_or_none()

        puerto_model = session.execute(
            select(Puerto).filter_by(nombre=puerto)).scalar_one_or_none()

        ingrediente_model = session.execute(
            select(Ingrediente).filter_by(nombre=ingrediente)).scalar_one_or_none()

        operacion_model = session.execute(select(CostosPortuario).filter_by(tipo_operacion=operacion,
                                                                            ingrediente=ingrediente_model,
                                                                            operadore=operador_model,
                                                                            puerto=puerto_model)).scalar_one_or_none()

        if operacion_model is None:
            operacion_model = CostosPortuario(tipo_operacion=operacion,
                                            ingrediente=ingrediente_model,
                                            operadore=operador_model,
                                            puerto=puerto_model,
                                            valor_kg=valor_kg)
            session.add(operacion_model)
        else:
            operacion_model.tipo_operacion = operacion
            operacion_model.ingrediente = ingrediente_model
            operacion_model.operadore = operador_model
            operacion_model.puerto = puerto_model
            operacion_model.valor_kg = valor_kg

        session.commit()

    # %% [markdown]
    # # Informacion específica del archivo
    # Archivos

    # %%
    file_model = session.execute(select(Archivo).filter_by(
        file_name=bios_input_file)).scalar_one_or_none()

    if file_model is None:
        file_model = Archivo(file_name=bios_input_file,
                            upload_date=datetime.now(),
                            status='loaded')
        session.add(file_model)
    else:
        file_model.file_name = bios_input_file
        file_model.status = 'loaded'

    session.commit()

    # %% [markdown]
    # ## Consumo proyectdo

    # %%
    index_values = ['planta', 'ingrediente']
    consumo_proyectado_df = consumo_proyectado_df.melt(id_vars=index_values,
                                                    value_vars=consumo_proyectado_df.drop(
                                                        columns=index_values).columns,
                                                    var_name='fecha',
                                                    value_name='consumo_kg')

    # %%
    for i in tqdm(consumo_proyectado_df.index):
        planta = consumo_proyectado_df.loc[i]['planta']
        ingrediente = consumo_proyectado_df.loc[i]['ingrediente']
        fecha = datetime.strptime(
            consumo_proyectado_df.loc[i]['fecha'], '%d/%m/%Y')
        consumo_kg = float(consumo_proyectado_df.loc[i]['consumo_kg'])

        planta_model = session.execute(
            select(Planta).filter_by(nombre=planta)).scalar_one_or_none()
        ingrediente_model = session.execute(
            select(Ingrediente).filter_by(nombre=ingrediente)).scalar_one_or_none()
        file_model = session.execute(select(Archivo).filter_by(
            file_name=bios_input_file)).scalar_one_or_none()
        consumo_model = session.execute(select(ConsumoProyectado).filter_by(archivo=file_model,
                                                                            planta=planta_model,
                                                                            ingrediente=ingrediente_model,
                                                                            fecha_consumo=fecha)).scalar_one_or_none()

        if consumo_model is None:
            consumo_model = ConsumoProyectado(planta=planta_model,
                                            ingrediente=ingrediente_model,
                                            fecha_consumo=fecha,
                                            archivo=file_model,
                                            consumo_kg=consumo_kg)
            session.add(consumo_model)
        else:
            consumo_model.planta = planta_model
            consumo_model.ingrediente = ingrediente_model
            consumo_model.fecha = fecha
            consumo_model.archivo = file_model
            consumo_model.consumo_kg = consumo_kg

    session.commit()

    # %% [markdown]
    # ## Unidades de almacenamiento
    # Unidades, ingredientes, Capacidades e inventarios

    # %%
    unidades_almacenamiento_df.head()

    # %%
    file_model = session.execute(select(Archivo).filter_by(
        file_name=bios_input_file)).scalar_one_or_none()

    ingredientes_list = list(productos_df['nombre'].unique())

    for i in tqdm(unidades_almacenamiento_df.index):
        planta_nombre = unidades_almacenamiento_df.loc[i]['planta']
        nombre_ua = unidades_almacenamiento_df.loc[i]['unidad_almacenamiento']
        ingrediente_actual = unidades_almacenamiento_df.loc[i]['ingrediente_actual']
        cantidad_actual = int(unidades_almacenamiento_df.loc[i]['cantidad_actual'])
        capacidad = int(unidades_almacenamiento_df.loc[i][ingrediente_actual])

        planta_model = session.execute(select(Planta).filter_by(
            nombre=planta_nombre)).scalar_one_or_none()

        ingrediente_model = session.execute(
            select(Ingrediente).filter_by(nombre=ingrediente_actual)).scalar_one_or_none()

        unidade_model = session.execute(select(Unidade).filter_by(
            archivo=file_model,
            planta=planta_model,
            ingrediente=ingrediente_model,
            nombre=nombre_ua)).scalar_one_or_none()

        if unidade_model is None:
            unidade_model = Unidade(
                archivo=file_model,
                planta=planta_model,
                ingrediente=ingrediente_model,
                nombre=nombre_ua,
                inventario=cantidad_actual,
                capacidad=capacidad
            )

            session.add(unidade_model)
        else:
            unidade_model.archivo = file_model
            unidade_model.planta = planta_model
            unidade_model.ingrediente = ingrediente_model
            unidade_model.nombre = nombre_ua
            unidade_model.inventario = cantidad_actual
            unidade_model.capacidad = capacidad


    session.commit()

    # %% [markdown]
    # ## Transito a plantas

    # %%
    transitos_planta_df['fecha_llegada'] = pd.to_datetime(
        transitos_planta_df['fecha_llegada'])
    transitos_planta_df.head()

    # %%
    for i in tqdm(transitos_planta_df.index):
        planta = transitos_planta_df.loc[i]['planta']
        ingrediente = transitos_planta_df.loc[i]['ingrediente']
        cantidad = int(transitos_planta_df.loc[i]['cantidad'])
        fecha = transitos_planta_df.loc[i]['fecha_llegada']
        fecha = fecha.date()

        file_model = session.execute(select(Archivo).filter_by(
            file_name=bios_input_file)).scalar_one_or_none()
        planta_model = session.execute(
            select(Planta).filter_by(nombre=planta)).scalar_one_or_none()
        ingrediente_model = session.execute(
            select(Ingrediente).filter_by(nombre=ingrediente)).scalar_one_or_none()

        transitos_planta_model = session.execute(select(TransitosPlanta).filter_by(archivo=file_model,
                                                                                planta=planta_model,
                                                                                ingrediente=ingrediente_model,
                                                                                fecha_llegada=fecha)).scalar_one_or_none()

        if transitos_planta_model is None:
            transitos_planta_model = TransitosPlanta(
                archivo=file_model,
                planta=planta_model,
                ingrediente=ingrediente_model,
                fecha_llegada=fecha,
                cantidad=cantidad
            )
            session.add(transitos_planta_model)

        else:
            transitos_planta_model.archivo = file_model
            transitos_planta_model.planta = planta_model
            transitos_planta_model.ingrediente = ingrediente_model
            transitos_planta_model.fecha_llegada = fecha
            transitos_planta_model.cantidad = cantidad

    session.commit()

    # %% [markdown]
    # ## Inventario en puertos

    # %%
    for i in tqdm(inventario_puerto_df.index):

        empresa = inventario_puerto_df.loc[i]['empresa']
        operador = inventario_puerto_df.loc[i]['operador']
        puerto = inventario_puerto_df.loc[i]['puerto']
        ingrediente = inventario_puerto_df.loc[i]['ingrediente']
        importacion = inventario_puerto_df.loc[i]['importacion']
        fecha = inventario_puerto_df.loc[i]['fecha_llegada']
        fecha = fecha.date()
        cantidad = inventario_puerto_df.loc[i]['cantidad_kg']
        valor_kg = inventario_puerto_df.loc[i]['valor_cif_kg']

        file_model = session.execute(select(Archivo).filter_by(
            file_name=bios_input_file)).scalar_one_or_none()
        empresa_model = session.execute(
            select(Empresa).filter_by(nombre=empresa)).scalar_one_or_none()
        operador_model = session.execute(
            select(Operadore).filter_by(nombre=operador)).scalar_one_or_none()
        puerto_model = session.execute(
            select(Puerto).filter_by(nombre=puerto)).scalar_one_or_none()
        ingrediente_model = session.execute(
            select(Ingrediente).filter_by(nombre=ingrediente)).scalar_one_or_none()

        importacion_model = session.execute(select(Importacione).filter_by(archivo=file_model,
                                                                        empresa=empresa_model,
                                                                        operadore=operador_model,
                                                                        puerto=puerto_model,
                                                                        ingrediente=ingrediente_model,
                                                                        importacion=importacion)).scalar_one_or_none()

        if importacion_model is None:
            importacion_model = Importacione(archivo=file_model,
                                            empresa=empresa_model,
                                            ingrediente=ingrediente_model,
                                            operadore=operador_model,
                                            puerto=puerto_model,
                                            importacion=importacion,
                                            cantidad_puerto_kg=cantidad,
                                            fecha_llegada=fecha,
                                            valor_kg=valor_kg)
            session.add(importacion_model)

        else:
            importacion_model.archivo = file_model
            importacion_model.empresa = empresa_model
            importacion_model.ingrediente = ingrediente_model
            importacion_model.operadore = operador_model
            importacion_model.puerto = puerto_model
            importacion_model.importacion = importacion
            importacion_model.cantidad_puerto_kg = cantidad
            importacion_model.fecha_llegada = fecha
            importacion_model.valor_kg = valor_kg

    session.commit()

    # %% [markdown]
    # ## Transitos a puertos

    # %%
    def insertar_transito_puerto(session, importacion_model, fecha, cantidad):

        transitos_puerto_model = session.execute(select(TransitosPuerto).filter_by(importacione=importacion_model,
                                                                                fecha_descarge=fecha.date())).scalar_one_or_none()

        if transitos_puerto_model is None:
            transitos_puerto_model = TransitosPuerto(
                importacione=importacion_model,
                fecha_descarge=fecha,
                cantidad=cantidad)
            session.add(transitos_puerto_model)
        else:
            transitos_puerto_model.importacione = importacion_model
            transitos_puerto_model.fecha_descarge = fecha
            transitos_puerto_model.cantidad = cantidad

        return transitos_puerto_model

    # %%
    file_model = session.execute(select(Archivo).filter_by(
        file_name=bios_input_file)).scalar_one_or_none()

    for i in tqdm(transitos_puerto_df.index):
        # print('-----------------')
        # print(transitos_puerto_df.loc[i])
        empresa = transitos_puerto_df.loc[i]['empresa']
        operador = transitos_puerto_df.loc[i]['operador']
        puerto = transitos_puerto_df.loc[i]['puerto']
        ingrediente = transitos_puerto_df.loc[i]['ingrediente']
        importacion = transitos_puerto_df.loc[i]['importacion']
        fecha = transitos_puerto_df.loc[i]['fecha_llegada']
        cantidad = int(transitos_puerto_df.loc[i]['cantidad_kg'])
        valor_kg = float(transitos_puerto_df.loc[i]['valor_kg'])

        empresa_model = session.execute(
            select(Empresa).filter_by(nombre=empresa)).scalar_one_or_none()
        operador_model = session.execute(
            select(Operadore).filter_by(nombre=operador)).scalar_one_or_none()
        puerto_model = session.execute(
            select(Puerto).filter_by(nombre=puerto)).scalar_one_or_none()
        ingrediente_model = session.execute(
            select(Ingrediente).filter_by(nombre=ingrediente)).scalar_one_or_none()

        importacion_model = session.execute(select(Importacione).filter_by(archivo=file_model,
                                                                        empresa=empresa_model,
                                                                        operadore=operador_model,
                                                                        puerto=puerto_model,
                                                                        ingrediente=ingrediente_model,
                                                                        importacion=importacion)).scalar_one_or_none()

        if importacion_model is None:
            importacion_model = Importacione(archivo=file_model,
                                            empresa=empresa_model,
                                            ingrediente=ingrediente_model,
                                            operadore=operador_model,
                                            puerto=puerto_model,
                                            importacion=importacion,
                                            cantidad_puerto_kg=0.0,
                                            fecha_llegada=fecha.date(),
                                            valor_kg=valor_kg)
            session.add(importacion_model)

        else:
            importacion_model.archivo = file_model
            importacion_model.empresa = empresa_model
            importacion_model.ingrediente = ingrediente_model
            importacion_model.operadore = operador_model
            importacion_model.puerto = puerto_model
            importacion_model.importacion = importacion
            importacion_model.cantidad_puerto_kg = 0.0
            importacion_model.fecha_llegada = fecha.date()
            importacion_model.valor_kg = valor_kg

        # print('importacion.id', importacion_model.id)

        # Agregar las llegadas segun la capacidad del puerto
        while cantidad > cap_descarge:
            insertar_transito_puerto(
                session, importacion_model, fecha, cap_descarge)

            cantidad -= cap_descarge
            fecha = fecha + timedelta(days=1)

        if cantidad > 0:
            insertar_transito_puerto(session, importacion_model, fecha, cantidad)

        session.commit()

    # %% [markdown]
    # ## Costos de almacenamiento de cargas

    # %%
    for i in tqdm(costos_almacenamiento_df.index):
        empresa = costos_almacenamiento_df.loc[i]['empresa']
        operador = costos_almacenamiento_df.loc[i]['operador']
        puerto = costos_almacenamiento_df.loc[i]['puerto']
        ingrediente = costos_almacenamiento_df.loc[i]['ingrediente']
        importacion = costos_almacenamiento_df.loc[i]['importacion']
        fecha = costos_almacenamiento_df.loc[i]['fecha_corte']
        valor_kg = float(costos_almacenamiento_df.loc[i]['valor_kg'])

        file_model = session.execute(select(Archivo).filter_by(
            file_name=bios_input_file)).scalar_one_or_none()
        empresa_model = session.execute(
            select(Empresa).filter_by(nombre=empresa)).scalar_one_or_none()
        operador_model = session.execute(
            select(Operadore).filter_by(nombre=operador)).scalar_one_or_none()
        puerto_model = session.execute(
            select(Puerto).filter_by(nombre=puerto)).scalar_one_or_none()
        ingrediente_model = session.execute(
            select(Ingrediente).filter_by(nombre=ingrediente)).scalar_one_or_none()

        importacion_model = session.execute(select(Importacione).filter_by(archivo=file_model,
                                                                        empresa=empresa_model,
                                                                        operadore=operador_model,
                                                                        puerto=puerto_model,
                                                                        ingrediente=ingrediente_model,
                                                                        importacion=importacion)).scalar_one_or_none()

        if not importacion_model is None:
            costo_almacenamiento_model = session.execute(select(CostosAlmacenamientoPuerto).filter_by(importacione=importacion_model,
                                                                                                    fecha_cobro=fecha.date())).scalar_one_or_none()

            if costo_almacenamiento_model is None:
                costo_almacenamiento_model = CostosAlmacenamientoPuerto(
                    importacione=importacion_model,
                    fecha_cobro=fecha.date(),
                    valor_a_cobrar_kg=valor_kg)

                session.add(costo_almacenamiento_model)
            else:
                costo_almacenamiento_model.importacione = importacion_model
                costo_almacenamiento_model.fecha_cobro = fecha.date()
                costo_almacenamiento_model.valor_a_cobrar_kg = valor_kg

        else:
            print(
                f'la importacion {importacion} en el puerto {puerto}, del operador {operador} e ingrediente {ingrediente} NO existe')

    session.commit()

    # %% [markdown]
    # ## Objetivo de inventario

    # %%
    objetivo_inventario_df = objetivo_df['objetivo_inventario'].copy()

    # %%
    for i in tqdm(objetivo_inventario_df.index):
        planta = objetivo_inventario_df.loc[i]['planta']
        ingrediente = objetivo_inventario_df.loc[i]['ingrediente']
        objetivo = objetivo_inventario_df.loc[i]['objetivo_dio']
        kilogramos = objetivo_inventario_df.loc[i]['objetivo_kg']

        planta_model = session.execute(
            select(Planta).filter_by(nombre=planta)).scalar_one_or_none()
        ingrediente_model = session.execute(
            select(Ingrediente).filter_by(nombre=ingrediente)).scalar_one_or_none()

        objetivo_model = session.execute(select(ObjetivosInventario).filter_by(
            archivo=file_model, ingrediente=ingrediente_model, planta=planta_model)).scalar_one_or_none()

        if objetivo_model is None:

            objetivo_model = ObjetivosInventario(
                archivo=file_model,
                ingrediente=ingrediente_model,
                planta=planta_model,
                objetivo=objetivo,
                kilogramos=kilogramos
            )

            session.add(objetivo_model)
        else:
            objetivo_model.archivo = file_model
            objetivo_model.ingrediente = ingrediente_model
            objetivo_model.planta = planta_model
            objetivo_model.objetivo = objetivo
            objetivo_model.kilogramos = kilogramos

    session.commit()

    return engine

