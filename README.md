# Modelo matemático

## Abstract

El presente documento contiene el modelo matemático de programación lineal mixta que describe la situación de almacenamiento, transporte y demanda de macro ingredientes para la compañia Grupo BIOS.

## Contexto del problema

Grupo BIOS es un grupo de empresas dedicadas a la fabricación de productos agrícolas destinados a diferentes propósitos. Para efectos de dicha fabricación emplea varias materias primas que son procesadas en 13 plantas al interior de Colombia y que tienen origen en el extranjero.

Dado el origen de las materias primas, surgen una serie de operaciones logísticas para colocarlas en las plantas con sus correspondientes costos y restricciones asociadas.

El modelo matemático descrito a continuación ayudará como herramienta a un usuario experto en la operación de Grupo BIOS a configurar la mejor decision logística partiendo de la información disponible y suministrada, y que de acuerdo con los entendimientos durante las reuniones del equipo de trabajo, conduce hacia obtener el menor costo logistico durante un periodo dado. Dicha decision está asociada específicamente con determinar:

- La cantidad de materias primas a almacenar en puerto de acuerdo con la información de barcos pendientes por llegar y las cargas actualmente almacenadas a los puertos;
- la cantidad de materias primas a despachar y el momento para hacerlo entre los puertos y las 13 plantas y la planta a donde llegarán estas cargas;
- En una segunda fase, las unidades de almacenamiento desde donde deberán consumirse las materias primas de acuerdo con la demanda proyectada de consumo que el usuario experto suministre.

El modelo matemático no tendrá como objetivo responder a preguntas o cuestiones adicionales relacionandas con otras decisiones o aspectos, por ejemplo:

- la cantidad de materias primas a comprar;
- la cantidad de materias primas a consumir para fabricar el producto terminado;
- la forma como se mezclarán las materias primas en las plantas;
- los esquemas de negociación de tarifas de almacenamiento, transporte;
- ni ningún otro aspecto del negocio que no haya sido explícitamente discutido, aprobado y costeado por parte de WA Solutions, Esteban Restrepo y Luis Fernando Pinilla.

## Conceptualización de la solución

El modelo matemático que se ha identificado como el más adecuado para aproximar una solución que ayuda al usuario a configurar la solución descrita, corresponde a un modelo de optimización para flujo en redes con nodos y arcos, que incluye el tiempo como parámetro enriquecido y restricciones conmutables usando variables binarias. 

En general, cada nodo abstrae la cantidad de inventario de un ingrediente particular en un periodo y lugar específico de la cadena de suministro que se ha incluído en el modelo y los arcos representan traslado de dicho inventario entre los nodos, lo anterior teniendo en cuenta en todo momento los balances de masa.

Esquemáticamente, el flujo de material sin tener en cuenta el tiempo, puede representarse de la siguiente manera:

```mermaid
graph LR;
    id0((Barco)) --Descarga--> id1[Bodega en Puerto]
    id0((Barco)) --Despacho Directo--> id2[Planta]
    id1[Bodega en Puerto] --Despacho hacia planta--> id2[Planta]
    id2[Unidad de Almacenamiento] --> id3((Consumo))
    id4((Transitos)) ----> id2[Planta]
```

El modelo Tendrá una segunda fase donde se determinará a qué unidad de almacenamiento deberá llegar el ingrediente despachado desde los puertos y de qué manera deberá distribuirse el consumo que se ha proyectado.

# Modelo matemático

Los modelos matemáticos son conjuntos de expresiones matemáticas relacionadas entre si que describen un sistema y permiten efectuar cálculos con el fin de encontrar una alternativa que optimiza la manera de alcanzar un objetivo mientras que se satisfacen una serie de restricciones que representan aspectos puntuales del sistema.

El sistema que se pretende modelar ha sido descrito por el personal de Grupo BIOS durante sesiones de trabajo con el equipo de WA Solutions, quien ha construido el modelo a partir de la interpretación resultante en cada sesión de trabajo.

Las expresions matemáticas son construidas usando variables, conjuntos y parámetros, que serán descritos a continuación.

## Conjuntos, parámetros y variables

### Sets:

El modelo tiene una granularidad diaria, los días en el horizonte de planeación definido constituye el conjunto de periodos.

$T$ : día, $i \in \{1,2,3,...,30\}$

Las empresas involucradas en la operación son Contegral y Finca. La importancia de este conjunto radica en hay un costo relevante de "venta" de material entre una y otra cuando sea necesario.

