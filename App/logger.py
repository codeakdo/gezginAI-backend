import logging
import sys

LOG_FORMAT = "%(asctime)s - %(levelname)s- %(message)s"


logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler("app.log"), # Logları dosyaya yazar
        logging.StreamHandler(sys.stdout) # Aynı zamanda ekrana basar
    ]
)

logger = logging.getLogger("GezginAI")