/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

$(document).ready(function() {
    $('.rabbitmq-accounts .edit').click(function() {
        var details = $($(this).closest('.rabbitmq-account'))
                .find('.rabbitmq-account-details');
        if (details.hasClass('hidden')) {
            // Close any other open details.
            $('.rabbitmq-account-details').addClass('hidden');
            details.removeClass('hidden');
        } else {
            details.addClass('hidden');
        }
    });

    deletableObjectHandler('rabbitmq-accounts', 'rabbitmq-account');
    deletableObject('rabbitmq-account');
});
