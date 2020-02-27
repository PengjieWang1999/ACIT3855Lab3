import connexion
import yaml
from flask_cors import CORS, cross_origin
import logging
import logging.config
import json
import os.path
from os import path
import requests

from apscheduler.schedulers.background import BackgroundScheduler

from connexion import NoContent

import datetime


with open('app_conf.yaml', 'r') as f:
    app_config = yaml.safe_load(f.read())

with open('log_conf.yaml', 'r') as f:
    log_config = yaml.safe_load(f.read())
    logging.config.dictConfig(log_config)
logger = logging.getLogger('basicLogger')


def populate_stats():
    logger.info("Scheduler Start")

    json_data = {}

    if os.path.exists(app_config['datastore']['filename']):
        with open(app_config['datastore']['filename']) as f:
            json_str = f.read()
            json_data = json.loads(json_str)

    timestamp = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    if json_data.get('timestamp'):
        response_hd = requests.get(app_config['eventstore']['url'] + "/humidity?startDate=" + json_data['timestamp']
                                   + "&endDate=" + timestamp)
        response_tp = requests.get(app_config['eventstore']['url'] + "/temperature?startDate=" + json_data['timestamp']
                                   + "&endDate=" + timestamp)
    else:
        response_hd = requests.get(app_config['eventstore']['url'] + "/humidity?startDate=" + timestamp + "&endDate="
                                   + timestamp)
        response_tp = requests.get(app_config['eventstore']['url'] + "/temperature?startDate="+ timestamp + "&endDate="
                                   + timestamp)

    if response_hd.status_code != 200:
        logger.error("Returned non 200 for HD")
        return

    if response_tp.status_code != 200:
        logger.error("Returned non 200 for TP")
        return

    hd_data = response_hd.json()
    tp_data = response_tp.json()

    logger.info("HD Events Received: " + str(len(hd_data)))
    logger.info("TP Events Received: " + str(len(tp_data)))

    if json_data.get('num_hd_readings'):
        json_data['num_hd_readings'] = json_data['num_hd_readings'] + len(hd_data)

    else:
        json_data['num_hd_readings'] = len(hd_data)

    if json_data.get('num_tp_readings'):
        json_data['num_tp_readings'] = json_data['num_tp_readings'] + len(tp_data)
    else:
        json_data['num_tp_readings'] = len(tp_data)

    logger.debug("Updated HD Events: " + str(json_data['num_hd_readings']))
    logger.debug("Updated TP Events: " + str(json_data['num_tp_readings']))

    json_data['timestamp'] = timestamp

    with open(app_config['datastore']['filename'], "w") as f:
        f.write(json.dumps(json_data))

    logger.info("Scheduler End")


def init_scheduler():
    sched = BackgroundScheduler(daemon=True)
    sched.add_job(populate_stats,
                  'interval',
                  seconds=app_config['scheduler']['period_sec'])
    sched.start()


def get_reading_stats():
    """ Get readings """
    logger.info("Request Start")

    json_data = {}

    if os.path.exists(app_config['datastore']['filename']):
        with open(app_config['datastore']['filename']) as f:
            json_str = f.read()
            json_data = json.loads(json_str)
    else:
        logger.error("File Does not Exist")
        return NoContent, 404

    logger.debug("Data in Dict: " + str(json_data))

    logger.info("Request End")
    return json_data, 200

app = connexion.FlaskApp(__name__, specification_dir='')
CORS(app.app)
app.app.config['CORS_HEADERS'] = 'Content-Type'
app.add_api("openapi.yaml")

if __name__ == "__main__":
    # run our standalone event server

    init_scheduler()
    app.run(port=8100, use_reloader=False)
