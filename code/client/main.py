from loader import Loader
import logging

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s: %(message)s', 
                    datefmt='%m/%d/%Y %I:%M:%S %p')


input_file = file = "../../data/0_model_template_2506.xlsm"

loader = Loader(input_file)

problema = loader.problema

fechas = loader.fechas

data= problema['importaciones']['maiz']['baq']['trademar']['finca']['45842TONHILII']
