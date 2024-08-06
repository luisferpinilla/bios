from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey, UniqueConstraint, create_engine
from sqlalchemy.orm import relationship

Base = declarative_base()

class Periodo(Base):
    __tablename__ = "periodos"
    
    id = Column(Integer, primary_key=True)
    fecha = Column(Date, nullable=False, unique=True)

class Empresa(Base):
    __tablename__ = "empresas"
    
    id = Column(Integer, primary_key=True)
    nombre = Column(String(15), nullable=False, unique=True)

class Intercompany(Base):
    __tablename__ = "intercompanies"
    __table_args__ = (
        UniqueConstraint('id_empresa_origen', 'id_empresa_destino', name='_unique_empresas_combination'),
    )

    id = Column(Integer, primary_key=True)
    id_empresa_origen = Column(Integer, ForeignKey("empresas.id"))
    id_empresa_destino = Column(Integer, ForeignKey("empresas.id")) 
    valor = Column(Float)

    empresa_origen = relationship("Empresa", foreign_keys=[id_empresa_origen])
    empresa_destino = relationship("Empresa", foreign_keys=[id_empresa_destino])

class Ingrediente(Base):
    __tablename__ = "ingredientes"
    
    id =Column(Integer, primary_key=True)
    nombre = Column(String(15), nullable=False, unique=True)
    densidad = float
    
class Planta(Base):
    __tablename__ = "plantas"
    
    id = Column(Integer, primary_key=True)
    id_empresa = Column(Integer, ForeignKey("empresas.id"))
    nombre = Column(String(15), nullable=False, unique=True)
    tiempo_disponible_recepcion = Column(Integer)
    latitud = Column(Float)
    longitud = Column(Float)
    
    empresa = relationship("Empresa")


class Puerto(Base):
    __tablename__ = "puertos"
    
    id = Column(Integer, primary_key=True)
    codigo = Column(String(3), nullable=False, unique=True)
    nombre = Column(String(15))
    latitud = Column(Float)
    longitud = Column(Float)
    latitud = Column(Float)
    longitud = Column(Float)
    

class Operador(Base):
    __tablename__ = "operadores"
    
    id = Column(Integer, primary_key=True)
    nombre = Column(String(15), nullable=False, unique=True)

                    
class InventarioPlanta(Base):
    __tablename__ = "plantas_inventarios"
    
    id = Column(Integer, primary_key=True)
    id_planta = Column(Integer, ForeignKey("plantas.id"))
    id_ingrediente = Column(Integer, ForeignKey("ingredientes.id"))
    id_periodo = Column(Integer, ForeignKey("periodos.id"))
    costo_backorder = Column(Integer)
    safety_stock = Column(Integer)
    objetivo = Column(Integer)
    capacidad = Column(Integer)
    demanda = Column(Integer)
    llegada_planeada = Column(Integer)
    var_consumo = Column(Integer)
    var_backorder = Column(Integer)
    var_inventario_al_cierre = Column(Integer)

    planta = relationship("Planta")
    ingrediente = relationship("Ingrediente")
    periodo = relationship("Periodo")


class Importacion(Base):
    __tablename__ = "importaciones"
    
    id = Column(Integer, primary_key=True)
    codigo = Column(String(25), nullable=False, unique=True)
    id_ingrediente = Column(Integer, ForeignKey("ingredientes.id"))
    id_empresa = Column(Integer, ForeignKey("empresas.id"))
    id_puerto = Column(Integer, ForeignKey("puertos.id"))
    id_operador = Column(Integer, ForeignKey("operadores.id"))
    fecha_llegada = Column(Date)
    inventario_inicial = Column(Integer)

    ingrediente = relationship("Ingrediente")
    empresa = relationship("Empresa")
    operador = relationship("Operador")


class InventarioPuerto(Base):
    __tablename__ = "puerto_inventarios"
    
    id = Column(Integer, primary_key=True)
    id_importacion = Column(Integer, ForeignKey("importaciones.id"))
    id_periodo = Column(Integer, ForeignKey("periodos.id"))
    costo_almacenamiento = Column(Float)
    costo_bodegaje = Column(Float)
    llegada_planeada = Column(Integer)
    var_inventario_al_cierre = Column(Integer)

    importacion = relationship("Importacion")
    periodo = relationship("Periodo")   


class Despachos(Base):
    __tablename__ = "despachos"     
    id = Column(Integer, primary_key=True)
    id_importacion = Column(Integer, ForeignKey("importaciones.id"))
    id_planta = Column(Integer, ForeignKey("plantas.id"))
    id_periodo_despacho = Column(Integer, ForeignKey("periodos.id"))
    id_periodo_llegada = Column(Integer)
    costo_flete = Column(Float)
    costo_directo = Column(Float)
    costo_intercompany = Column(Float)
    tiempo_recepcion = Column(Integer)    
    var_cantidad_camiones = Column(Integer)

    importacion = relationship("Importacion")
    planta = relationship("Planta")
    perido_despacho = relationship("Periodo")


def generar_archivo(database:str):
    
    connection_string = f"sqlite:///{database}"
    
    engine = create_engine(connection_string, echo=True, future=True)
    
    Base.metadata.create_all(engine)
