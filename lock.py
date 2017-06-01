import uuid
from flask import Flask
import json

app = Flask(__name__)


@app.route('/', methods=['POST'])
def all_master_branch():
  json_str = " "
