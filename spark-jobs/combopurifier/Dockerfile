# Use the base image
FROM  cloudificando/spark-py-s3a-delta:3.5.3

RUN pip install delta-spark
# Copy your PySpark scripts into the container
COPY combopurifier_spark.py /opt/spark/scripts/
COPY spark_session.py /opt/spark/scripts/