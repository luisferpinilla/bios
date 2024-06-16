from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey, create_engine
from sqlalchemy.orm import relationship

Base = declarative_base()
engine = create_engine("sqlite:///base.db", echo=True, future=True)

class Periodo(Base):
    __tablename__ = "periodos"
    
    id = Column(Integer, primary_key=True)
    nombre = Column(String(15))
    fecha = Column(Date)

class Empresa(Base):
    __tablename__ = "empresas"
    
    id = Column(Integer, primary_key=True)
    nombre = Column(String(15))

class Ingrediente(Base):
    __tablename__ = "ingredientes"
    
    id =Column(Integer, primary_key=True)
    nombre = Column(String(15))
    densidad = float
    
class Plant(Base):
    __tablename__ = "plantas"
    
    id = Column(Integer, primary_key=True)
    id_empresa = Column(Integer, ForeignKey("empresas.id"))
    nombre = Column(String(15))
    tiempo_disponible_recepcion = Column(Integer)
    latitud = Column(Float)
    longitud = Column(Float)
    
    empresa = relationship("Empresa", back_populates="planta_detalles")


class Puerto(Base):
    __tablename__ = "puertos"
    
    id = Column(Integer, primary_key=True)
    nombre = Column(String(15))
    latitud = Column(Float)
    longitud = Column(Float)
    latitud = Column(Float)
    longitud = Column(Float)
    

class Operador(Base):
    __tablename__ = "operadores"
    
    id = Column(Integer, primary_key=True)
    nombre = Column(String(15))

                    
class InventarioPlanta(Base):
    __tablename__ = "plantas_inventarios"
    
    id = Column(Integer, primary_key=True)
    id_planta = Column(Integer, ForeignKey("plantas.id"))
    id_ingrediente = Column(Integer, ForeignKey("ingredientes.id"))
    id_periodo = Column(Integer, ForeignKey("periodos.id"))
    capacidad = Column(Integer)
    consumo = Column(Integer)
    costo_backorder = Column(Integer)
    safety_stock = Column(Integer)
    objetivo = Column(Integer)
    llegada_planeada = Column(Integer)
    inventario_al_cierre = Column(Integer)

    planta = relationship("Planta", back_populates="plantas_inventarios")
    ingrediente = relationship("Ingrediente", back_populates="plantas_inventarios")
    periodo = relationship("Periodo", back_populates="plantas_inventarios")


class Importacion(Base):
    __tablename__ = "importaciones"
    
    id = Column(Integer, primary_key=True)
    codigo = Column(String(25))
    id_ingrediente = Column(Integer, ForeignKey("ingredientes.id"))
    id_empresa = Column(Integer, ForeignKey("empresas.id"))
    id_puerto = Column(Integer, ForeignKey("puertos.id"))
    id_operador = Column(Integer, ForeignKey("operadores.id"))
    fecha_llegada = Column(Date)
    inventario_inicial = Column(Integer)

    ingrediente = relationship("Ingrediente", back_populates="importaciones")
    empresa = relationship("Empresa", back_populates="importaciones")
    operador = relationship("Operador", back_populates="importaciones")


class InventarioPuerto(Base):
    __tablename__ = "puerto_inventarios"
    
    id = Column(Integer, primary_key=True)
    id_importacion = Column(Integer, ForeignKey("importaciones.id"))
    id_periodo = Column(Integer, ForeignKey("periodos.id"))
    costo_almacenamiento = Column(Float)
    costo_bodegaje = Column(Float)
    llegada_planeada = Column(Integer)
    inventario_al_cierre = Column(Integer)

    importacion = relationship("Importacion", back_populates="puerto_inventarios")
    periodo = relationship("Periodo", back_populates="puerto_inventarios")   


class Despachos(Base):
    __tablename__ = "despachos"     
    id = Column(Integer, primary_key=True)
    id_importacion = Column(Integer, ForeignKey("importaciones.id"))
    id_planta = Column(Integer, ForeignKey("plantas.id"))
    id_periodo_despacho = Column(Integer, ForeignKey("periodos.id"))
    id_periodo_llegada = Column(Integer, ForeignKey("periodos.id"))
    costo_flete = Column(Float)
    costo_directo = Column(Float)
    costo_intercompany = Column(Float)
    tiempo_recepcion = Column(Integer)    
    cantidad_camiones = Column(Integer)

    importacion = relationship("Importacion", back_populates="despachos")
    planta = relationship("Planta", back_populates="despachos")
    perido_despacho = relationship("Periodo", back_populates="despachos")
    periodo_llegada = relationship("Periodo", back_populates="despachos")

Base.metadata.create_all(engine)
