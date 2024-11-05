from spark_session import execute_spark
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    regexp_replace,
    split,
    explode,
    trim,
    col
)
def spark_job(spark: SparkSession, params, *args, **kwargs):
    s3_input_combo_path = params.get("source_bucket")
    s3_output_combo_path = params.get("target_bucket")
    s3_master_combo_path = params.get("master_bucket")

    # 3. Read Incoming File
    df_raw = spark.read.text(s3_input_combo_path)

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
    try:
        df_master = spark.read.format("delta").load(s3_master_combo_path)
    except:
        # If master data doesn't exist, create an empty DataFrame
        df_master = spark.createDataFrame([], "email_password STRING")
    # 6. Identify New Records (Left Anti-Join)
    df_new_data = df_extracted.join(df_master, on='email_password', how='left_anti')

    # 7. Repartition and Cache
    df_new_data = df_new_data.repartition(1).cache()

    # 9. Write to Output File with Compression
    df_new_data.coalesce(1).write \
        .mode("overwrite") \
        .text(s3_output_combo_path)

    # 10. Update Master Delta Table
    # 5. Append New Records to Master Data
    df_combined_master = df_master.unionByName(df_new_data)

    # 6. Write Updated Master Data
    df_combined_master.write \
        .format("delta") \
        .mode("overwrite") \
        .save(s3_master_combo_path)
    # 11. Finalization
    # Unpersist the cached DataFrame to free up memory
    df_new_data.unpersist()

if __name__ == "__main__":
    execute_spark(method=spark_job)