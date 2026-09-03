# Job backfill (module 15). Build : docker compose --profile spark build spark-backfill
FROM eclipse-temurin:17-jdk-jammy AS build
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -fsSL "https://github.com/sbt/sbt/releases/download/v1.10.2/sbt-1.10.2.tgz" \
      | tar -xz -C /usr/local \
    && ln -s /usr/local/sbt/bin/sbt /usr/local/bin/sbt \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY build.sbt .
COPY project ./project
COPY src ./src
RUN sbt --batch assembly

FROM apache/spark:3.5.5-java17
USER root
COPY --from=build /src/target/scala-2.12/presslake-spark.jar /opt/presslake/presslake-spark.jar
COPY submit.sh /opt/presslake/submit.sh
RUN chmod 755 /opt/presslake/submit.sh && chmod 644 /opt/presslake/presslake-spark.jar
WORKDIR /opt/spark
USER spark
ENTRYPOINT ["/opt/presslake/submit.sh"]
