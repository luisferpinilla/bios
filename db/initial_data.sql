USE bios;

INSERT INTO empresas(id, name) VALUES
(1, 'contegral'),
(2, 'finca');

INSERT INTO intercompanies(id_empresa_origen,id_empresa_destino,valor_intercompany)
VALUES
(1,2, 0.00002330),
(2,1, 0.00004720),
(1,1, 0.00000000),
(2,2, 0.00000000);

INSERT INTO plantas(id, name, id_empresa) VALUES
(1, 'envigado', 1),
(2, 'cartago', 1),
(3, 'neiva', 1),
(4, 'bogota', 1),
(5, 'launion', 1),
(6, 'barbosa', 1),
(7, 'ibague', 1),
(8, 'mosquera', 2),
(9, 'buga', 2),
(10,'itagui', 2),
(11, 'bmanga', 2),
(12, 'cienaga', 2),
(13, 'pimpollo', 2);

INSERT INTO ingredientes(id, name)
VALUES
(1, 'maiz'),
(2, 'tsoya'),
(3,'destilado'),
(4, 'gluten'),
(5, 'destiladohp'),
(6, 'forraje'),
(7, 'cascarilla'),
(8, 'frijol'),
(9, 'tgirasol'),
(10, 'trigo');