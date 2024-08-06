from loader import Loader
import logging

logging.basicConfig(level=logging.DEBUG,format='%(asctime)s %(message)s')


input_file = "../../data/0_model_template_2204.xlsm"

loader = Loader(input_file)

loader.problema['plantas']['envigado']['ingredientes']['maiz'].keys()

logging.debug("ejemplo de debug")
