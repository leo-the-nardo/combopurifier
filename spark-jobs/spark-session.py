from sys import argv
from pyspark.sql import SparkSession
from pyspark.conf import SparkConf


def execute_spark(method, configs=None):
    conf = SparkConf()

    if configs is not None:
        conf.setAll(configs)

    parameters = {}
    if len(argv) > 1:
        for argument in argv[1:]:
            data = argument.split("=")
            key = data[0]
            value = data[1]

            parameters[key] = value

    # with SparkSession.builder.appName(parameters["job_name"]).enableHiveSupport().config(
    #   conf=conf).getOrCreate() as spark:
    with SparkSession.builder.appName(parameters["job_name"])\
            .config(conf=conf)\
            .getOrCreate() as spark:

        method(spark=spark, params=parameters)