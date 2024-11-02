from spark_session import execute

def spark_job(spark, params, *args, **kwargs):

    s3_input_users_path = params.get("source_bucket")
    s3_output_users_path = params.get("target_bucket")

    print(f"-> s3_input_users_path: {s3_input_users_path}")
    print(f"-> s3_output_users_path: {s3_output_users_path}")

    # read users
    df_users = spark.read\
        .format('json')\
        .option('inferSchema', 'true')\
        .option('header','true')\
        .json(s3_input_users_path)

    # convert to delta format
    df_users\
        .write\
        .mode('overwrite')\
        .format('delta')\
        .save(s3_output_users_path)

if __name__ == "__main__":
    execute(method=spark_job)