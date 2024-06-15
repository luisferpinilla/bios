from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, Float

Base = declarative_base()

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
    nombre = Column(String(15))
    id_empresa = int

class Puerto(Base):
    __tablename__ = "puertos"
    id = Column(Integer, primary_key=True)
    nombre = Column(String(15))
    latitud = Column(Float)
    longitud = Column(Float)

