CREATE DATABASE IF NOT EXISTS bios;

USE bios;

CREATE TABLE IF NOT EXISTS empresas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(15) NOT NULL,
    UNIQUE (name)
);

CREATE TABLE IF NOT EXISTS intercompanies
(
    id_empresa_origen INT,
    id_empresa_destino INT,
    valor_intercompany DECIMAL(10, 8),
    PRIMARY KEY (id_empresa_origen,id_empresa_destino),
    FOREIGN KEY (id_empresa_origen) REFERENCES empresas(id),
    FOREIGN KEY (id_empresa_destino) REFERENCES empresas(id)
);

CREATE TABLE IF NOT EXISTS plantas
(
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(15) NOT NULL,
    latitude DECIMAL(10, 8) NULL,
    longitude DECIMAL(11, 8) NULL,
    id_empresa INT NOT NULL,
    FOREIGN KEY (id_empresa) REFERENCES empresas(id),
    UNIQUE (name)
);

CREATE TABLE IF NOT EXISTS unidades
(
    id INT AUTO_INCREMENT PRIMARY KEY,
    id_planta INT NOT NULL,
    name VARCHAR(10) NOT NULL,
    FOREIGN KEY (id_planta) REFERENCES plantas(id)
);

CREATE TABLE IF NOT EXISTS ingredientes
(
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(15) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS unidades_ingredientes
(
    id INT AUTO_INCREMENT PRIMARY KEY,
    id_unidad INT NOT NULL,
    id_ingrediente INT NOT NULL,
    capacidad INT NOT NULL,
    UNIQUE (id_unidad, id_ingrediente),
    FOREIGN KEY (id_unidad) REFERENCES unidades(id),
    FOREIGN KEY (id_ingrediente) REFERENCES ingredientes(id)
);

CREATE TABLE IF NOT EXISTS puertos
(
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(15) NOT NULL UNIQUE,
    latitude DECIMAL(10, 8) NULL,
    longitude DECIMAL(11, 8) NULL,
    capacidad_descarga_kg_dia INT NOT NULL DEFAULT 5000000
);

CREATE TABLE IF NOT EXISTS operadores
(
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(15) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS fletes
(
    id INT AUTO_INCREMENT PRIMARY KEY,
    id_puerto INT NOT NULL,
    id_operador INT NOT NULL,
    id_ingrediente INT NOT NULL,
    id_planta INT NOT NULL,
    valor_flete_kg INT NOT NULL, 
    UNIQUE (id_puerto, id_operador, id_ingrediente),
    FOREIGN KEY (id_puerto) REFERENCES puertos(id),
    FOREIGN KEY (id_operador) REFERENCES operadores(id),
    FOREIGN KEY (id_ingrediente) REFERENCES ingredientes(id),
    FOREIGN KEY (id_planta) REFERENCES plantas(id)
);

CREATE TABLE IF NOT EXISTS safety_stocks
(
	id_planta INT NOT NULL,
    id_ingrediente INT NOT NULL,
    dias_safety_stock INT NOT NULL DEFAULT 0,
    PRIMARY KEY(id_planta, id_ingrediente),
    FOREIGN KEY(id_planta) REFERENCES plantas(id),
    FOREIGN KEY(id_ingrediente) REFERENCES ingredientes(id)
); 

CREATE TABLE IF NOT EXISTS costos_portuarios
(
	id_operador INT NOT NULL,
    id_puerto INT NOT NULL,
    id_ingrediente INT NOT NULL,
    tipo_operacion ENUM('directo', 'bodega'),
    PRIMARY KEY(id_operador, id_puerto, id_ingrediente, tipo_operacion),
    FOREIGN KEY (id_operador) REFERENCES operadores(id),
    FOREIGN KEY (id_puerto) REFERENCES puertos(id),
    FOREIGN KEY (id_ingrediente) REFERENCES ingredientes(id)
); 

