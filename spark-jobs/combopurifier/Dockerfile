# Use the base image
FROM  cloudificando/spark-py-s3a-delta:3.5.3

# Copy your PySpark scripts into the container
COPY combopurifier_spark.py /opt/spark/scripts/
COPY spark_session.py /opt/spark/scripts/
#docker build -t leothenardo/spark-combopurifier:1.1.0 ./spark-jobs/combopurifier/ && docker push leothenardo/spark-combopurifier:1.1.0