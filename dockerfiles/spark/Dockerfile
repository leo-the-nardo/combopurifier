# Use the base image
FROM cloudificando/spark-py:3.5.3

ADD https://repo1.maven.org/maven2/io/delta/delta-spark_2.12/3.2.1/delta-spark_2.12-3.2.1.jar /opt/spark/jars
ADD https://repo1.maven.org/maven2/io/delta/delta-storage/3.2.1/delta-storage-3.2.1.jar /opt/spark/jars

USER root
RUN pip install delta-spark
RUN chown -R 185:185 /opt/spark/jars

USER 185