$E$ : Empresas, $e \in \{Contegral, Finca\}$

Los ingredientes que serán almacenados en distintos puntos de la cadena de suministro relevante al modelo componen el conjunto de ingredientes.

$I$ : Ingredientes, $i \in \{Maiz, Harina, ...\}$

Los operadores están ubicados en los puertos y son los encoargardos de manejar la carga. Cada uno de los operadores están ubicados en un puerto, lo que permite relacionarlos con las tablas de fletes de transporte.

$J$ : Operadores, $j \in \{compasbun, compastlu, compasstm, ...\}$

La agrupación entre una empresa, un operador, un ingrediente y la identificación de una importación permiten individualizar una carga, desde donde se pueden obtener atributos como la cantidad de producto pendiente por llegar a puerto o, almacenada en bodega en el mismo.

$L$ : Cargas, $l \in \{1,2,3,..\}, j \in J, i \in I, e \in E$

Las 13 plantas distribuidas al interior del país y que consumen los macro ingredientes del conjunto ya descrito, y que son el destino para el cálculo de los costos de transporte, además de totalizar la capacidad de almacenamiento y requerir inventarios de seguridad, constituyen el conjunto de plantas.

$K$ : Plantas $k \in E$ 

Las unidades de almacenamiento que se encuentran en las plantas y que tienen una capacidad en toneladas por cada ingrediente conforman el conjunto de unidades de almacenamiento. Desde estas unidades se descontará el inventario con base en la demanda diaria entregada por Grupo BIOS. Adicionalmente estas pueden contener diferentes tipos de producto según se ha descrito y la suma de sus contenidos conforman el inventario del ingrediente en la planta y, que deberá interactuar con las capacidades máximas de almacenamiento e inventarios de seguridad.

$M$ : Unidades de Almacenamiento $m \in \{1,2,3...\}$

### Parametros

Los parámetros son valores encontrados dentro de la información suministrada por el usuario cada vez que requiere evaluar una alternativa de despacho. Estos se asocian a diferentes aspectos del negocio y deben ser verificados y suministrados por Grupo BIOS antes de ejecutar la aplicación.  la lista de parámetros para efectos del modelo explican a continuación:

#### Parámetros asociados a almacenamiento en puerto

$IP_{l}$ : inventario inicial en puerto para la carga $l$.

$AR_{l}^{t}$ : Cantidad de material que va a llegar a la carga $l$ durante el día $t$, sabiendo que: $material \in I$ y $carga \in J$.

$CC_{l}^{t}$ : Costo de almacenamiento de la carga $l$ por tonelada a cobrar al final del día $t$ en el puerto $J$.

$CB$ : Costo de la Operación portuaria por tonelada llevada a bodega en puerto

#### Parámetros asociados al transporte entre puertos y plantas

$CF_{lm}$ : Costo fijo de transporte por camión despachado llevando la carga $l$ hasta la planta.

$CV_{lm}$ : Costo de transporte por tonelada despachada de la carga $l$ hasta la planta.

$CW_{lm}$ : Costo de vender una carga perteneciente a una empresa a otra.

$CD$ : Costo de la operación porturaria por tonelada despachada de manera directa

#### Parámetros asociados a la operación en planta

$CA_{m}^{i}$ : Capacidad de almacenamiento de la unidad $m$ en toneladas del ingrediente $i$, tenendo en cuenta que $m \in K$.

$II_{m}^{i}$ : Inventario inicial del ingrediente $i$ en la unidad $m$, teniendo en cuenta que $m \in K$

$DM_{ki}^{t}$: Demanda o consumo proyectado del ingrediente $i$ en la planta $k$ durante el día $t$.

$SS_{ik}^{t}$ : Inventario de seguridad a tener del ingrediente $i$ en la planta $k$ al final del día $t$.

$TR_{im}^{t}$ : Cantidad en tránsito programada para llegar a la unidad de almacenamiento $m$ durante el día $t$

#### Parámetros base para penalización

Para efectos de hacer operativo el funcionamiento de las penalizaciones, vamos a definir un número 'grande' con respecto al cual se priorizarán estos aspectos.

$$ BigM = 100000 $$

$CK_{ik}^{t}$ : Costo del backorder del ingrediente $i$  en la planta $k$ durante el día $t$. Esta relacionado con BigM al 100%

$CS_{ik}^{t}$ : Costo de no satisfacer el inventario de seguridad para el ingrediente $i$ en la planta $k$ durante el día $t$. Esta relacionado con BigM al 50%

