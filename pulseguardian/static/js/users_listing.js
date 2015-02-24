/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

// FIXME: There are a few functions related to "deletableObjects" (a server
// resource that has a DELETE API and which, on the client side, uses a
// confirmation dialog) which should be organized better.  See also
// dialogs.html.

$(document).ready(function() {
    // DataTables
    $('#pulse_users').dataTable();
});
