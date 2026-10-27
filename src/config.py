import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CERTS_DIR = os.path.join(BASE_DIR, "certs")
FIXTURES_DIR = os.path.join(BASE_DIR, "fixtures")
SCENARIOS_DIR = os.path.join(BASE_DIR, "scenarios")
RULES_DIR = os.path.join(BASE_DIR, "rules")

CA_CERT = os.path.join(CERTS_DIR, "ca.crt")
CA_KEY = os.path.join(CERTS_DIR, "ca.key")
SERVER_CERT = os.path.join(CERTS_DIR, "server.crt")
SERVER_KEY = os.path.join(CERTS_DIR, "server.key")
CA_BUNDLE = os.path.join(CERTS_DIR, "ca-bundle.crt")

# Server settings
DEFAULT_PORT = 8081
DEFAULT_HOST = "0.0.0.0"
MAX_REQUEST_LOGS = 500

# ANSI Terminal Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"