$CL_{ik}^{t}$ : Costo de no satisfacer el inventario objetivo del ingrediente $i$ en la planta $k$ durante el día $t$. Esta relacionado con BigM al 25%. 

Por definición, el inventario objetivo estará dado por la siguiente expresión:

Inventario Objetivo = (Inventario en puertos + Transito hacia planta + inventario en planta)/Consumo Promedio Ingrediente

$CX_{ik}^{t}$ : Costo de no alcanzar la capacidad máxima del ingrediente $i$ en la planta $k$ durante el día $t$. Esta relacionado con BigM al 5%

### Variables

Las variables son los elementos matemáticos que se asocian con la decisión a tomar y tienen relación directa con los parámetros y los conjuntos descritos anteriormente. A continuación, se detalla el diagrama de red para los inventarios 

```mermaid
graph LR;

    id0((Barco)) --AR--> id1{bif}
    id1{bif} --XPL--> id2[Bodega en Puerto]
    id3((Transitos)) --TR--> id4[Planta]
    id1{bif} --ITD--> id4[Planta]
    id2[Bodega en Puerto] --ITR--> id4[Planta]
    id2[Bodega en Puerto] --XIP--> id2[Bodega en Puerto]
    id4[Planta] --XIU--> id4[Planta]
    id4[Planta] --XDM-->id5((Consumo))
```

A continuación se describe la lista de variables:

#### Variables asociadas al almacenamiento en puerto

$XPL_{l}^{t}$ : Cantidad de la carga $l$ que llega al puerto y que será almacenada en el mismo. 

$XIP_{j}^{t}$ : Cantidad de la carga $l$ en puerto al final del periodo $t$

#### Variables asociadas al transporte entre puertos y plantas

$ITR_{lm}^{t}$ : Cantidad de camiones con carga $l$ en puerto a despachar hacia la unidad $m$ durante el día $t$

$ITD_{lm}^{t}$ : Cantidad de camiones con carga $l$ a despachar directamente hacia la unidad $m$ durante el día $t$

#### Variables asociadas a la operación en planta

$XIU_{mi}^{t}$ : Cantidad de ingrediente $i$ almacenado en la unidad de almacenameinto $m$ al final del periodo $t$

$XBK_{ik}^{t}$: Cantidad de backorder del ingrediente $i$ en planta $k$ luego de no cumplir la demanda  del día $t$.

$BSS_{ik}^{t}$ : Binaria, si se cumple que el inventario del ingrediente $i$ en la planta $k$ al final del día $t$ esté por encima del nivel de seguridad $SS_{ik}^{t}$

$BLV_{ik}^{t}$ : Binaria, si se cumple que el inventario del ingrediente $i$ en la planta $k$ al final del día $t$ esté por encima del nivel objetivo $CL_{ik}^{t}$

$BMX_{ik}^{t}$ : Binaria, si se cumple que el inventario del ingrediente $i$ en la planta $k$ al final del día $t$ esté al nivel máximo de capacidad $CX_{ik}^{t}$

## Función Objetivo:

La función objetivo es el criterio general que toma el solucionador del modelo para seleccionar la mejor decisión que cumple con todas las restricciones. 

Para efectos del problema, se ha definido que esta función esta relacionada con los costos totales causados al final del horizonte de planeación. Estos costos son el resultado del cobro por almacenamiento en puerto durante los cortes de facturación para cada carga y, los costos de transporte causados para despachar la carga desde el puerto a la planta según la tabla de fletes suministrada.

### Costos por operaciones portuarias

En el momento en el que el barco ha atracado en el terminal y está siendo descargado, la operación tendrá un costo por tonelada descargada que depende de si el ingrediente que está siendo descargado se pone en un camión con destino a una planta o si se lleva a una bodega de almacenamiento.

```mermaid
graph LR;

    id0((Barco)) --> id1{bif}
    id1{bif} --34000*CB*XPL--> id2[Bodega en Puerto]
    id1{bif} --CD*ITR--> id4[Planta]
```

#### Costo de operación porturaria por descargar el barco directamente sobre un camión

Este costo se adicionará al valor pagado al flete hasta la planta

$$ \sum_{l \in j}\sum_{m \in E}{34000\cdot CD \cdot ITD_{lm}^{t}} \forall t \in T$$ 

#### Costo de operación porturaria por descargar el barco y llevar el producto a bodega en puerto 

$$ \sum_{l \in j}\sum_{m \in E}{PA \cdot XPL_{lm}^{t}} \forall t \in T$$


