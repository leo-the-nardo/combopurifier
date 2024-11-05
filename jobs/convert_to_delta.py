from pyspark.sql import SparkSession
from delta import *

# Initialize Spark Session with Delta support
builder = SparkSession.builder \
    .appName("ConvertToDelta") \
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
    .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")

# Configure Spark with Delta pip
spark = configure_spark_with_delta_pip(builder).getOrCreate()

# Read the text file as a single column
df = spark.read.text("/opt/bitnami/spark/jobs/input/master.txt").withColumnRenamed("value", "email_password")

# Write to Delta format
df.write.format("delta").mode("overwrite").save("/opt/bitnami/spark/jobs/master")

# Stop the Spark session
spark.stop()
