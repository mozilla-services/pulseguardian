/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

// FIXME: There are a few functions related to "deletableObjects" (a server
// resource that has a DELETE API and which, on the client side, uses a
// confirmation dialog) which should be organized better.  See also
// dialogs.html.

$(document).ready(function() {
    // Auto-reload
    var autoReload = false;
    var reloadInterval = 8000;

    function deleteableObjectHandler(objectType) {
        $('.' + objectType + 's .delete').click(function() {
            var objectInstance = $(this).closest('.' + objectType);
            var objectName = objectInstance.data(objectType + '-name');
            var modal = $('.modal-delete-' + objectType);
            modal.data(objectType + '-object', objectInstance);
            modal.find('.' + objectType + '-name').text(objectName);
            modal.modal();
        });
    }

    deleteableObjectHandler('queue');
    deleteableObjectHandler('pulse-user');

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
        function deleteObject(objectInstance, objectName) {
            $.ajax({
                url: '/' + objectType + '/' + objectName,
                type: 'DELETE',
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
                         $(modalClass + ' .' + objectType + '-name').text());
        });
    }

    deleteableObject('queue');
    deleteableObject('pulse-user');

    // notification create
    $('.notifications form button[type="submit"]').click(function(event) {
        event.preventDefault();

        var that = this;
        var current = $(that).parents('.notifications');
        current.find('.message').text('');

        var email = current.find('input[name="email"]').val();
        var queue = current.find('input[name="queue"]').val();

        var validate = function() {
            if (email == '') {
                current.find('.message').text('Email is empty');
                return false;
            }

            return true;
        };

        if (!validate()) return;

        var postData = {'email':email,'queue':queue};
        $.post('/notification/create', postData, 'json')
            .fail(function(xhr) {
                current.find('.message').text(xhr.statusText+' - '+xhr.status);
            })
            .done(function(data, textStatus, xhr) {
                if (data.ok) {
                    var removeBtn = '<button type="button" class="btn-primary close" aria-label="Close"><span aria-hidden="true">&times;</span></button>';
                    var emailItem = '<li class="pull-left"><span>'+email+'</span>'+removeBtn+'</li>';
                    current.find('.emails').append(emailItem);
                    current.find('input[name="email"]').val('');
                } else {
                    current.find('.message').text(data.message);
                }
            });
    });

    // notification delete
    $('.notifications .emails').delegate('li button', 'click', function() {
        var that = this;
        var current = $(that).parents('.notifications');
        var postData = {
            'notification': $(this).siblings('span').text(),
            'queue': current.find('input[name="queue"]').val()
        };
        $.post('/notification/delete', postData, 'json')
            .fail(function(xhr) {
                current.find('.message').text(xhr.statusText+' - '+xhr.status);
            })
            .done(function(data, textStatus, xhr) {
                if (data.ok) {
                    $(that).parent().remove();
                }
            });
    });
});