#### Almacenamiento en puerto por corte de Facturación:

Dado que las cargas almacenadas en el puerto causan un costo de almacenamiento que suma al costo total, la suma de los productos escalares entre el costo de almacenamiento colocado a cada carga $l$ en el tiempo y la cantidad almacenada al final del día $t$, nos dará el componente del costo del almacenamiento en el puerto.

```mermaid
graph LR;
    id1{bif} --> id2[Bodega en Puerto]
    id2[Bodega en Puerto] --CC*XIP--> id2[Bodega en Puerto]
```

$$\sum_{l \in j}{\sum_{t \in T}{CC_{l}^{t} \cdot XIP_{l}^{t}}}$$

### Costos por transporte terrestre

```mermaid
graph LR;
    id1{bif} --> id2[Bodega en Puerto]
    id1{bif} --ITD--> id4[Planta]
    id2[Bodega en Puerto] --ITR--> id4[Planta]
```

#### Costo variable de transportar cargas desde puertos hacia plantas

Existe una tabla de fletes que muestra el costo por tonelada a enviar desde plantas hacia los puertos. dado que no esta definido el costo desde una carga en particular en un puerto hacia una unidad de almacenamiento, asumiremos que el costo de despacho de carga entre puertos y fábricas se puede aplicar de esta manera.

$$ \sum_{l \in j}{\sum_{m \in k}{\sum_{t}{34000 \cdot CV_{lm}(ITR_{lm}^{t} + ITD_{lm}^{t})}}}$$

#### Costo fijo de transportar un camion desde puerto hacia plantas

Aunque las negociaciones están dadas por toneada transportada de manera terrestre entre el origen y destino, existe la posibilidad que en el futuro se decida agregar algun costo fijo asociado al despacho por camión.

$$ \sum_{l \in j}{\sum_{l \in E }\sum_{t}{CF_{lm}(ITR_{lm}^{t} + ITD_{lm}^{t})}}$$

#### Costo por venta intercompañia

Es el costo causado cuando una compañia vende a la otra la carga que tiene en puerto. Se ha definido como un porcentaje sobre el valor de la carga

$$ \sum_{l \in j}{\sum_{m \in k}{\sum_{t}{34000 \cdot CW_{lm} \cdot CC_{lm} (ITR_{lm}^{t} + ITD_{lm}^{t})}}}$$

### Costos por Penalización

Los costos por penalización son elementos matemáticos empleados para tratar con restricciones blandas, de modo que es posible para el solucionador permitir que ciertas restricciones no se cumplan y se garantice la factibilidad del la solución.

A continuación, se describen las restricciones que por la naturaleza del negocio podrán no cumplirse: 

#### Costo de Backorder en planta

Cuando el inventario en planta en todas las unidades de almacenamiento no llega a ser suficiente para satisfacer la demanda, se genera un backorder, éste último se penaliza en la función objetivo de modo que si bien no se cumple la demanda, se garantiza que se use todo el inventario para cumplir la mayor parte de ella.

$$ \sum_{i}{\sum_{k}{\sum_{t}{CK_{ik}^{t} \cdot XBK_{ik}^{t}}}} $$

#### Costo de no respetar un inventario de seguridad de un ingrediente en una planta

El solucionador del modelo intentará en todo momento garantizar que todas las plantas mantengan el nivel de inventario sobre el nivel de seguridad. Sin embargo, cuando un ingrediente esta escaso, como primera contingencia se permitirá que el nivel de ingredientes baje por debajo de dicho nivel. El usuario será alertado de esta situación para el momento cuando se prevee que ocurrirá

$$ \sum_{i}{\sum_{k}{\sum_{t}{CS_{ik}^{t} \cdot BSS_{ik}^{t}}}} $$

#### Costo de no respetar el inventario objetivo de un ingrediente en una planta

El solucionador del modelo intentará en todo momento y luego evitar el backorder o no respetar los inventarios de seguridad, mantener el inventario al final del día sobre el nivel objetivo

$$ \sum_{i}{\sum_{k}{\sum_{t}{CL_{ik}^{t} \cdot BSS_{ik}^{t}}}} $$

#### Costo de no alcanzar el inventario máximo de un ingrediente en una planta

El solucionador del modelo intentará como última prioridad mantener el inventario al final del día sobre el cerca del máximo.

$$ \sum_{i}{\sum_{k}{\sum_{t}{CX_{ik}^{t} \cdot BSS_{ik}^{t}}}} $$

## Restricciones

