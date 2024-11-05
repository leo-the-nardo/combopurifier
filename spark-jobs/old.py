import time
from pyspark.sql import SparkSession
from delta.tables import DeltaTable
from pyspark.sql.functions import (
    regexp_replace,
    split,
    explode,
    trim,
    col
)
start_time = time.time()

# 1. Initialize Spark Session
spark = SparkSession.builder \
    .appName("OptimizedProcessLocalFileWithoutUDF") \
    .config("spark.sql.shuffle.partitions", "1") \
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
    .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
    .config("spark.sql.adaptive.enabled", "true") \
    .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
    .config("spark.sql.adaptive.skewJoin.enabled", "true") \
    .config("spark.databricks.delta.optimizeWrite.enabled", "true") \
    .config("spark.databricks.delta.autoCompact.enabled", "true") \
    .getOrCreate()

# 2. Define File Paths
incoming_file_path = "/opt/bitnami/spark/jobs/input/coming.txt"  # Path to the incoming .txt file
master_data_path = "/opt/bitnami/spark/jobs/master"             # Path to master data in Delta format
output_path = "/opt/bitnami/spark/jobs/output/cleaned.txt"      # Path to save the cleaned .txt file

# 3. Read Incoming File
df_raw = spark.read.text(incoming_file_path)

# 4. Extract 'email:password' Patterns
# Define a unique delimiter unlikely to appear in the data
delimiter = "|||"

# Apply transformations to extract patterns
df_extracted = df_raw \
    .withColumn('trimmed', trim(col('value'))) \
    .withColumn(
    'replaced',
    regexp_replace(col('trimmed'), r'(\S+@\S+:\S+)', r'$1' + delimiter)
) \
    .withColumn(
    'splitted',
    split(col('replaced'), r'\|\|\|')
) \
    .withColumn(
    'email_password',
    explode(col('splitted'))
) \
    .select('email_password') \
    .filter(
    (col('email_password') != '') &
    (col('email_password').rlike(r'^\S+@\S+:\S+$'))
) \
    .distinct()

# 5. Load Master Data
if DeltaTable.isDeltaTable(spark, master_data_path):
    df_master = spark.read.format("delta").load(master_data_path)
else:
    # Create an empty DataFrame with the same schema as master_data
    df_master = spark.createDataFrame([], "email_password STRING")

# 6. Identify New Records (Left Anti-Join)
df_new_data = df_extracted.join(df_master, on='email_password', how='left_anti')

# 7. Repartition and Cache
df_new_data = df_new_data.repartition(1).cache()

# 8. Count and Validate
spark_count = df_new_data.count()
expected_unix_count = 359449  # Replace with the actual Unix count if dynamic

if spark_count != expected_unix_count:
    print(f"Warning: Spark count ({spark_count}) does not match Unix count ({expected_unix_count})")
else:
    print("Spark count matches Unix count.")

# 9. Write to Output File with Compression
df_new_data.write \
    .mode("overwrite") \
    .text(output_path)

# 10. Update Master Delta Table
if DeltaTable.isDeltaTable(spark, master_data_path):
    delta_table = DeltaTable.forPath(spark, master_data_path)
    delta_table.alias("m") \
        .merge(
        df_new_data.alias("n"),
        "m.email_password = n.email_password"
    ) \
        .whenNotMatchedInsertAll() \
        .execute()
else:
    # Initialize the Delta table with new data
    df_new_data.write \
        .format("delta") \
        .mode("overwrite") \
        .save(master_data_path)

# 11. Finalization
# Unpersist the cached DataFrame to free up memory
df_new_data.unpersist()

# Stop the Spark session gracefully
spark.stop()

# 12. Report Execution Time
end_time = time.time()
elapsed_time = end_time - start_time
print(f"Job completed in {elapsed_time:.2f} seconds.")
