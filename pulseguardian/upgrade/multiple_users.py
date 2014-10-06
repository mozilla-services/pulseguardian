# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Upgrades schema from single Pulse user per Pulse Guardian account to
# multiple.

import MySQLdb

DB_DATABASE = 'pulseguardian'
DB_USER = 'pulseguardian'
DB_PASSWORD = ''
DB_HOST = 'localhost'

conn = MySQLdb.connect(host=DB_HOST, user=DB_USER, passwd=DB_PASSWORD,
                       db=DB_DATABASE)
c = conn.cursor()

c.execute('''CREATE TABLE `pulse_users` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `owner_id` int(11) DEFAULT NULL,
  `username` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`),
  KEY `owner_id` (`owner_id`),
  CONSTRAINT `pulse_users_ibfk_1` FOREIGN KEY (`owner_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;''')
conn.commit()

c.execute('select id, username from users order by id')
for row in c.fetchall():
    c.execute('insert into pulse_users (owner_id, username) values (%s, %s)',
              (row[0], row[1]))

conn.commit()

c.execute('rename table queues to queues_old')
conn.commit()

c.execute('''CREATE TABLE `queues` (
  `name` varchar(255) NOT NULL,
  `owner_id` int(11) DEFAULT NULL,
  `size` int(11) DEFAULT NULL,
  `warned` tinyint(1) DEFAULT NULL,
  PRIMARY KEY (`name`),
  KEY `owner_id` (`owner_id`),
  CONSTRAINT `queues_ibfk_1` FOREIGN KEY (`owner_id`) REFERENCES `pulse_users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;''')

c.execute('select name, owner_id, size, warned from queues_old')
for row in c.fetchall():
    c.execute('select id from pulse_users where owner_id=%s', (row[1],))
    pulse_user_id = c.fetchone()[0]
    c.execute('insert into queues (name, owner_id, size, warned) values '
              '(%s, %s, %s, %s)', (row[0], pulse_user_id, row[2], row[3]))

conn.commit()

c.execute('alter table users drop column username')
c.execute('alter table users drop column salt')
c.execute('alter table users drop column secret_hash')
c.execute('alter table users add constraint `email` unique key (`email`)')
c.execute('drop table queues_old')

conn.commit()
