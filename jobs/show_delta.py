import time
from pyspark.sql import SparkSession

# Initialize Spark Session with Delta support
spark = SparkSession.builder \
    .appName("ReadDeltaTable") \
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
    .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
    .getOrCreate()
start_time = time.time()

# Path to the Delta table
delta_path = "/opt/bitnami/spark/jobs/master"

# Read the Delta table
delta_df = spark.read.format("delta").load(delta_path)

# Show the data
print(delta_df.count())

# Stop the Spark session
spark.stop()
# End timing
end_time = time.time()

# Calculate and print the elapsed time
elapsed_time = end_time - start_time
print(f"Job completed in {elapsed_time:.2f} seconds.")
