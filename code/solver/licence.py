# -*- coding: utf-8 -*-
"""
Created on Mon Aug  5 12:39:27 2024

@author: luisf
"""

import requests

from datetime import datetime, timezone


fecha_limite = datetime(2024, 9, 1, 0, 0, 0, tzinfo=timezone.utc)

def licence_active()->bool:

    URL = "http://worldtimeapi.org/api/timezone/America/Bogota"
    response = requests.get(URL)
    
    if response.status_code == 200:
        data = response.json()
        fecha_actual = datetime.fromisoformat(data['datetime']).replace(tzinfo=timezone.utc)
        if fecha_actual <= fecha_limite:
            return True
        else:
            return False
    else:
        print('Error en la solicitud, detalles:', response.text)
        return False