# Base image
FROM ubuntu:16.04

# Update repositories
RUN apt-get update

# Install rabbitmq
RUN apt-get install -y rabbitmq-server

# Enable managment plugin
RUN rabbitmq-plugins enable rabbitmq_management

# Allow 'guest' account to log in remotely
COPY rabbitmq.config /etc/rabbitmq/

RUN chmod 644 /etc/rabbitmq/rabbitmq.config
RUN chown rabbitmq.rabbitmq /etc/rabbitmq/rabbitmq.config

EXPOSE 5672
EXPOSE 15672

# Start rabbitmq-server
CMD rabbitmq-server
