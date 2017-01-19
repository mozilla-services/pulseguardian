/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

$(document).ready(function() {
    var usersTable = $('#users').DataTable();

    $('#users tbody').on('click', '.admin-check', function() {
        $('#userAlert').addClass('hide');
        var isAdmin = $(this).is(':checked');
        var userData = usersTable.row($(this).closest('tr')).data();
        var confirmMsg = (isAdmin ? 'Enable' : 'Disable') + ' admin mode for user ' + userData[0] + ' ?';
        var confirmation = confirm(confirmMsg);

        if (confirmation) {
            var urlApi = '/user/' + $(this).data('uid') + '/set-admin';

            $.ajax({
                        type: 'PUT',
                        url: urlApi,
                        contentType: 'application/json',
                        data: JSON.stringify({isAdmin: isAdmin}),
                        dataType: 'json',
                        success: function(data) {
                            if (!data.ok) {
                                $('#userAlert').removeClass('hide');
                                return false;
                            }
                        },
                        error: function() {
                            $('#userAlert').removeClass('hide');
                            return false;
                        }});
        }

        return confirmation;
    });
});
