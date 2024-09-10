import pandas as pd
import numpy as np
from sklearn.cluster import KMeans


def asignar_etiquetas(df: pd.DataFrame, column_name: str, n_clusters=3):
    # Copiamos el DataFrame para no modificar el original
    df_resultado = df.copy()

    # Instanciar el modelo KMeans
    kmeans = KMeans(n_clusters=3,
                    init='random',
                    n_init=10,
                    max_iter=300,
                    random_state=0)

    # Ajustar el modelo a los datos
    kmeans.fit(np.array(df[column_name]).reshape(-1, 1))

    # Obtener las etiquetas de los clusters
    labels = kmeans.labels_

    # Agregar las etiquetas al DataFrame
    df_resultado['cluster'] = labels

    # Calcular los centroides
    centroids = kmeans.cluster_centers_

    # Calcular los límites de los clusters
    # limits = [df[labels == i].describe() for i in range(n_clusters)]

    # Asignar etiquetas de 'alto', 'medio' y 'bajo'
    for i in range(n_clusters):
        df_resultado.loc[df_resultado['cluster'] == i, 'etiqueta'] = (
            'alto' if centroids[i] == max(centroids) else
            'bajo' if centroids[i] == min(centroids) else
            'medio'
        )

    return df_resultado