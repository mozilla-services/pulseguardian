/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

$(document).ready(function() {
    // Auto-reload
    var autoReload = true;
    var reloadInterval = 8000;

    $('.pulse-users .edit').click(function() {
        var details = $($(this).closest('.pulse-user'))
                .find('.pulse-user-details');
        if (details.hasClass('hidden')) {
            // Close any other open details.
            $('.pulse-user-details').addClass('hidden');
            details.removeClass('hidden');
        } else {
            details.addClass('hidden');
        }
    });

    setInterval(function() {
        if (autoReload) {
            $('#queues-info').load('/queues_listing', function() {
                deletableObjectHandler('queues', 'queue');
            });
        }
    }, reloadInterval);

    $('.autoreload').click(function() {
        autoReload = !autoReload;
        $(this).toggleClass('inactive');
    });
});
