# coding: utf-8
from sqlalchemy import Column, DECIMAL, Date, Enum, ForeignKey, Index, Integer, String, TIMESTAMP, text
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()
metadata = Base.metadata


class Empresa(Base):
    __tablename__ = 'empresas'

    id = Column(Integer, primary_key=True)
    name = Column(String(15), nullable=False, unique=True)


class File(Base):
    __tablename__ = 'files'

    id = Column(Integer, primary_key=True)
    file_name = Column(String(255), nullable=False, unique=True)
    upload_date = Column(TIMESTAMP, nullable=False,
                         server_default=text("CURRENT_TIMESTAMP"))


class Ingrediente(Base):
    __tablename__ = 'ingredientes'

    id = Column(Integer, primary_key=True)
    name = Column(String(15), nullable=False, unique=True)


class Operador(Base):
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
    tipo_operacion = Column(Enum('directo', 'bodega'))


class Importacion(Base):
    __tablename__ = 'importaciones'
    __table_args__ = (
        Index('id_file', 'id_file', 'id_empresa', 'id_puerto',
              'id_operador', 'id_ingrediente', 'fecha_llegada', unique=True),
    )

    id = Column(Integer, primary_key=True)
    id_file = Column(ForeignKey('files.id'), nullable=False)
    id_empresa = Column(ForeignKey('empresas.id'), nullable=False, index=True)
    id_puerto = Column(ForeignKey('puertos.id'), nullable=False, index=True)
    id_operador = Column(ForeignKey('operadores.id'),
                         nullable=False, index=True)
    id_ingrediente = Column(ForeignKey('ingredientes.id'),
                            nullable=False, index=True)
    importacion = Column(String(50), nullable=False)
    cantidad_puerto_kg = Column(
        Integer, nullable=False, server_default=text("'0'"))
    fecha_llegada = Column(Date, nullable=False)


class Intercompany(Base):
    __tablename__ = 'intercompanies'
    __table_args__ = (
        Index('id_empresa_origen', 'id_empresa_origen',
              'id_empresa_destino', unique=True),
    )

    id = Column(Integer, primary_key=True)
    id_empresa_origen = Column(ForeignKey('empresas.id'))
    id_empresa_destino = Column(ForeignKey('empresas.id'), index=True)
    valor_intercompany = Column(DECIMAL(10, 8))


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


class ConsumoProyectado(Base):
    __tablename__ = 'consumo_proyectado'
    __table_args__ = (
        Index('id_file', 'id_file', 'id_planta',
              'id_ingrediente', 'fecha_consumo', unique=True),
    )

    id = Column(Integer, primary_key=True)
    id_file = Column(ForeignKey('files.id'), nullable=False)
    id_planta = Column(ForeignKey('plantas.id'), nullable=False, index=True)
    id_ingrediente = Column(ForeignKey('ingredientes.id'),
                            nullable=False, index=True)
    fecha_consumo = Column(Integer, nullable=False)


class CostosAlmacenamientoPuerto(Base):
    __tablename__ = 'costos_almacenamiento_puerto'
    __table_args__ = (
        Index('id_importacion', 'id_importacion', 'fecha_cobro', unique=True),
    )

    id = Column(Integer, primary_key=True)
    id_importacion = Column(ForeignKey('importaciones.id'), nullable=False)
    fecha_cobro = Column(Date, nullable=False)
    valor_a_cobrar_kg = Column(DECIMAL(10, 2), nullable=False)


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


class TiempoDescarguePlanta(Base):
    __tablename__ = 'tiempo_descargue_planta'
    __table_args__ = (
        Index('id_planta', 'id_planta', 'id_ingrediente', unique=True),
    )

    id = Column(Integer, primary_key=True)
    id_planta = Column(ForeignKey('plantas.id'), nullable=False)
    id_ingrediente = Column(ForeignKey('ingredientes.id'),
                            nullable=False, index=True)


class TransitosPlanta(Base):
    __tablename__ = 'transitos_planta'
    __table_args__ = (
        Index('id_file', 'id_file', 'id_planta',
              'id_ingrediente', 'fecha_llegada', unique=True),
    )

    id = Column(Integer, primary_key=True)
    id_file = Column(ForeignKey('files.id'), nullable=False)
    id_planta = Column(ForeignKey('plantas.id'), nullable=False, index=True)
    id_ingrediente = Column(ForeignKey('ingredientes.id'),
                            nullable=False, index=True)
    fecha_llegada = Column(Date, nullable=False)


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


class Unidade(Base):
    __tablename__ = 'unidades'

    id = Column(Integer, primary_key=True)
    id_planta = Column(ForeignKey('plantas.id'), nullable=False, index=True)
    nombre = Column(String(10), nullable=False)


class UnidadesIngrediente(Base):
    __tablename__ = 'unidades_ingredientes'
    __table_args__ = (
        Index('id_unidad', 'id_unidad', 'id_ingrediente', unique=True),
    )

    id = Column(Integer, primary_key=True)
    id_unidad = Column(ForeignKey('unidades.id'), nullable=False)
    id_ingrediente = Column(ForeignKey('ingredientes.id'),
                            nullable=False, index=True)
    capacidad = Column(Integer, nullable=False)


class InventarioPlanta(Base):
    __tablename__ = 'inventario_planta'
    __table_args__ = (
        Index('id_file', 'id_file', 'id_unidad_ingrediente', unique=True),
    )

    id = Column(Integer, primary_key=True)
    id_file = Column(ForeignKey('files.id'), nullable=False)
    id_unidad_ingrediente = Column(ForeignKey(
        'unidades_ingredientes.id'), nullable=False, index=True)
    inventario_kg = Column(Integer, nullable=False, server_default=text("'0'"))
