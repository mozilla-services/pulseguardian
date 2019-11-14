# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from subprocess import call, Popen, PIPE


def create_image():
    create_image_command = 'docker build -t=pulse:testing test'
    call(create_image_command.split(' '))


def delete_image():
    delete_image_pulse_command = 'docker rmi pulse:testing'
    delete_image_ubuntu_command = 'docker rmi ubuntu:14.04'

    call(delete_image_pulse_command.split(' '))
    call(delete_image_ubuntu_command.split(' '))


def setup_container():
    setup_command = 'docker run -d -p 5672:5672 -p 15672:15672 --name pulse pulse:testing'
    call(setup_command.split(' '))


def teardown_container():
    stop_command = 'docker stop pulse'
    remove_command = 'docker rm pulse'

    call(stop_command.split(' '))
    call(remove_command.split(' '))


def check_rabbitmq():
    string_to_check = 'Starting broker... completed'
    get_logs_command = 'docker logs pulse'

    logs_output = Popen(get_logs_command.split(' '),
                        stdout=PIPE).communicate()[0]

    return string_to_check in logs_output.decode('utf8')
