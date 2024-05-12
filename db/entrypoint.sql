CREATE DATABASE IF NOT EXISTS bios;

USE bios;

CREATE TABLE IF NOT EXISTS empresas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(15) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS ingredientes
(
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(15) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS puertos
(
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(15) NOT NULL UNIQUE,
    latitude DECIMAL(10, 8) NULL,
    longitude DECIMAL(11, 8) NULL,
    capacidad_descarga_kg_dia INT NOT NULL DEFAULT 5000000
);

CREATE TABLE IF NOT EXISTS operadores
(
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(15) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS plantas
(
    id INT AUTO_INCREMENT PRIMARY KEY,
    id_empresa INT NOT NULL,
    nombre VARCHAR(15) NOT NULL UNIQUE,
    latitude DECIMAL(10, 8) NULL,
    longitude DECIMAL(11, 8) NULL,
    capacidad_recepcion_min_dia INT NOT NULL DEFAULT 0,
    tiempo_limpieza_min_dia INT NOT NULL DEFAULT 0,
    FOREIGN KEY (id_empresa) REFERENCES empresas(id)
);

CREATE TABLE IF NOT EXISTS intercompanies
(
    id INT AUTO_INCREMENT PRIMARY KEY,
    id_empresa_origen INT NOT NULL,
    id_empresa_destino INT NOT NULL,
    valor_intercompany DECIMAL(10, 8) NOT NULL,
    UNIQUE (id_empresa_origen,id_empresa_destino),
    FOREIGN KEY (id_empresa_origen) REFERENCES empresas(id),
    FOREIGN KEY (id_empresa_destino) REFERENCES empresas(id)
);

CREATE TABLE IF NOT EXISTS tiempo_descargue_planta
(
    id INT AUTO_INCREMENT PRIMARY KEY,
    id_planta INT NOT NULL,
    id_ingrediente INT NOT NULL,
    tiempo_minutos INT NOT NULL,
    UNIQUE(id_planta, id_ingrediente),
    FOREIGN KEY (id_planta) REFERENCES plantas(id),
    FOREIGN KEY (id_ingrediente) REFERENCES ingredientes(id)
);

CREATE TABLE IF NOT EXISTS archivos
(
	id INT AUTO_INCREMENT NOT NULL PRIMARY KEY,
    file_name VARCHAR(255) NOT NULL UNIQUE,
    upload_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    status ENUM('loaded', 'validated', 'unfeasible', 'sub_obtimal', 'optimal')
);

CREATE TABLE IF NOT EXISTS unidades
(
    id INT AUTO_INCREMENT PRIMARY KEY,
    id_archivo INT NOT NULL,
    id_planta INT NOT NULL,
    id_ingrediente INT NOT NULL,
    nombre VARCHAR(10) NOT NULL,    
    capacidad INT NOT NULL,
    inventario INT NOT NULL,
    UNIQUE (id_archivo, id_planta,id_ingrediente,nombre),
    FOREIGN KEY (id_archivo) REFERENCES archivos(id),
    FOREIGN KEY (id_planta) REFERENCES plantas(id),
    FOREIGN KEY (id_ingrediente) REFERENCES ingredientes(id)
);

CREATE TABLE IF NOT EXISTS fletes
(
    id INT AUTO_INCREMENT PRIMARY KEY,
    id_puerto INT NOT NULL,
    id_operador INT NOT NULL,
    id_ingrediente INT NOT NULL,
    id_planta INT NOT NULL,
    valor_flete_kg INT NOT NULL, 
    UNIQUE (id_puerto, id_operador, id_ingrediente, id_planta),
    FOREIGN KEY (id_puerto) REFERENCES puertos(id),
    FOREIGN KEY (id_operador) REFERENCES operadores(id),
    FOREIGN KEY (id_ingrediente) REFERENCES ingredientes(id),
    FOREIGN KEY (id_planta) REFERENCES plantas(id)
);

CREATE TABLE IF NOT EXISTS safety_stocks
(
    id INT AUTO_INCREMENT PRIMARY KEY,
	id_planta INT NOT NULL,
    id_ingrediente INT NOT NULL,
    dias_safety_stock INT NOT NULL DEFAULT 0,
    UNIQUE(id_planta, id_ingrediente),
    FOREIGN KEY(id_planta) REFERENCES plantas(id),
    FOREIGN KEY(id_ingrediente) REFERENCES ingredientes(id)
); 

CREATE TABLE IF NOT EXISTS costos_portuarios
(
    id INT AUTO_INCREMENT PRIMARY KEY,
	id_operador INT NOT NULL,
    id_puerto INT NOT NULL,
    id_ingrediente INT NOT NULL,
    tipo_operacion ENUM('directo', 'bodega') NOT NULL,
    valor_kg DECIMAL(10, 8) NOT NULL,
    UNIQUE(id_operador, id_puerto, id_ingrediente, tipo_operacion),
    FOREIGN KEY (id_operador) REFERENCES operadores(id),
    FOREIGN KEY (id_puerto) REFERENCES puertos(id),
    FOREIGN KEY (id_ingrediente) REFERENCES ingredientes(id)
); 

CREATE TABLE IF NOT EXISTS consumo_proyectado
(
    id INT AUTO_INCREMENT PRIMARY KEY,
    id_archivo INT NOT NULL,
    id_planta INT NOT NULL,
    id_ingrediente INT NOT NULL,
    fecha_consumo DATE NOT NULL,
    consumo_kg double NOT NULL,
    UNIQUE(id_archivo, id_planta, id_ingrediente, fecha_consumo),
    FOREIGN KEY (id_archivo) REFERENCES archivos(id),
    FOREIGN KEY (id_planta) REFERENCES plantas(id),
    FOREIGN KEY (id_ingrediente) REFERENCES ingredientes(id)
);

CREATE TABLE IF NOT EXISTS transitos_planta
(
    id INT AUTO_INCREMENT PRIMARY KEY,
    id_archivo INT NOT NULL,
    id_planta INT NOT NULL,
    id_ingrediente INT NOT NULL,
    fecha_llegada DATE NOT NULL,
    cantidad INT NOT NULL,
    UNIQUE(id_archivo, id_planta, id_ingrediente, fecha_llegada),
    FOREIGN KEY (id_archivo) REFERENCES archivos(id),
    FOREIGN KEY (id_planta) REFERENCES plantas(id),
    FOREIGN KEY (id_ingrediente) REFERENCES ingredientes(id)
);

CREATE TABLE IF NOT EXISTS importaciones
(
	id INT AUTO_INCREMENT PRIMARY KEY,
	id_archivo INT NOT NULL,
    id_empresa INT NOT NULL,
    id_puerto INT NOT NULL,
    id_operador INT NOT NULL,
    id_ingrediente INT NOT NULL,
    importacion VARCHAR(50) NOT NULL,
    fecha_llegada DATE NOT NULL,
    cantidad_puerto_kg INT NOT NULL DEFAULT 0,
    valor_kg DECIMAL(10,2) NOT NULL,
    UNIQUE(id_archivo, id_empresa, id_puerto, id_operador, id_ingrediente, importacion),
    FOREIGN KEY (id_archivo) REFERENCES archivos(id),
    FOREIGN KEY (id_empresa) REFERENCES empresas(id),
    FOREIGN KEY (id_puerto) REFERENCES puertos(id),
    FOREIGN KEY (id_operador) REFERENCES operadores(id),
    FOREIGN KEY (id_ingrediente) REFERENCES ingredientes(id)
);

CREATE TABLE IF NOT EXISTS transitos_puerto
(
    id INT AUTO_INCREMENT PRIMARY KEY,
	id_importacion INT NOT NULL,
    fecha_descarge DATE NOT NULL,
    cantidad INT NOT NULL DEFAULT 5000000,
    UNIQUE (id_importacion, fecha_descarge),
    FOREIGN KEY (id_importacion) REFERENCES importaciones(id)
);

CREATE TABLE IF NOT EXISTS costos_almacenamiento_puerto
(
    id INT AUTO_INCREMENT PRIMARY KEY,
	id_importacion INT NOT NULL,
    fecha_cobro DATE NOT NULL,
    valor_a_cobrar_kg DECIMAL(10,2) NOT NULL,
    UNIQUE(id_importacion, fecha_cobro),
    FOREIGN KEY (id_importacion) REFERENCES importaciones(id)
);
