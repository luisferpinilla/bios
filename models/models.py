# coding: utf-8
import db

from sqlalchemy import Column, DECIMAL, Date, Enum, Float, ForeignKey, Index, Integer, String, TIMESTAMP, text
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()
# metadata = Base.metadata


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
    __table_args__ = (
        Index('id_operador', 'id_operador', 'id_puerto',
              'id_ingrediente', 'tipo_operacion', unique=True),
    )

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
    __table_args__ = (
        Index('id_archivo', 'id_archivo', 'id_empresa', 'id_puerto',
              'id_operador', 'id_ingrediente', 'importacion', unique=True),
    )

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
    __table_args__ = (
        Index('id_empresa_origen', 'id_empresa_origen',
              'id_empresa_destino', unique=True),
    )

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
    __table_args__ = (
        Index('id_archivo', 'id_archivo', 'id_planta',
              'id_ingrediente', 'fecha_consumo', unique=True),
    )

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
    __table_args__ = (
        Index('id_importacion', 'id_importacion', 'fecha_cobro', unique=True),
    )

    id = Column(Integer, primary_key=True)
    id_importacion = Column(ForeignKey('importaciones.id'), nullable=False)
    fecha_cobro = Column(Date, nullable=False)
    valor_a_cobrar_kg = Column(DECIMAL(10, 2), nullable=False)

    importacione = relationship('Importacione')


class Flete(Base):
    __tablename__ = 'fletes'
    __table_args__ = (
        Index('id_puerto', 'id_puerto', 'id_operador',
              'id_ingrediente', 'id_planta', unique=True),
    )

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
    __table_args__ = (
        Index('id_planta', 'id_planta', 'id_ingrediente', unique=True),
    )

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
    __table_args__ = (
        Index('id_planta', 'id_planta', 'id_ingrediente', unique=True),
    )

    id = Column(Integer, primary_key=True)
    id_planta = Column(ForeignKey('plantas.id'), nullable=False)
    id_ingrediente = Column(ForeignKey('ingredientes.id'),
                            nullable=False, index=True)
    tiempo_minutos = Column(Integer, nullable=False)

    ingrediente = relationship('Ingrediente')
    planta = relationship('Planta')


class TransitosPlanta(Base):
    __tablename__ = 'transitos_planta'
    __table_args__ = (
        Index('id_archivo', 'id_archivo', 'id_planta',
              'id_ingrediente', 'fecha_llegada', unique=True),
    )

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
    __table_args__ = (
        Index('id_importacion', 'id_importacion',
              'fecha_descarge', unique=True),
    )

    id = Column(Integer, primary_key=True)
    id_importacion = Column(ForeignKey('importaciones.id'), nullable=False)
    fecha_descarge = Column(Date, nullable=False)
    cantidad = Column(Integer, nullable=False,
                      server_default=text("'5000000'"))

    importacione = relationship('Importacione')


class Unidade(Base):
    __tablename__ = 'unidades'
    __table_args__ = (
        Index('id_archivo', 'id_archivo', 'id_planta',
              'id_ingrediente', 'nombre', unique=True),
    )

    id = Column(Integer, primary_key=True)
    id_archivo = Column(ForeignKey('archivos.id'), nullable=False)
    id_planta = Column(ForeignKey('plantas.id'), nullable=False, index=True)
    id_ingrediente = Column(ForeignKey('ingredientes.id'),
                            nullable=False, index=True)
    nombre = Column(String(10), nullable=False)
    capacidad = Column(Integer, nullable=False)
    inventario = Column(Integer, nullable=False)

    archivo = relationship('Archivo')
    ingrediente = relationship('Ingrediente')
    planta = relationship('Planta')


class ObjetivosInventario(Base):
    __tablename__ = 'objetivos_inventario'
    __table_args__ = (
        Index('id_archivo', 'id_archivo', 'id_planta', 'id_ingrediente', unique=True),
    )

    id = Column(Integer, primary_key=True)
    id_archivo = Column(ForeignKey('archivos.id'), nullable=False)
    id_planta = Column(ForeignKey('plantas.id'), nullable=False, index=True)
    id_ingrediente = Column(ForeignKey('ingredientes.id'), nullable=False, index=True)
    objetivo = Column(Integer, nullable=False)
    kilogramos = Column(Integer, nullable=False)

    archivo = relationship('Archivo')
    ingrediente = relationship('Ingrediente')
    planta = relationship('Planta')
