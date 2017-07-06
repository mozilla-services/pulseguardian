/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

// FIXME: There are a few functions related to "deletableObjects" (a server
// resource that has a DELETE API and which, on the client side, uses a
// confirmation dialog) which should be organized better.  See also
// dialogs.html.

$(document).ready(function() {
    // Auto-reload
    var autoReload = true;
    var reloadInterval = 8000;

    function deleteableObjectHandler(collectionClass, objectType) {
        $('.' + objectType + 's .delete').click(function() {
            var objectInstance = $(this).closest('.' + objectType);
            var objectName = objectInstance.data(objectType + '-name');
            var modal = $('.modal-delete-' + objectType);
            modal.data(objectType + '-object', objectInstance);
            modal.data('csrf-token',
                       $('.' + collectionClass).data('csrf-token'));
            modal.find('.' + objectType + '-name').text(objectName);
            modal.modal();
        });
    }

    deleteableObjectHandler('queues', 'queue');
    deleteableObjectHandler('pulse-users', 'pulse-user');

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
                deleteableObjectHandler('queue');
            });
        }
    }, reloadInterval);

    $('.autoreload').click(function() {
        autoReload = !autoReload;
        $(this).toggleClass('inactive');
    });

    function deleteableObject(objectType) {
        function deleteObject(objectInstance, objectName, csrfToken) {
            $.ajax({
                url: '/' + objectType + '/' + objectName,
                type: 'DELETE',
                headers: {
                    'X-CSRF-Token': csrfToken,
                },
                success: function(result) {
                    if (!result.ok) {
                        errorMessage("Couldn't delete " + objectType + " '" +
                                     objectName + "'.");
                        return;
                    }

                    $(objectInstance).slideUp(300);
                },
                error: function() {
                    errorMessage("Couldn't delete " + objectType + " '" +
                             objectName + "'.");
                },
                complete: function() {
                    $('.modal-delete-' + objectType).modal('hide');
                }
            });
        }

        var modalClass = '.modal-delete-' + objectType;
        $(modalClass + ' .delete-' + objectType + '-ok').click(function() {
            deleteObject($(modalClass).data(objectType + '-object'),
                         $(modalClass + ' .' + objectType + '-name').text(),
                         $(modalClass).data('csrf-token'));
        });
    }

    deleteableObject('queue');
    deleteableObject('pulse-user');
});