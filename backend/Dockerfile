FROM --platform=$BUILDPLATFORM maven:3.9-eclipse-temurin-21 AS builder
WORKDIR /app
COPY pom.xml .
RUN mvn dependency:go-offline -B
COPY src ./src
RUN mvn package -DskipTests -B

FROM eclipse-temurin:21-jre
WORKDIR /app
ENV TZ=Asia/Shanghai
RUN if [ -f /etc/apt/sources.list.d/ubuntu.sources ]; then \
        sed -i 's/http:\/\/archive.ubuntu.com\/ubuntu/http:\/\/mirrors.aliyun.com\/ubuntu/g' /etc/apt/sources.list.d/ubuntu.sources && \
        sed -i 's/http:\/\/security.ubuntu.com\/ubuntu/http:\/\/mirrors.aliyun.com\/ubuntu/g' /etc/apt/sources.list.d/ubuntu.sources; \
    elif [ -f /etc/apt/sources.list ]; then \
        sed -i 's/archive.ubuntu.com/mirrors.aliyun.com/g' /etc/apt/sources.list && \
        sed -i 's/security.ubuntu.com/mirrors.aliyun.com/g' /etc/apt/sources.list; \
    fi && \
    apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone
COPY --from=builder /app/target/*.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-Duser.timezone=Asia/Shanghai", "-Dfile.encoding=UTF-8", "-jar", "app.jar"]
