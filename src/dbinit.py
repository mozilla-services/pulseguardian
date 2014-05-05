from model.base import db_session, init_db
from model.user import User
from model.queue import Queue
from management import PulseManagementAPI, PulseManagementException

pulse_management = PulseManagementAPI()

# Initializing the databse schema
init_db()

# Removing all pulse users created by the web app
for user in User.query.all():
    try:
        pulse_management.delete_user(user.username)
    except PulseManagementException:
        pass

# Clearing the database from old data
User.query.delete()
Queue.query.delete()

# Dummy test user
dummy_user = User.new_user(email='dummy@dummy.com', username='dummy', password='dummy')
dummy_user.activate(pulse_management)
db_session.add(dummy_user)
db_session.commit()

# And a dummy queue
dummy_queue = Queue(name='iamadummyqueue', size=2, owner=dummy_user)
db_session.add(dummy_queue)
db_session.commit()