### Balances de masa de inventarios

#### Balance de masa en cargas en puerto

Dado que las cargas pueden ir directamente desde el Barco a una unidad de almacenamiento, necesitamos colocar un bunto de bifurcación 'bif' y armar un balance de masa en este punto.

```mermaid
graph LR;

    id0((Barco)) --AR--> id1{bif}
    id1{bif} --34000*XPL--> id2[Bodega en Puerto]
    id1{bif} --ITD--> id4[Unidad de Almacenamiento]
```

$$ AR_{l}^{t} = XPL_{l}^{t} + \sum_{m \in M}{34000 \cdot ITD_{lm}^{t}} \hspace{1cm} \forall l \in L$$


La cantidad de inventario para la carga $l$ al final del periodo $t$ será el inventario del periodo anterior, más las llegadas en el periodo actual menos todos los envios hacia las unidades de almacenamiento:

```mermaid
graph LR;
    id1{bif} --XPL--> id2[Bodega en Puerto]
    id2[Bodega en Puerto] --34000*ITR--> id4[Unidad de Almacenamiento]
    id2[Bodega en Puerto] --XIP--> id2[Bodega en Puerto]
```

$$ XIP_{l}^{t} = XIP_{l}^{t-1} + XPL_{l}^{t} - \sum_{m}{34000 \cdot ITR_{lm}^{t}} \hspace{1cm} \forall{ \mathbb{t \in T}}$$

Adicionalmente, debemos tener en cuenta el inventario inicial en el almacenamiento de puerto:

$$ XIP_{l}^{t=0} = IP_{l} $$

#### Balance de masa en unidades de almacenamiento por producto en planta

El inventario en las unidades de almacenamiento $m$ al final de un día $t$ es igual al inventario al final del día anterior más las llegadas desde cualquier carga $l$ teniendo en cuenta el tiempo de despacho entre puertos y plantas, menos la cantidad de producto a sacar desde la unidad $m$.

```mermaid
graph LR;
    id3((Transitos)) --TR--> id4[Unidad de Almacenamiento]
    id1{bif} --XTD--> id4[Unidad de Almacenamiento]
    id2[Bodega en Puerto] --34000*ITR--> id4[Unidad de Almacenamiento]
    id4[Unidad de Almacenamiento] --XIU--> id4[Unidad de Almacenamiento]
    id4[Unidad de Almacenamiento] --XDM-->id5((Consumo))
```

$$ XIU_{m}^{t} = XIU_{m}^{t-1} + TR + \sum_{lm}{34000 \cdot ITD_{lm}^{t-TT}} + \sum_{l}{34000 \cdot ITR_{lm}^{t-TT}} - XDM_{km}^{t} \hspace{1cm} \forall{\mathbb{t>1}}$$

### Capacidad de almacenamiento en planta

El inventario de producto en la planta $l$ al final del periodo $t$ debe ser menor a la capacidad señalada:

$$ {XIP_{l}^{t}} \leq CA_{mi} \hspace{2cm} \forall l \in L, t \in T  $$

La suma de las prorciones de capacidad usada por planta deben ser inferiores al 100% de la capacidad disponible para cada ingrediente

$$ \sum_{l}{\frac{XIP_{l}^{t}}{CA_{mi}}} \leq 1 $$

#### Mantenimiento del nivel de seguridad de igredientes en plantas

El inventario al final del día para todo ingrediente en toda planta debe quedar sobre el nivel de seguridad definido, salvo que este valor sea imposible de alcanzar

$$ \sum_{m \in i}^{t}{XIU_{m}^{t}} \geq SS_{ki}^{t} \cdot (1-BSS_{ik}^{t}) $$

#### Alcance del nivel objetivo de inventario en planta

El inventario al final del día para todo ingrediente en toda planta debe quedar sobre el nivel de seguridad definido, salvo que este valor sea imposible de alcanzar por problemas de abastecimiento en otras plantas

$$ \sum_{m \in i}^{t}{XIU_{m}^{t}} \geq CL_{ki}^{t} \cdot (1-BLV_{ik}^{t}) $$

#### Alcance del nivel objetivo de inventario en planta

El inventario al final del día para todo ingrediente en toda planta debe quedar sobre el nivel de seguridad definido, salvo que este valor sea imposible de alcanzar por problemas de abastecimiento en otras plantas

$$ \sum_{m \in i}^{t}{XIU_{m}^{t}} \geq CX_{ki}^{t} \cdot (1-BMX_{ik}^{t}) $$