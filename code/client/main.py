from loader import Loader
import logging

logging.basicConfig(level=logging.DEBUG,format='%(asctime)s %(message)s')


input_file = file = "../../data/0_model_template_2506.xlsm"

loader = Loader(input_file)

problema = loader.problema

fechas = loader.fechas

