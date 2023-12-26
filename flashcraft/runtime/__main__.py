import json
import os

from flashcraft.runtime import Runtime

Runtime(json.loads(os.environ["FC_RUNTIME_CONFIG"])).start()
