
from bios_utils.problema import Problema

import pulp as pu
import pandas as pd



problema = Problema(bios_input_file='data/0_model_template_20240705.xlsm')


from bios_utils.evitar_backorder_model import EvitarBackorder
model_01 = EvitarBackorder(problema)
model_01.solve()
