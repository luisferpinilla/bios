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

CREATE TABLE IF NOT EXISTS objetivos_inventario
(
	id INT AUTO_INCREMENT PRIMARY KEY,
	id_archivo INT NOT NULL,
	id_planta INT NOT NULL,
	id_ingrediente INT NOT NULL,
	objetivo INT NOT NULL,
	kilogramos INT NOT NULL,
	UNIQUE (id_archivo, id_planta, id_ingrediente),
	FOREIGN KEY (id_archivo) REFERENCES archivos(id),
	FOREIGN KEY (id_planta) REFERENCES plantas(id),
	FOREIGN KEY (id_ingrediente) REFERENCES ingredientes(id)
);

-- Lista de vistas

-- Productos con nivel de seguridad pero sin consumo
CREATE VIEW ingredientes_sin_consumo_y_con_ss AS
SELECT pl.nombre AS nombre_planta, 
	ing.nombre AS ingrediente, 
    ifnull(ss.dias_safety_stock, 0) as SS, 
    sum(cp.consumo_kg) as total_consumo 
FROM consumo_proyectado cp
LEFT JOIN plantas pl ON cp.id_planta = pl.id
LEFT JOIN ingredientes ing ON cp.id_ingrediente = ing.id
LEFT JOIN safety_stocks ss ON ss.id_ingrediente = ing.id AND ss.id_planta = cp.id 
GROUP BY nombre_planta, ingrediente, SS
HAVING total_consumo = 0 AND SS > 0;



-- Inventario realmente en transito hacia el puerto
CREATE VIEW inventario_en_transito_view AS
SELECT i.id_archivo,
	i.id_empresa,
	e.nombre AS Empresa,
	i.id_puerto ,
	p.nombre AS Puerto,
	i.id_operador,
	o.nombre AS Operador,
	i.id_ingrediente,
	i2.nombre AS Ingrediente, 
	i.importacion,
	tp.fecha_descarge AS fecha_llegada,
	i.valor_kg ,
	tp.cantidad  AS cantidad_puerto_kg,
	'transito' AS Status
FROM transitos_puerto tp 
JOIN importaciones i ON i.id = tp.id_importacion
JOIN empresas e ON e.id=i.id_empresa 
JOIN puertos p ON p.id=i.id_puerto 
JOIN operadores o ON o.id=i.id_operador 
JOIN ingredientes i2 ON i2.id=i.id_ingrediente
HAVING tp.fecha_descarge > (SELECT DATE_SUB(MIN(cp.fecha_consumo), INTERVAL 1 DAY) FROM consumo_proyectado cp);


-- Costos por despacho directo
CREATE VIEW costos_despacho_directo_view AS
SELECT 
    tp.id_importacion AS id_importacion, 
    tp.fecha_descarge AS fecha_descarge, 
    ROUND(34000*cp2.valor_kg) AS Directo
FROM transitos_puerto tp
LEFT JOIN importaciones i ON i.id=tp.id_importacion 
LEFT JOIN (SELECT * FROM costos_portuarios WHERE tipo_operacion='directo') cp2 ON cp2.id_operador = i.id_operador AND cp2.id_puerto = i.id_puerto AND cp2.id_ingrediente = i.id_ingrediente;

-- Costos fletes
CREATE VIEW costos_fletes_view AS
SELECT 
    i.id_archivo AS id_archivo,
    i.id AS id_importacion,
	i.id_empresa AS id_empresa,
	i.id_puerto AS id_puerto,
	i.id_operador AS id_operador,
	i.id_ingrediente AS id_ingrediente,
	i.importacion AS importacion,
	f.id_planta AS id_planta,
	i.fecha_llegada AS fecha_llegada,
	fechas.fecha_consumo AS Fecha,
	34000*f.valor_flete_kg AS Flete
FROM importaciones i 
LEFT JOIN fletes f ON f.id_puerto = i.id_puerto AND f.id_operador = i.id_operador AND f.id_ingrediente = i.id_ingrediente
CROSS JOIN (SELECT id_archivo, fecha_consumo FROM consumo_proyectado cp GROUP BY id_archivo, fecha_consumo) fechas ON i.id_archivo = fechas.id_archivo
ORDER BY id_archivo, id_ingrediente, importacion, id_puerto, id_operador , id_planta, Fecha;

-- Costo total despacho por camion
CREATE VIEW costo_total_despacho AS
SELECT cfv.id_archivo,
	cfv.id_importacion,
	cfv.id_empresa,
	cfv.id_puerto,
	cfv.id_operador,
	cfv.id_ingrediente,
	cfv.importacion,
	cfv.id_planta,
	cfv.fecha_llegada,
	cfv.Fecha,
	cfv.Flete,
	cddv.Directo,
	(IFNULL(cddv.Directo,0.0)+cfv.flete) AS Costo_Total_Despacho
FROM costos_fletes_view cfv
LEFT JOIN costos_despacho_directo_view cddv ON cddv.id_importacion = cfv.id_importacion;

-- Costos de almacenamiento en puerto por corte de inventario
CREATE VIEW costo_total_almacenamiento AS
SELECT 
	data.id_archivo as id_archivo,
    data.id_importacion AS id_importacion, 
	data.fecha AS fecha, 
	SUM(data.valor_kg) as costo_kg FROM 
		(SELECT 
			i.id_archivo AS id_archivo,
			cap.id_importacion AS id_importacion, 
			cap.fecha_cobro AS fecha, 
			ROUND(cap.valor_a_cobrar_kg) AS valor_kg,
			'corte' as causa
		FROM costos_almacenamiento_puerto cap
        LEFT JOIN importaciones i ON i.id=cap.id_importacion
		UNION ALL
		SELECT 
			i.id_archivo AS id_archivo,
			id_importacion , 
			MAX(fecha_descarge) AS fecha,
			ROUND(i.valor_kg) AS valor_kg,
			'bodegaje' AS causa
		FROM transitos_puerto tp
		LEFT JOIN importaciones i ON i.id = tp.id_importacion
		GROUP BY id_importacion
		ORDER BY id_importacion, fecha) data 
GROUP BY id_archivo, id_importacion, fecha;

-- Importaciones no despachables
CREATE VIEW importaciones_no_despachables AS
SELECT 
	i.id_archivo,
	i.id_empresa,
	i.id_puerto ,
	i.id_operador, 
	i.id_ingrediente,
	i.importacion,
	ROUND(i.cantidad_puerto_kg) as cantidad_puerto_kg,
	i.valor_kg,
	IFNULL(SUM(tp.cantidad),0.0) AS cantidad 
FROM importaciones i 
LEFT JOIN transitos_puerto tp ON i.id = tp.id_importacion
GROUP BY i.id_archivo, i.id_empresa, i.id_puerto , i.id_operador, i.id_ingrediente, i.importacion
HAVING cantidad_puerto_kg < 34000 AND cantidad = 0;  

-- Importaciones activas
CREATE VIEW importaciones_despachables AS
SELECT 
	i.id_archivo,
	i.id_empresa,
	i.id_puerto ,
	i.id_operador, 
	i.id_ingrediente,
	i.importacion,
	ROUND(i.cantidad_puerto_kg) as cantidad_puerto_kg,
	i.valor_kg,
	IFNULL(SUM(tp.cantidad),0.0) AS cantidad 
FROM importaciones i 
LEFT JOIN transitos_puerto tp ON i.id = tp.id_importacion
GROUP BY i.id_archivo, i.id_empresa, i.id_puerto , i.id_operador, i.id_ingrediente, i.importacion
HAVING cantidad_puerto_kg > 34000 OR cantidad > 34000;  