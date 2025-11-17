import logging, sys
def get_logger(name=__name__):
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    return logging.getLogger(name)

logger = get_logger("gen_sql")
