from pyspark.sql import SparkSession

if __name__ == '__main__':
    spark = SparkSession.builder.appName("elt-addresses-lakehouse-spok").enableHiveSupport().getOrCreate()
    df_users = spark.table('workshop_db.users')

    print("Quantidade users")
    print(df_users.count())

    users_birthday = df_users.select(
        "uid",
        "first_name",
        "last_name",
        "date_of_birth"
    )

    s3_output_users_birthday_path = 's3a://spok-lakehouse/silver/users_birthday'

    # # convert to delta format
    users_birthday\
        .write\
        .mode('overwrite')\
        .format('delta')\
        .save(s3_output_users_birthday_path)

    spark.stop()