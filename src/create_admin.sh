# Creates a rabbitmq admin user
rabbitmqctl add_user admin admin
rabbitmqctl set_permissions -p / guest .* .* .*
rabbitmqctl set_user_tags admin administrator
