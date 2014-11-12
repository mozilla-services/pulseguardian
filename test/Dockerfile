# Base image
FROM ubuntu:14.04

# Update repositories
RUN apt-get update

# Install rabbitmq
RUN apt-get install -y rabbitmq-server

# Enable managment plugin
RUN rabbitmq-plugins enable rabbitmq_management

# Start rabbitmq-server
CMD rabbitmq-server
