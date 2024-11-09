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
    s3_output_delta_combo_path = params.get("target_bucket_delta")
    s3_master_combo_path = params.get("master_bucket")

    # 3. Read Incoming File
    df_raw = spark.read.text(s3_input_combo_path)

    delimiter = "|||"
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
        'email_tel',
        explode(col('splitted'))
    ) \
        .select('email_tel') \
        .filter(
        (col('email_tel') != '') &
        (col('email_tel').rlike(r'^\S+@\S+:\S+$'))
    ) \
        .distinct()
    try:
        df_master = spark.read.format("delta").load(s3_master_combo_path)
    except:
        df_master = spark.createDataFrame([], "email_tel STRING")
    df_new_data = df_extracted.join(df_master, on='email_tel', how='left_anti')

    df_new_data = df_new_data.repartition(1).cache()

    df_new_data.coalesce(1).write \
        .mode("append") \
        .text(s3_output_combo_path)

    df_new_data.write \
        .mode("append") \
        .format("delta") \
        .save(s3_output_delta_combo_path)

    df_new_data.write \
        .format("delta") \
        .mode("append") \
        .option("delta.enableChangeDataFeed", "true") \
        .save(s3_master_combo_path)

    df_new_data.unpersist()

if __name__ == "__main__":
    execute_spark(method=spark_job)