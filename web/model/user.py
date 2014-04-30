import os
import hashlib

from sqlalchemy import Column, String

from base import Base, db_session, init_db
 
def generate_salt():
    return os.urandom(16).encode('base_64')

def hash_password(password, salt):
    return hashlib.sha512(salt + password).hexdigest()

class User(Base):
    __tablename__ = 'users'

    username = Column(String)
    email = Column(String, primary_key=True)

    secret_hash = Column(String)
    salt = Column(String)

    def valid_password(self, password):
	    return hash_password(password, self.salt) == self.secret_hash

    @staticmethod
    def new_user(email, username, password):
        user = User(email=email, username=username)

        user.salt = generate_salt()
        user.secret_hash = hash_password(password, user.salt)

        return user

    def __repr__(self):
		return "<User(email='%s', password='%s')>" % (
		                    self.email, self.fullemail, self.password)

if __name__ == '__main__':
    init_db()

    user = User.new_user(email='dummy@email.com', username='dummy', password='dummypassword')
    assert user.valid_password('dummypassword')
    assert not user.valid_password('dummyPassword')

    db_session.add(user)

    db_session.commit()

    assert user in User.query.all()
    assert User.query.filter(User.username == 'dummy').first() == user
    assert User.query.filter(User.username == 'DOMMY').first() is None